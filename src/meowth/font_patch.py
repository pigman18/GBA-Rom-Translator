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


def _glyph_slot_slice(data: bytes | bytearray, gidx: int, bpg: int) -> memoryview:
    off = gidx * bpg
    return memoryview(data)[off : off + bpg]


def _glyph_slot_empty(data: bytes | bytearray, gidx: int, bpg: int = 128) -> bool:
    return all(b == 0 for b in _glyph_slot_slice(data, gidx, bpg))


def _glyph_slot_has_ink(data: bytes | bytearray, gidx: int, bpg: int = 128) -> bool:
    return any(b != 0 for b in _glyph_slot_slice(data, gidx, bpg))


def _unshadow_name_for_primary_name(primary_name: str) -> str | None:
    parts = primary_name.split("(", 1)
    if len(parts) != 2:
        return None
    return f"{parts[0]}_unshadow({parts[1]}"


def _unshadow_path_for_primary(primary: Path, *, dest_dir: Path | None = None) -> Path | None:
    name = _unshadow_name_for_primary_name(primary.name)
    if name is None:
        return None
    return (dest_dir or primary.parent) / name


def _glyph_index_from_charmap(charmap_path: Path, char: str) -> int | None:
    """Return packed gidx for ``charmap.txt`` entry (same as ``build_chinese_font``)."""
    import importlib.util

    scripts = Path(__file__).resolve().parents[2] / "scripts"
    spec = importlib.util.spec_from_file_location(
        "build_chinese_font", scripts / "build_chinese_font.py"
    )
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mapping = mod.parse_charmap(charmap_path)
    for idx, ch in mapping.items():
        if ch == char:
            return idx
    return None


def _reference_unshadow_pair(
    primary_name: str,
    *,
    game_id: str,
    ref_char: str = "佑",
) -> tuple[bytes, bytes] | None:
    """Load tuned primary/unshadow 128B pair for ``ref_char`` from hook/work reference."""
    ref_dir = get_game_patch_dir(game_id) / "work" / game_id / "graphic" / "fonts"
    if not ref_dir.is_dir():
        return None
    charmap = get_charmap_path(game_id)
    gidx = _glyph_index_from_charmap(charmap, ref_char) if charmap.is_file() else None
    if gidx is None:
        return None
    primary_path = ref_dir / primary_name
    unshadow_name = _unshadow_name_for_primary_name(primary_name)
    if unshadow_name is None:
        return None
    unshadow_path = ref_dir / unshadow_name
    if not primary_path.is_file() or not unshadow_path.is_file():
        return None
    primary = primary_path.read_bytes()
    unshadow = unshadow_path.read_bytes()
    off = gidx * 128
    if off + 128 > len(primary) or off + 128 > len(unshadow):
        return None
    ref_p = primary[off : off + 128]
    ref_u = unshadow[off : off + 128]
    if not _glyph_slot_has_ink(ref_p, 0, 128) or not _glyph_slot_has_ink(ref_u, 0, 128):
        return None
    return ref_p, ref_u


def _load_font_slot_codec():
    """Import decompress_slot + pack_slot16_4bpp from offline font scripts."""
    import importlib.util

    scripts = Path(__file__).resolve().parents[2] / "scripts"
    spec_blit = importlib.util.spec_from_file_location(
        "sim_gba_font_blit", scripts / "sim_gba_font_blit.py"
    )
    spec_bcf = importlib.util.spec_from_file_location(
        "build_chinese_font", scripts / "build_chinese_font.py"
    )
    if (
        spec_blit is None
        or spec_blit.loader is None
        or spec_bcf is None
        or spec_bcf.loader is None
    ):
        raise RuntimeError("font slot codec scripts missing under scripts/")
    blit = importlib.util.module_from_spec(spec_blit)
    bcf = importlib.util.module_from_spec(spec_bcf)
    spec_blit.loader.exec_module(blit)
    spec_bcf.loader.exec_module(bcf)
    return blit.decompress_slot, bcf.pack_slot16_4bpp


def _build_unshadow_tile_nn_bank(
    ref_primary: bytes,
    ref_unshadow: bytes,
    *,
    bytes_per_glyph: int = 128,
) -> list[list[tuple[bytes, bytes]]]:
    """Index tuned primary/unshadow 32B tiles for NN conversion."""
    bank: list[list[tuple[bytes, bytes]]] = [[], [], [], []]
    slot_count = len(ref_primary) // bytes_per_glyph
    for gidx in range(slot_count):
        off = gidx * bytes_per_glyph
        pp = ref_primary[off : off + bytes_per_glyph]
        uu = ref_unshadow[off : off + bytes_per_glyph]
        if not _glyph_slot_has_ink(pp, 0, bytes_per_glyph):
            continue
        if not _glyph_slot_has_ink(uu, 0, bytes_per_glyph):
            continue
        for tile in range(4):
            tile_off = tile * 32
            pt = bytes(pp[tile_off : tile_off + 32])
            if any(pt):
                bank[tile].append((pt, bytes(uu[tile_off : tile_off + 32])))
    return bank


def convert_primary_glyph_to_unshadow_tile_nn(
    primary_glyph: bytes,
    bank: list[list[tuple[bytes, bytes]]],
) -> bytes:
    """Map a primary glyph into ``*_unshadow`` via per-tile nearest neighbour.

    For charmap-only glyphs (e.g. ``祐``) whose hook/work unshadow slot is still
    blank, pixel-morph from ``佑`` distorts the shape. Copy each 32B primary tile
    from the closest tuned primary tile in the reference bank, taking the paired
    tuned unshadow tile bytes.
    """
    if len(primary_glyph) != 128:
        raise ValueError("glyph slots must be 128 bytes")
    out = bytearray(128)
    for tile in range(4):
        pt = bytes(primary_glyph[tile * 32 : (tile + 1) * 32])
        if not any(pt):
            continue
        best_dist = 10**9
        best_u: bytes | None = None
        for pt2, ut in bank[tile]:
            dist = sum(1 for a, b in zip(pt, pt2) if a != b)
            if dist < best_dist:
                best_dist = dist
                best_u = ut
        if best_u is not None:
            out[tile * 32 : (tile + 1) * 32] = best_u
    return bytes(out)


def compose_yu_unshadow_glyph(
    primary_yu: bytes,
    unshadow_you: bytes,
    tile_bank: list[list[tuple[bytes, bytes]]],
) -> bytes:
    """Compose ``祐``: TL/BL from primary via tile-NN; TR/BR from tuned ``右`` unshadow."""
    if len(primary_yu) != 128 or len(unshadow_you) != 128:
        raise ValueError("glyph slots must be 128 bytes")
    out = bytearray(128)
    for tile in (0, 1):
        pt = bytes(primary_yu[tile * 32 : (tile + 1) * 32])
        if not any(pt):
            continue
        best_dist = 10**9
        best_u: bytes | None = None
        for pt2, ut in tile_bank[tile]:
            dist = sum(1 for a, b in zip(pt, pt2) if a != b)
            if dist < best_dist:
                best_dist = dist
                best_u = ut
        if best_u is not None:
            out[tile * 32 : (tile + 1) * 32] = best_u
    if any(unshadow_you[64:96]):
        out[64:96] = unshadow_you[64:96]
    if any(unshadow_you[96:128]):
        out[96:128] = unshadow_you[96:128]
    return bytes(out)


def _patch_yu_unshadow_composite(
    fonts_dir: Path,
    *,
    game_id: str,
    prefix: str,
    bytes_per_glyph: int,
) -> int:
    """Refine ``祐`` unshadow: 礻 from primary + ``右`` from tuned unshadow ``右``."""
    charmap = get_charmap_path(game_id)
    yu_idx = _glyph_index_from_charmap(charmap, "祐")
    you_idx = _glyph_index_from_charmap(charmap, "右")
    ref_dir = _reference_fonts_dir(game_id)
    if yu_idx is None or you_idx is None or ref_dir is None:
        return 0
    patched = 0
    for primary_path in sorted(fonts_dir.glob(f"{prefix}*.bin")):
        if "_unshadow" in primary_path.name:
            continue
        if "Sym" in primary_path.name:
            continue
        unshadow_path = _unshadow_path_for_primary(primary_path, dest_dir=fonts_dir)
        if unshadow_path is None or not unshadow_path.is_file():
            continue
        ref_primary_path = ref_dir / primary_path.name
        if not ref_primary_path.is_file():
            continue
        ref_primary = ref_primary_path.read_bytes()
        ref_unshadow_path = ref_dir / (_unshadow_name_for_primary_name(primary_path.name) or "")
        if not ref_unshadow_path.is_file():
            continue
        ref_unshadow = ref_unshadow_path.read_bytes()
        tile_bank = _build_unshadow_tile_nn_bank(
            ref_primary,
            ref_unshadow,
            bytes_per_glyph=bytes_per_glyph,
        )
        end_yu = yu_idx * bytes_per_glyph + bytes_per_glyph
        end_you = you_idx * bytes_per_glyph + bytes_per_glyph
        if end_yu > len(ref_primary) or end_you > len(unshadow_path.read_bytes()):
            continue
        primary_yu = ref_primary[yu_idx * bytes_per_glyph : end_yu]
        if not _glyph_slot_has_ink(primary_yu, 0, bytes_per_glyph):
            continue
        dst = bytearray(unshadow_path.read_bytes())
        you_slot = dst[you_idx * bytes_per_glyph : end_you]
        if not _glyph_slot_has_ink(you_slot, 0, bytes_per_glyph):
            you_slot = ref_unshadow[you_idx * bytes_per_glyph : end_you]
        if not _glyph_slot_has_ink(you_slot, 0, bytes_per_glyph):
            continue
        composed = compose_yu_unshadow_glyph(primary_yu, bytes(you_slot), tile_bank)
        off = yu_idx * bytes_per_glyph
        if dst[off:end_yu] == composed:
            continue
        dst[off:end_yu] = composed
        unshadow_path.write_bytes(dst)
        ref_dst = bytearray(ref_unshadow_path.read_bytes())
        if len(ref_dst) >= end_yu:
            ref_dst[off:end_yu] = composed
            ref_unshadow_path.write_bytes(ref_dst)
        patched += 1
    return patched


def morph_primary_glyph_to_unshadow_display(
    primary_glyph: bytes,
    ref_primary_glyph: bytes,
    ref_unshadow_glyph: bytes,
) -> bytes:
    """Map a primary-bank glyph into tuned ``*_unshadow`` tile packing.

    AXVJ ``*_unshadow`` bins use a different byte layout than primary. Pixel-diff
    morph against a tuned pair (default ``佑``) round-trips all 6657+ hook slots;
    raw primary bytes or byte-blend leave new glyphs like ``祐`` torn in-game.
    """
    if len(primary_glyph) != 128 or len(ref_primary_glyph) != 128 or len(ref_unshadow_glyph) != 128:
        raise ValueError("glyph slots must be 128 bytes")
    decompress_slot, pack_slot16_4bpp = _load_font_slot_codec()
    target_px = decompress_slot(primary_glyph)
    ref_px = decompress_slot(ref_primary_glyph)
    out_px = list(decompress_slot(ref_unshadow_glyph))
    for i in range(256):
        if target_px[i] and not ref_px[i]:
            out_px[i] = 15
        elif not target_px[i] and ref_px[i]:
            out_px[i] = 0
    slot = bytearray(256)
    for i, val in enumerate(out_px):
        slot[i] = 15 if val else 0
    return pack_slot16_4bpp(slot)


def convert_primary_glyph_to_unshadow_display(
    primary_glyph: bytes,
    ref_primary_glyph: bytes,
    ref_unshadow_glyph: bytes,
) -> bytes:
    """Backward-compatible alias — always use pixel morph."""
    return morph_primary_glyph_to_unshadow_display(
        primary_glyph, ref_primary_glyph, ref_unshadow_glyph
    )


def restore_tuned_font_bins_from_reference(
    fonts_dir: Path,
    *,
    game_id: str,
    prefix: str = "PokeRSFontChs",
) -> int:
    """Restore hook/work tuned ``*_unshadow`` + Sym bins after Meowth BDF build.

    Meowth primary bins are regenerated each build; tuned display bins must stay
    identical to hook/work reference or Small/Normal draw corrupts (empty extension
    slots must remain zero).
    """
    ref_dir = _reference_fonts_dir(game_id)
    if ref_dir is None:
        return 0
    restored = 0
    for ref in sorted(ref_dir.glob(f"{prefix}*.bin")):
        if "_unshadow" not in ref.name and "Sym" not in ref.name:
            continue
        dst = fonts_dir / ref.name
        ref_data = ref.read_bytes()
        if dst.is_file() and dst.read_bytes() == ref_data:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ref, dst)
        restored += 1
    return restored


def seed_unshadow_banks_from_reference(
    fonts_dir: Path,
    *,
    game_id: str,
    prefix: str = "PokeRSFontChs",
) -> int:
    """Overlay tuned ``*_unshadow`` banks from hook/work before morph fill."""
    ref_dir = get_game_patch_dir(game_id) / "work" / game_id / "graphic" / "fonts"
    if not ref_dir.is_dir():
        return 0
    seeded = 0
    for ref in sorted(ref_dir.glob(f"{prefix}*_unshadow*.bin")):
        dst = fonts_dir / ref.name
        ref_data = ref.read_bytes()
        if dst.is_file() and dst.read_bytes() == ref_data:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ref, dst)
        seeded += 1
    return seeded


def _reference_unshadow_bin(primary_name: str, *, game_id: str) -> bytes | None:
    ref_dir = get_game_patch_dir(game_id) / "work" / game_id / "graphic" / "fonts"
    unshadow_name = _unshadow_name_for_primary_name(primary_name)
    if unshadow_name is None or not ref_dir.is_dir():
        return None
    path = ref_dir / unshadow_name
    if not path.is_file():
        return None
    return path.read_bytes()


def _reference_fonts_dir(game_id: str) -> Path | None:
    ref_dir = get_game_patch_dir(game_id) / "work" / game_id / "graphic" / "fonts"
    return ref_dir if ref_dir.is_dir() else None


def _charmap_glyph_indices(game_id: str) -> set[int]:
    charmap = get_charmap_path(game_id)
    if not charmap.is_file():
        return set()
    import importlib.util

    scripts = Path(__file__).resolve().parents[2] / "scripts"
    spec = importlib.util.spec_from_file_location(
        "build_chinese_font", scripts / "build_chinese_font.py"
    )
    if spec is None or spec.loader is None:
        return set()
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return set(mod.parse_charmap(charmap).keys())


def patch_primary_missing_glyphs_from_reference(
    fonts_dir: Path,
    *,
    game_id: str,
    prefix: str = "PokeRSFontChs",
    bytes_per_glyph: int = 128,
) -> int:
    """Fill empty primary slots from hook/work tuned bins.

    Meowth BDF may omit charmap entries (e.g. ``祐`` / U+7950). Those slots stay
    blank after ``build_chinese_font``; copy only per-glyph from hook/work primary
    when the destination slot is still empty.
    """
    ref_dir = _reference_fonts_dir(game_id)
    if ref_dir is None:
        return 0
    charmap_gidx = _charmap_glyph_indices(game_id)
    if not charmap_gidx:
        return 0
    patched = 0
    for dst_path in sorted(fonts_dir.glob(f"{prefix}*.bin")):
        if "_unshadow" in dst_path.name:
            continue
        ref_path = ref_dir / dst_path.name
        if not ref_path.is_file():
            continue
        ref_data = ref_path.read_bytes()
        dst_data = bytearray(dst_path.read_bytes())
        if len(dst_data) < len(ref_data):
            dst_data.extend(b"\x00" * (len(ref_data) - len(dst_data)))
        file_patched = 0
        for gidx in charmap_gidx:
            end = gidx * bytes_per_glyph + bytes_per_glyph
            if end > len(dst_data) or end > len(ref_data):
                continue
            if not _glyph_slot_empty(dst_data, gidx, bytes_per_glyph):
                continue
            if not _glyph_slot_has_ink(ref_data, gidx, bytes_per_glyph):
                continue
            off = gidx * bytes_per_glyph
            dst_data[off:end] = ref_data[off:end]
            file_patched += 1
        if file_patched:
            dst_path.write_bytes(dst_data)
            patched += file_patched
    return patched


def patch_unshadow_missing_glyphs(
    fonts_dir: Path,
    *,
    source_dir: Path | None = None,
    prefix: str = "PokeRSFontChs",
    bytes_per_glyph: int = 128,
    game_id: str = "",
) -> int:
    """Fill empty ``*_unshadow`` slots from a source bin — never full-file overwrite.

    AXVJ ``shadow: false`` embeds ``*_unshadow*.bin`` in ``fonts.s``. Those bins are
    tuned display assets (often != primary). Only write per-glyph when hook/work
    reference still has a blank slot (new charmap entries like ``祐``), or when a
    prior bad primary copy must be repaired. Glyphs are morphed via tuned ``佑``.
    """
    src_root = source_dir or fonts_dir
    patched = 0
    for primary in sorted(src_root.glob(f"{prefix}*.bin")):
        if "_unshadow" in primary.name:
            continue
        unshadow = _unshadow_path_for_primary(primary, dest_dir=fonts_dir)
        if unshadow is None:
            continue
        primary_path = primary if source_dir is None else (fonts_dir / primary.name)
        if not primary_path.is_file():
            continue
        ref_pair = (
            _reference_unshadow_pair(primary.name, game_id=game_id) if game_id else None
        )
        ref_unshadow = (
            _reference_unshadow_bin(primary.name, game_id=game_id) if game_id else None
        )
        ref_primary: bytes | None = None
        ref_dir = _reference_fonts_dir(game_id) if game_id else None
        if ref_dir is not None:
            ref_primary_path = ref_dir / primary.name
            if ref_primary_path.is_file():
                ref_primary = ref_primary_path.read_bytes()
        tile_bank = None
        if ref_primary and ref_unshadow:
            tile_bank = _build_unshadow_tile_nn_bank(
                ref_primary,
                ref_unshadow,
                bytes_per_glyph=bytes_per_glyph,
            )
        if not unshadow.is_file():
            if ref_unshadow is not None:
                unshadow.write_bytes(ref_unshadow)
            else:
                shutil.copy2(primary_path, unshadow)
            continue
        src = bytearray(primary.read_bytes() if source_dir is not None else primary_path.read_bytes())
        dst = bytearray(unshadow.read_bytes())
        if len(dst) < len(src):
            dst.extend(b"\x00" * (len(src) - len(dst)))
        slot_count = len(src) // bytes_per_glyph
        charmap_gidx = _charmap_glyph_indices(game_id) if game_id else None
        file_patched = 0
        for gidx in range(slot_count):
            if charmap_gidx is not None and gidx not in charmap_gidx:
                continue
            if not _glyph_slot_has_ink(src, gidx, bytes_per_glyph):
                continue
            ref_has_ink = ref_unshadow is not None and not _glyph_slot_empty(
                ref_unshadow, gidx, bytes_per_glyph
            )
            dst_empty = _glyph_slot_empty(dst, gidx, bytes_per_glyph)
            if not dst_empty and ref_has_ink:
                continue
            if dst_empty and ref_has_ink:
                off = gidx * bytes_per_glyph
                dst[off : off + bytes_per_glyph] = ref_unshadow[off : off + bytes_per_glyph]
                file_patched += 1
                continue
            if ref_pair is None and tile_bank is None:
                continue
            off = gidx * bytes_per_glyph
            src_slot = bytes(src[off : off + bytes_per_glyph])
            if tile_bank is not None:
                slot = convert_primary_glyph_to_unshadow_tile_nn(src_slot, tile_bank)
            else:
                slot = morph_primary_glyph_to_unshadow_display(src_slot, *ref_pair)
            dst[off : off + bytes_per_glyph] = slot
            file_patched += 1
        if file_patched:
            unshadow.write_bytes(dst)
            patched += file_patched
    return patched


def sync_unshadow_font_bins(fonts_dir: Path, prefix: str = "PokeRSFontChs") -> int:
    """Deprecated: full primary→unshadow copy destroys tuned ``*_unshadow`` banks."""
    return patch_unshadow_missing_glyphs(fonts_dir, prefix=prefix)


def _embed_primary_bins(cfg: dict[str, Any]) -> bool:
    """When true, ``fonts.s`` incbins primary ``*.bin`` (not ``*_unshadow``)."""
    return cfg.get("embed_primary") is True


def _generate_fonts_s(cfg: dict[str, Any], work_font_dir: Path, output_path: Path, game_id: str = "") -> None:
    """生成 graphic/fonts.s：字库 .incbin + phrase data include。"""
    slots = _normalize_font_slots(cfg, game_id=game_id)
    prefix = cfg.get("font_bin_prefix", "PokeRSFontChs")
    embed_primary = _embed_primary_bins(cfg)
    prefer_unshadow = cfg.get("shadow") is False and not embed_primary
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
            if prefer_unshadow:
                us = [p for p in alt if "_unshadow" in p.name]
                bin_path = us[0] if us else (alt[0] if alt else bin_path)
            else:
                prim = [p for p in alt if "_unshadow" not in p.name]
                bin_path = prim[0] if prim else (alt[0] if alt else bin_path)
        if addr is not None:
            lines.append(f".org 0x{int(addr):08X}")
        if bin_path.exists():
            lines.append(f".incbin \"{bin_path.resolve()}\"")
            if embed_primary:
                lines.append(f"; embed_primary → {bin_path.name}")
            elif prefer_unshadow:
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
    prefix = font_patch_cfg.get("font_bin_prefix", "PokeRSFontChs")
    embed_primary = _embed_primary_bins(font_patch_cfg)
    if (
        font_patch_cfg.get("shadow") is False
        and fonts_src.exists()
        and not embed_primary
    ):
        restore_tuned_font_bins_from_reference(fonts_src, game_id=game_id, prefix=prefix)
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

    # type=slot → translated_slot.asm（JP hex → 中文 F9 流查找表）
    from .translated_slot import write_slot_table_asm

    n_slot = write_slot_table_asm(
        work_dir / "translate.build.json",
        build_dir / "gen" / "translated_slot.asm",
        rom_path=build_dir / "baserom.gba",
    )
    if n_slot:
        print(f"[slot] translated_slot.asm: {n_slot} type=slot entries")

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
