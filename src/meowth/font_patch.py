"""字库/补丁阶段：armips 打 hook + game.bin + 字库。

``patch/`` 消费 ``font/`` 字形与 F9 转义；``game.bin`` 由 ``build.bat`` 编一次
（仅 C/hook 变更时重编）。短语表来自 ``translate.build.json`` →
``phrase_data.asm``（armips 数据，不进 game.bin）。
"""

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .config_loader import (
    get_charmap_path,
    get_game_patch_dir,
    game_config_dir,
)

_GAME_BIN_MAX = 0x10000  # 不得超过 PhraseOffsets @ 0x08810000（StyleLeft 已移除）
_GAME_BIN_VMA = 0x08800000
_ROM_LOAD_ADDR = 0x08000000


def _verify_game_bin_embedded(rom_path: Path, game_bin: Path, vma: int = _GAME_BIN_VMA) -> None:
    """Ensure armips output ROM contains exactly the just-built game.bin.

    Prevents half-new ROMs (e.g. nick pools patched but stale C at 0x08800000).
    """
    if not game_bin.is_file():
        raise RuntimeError(f"game.bin missing for embed check: {game_bin}")
    bin_data = game_bin.read_bytes()
    if not bin_data:
        raise RuntimeError(f"game.bin empty: {game_bin}")
    rom = rom_path.read_bytes()
    file_off = vma - _ROM_LOAD_ADDR
    if file_off < 0 or file_off + len(bin_data) > len(rom):
        raise RuntimeError(
            f"game.bin embed out of range: vma=0x{vma:08X} off=0x{file_off:X} "
            f"bin={len(bin_data)} rom={len(rom)}"
        )
    embedded = rom[file_off : file_off + len(bin_data)]
    if embedded != bin_data:
        first = next((i for i, (a, b) in enumerate(zip(embedded, bin_data)) if a != b), 0)
        raise RuntimeError(
            f"ROM @0x{vma:08X} does not match out/game.bin "
            f"(first diff @+0x{first:X}; refuse stale C / half-new build)"
        )


# AXVJ: Sym punct bank lives after Small (0x09100000+0xE0000). Must match
# ADDR_FONT_CHS_SYM in patch/src/game.h — never overlay JP Font3 @ 0x081B7AAC.
_AXVJ_SYM_VMA = 0x091E0000


def _normalize_font_slots(cfg: dict[str, Any], game_id: str = "") -> list[dict[str, Any]]:
    """Copy slots; pin Sym VMA for Ruby JP so C draw path and .incbin agree."""
    slots = [dict(s) for s in (cfg.get("font_slots") or [])]
    gid = (game_id or "").upper()
    if (not gid) or ("RUBY_AXVJ" in gid) or gid.endswith("AXVJ00"):
        for s in slots:
            if str(s.get("label", "")).lower() == "sym":
                s["addr"] = _AXVJ_SYM_VMA
    return slots


def _generate_fonts_s(cfg: dict[str, Any], work_font_dir: Path, output_path: Path, game_id: str = "") -> None:
    """生成 graphic/fonts.s：字库 .incbin + phrase data include。"""
    slots = _normalize_font_slots(cfg, game_id=game_id)
    prefix = cfg.get("font_bin_prefix", "PokeRSFontChs")
    prefer_unshadow = cfg.get("shadow") is False
    lines = []
    for i, slot in enumerate(slots):
        label = slot.get("label", "Unknown")
        addr = slot.get("addr")
        slot_size = slot.get("slot_size", slot.get("glyph_count", 7168) * slot.get("bytes_per_glyph", 128))
        fname = f"{prefix}{label}(0x{slot_size:X}).bin"
        unshadow_name = f"{prefix}{label}_unshadow(0x{slot_size:X}).bin"
        bin_path = work_font_dir / fname
        unshadow_path = work_font_dir / unshadow_name
        if prefer_unshadow and unshadow_path.exists():
            bin_path = unshadow_path
        elif not bin_path.exists():
            alt = sorted(work_font_dir.glob(f"{prefix}{label}*.bin"))
            # Prefer unshadow when shadow disabled
            if prefer_unshadow:
                us = [p for p in alt if "_unshadow" in p.name]
                bin_path = us[0] if us else (alt[0] if alt else bin_path)
            else:
                bin_path = alt[0] if alt else bin_path
        if addr is not None:
            lines.append(f".org 0x{int(addr):08X}")
        if bin_path.exists():
            lines.append(f".incbin \"{bin_path.resolve()}\"")
            if prefer_unshadow:
                lines.append(f"; shadow=false → {bin_path.name}")
        lines.append("")

    graphic_dir = output_path.parent
    # phrase (0x08810000 / 0x08820000)
    name = "phrase_data.asm"
    src = work_font_dir / name
    if src.is_file():
        staged = graphic_dir / name
        _stage_phrase_data_fixed_vma(src, staged)
        lines.append(f'.include "{staged.resolve()}"')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _stage_phrase_data_fixed_vma(src: Path, dst: Path) -> None:
    """把短语表钉到固定 VMA：Offsets@0x08810000、Table@0x08820000（供 C 直读）。"""
    raw = src.read_text(encoding="utf-8")
    body = [ln for ln in raw.splitlines() if not ln.strip().startswith(".org")]
    text = "\n".join(body)
    if "PhraseOffsets:" not in text or "PhraseTable:" not in text:
        dst.write_text(raw, encoding="utf-8")
        return
    before, table = text.split("PhraseTable:", 1)
    # before includes PhraseOffsets: ... ; drop trailing blanks
    out = [
        ".org 0x08810000",
        before.rstrip(),
        "",
        ".org 0x08820000",
        "PhraseTable:" + table,
        "",
    ]
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(out), encoding="utf-8")


def apply_font_patch(
    rom_path: Path,
    output_path: Path,
    armips_path: Path | None = None,
    font_patch_cfg: dict[str, Any] | None = None,
    work_dir: Path | None = None,
    game_id: str = "",
) -> Path:
    """打字库补丁：armips（hook + game.bin + fonts + phrase data）→ 输出 ROM。

    ``translate.build.json`` → ``phrase_data.asm``（数据区）。
    ``game.bin`` 由 hook ``build.bat`` 预编好复制进来；改 phrases 不重编 C。
    """
    if not font_patch_cfg:
        raise ValueError("font_patch_cfg is required")
    if not game_id:
        raise ValueError("game_id is required")
    if work_dir is None:
        work_dir = Path("work") / game_id

    src_dir = get_game_patch_dir(game_id)
    build_dir = work_dir / "build"
    fonts_src = work_dir / "graphic" / "fonts"
    graphic_dir = build_dir / "graphic"
    fonts_build_dir = graphic_dir / "fonts"

    if build_dir.exists():
        shutil.rmtree(build_dir)
    shutil.copytree(src_dir, build_dir)

    # Shared charmap: configs/<game>/charmap.txt (beside game.json).
    # Stage a copy next to main.asm — work/build cwd is flat (loadtable ./).
    charmap_src = get_charmap_path(game_id)
    if charmap_src.is_file():
        shutil.copy2(charmap_src, build_dir / "charmap.txt")

    # Optional: game-root tools/armips (sibling of stage packs, not inside patch/)
    root_tools = game_config_dir(game_id) / "tools"
    if root_tools.is_dir() and not (build_dir / "tools").exists():
        shutil.copytree(root_tools, build_dir / "tools")

    fonts_build_dir.mkdir(parents=True, exist_ok=True)
    if fonts_src.exists():
        for bin_file in fonts_src.glob("*.bin"):
            shutil.copy2(bin_file, fonts_build_dir / bin_file.name)
        _generate_fonts_s(
            font_patch_cfg, fonts_src, graphic_dir / "fonts.s", game_id=game_id
        )

    shutil.copy2(rom_path, build_dir / "baserom.gba")

    # translate.build.json → phrase_data.asm（armips 数据，不编进 game.bin）
    build_json = work_dir / "translate.build.json"
    fonts_src.mkdir(parents=True, exist_ok=True)
    if build_json.is_file():
        from .build_rom_data import emit_data_asms_from_build_json
        from .charmap import Charmap

        encode_fn = None
        try:
            cm_path = get_charmap_path(game_id)
            cm = Charmap(charmap_path=cm_path, target_lang="zh-Hans")
            # PhraseTable streams must be F9 00 sideload, not F9 80 wrap
            encode_fn = cm.encode
        except Exception as exc:
            print(f"[data] warn: charmap for phrases unavailable ({exc}); no phrases")
        stats = emit_data_asms_from_build_json(
            build_json,
            fonts_src,
            encode_fn=encode_fn,
            write_phrases=encode_fn is not None,
        )
        print(
            f"[data] from translate.build.json → "
            f"phrases={stats.get('phrase_count', 0)}/{stats.get('phrase_bytes', 0)}B"
        )
        # refresh fonts.s so includes pick up new asms
        _generate_fonts_s(
            font_patch_cfg, fonts_src, graphic_dir / "fonts.s", game_id=game_id
        )
    else:
        print(f"[data] warn: no {build_json}; phrases only")

    # type=hook → pointer_redirect.asm（正文池 + 指针槽 .word）；无条目则空桩
    from .pointer_redirect import write_pointer_redirect_asm

    n_hook = write_pointer_redirect_asm(
        work_dir / "translate.build.json",
        build_dir / "gen" / "pointer_redirect.asm",
        rom_path=build_dir / "baserom.gba",
    )
    if n_hook:
        print(f"[hook] pointer_redirect.asm: {n_hook} type=hook entries")

    # game.bin：仅当 out/ 缺失时提示；pack 不强制重编（改 phrase 只走 asm）
    game_bin = build_dir / "out" / "game.bin"

    # armips: 只管 main.asm
    armips_exe = "armips.exe" if sys.platform == "win32" else "armips"
    if armips_path is None:
        root_armips = Path(__file__).resolve().parent.parent.parent / "tools" / armips_exe
        if root_armips.exists():
            armips_path = root_armips
    if armips_path is None:
        local_armips = build_dir / "tools" / armips_exe
        if local_armips.exists():
            armips_path = local_armips
    if armips_path is None:
        which = shutil.which("armips") or shutil.which("armips.exe")
        if which:
            armips_path = Path(which)
    if armips_path is None:
        raise RuntimeError("armips not found")

    asm_file = build_dir / "main.asm"

    result = subprocess.run(
        [str(armips_path), str(asm_file.name)],
        cwd=str(build_dir),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"armips failed:\n{result.stderr}\n{result.stdout}")

    patched = build_dir / "output.gba"
    if not patched.exists():
        gba_files = sorted(build_dir.glob("*.gba"))
        if gba_files:
            patched = [f for f in gba_files if f.stem != "baserom"][0]
    if not patched.exists():
        raise RuntimeError(f"Font patch output not found: {patched}")

    _verify_game_bin_embedded(patched, game_bin)
    # Keep patch/out/game.bin in sync with what was just burned into the ROM.
    src_out = src_dir / "out" / "game.bin"
    src_out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(game_bin, src_out)

    shutil.copy2(patched, output_path)
    return output_path
