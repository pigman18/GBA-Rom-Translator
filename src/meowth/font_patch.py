"""字库/补丁阶段：armips 打 hook + game.bin + 字库。

``patch/`` 消费 ``font/`` 字形与 F9 转义；armips 前用 arm-none-eabi-gcc
把 ``c/`` 编成 ``game.bin``（装入 GameBinAddresses）。
"""

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .config_loader import get_charmap_path, get_game_patch_dir, game_config_dir

_system = platform.system()
if _system == "Windows":
    DEFAULT_ARMIPS = None  # will try local tools/armips.exe first
elif _system == "Darwin":
    DEFAULT_ARMIPS = None
else:
    DEFAULT_ARMIPS = None

_GAME_BIN_MAX = 0x10000  # 不得超过 PhraseOffsets @ 0x08810000


def _find_arm_gcc() -> Path:
    """查找 arm-none-eabi-gcc；找不到则提示安装 Arm GNU Toolchain。"""
    which = shutil.which("arm-none-eabi-gcc")
    if which:
        return Path(which)
    candidates: list[Path] = []
    if _system == "Windows":
        for base in (
            Path(r"C:\Program Files (x86)"),
            Path(r"C:\Program Files"),
            Path(r"C:\devkitPro\devkitARM\bin"),
        ):
            if not base.exists():
                continue
            if base.name == "bin":
                candidates.append(base / "arm-none-eabi-gcc.exe")
            else:
                candidates.extend(base.glob("Arm GNU Toolchain*/**/arm-none-eabi-gcc.exe"))
                candidates.extend(base.glob("GNU Arm*/**/arm-none-eabi-gcc.exe"))
    else:
        for p in (
            Path("/opt/devkitpro/devkitARM/bin/arm-none-eabi-gcc"),
            Path("/usr/bin/arm-none-eabi-gcc"),
        ):
            candidates.append(p)
    for c in candidates:
        if c.is_file():
            return c
    raise RuntimeError(
        "未找到 arm-none-eabi-gcc。请安装 Arm GNU Toolchain："
        "winget install Arm.GnuArmEmbeddedToolchain（或 devkitARM），"
        "并确保 arm-none-eabi-gcc 在 PATH 中。"
    )


def _build_game_bin(patch_dir: Path) -> Path:
    """编译 patch/src → out/game.bin（VMA 0x08800000）。

    优先 ``make``；Windows 无 make 时直接调 gcc/objcopy。
    """
    out_dir = patch_dir / "out"
    out_bin = out_dir / "game.bin"
    makefile = patch_dir / "Makefile"
    if makefile.is_file():
        make_cmd = shutil.which("make") or shutil.which("mingw32-make")
        if make_cmd:
            env = os.environ.copy()
            gcc = _find_arm_gcc()
            env["PATH"] = str(gcc.parent) + os.pathsep + env.get("PATH", "")
            result = subprocess.run(
                [make_cmd, "-C", str(patch_dir), "all"],
                capture_output=True,
                text=True,
                env=env,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"make game.bin 失败:\n{result.stderr}\n{result.stdout}"
                )
            if out_bin.is_file():
                if out_bin.stat().st_size >= _GAME_BIN_MAX:
                    raise RuntimeError(
                        f"game.bin 过大 ({out_bin.stat().st_size} >= {_GAME_BIN_MAX})"
                    )
                _write_game_syms(out_dir / "game.map", out_dir / "game_syms.asm")
                return out_bin

    gcc = _find_arm_gcc()
    bindir = gcc.parent
    stem = gcc.name
    if stem.lower().endswith(".exe"):
        stem = stem[:-4]
    if stem.endswith("-gcc"):
        prefix = stem[:-3]  # arm-none-eabi-
    elif stem.endswith("gcc"):
        prefix = stem[:-3]
    else:
        prefix = "arm-none-eabi-"
    ext = ".exe" if _system == "Windows" else ""
    objcopy = bindir / f"{prefix}objcopy{ext}"
    if not objcopy.is_file():
        raise RuntimeError(f"gcc 同目录未找到 objcopy: {objcopy}")

    obj_dir = out_dir / "obj"
    obj_dir.mkdir(parents=True, exist_ok=True)
    src_root = patch_dir / "src"
    pnc = src_root / "text" / "PrintNextChar"
    ld = patch_dir / "link" / "game.ld"
    cflags = [
        "-mthumb", "-mcpu=arm7tdmi", "-ffreestanding", "-O2", "-fno-builtin",
        "-Wall", f"-I{src_root}", "-nostdlib", "-c",
    ]
    objs: list[Path] = []

    entry_s = pnc / "entry.s"
    entry_o = obj_dir / "entry.o"
    r = subprocess.run(
        [str(gcc), "-mthumb", "-mcpu=arm7tdmi", "-ffreestanding",
         "-x", "assembler-with-cpp", "-c", str(entry_s), "-o", str(entry_o)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"汇编 entry.s 失败:\n{r.stderr}\n{r.stdout}")
    objs.append(entry_o)

    for name in ("print_next_char", "draw_glyph", "draw_scene", "get_string_width"):
        src = pnc / f"{name}.c"
        obj = obj_dir / f"{name}.o"
        r = subprocess.run(
            [str(gcc), *cflags, str(src), "-o", str(obj)],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            raise RuntimeError(f"编译 {name}.c 失败:\n{r.stderr}\n{r.stdout}")
        objs.append(obj)

    elf = out_dir / "game.elf"
    r = subprocess.run(
        [
            str(gcc), "-mthumb", "-mcpu=arm7tdmi", "-nostdlib",
            f"-T{ld}", f"-Wl,-Map={out_dir / 'game.map'}",
            "-o", str(elf), *[str(o) for o in objs],
        ],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"链接 game.elf 失败:\n{r.stderr}\n{r.stdout}")

    r = subprocess.run(
        [str(objcopy), "-O", "binary", str(elf), str(out_bin)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"objcopy game.bin 失败:\n{r.stderr}\n{r.stdout}")
    if not out_bin.is_file():
        raise RuntimeError("未生成 out/game.bin")
    if out_bin.stat().st_size >= _GAME_BIN_MAX:
        raise RuntimeError(
            f"game.bin 过大 ({out_bin.stat().st_size} >= {_GAME_BIN_MAX})"
        )
    _write_game_syms(out_dir / "game.map", out_dir / "game_syms.asm")
    return out_bin


def _write_game_syms(map_path: Path, out_asm: Path) -> None:
    """Export linker symbols for armips (GetStringWidthChinese thin-shell)."""
    syms: dict[str, int] = {}
    if map_path.is_file():
        for line in map_path.read_text(encoding="utf-8", errors="replace").splitlines():
            # "                0x08800040                PrintNextChar_C"
            parts = line.strip().split()
            if len(parts) >= 2 and parts[0].startswith("0x"):
                name = parts[-1]
                if name in ("GetStringWidthChinese", "PrintNextChar"):
                    try:
                        syms[name] = int(parts[0], 16)
                    except ValueError:
                        pass
    lines = [
        "; Auto-generated from out/game.map — do not edit",
        f"GetStringWidthChinese                   equ 0x{syms.get('GetStringWidthChinese', 0x08800000):08X}",
        "",
    ]
    out_asm.parent.mkdir(parents=True, exist_ok=True)
    out_asm.write_text("\n".join(lines), encoding="utf-8")


def _generate_addrs_asm(cfg: dict[str, Any], output_path: Path) -> None:
    """由 config 生成 include/axvj_addrs.asm（供部分旧 include；主入口用 game_addrs.asm）。"""
    addrs = cfg.get("addrs", {})
    win = cfg.get("win_offsets", {})
    lines = ["; Auto-generated from config"]
    lines.append("")
    if addrs:
        lines.append("; --- ROM addresses ---")
        for name in sorted(addrs):
            lines.append(f"{name:<40s} equ 0x{addrs[name]:08X}")
        lines.append("")
    slots = cfg.get("font_slots", [])
    if slots:
        lines.append("; --- Font slot addresses ---")
        for slot in slots:
            label = slot.get("label", "Unknown")
            addr = slot.get("addr")
            if addr is not None:
                lines.append(f"FontChs{label:<35s} equ 0x{addr:08X}")
        lines.append("")
    if win:
        lines.append("; --- Window struct offsets ---")
        for name in sorted(win):
            lines.append(f"{name:<40s} equ 0x{win[name]:02X}")
    if "escape_byte" in cfg:
        lines.append("")
        lines.append(f"CHS_ESCAPE{'':37s} equ 0x{cfg['escape_byte']:02X}")
    else:
        lines.append("")
        lines.append(f"CHS_ESCAPE{'':37s} equ 0xF9")
    lines.append("")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _generate_fonts_s(cfg: dict[str, Any], work_font_dir: Path, output_path: Path) -> None:
    """生成 graphic/fonts.s：字库 .incbin + 短语表 include。"""
    slots = cfg.get("font_slots", [])
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
            lines.append(f".org 0x{addr:08X}")
        if bin_path.exists():
            lines.append(f".incbin \"{bin_path.resolve()}\"")
            if prefer_unshadow:
                lines.append(f"; shadow=false → {bin_path.name}")
        lines.append("")
    phrase_asm = work_font_dir / "phrase_data.asm"
    if phrase_asm.exists():
        # C dispatch uses fixed VMA; rewrite orgs even for older phrase_data.asm
        staged = output_path.parent / "phrase_data.asm"
        _stage_phrase_data_fixed_vma(phrase_asm, staged)
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
    """打字库补丁：编 game.bin → armips（hook + .incbin + fonts）→ 输出 ROM。

    补丁源目录来自 ``get_game_patch_dir``；产物在 ``work_dir/build/``。
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
    include_dir = build_dir / "include"
    graphic_dir = build_dir / "graphic"
    fonts_build_dir = graphic_dir / "fonts"

    if build_dir.exists():
        shutil.rmtree(build_dir)
    shutil.copytree(src_dir, build_dir)

    # font stage owns charmap.txt; patch/main.asm loads ./charmap.txt from build cwd.
    charmap_src = get_charmap_path(game_id)
    if charmap_src.is_file():
        shutil.copy2(charmap_src, build_dir / "charmap.txt")

    # Optional: game-root tools/armips (sibling of stage packs, not inside patch/)
    root_tools = game_config_dir(game_id) / "tools"
    if root_tools.is_dir() and not (build_dir / "tools").exists():
        shutil.copytree(root_tools, build_dir / "tools")

    _generate_addrs_asm(font_patch_cfg, include_dir / "axvj_addrs.asm")

    fonts_build_dir.mkdir(parents=True, exist_ok=True)
    if fonts_src.exists():
        for bin_file in fonts_src.glob("*.bin"):
            shutil.copy2(bin_file, fonts_build_dir / bin_file.name)
        _generate_fonts_s(font_patch_cfg, fonts_src, graphic_dir / "fonts.s")

    shutil.copy2(rom_path, build_dir / "baserom.gba")

    # C 逻辑 → game.bin，再交给 armips .incbin
    _build_game_bin(build_dir)

    root_armips = Path(__file__).resolve().parent.parent.parent / "tools" / ("armips.exe" if _system == "Windows" else "armips")
    if root_armips.exists():
        armips_path = root_armips
    if armips_path is None:
        local_armips = build_dir / "tools" / ("armips.exe" if _system == "Windows" else "armips")
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

    shutil.copy2(patched, output_path)
    return output_path
