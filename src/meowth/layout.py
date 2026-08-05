"""Layout stage: generate xxx_translated.bin + xxx_translated.asm.

Decouples "decision-making" from "ROM byte writing". The layout stage
decides where every piece of data goes and emits two files that a
single armips invocation can apply to baserom.gba.
"""

from __future__ import annotations

import json
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .charmap import Charmap

_POINTER_OFFSET = 0x08000000
_GBA_MAX = 0x02000000  # 32 MB


@dataclass
class PatchEntry:
    """One data chunk to write into the ROM."""
    rom_offset: int          # file offset (VMA − 0x08000000)
    data: bytes
    comment: str = ""


@dataclass
class PtrPatch:
    """One 4-byte pointer patch."""
    rom_offset: int          # file offset of the pointer
    value: int               # GBA pointer value (addr + 0x08000000)
    comment: str = ""


@dataclass
class HalfPatch:
    """One 2-byte patch (e.g. multiply instruction)."""
    rom_offset: int
    value: int               # 16-bit value
    comment: str = ""


@dataclass
class LayoutResult:
    """Complete output of the layout stage."""
    # Binary data chunks (written via .incbin)
    chunks: list[PatchEntry] = field(default_factory=list)
    # Inline patches (written as .word / .halfword)
    ptr_patches: list[PtrPatch] = field(default_factory=list)
    half_patches: list[HalfPatch] = field(default_factory=list)
    # Metadata
    stats: dict = field(default_factory=dict)


# ------------------------------------------------------------------ #
#  helpers
# ------------------------------------------------------------------ #

def _align4(n: int) -> int:
    return (n + 3) & ~3


def _gba_ptr(file_offset: int) -> int:
    """ROM file offset → GBA pointer word."""
    return file_offset + _POINTER_OFFSET


# ------------------------------------------------------------------ #
#  Step 1 – build expansion area binary
# ------------------------------------------------------------------ #

def _load_bin(path: Path) -> bytes:
    return path.read_bytes() if path.exists() else b""


def build_expansion_bin(
    work_dir: Path,
    game_id: str,
    fp_cfg: dict[str, Any],
    extra_chunks: list[PatchEntry] | None = None,
) -> tuple[bytes, dict[str, tuple[int, int, int]]]:
    """Pack fonts + extra chunks into one contiguous expansion-area blob.

    Returns (blob, map) where *map* maps a component name to
    ``(offset_within_blob, byte_length, target_vma)``.
    """
    game_work = work_dir / game_id
    fonts_dir = game_work / "graphic" / "fonts"
    prefix = fp_cfg.get("font_bin_prefix", "PokeRSFontChs")
    slots = fp_cfg.get("font_slots") or []
    _POINTER_OFFSET = 0x08000000

    parts: list[bytes] = []
    mapping: dict[str, tuple[int, int, int]] = {}
    off = 0

    # ---- fonts ----
    prefer_unshadow = fp_cfg.get("shadow") is False
    for slot in slots:
        label = slot.get("label", "Unknown")
        slot_size = slot.get(
            "slot_size",
            slot.get("glyph_count", 7168) * slot.get("bytes_per_glyph", 128),
        )
        slot_addr = int(str(slot.get("addr", 0)), 0)
        fname = f"{prefix}{label}(0x{slot_size:X}).bin"
        unfname = f"{prefix}{label}_unshadow(0x{slot_size:X}).bin"
        bin_path = fonts_dir / fname
        if prefer_unshadow and (fonts_dir / unfname).exists():
            bin_path = fonts_dir / unfname
        data = _load_bin(bin_path)
        if not data:
            continue
        mapping[f"font_{label}"] = (off, len(data), slot_addr)
        parts.append(data)
        off += len(data)

    # ---- extra chunks (name tables + relocated text) ----
    # Place data after the last font slot to avoid VMA overlap.
    data_base_vma = 0
    for slot in slots:
        slot_addr = int(str(slot.get("addr", 0)), 0)
        slot_size = slot.get(
            "slot_size",
            slot.get("glyph_count", 7168) * slot.get("bytes_per_glyph", 128),
        )
        end = slot_addr + slot_size
        if end > data_base_vma:
            data_base_vma = end
    # Align to 0x1000 boundary
    data_base_vma = (data_base_vma + 0xFFF) & ~0xFFF
    font_total = off  # bytes consumed by fonts so far

    if extra_chunks:
        for chunk in extra_chunks:
            while off % 4:
                parts.append(b"\x00")
                off += 1
            vma = data_base_vma + (off - font_total)
            mapping[chunk.comment] = (off, len(chunk.data), vma)
            parts.append(chunk.data)
            off += len(chunk.data)

    blob = b"".join(parts)
    return blob, mapping


# ------------------------------------------------------------------ #
#  Step 2 – translate & collect text write ops
# ------------------------------------------------------------------ #

def layout_texts(
    rom: bytearray,
    entries: list[dict],
    charmap: Charmap,
    *,
    fp_cfg: dict[str, Any],
    game: str = "",
    target_lang: str = "zh-Hans",
    custom_translations: dict[str, str] | None = None,
    line_width_default: int | None = None,
    line_width_modules: dict[str, int] | None = None,
    on_progress=None,
) -> LayoutResult:
    """Decide placement for every entry and return a LayoutResult.

    This is the *decision* counterpart of RomWriter.inject_texts.
    Instead of mutating *rom*, it records PatchEntry / PtrPatch objects.
    """
    from .extract import trusted_lz_spans
    from .policy import filter_pointer_sources
    from .config_loader import (
        F9_PHRASE_DEFAULT, F9_EOS, module_write_op, load_game_config,
    )
    from .text_wrap import wrap_text

    is_armips = bool(fp_cfg.get("expands_rom", False))
    fill_byte = fp_cfg.get("fill_byte", 0x00 if is_armips else 0xFF)
    expansion_start = int(fp_cfg.get("expansion_start", 0x01000000))
    font_boundary = int(fp_cfg.get("font_boundary", 0x01FD3000))
    min_ptr_src = int(fp_cfg.get("min_pointer_source", 0x6000))

    result = LayoutResult()

    # ---- find free space in expansion area ----
    floor = max(expansion_start, _font_slots_end_offset(fp_cfg))
    if is_armips:
        free_start = _find_free_space(rom, font_boundary, fill=0x00)
        free_start = max(free_start, floor)
        if free_start >= font_boundary - 0x1000:
            free_start = floor
    else:
        free_start = max(_find_free_space(rom, font_boundary, fill=0xFF), floor)

    write_offset = free_start
    lz_spans = trusted_lz_spans(rom) if is_armips else []

    # ---- name tables (expanded CHS tables) ----
    expanded_modules: set[str] = set()
    if is_armips:
        from .table_patch import _load_table_patches, _merge_table_entries
        from .tables import build_chs_table, find_literal_refs, base

        game_cfg = {}
        try:
            game_cfg = load_game_config(game)
        except Exception:
            pass
        tables_cfg = game_cfg.get("tables", {})
        patches_list = _load_table_patches(tables_cfg)

        for patch in patches_list:
            key = patch["tables_key"]
            module = patch.get("module") or key
            expanded_modules.add(module)
            expanded_modules.add(key)

            # Collect entries for this table
            matched = [e for e in entries if (e.get("module") or e.get("_axvj_module") or e.get("category") or "") == module]
            if not matched:
                continue

            # Build table binary
            def encode_tbl(text: str) -> bytes:
                raw = charmap.encode(text)
                if len(raw) < 4 or raw[0] != 0xF9 or raw[1] != F9_PHRASE_DEFAULT:
                    return raw
                code = module_write_op(game, module) if game else None
                if code is not None:
                    return bytes([0xF9, code & 0xFF]) + raw[2:]
                return raw

            # Simple path: write table data to expansion area
            chs_stride = patch.get("chs_stride", 0)
            count = patch.get("count", 0)
            stride = patch.get("stride", 0)
            if chs_stride and count and stride:
                full = _merge_table_entries(
                    bytes(rom), matched,
                    offset=patch["offset"], stride=stride,
                    count=count, module=module,
                )
                table_bin = build_chs_table(
                    full, encode_tbl,
                    stride=chs_stride, count=count, table_label=module,
                )
                while write_offset % 4:
                    write_offset += 1
                result.chunks.append(PatchEntry(
                    rom_offset=write_offset,
                    data=table_bin,
                    comment=f"name_table_{module}",
                ))
                # Retarget literal pool pointers
                patch_offset = patch.get("offset", 0)
                lits = [
                    lit for lit in find_literal_refs(bytes(rom), patch_offset)
                    if struct.unpack_from("<I", rom, lit)[0] == base() + patch_offset
                ]
                new_gba = _gba_ptr(write_offset)
                for lit in lits:
                    result.ptr_patches.append(PtrPatch(
                        rom_offset=lit,
                        value=new_gba,
                        comment=f"table_ptr_{module}",
                    ))
                write_offset += len(table_bin)

    # ---- main text injection loop ----
    baseline = bytes(rom) if is_armips else b""
    rom_ba = bytearray(rom)
    total = len(entries)
    stats = {"in_place": 0, "relocated": 0, "skipped": 0}

    for i, entry in enumerate(entries):
        original = entry.get("original", "").strip('"')
        translated = entry.get("translated", "").strip('"')
        if not translated or translated == original:
            stats["skipped"] += 1
            continue

        address = int(entry.get("address", "0x0").replace("0x", ""), 16)
        if address >= _POINTER_OFFSET:
            address -= _POINTER_OFFSET
        pointer_sources = entry.get("pointer_addresses", entry.get("pointer_sources", []))
        is_pointer_based = entry.get("is_pointer_based", bool(pointer_sources))
        original_length = entry.get("byte_length", 0)
        category = entry.get("module") or entry.get("_axvj_module") or entry.get("category") or ""
        entry_id = entry.get("id", "?")

        # Skip expanded modules (handled by name table armips include)
        if category in expanded_modules:
            continue

        # Prepare text
        if is_armips and target_lang.startswith("zh"):
            lw = (line_width_modules or {}).get(category, line_width_default or 20)
            translated = _prepare_zh_text(translated, line_width=lw)

        # ---- encode with phrase codes (same as build_rom) ----
        # PhraseTable stores expanded F9 00+PCS streams, so \\n/controls are OK.
        sanitized = charmap._sanitize(translated)
        phrase_codes = getattr(charmap, "_phrase_codes", None)
        if phrase_codes and sanitized in phrase_codes:
            code = phrase_codes[sanitized]
            encoded = bytes([
                0xF9,
                F9_PHRASE_DEFAULT,
                (code >> 8) & 0xFF,
                code & 0xFF,
                F9_EOS,
            ])
        else:
            encoded = charmap.encode(translated)

        # F9 phrase channel op rewrite (module-specific write.type=op)
        if is_armips and target_lang.startswith("zh") and len(encoded) >= 4:
            mid = entry.get("_axvj_module") or entry.get("module")
            code = module_write_op(game, mid)
            if (
                code is not None
                and encoded[0] == 0xF9
                and encoded[1] == F9_PHRASE_DEFAULT
            ):
                encoded = bytes([0xF9, code & 0xFF]) + encoded[2:]

        # ---- decide: relocate or in-place ----
        if is_armips:
            if is_pointer_based and pointer_sources:
                # Relocate: write to expansion area
                encoded = _axvj_pad_relocated(encoded)
                if write_offset + len(encoded) >= font_boundary:
                    stats["skipped"] += 1
                    continue
                # Ensure rom is big enough
                need = write_offset + len(encoded)
                if need > len(rom):
                    rom.extend(b"\x00" * (need - len(rom) + 0x1000))

                # Write text data
                result.chunks.append(PatchEntry(
                    rom_offset=write_offset,
                    data=encoded,
                    comment=f"reloc_{entry_id}",
                ))

                # Patch pointers
                new_gba = _gba_ptr(write_offset)
                verified = filter_pointer_sources(
                    rom_ba, pointer_sources, address,
                    category=category, original=original,
                    expected_pointer=_gba_ptr(address),
                    lz_spans=lz_spans,
                    min_pointer_source=min_ptr_src,
                )
                for ptr_addr in verified:
                    result.ptr_patches.append(PtrPatch(
                        rom_offset=ptr_addr,
                        value=new_gba,
                        comment=f"ptr_{entry_id}",
                    ))

                write_offset += len(encoded)
                stats["relocated"] += 1
                continue

            # In-place
            if address <= 0 or original_length <= 0:
                stats["skipped"] += 1
                continue
            if len(encoded) > original_length:
                encoded = encoded[: original_length - 1] + b"\xFF"

            result.chunks.append(PatchEntry(
                rom_offset=address,
                data=encoded,
                comment=f"inplace_{entry_id}",
            ))
            stats["in_place"] += 1
            continue

        # ---- non-armips path ----
        if is_pointer_based and pointer_sources:
            encoded = _axvj_pad_relocated(encoded)
            if write_offset + len(encoded) >= font_boundary:
                stats["skipped"] += 1
                continue
            need = write_offset + len(encoded)
            if need > len(rom):
                rom.extend(b"\x00" * (need - len(rom) + 0x1000))

            result.chunks.append(PatchEntry(
                rom_offset=write_offset,
                data=encoded,
                comment=f"reloc_{entry_id}",
            ))
            new_gba = _gba_ptr(write_offset)
            for ptr_src in pointer_sources:
                ptr_addr = int(str(ptr_src).replace("0x", ""), 16)
                if ptr_addr >= _POINTER_OFFSET:
                    ptr_addr -= _POINTER_OFFSET
                if ptr_addr < min_ptr_src:
                    continue
                if ptr_addr + 4 <= len(rom):
                    result.ptr_patches.append(PtrPatch(
                        rom_offset=ptr_addr,
                        value=new_gba,
                        comment=f"ptr_{entry_id}",
                    ))
            write_offset += len(encoded)
            stats["relocated"] += 1
        elif address > 0 and original_length > 0:
            if len(encoded) > original_length:
                encoded = encoded[: original_length - 1] + b"\xFF"
            result.chunks.append(PatchEntry(
                rom_offset=address,
                data=encoded,
                comment=f"inplace_{entry_id}",
            ))
            stats["in_place"] += 1
        else:
            stats["skipped"] += 1

        if on_progress and (i % 200 == 0 or i + 1 == total):
            on_progress(i + 1, total)

    result.stats = stats
    return result


# ------------------------------------------------------------------ #
#  Step 3 – generate output files
# ------------------------------------------------------------------ #

def _generate_asm(
    result: LayoutResult,
    expansion_bin: dict[str, tuple[int, int]],
    expansion_vma_base: int,
    *,
    game_bin_path: Path | None = None,
    game_bin_vma: int = 0x08800000,
    fp_cfg: dict | None = None,
    game_addrs_asm: str = "",
    bin_filename: str = "xxx_translated.bin",
) -> str:
    """Generate the xxx_translated.asm content."""
    fp_cfg = fp_cfg or {}
    lines: list[str] = []

    lines.append("; Auto-generated by meowth layout – do not edit")
    lines.append(".gba")
    lines.append(".thumb")
    lines.append('.open "baserom.gba", "output.gba", 0x08000000')
    lines.append("")

    # ---- hooks (hardcoded for AXVJ – read from game_addrs) ----
    if game_addrs_asm:
        lines.append("; --- ROM hooks ---")
        for ln in game_addrs_asm.splitlines():
            ln = ln.strip()
            if not ln or ln.startswith(";"):
                continue
            # Only include .org / instruction lines, skip .include/.incbin
            if ".include" in ln or ".incbin" in ln or ".close" in ln or ".open" in ln:
                continue
            lines.append(ln)
    lines.append("")

    # ---- game.bin ----
    if game_bin_path and game_bin_path.exists():
        game_size = game_bin_path.stat().st_size
        lines.append(f"; --- game.bin ({game_size} bytes) ---")
        lines.append(f".org 0x{game_bin_vma:08X}")
        lines.append(f'.incbin "{game_bin_path.name}"')
        lines.append("")

    # ---- expansion area: fonts + name tables + relocated text ----
    if expansion_bin:
        lines.append("; --- expansion area: fonts + name tables + relocated text ---")
        for name, (off, size, vma) in sorted(expansion_bin.items(), key=lambda x: x[1][2]):
            lines.append(f".org 0x{vma:08X}")
            lines.append(f'.incbin "{bin_filename}", 0x{off:X}, 0x{size:X}  ; {name}')
        lines.append("")

    # ---- text chunks ----
    # Note: all chunks (name_table_, reloc_, inplace_) are already packed into
    # expansion_bin and rendered via .incbin above. Do NOT re-render them here.

    # ---- pointer patches (deduplicated – last value wins) ----
    if result.ptr_patches:
        seen_ptr: dict[int, str] = {}
        for p in result.ptr_patches:
            addr = _POINTER_OFFSET + p.rom_offset
            seen_ptr[addr] = p.comment
        # Rebuild deduplicated patches
        dedup_ptr = {}
        for p in result.ptr_patches:
            addr = _POINTER_OFFSET + p.rom_offset
            dedup_ptr[addr] = p
        lines.append("; --- pointer patches ---")
        for addr in sorted(dedup_ptr):
            p = dedup_ptr[addr]
            lines.append(f".org 0x{addr:08X}")
            lines.append(f".word 0x{p.value:08X}  ; {p.comment}")
        lines.append("")

    # ---- halfword patches ----
    if result.half_patches:
        lines.append("; --- halfword patches ---")
        for p in result.half_patches:
            lines.append(f".org 0x{_POINTER_OFFSET + p.rom_offset:08X}")
            lines.append(f".halfword 0x{p.value:04X}  ; {p.comment}")
        lines.append("")

    lines.append(".close")
    return "\n".join(lines)


def _generate_bin(
    result: LayoutResult,
    expansion_bin: bytes,
    game_bin_path: Path | None = None,
) -> bytes:
    """Generate the xxx_translated.bin.

    Layout:
      [0 .. game_bin_size)                          = game.bin
      [game_bin_size .. game_bin_size + exp_size)    = expansion area
        (fonts + name tables + relocated text data)

    In-place text data is NOT included (it overwrites original ROM bytes
    and is handled as .byte in the .asm).
    """
    parts: list[bytes] = []

    # ---- game.bin ----
    if game_bin_path and game_bin_path.exists():
        game_data = game_bin_path.read_bytes()
        parts.append(game_data)
        # Pad to 4-byte alignment
        while len(parts[-1]) % 4:
            parts[-1] += b"\x00"

    # ---- expansion area (fonts + name tables + reloc text) ----
    if expansion_bin:
        padded = expansion_bin
        while len(padded) % 4:
            padded += b"\x00"
        parts.append(padded)

    return b"".join(parts)


# ------------------------------------------------------------------ #
#  public API
# ------------------------------------------------------------------ #

def run_layout(
    original_rom: Path,
    translations_path: Path,
    output_dir: Path,
    work_dir: Path,
    game: str,
    target_lang: str = "zh-Hans",
    charmap: Charmap | None = None,
    fp_cfg: dict | None = None,
    custom_translations: dict[str, str] | None = None,
    on_progress=None,
) -> tuple[Path, Path, dict]:
    """Run the full layout stage.

    Returns (bin_path, asm_path, stats).
    """
    from .config_loader import load_game_config, get_game_patch_dir, get_charmap_path

    if charmap is None:
        charmap = Charmap(target_lang=target_lang)
    if fp_cfg is None:
        try:
            cfg = load_game_config(game)
            fp_cfg = cfg.get("font_patch", {})
        except Exception:
            fp_cfg = {}

    rom = bytearray(original_rom.read_bytes())
    data = json.loads(translations_path.read_text(encoding="utf-8"))

    # Flatten entries
    entries = []
    for e in data.get("entries") or []:
        entries.append(e)
    for table in data.get("tables") or []:
        for e in table.get("entries") or []:
            entries.append(e)
    for e in data.get("free_texts") or []:
        entries.append(e)

    # ---- wrap charmap with phrase codes (same as build_rom) ----
    if custom_translations and target_lang.startswith("zh"):
        from .config_loader import F9_PHRASE_DEFAULT, F9_EOS

        charmap._phrase_codes = {}
        phrases = sorted(
            {charmap._sanitize(v) for v in custom_translations.values() if len(v) > 1},
            key=lambda s: (len(s), s),
        )
        for code, s in enumerate(phrases):
            charmap._phrase_codes[s] = code

        _orig_encode = charmap.encode
        charmap._sideload_encode = _orig_encode

        def _encode(text):
            s = charmap._sanitize(text)
            pc = getattr(charmap, "_phrase_codes", None)
            if pc and s in pc:
                code = pc[s]
                return bytes([
                    0xF9,
                    F9_PHRASE_DEFAULT,
                    (code >> 8) & 0xFF,
                    code & 0xFF,
                    F9_EOS,
                ])
            return _orig_encode(text)

        charmap.encode = _encode

    # ---- layout text injection ----
    result = layout_texts(
        rom, entries, charmap,
        fp_cfg=fp_cfg,
        game=game,
        target_lang=target_lang,
        custom_translations=custom_translations,
        on_progress=on_progress,
    )

    # ---- collect extra chunks (name tables + relocated text) for expansion bin ----
    extra_chunks = []
    for chunk in result.chunks:
        if chunk.comment.startswith("name_table_") or chunk.comment.startswith("reloc_"):
            extra_chunks.append(chunk)

    # ---- build expansion bin (fonts + name tables + reloc text) ----
    expansion_blob, expansion_map = build_expansion_bin(
        work_dir, game, fp_cfg, extra_chunks=extra_chunks,
    )

    # ---- build game.bin path ----
    game_work = work_dir / game
    patch_dir = get_game_patch_dir(game)
    game_bin = game_work / "build" / "out" / "game.bin"
    if not game_bin.exists():
        game_bin = patch_dir / "out" / "game.bin"

    # ---- generate asm ----
    expansion_start = int(fp_cfg.get("expansion_start", 0x01000000))
    # VMA = ROM offset + 0x08000000 (GBA ROM mapping)
    expansion_vma = expansion_start + _POINTER_OFFSET

    asm_content = _generate_asm(
        result,
        expansion_map,
        expansion_vma,
        game_bin_path=game_bin,
        fp_cfg=fp_cfg,
        bin_filename=f"{original_rom.stem}_translated.bin",
    )

    # ---- generate bin ----
    bin_data = _generate_bin(
        result,
        expansion_blob,
        game_bin_path=game_bin,
    )

    # ---- write files ----
    output_dir.mkdir(parents=True, exist_ok=True)
    bin_path = output_dir / f"{original_rom.stem}_translated.bin"
    asm_path = output_dir / f"{original_rom.stem}_translated.asm"
    bin_path.write_bytes(bin_data)
    asm_path.write_text(asm_content, encoding="utf-8")

    print(f"Layout: {bin_path.name} ({len(bin_data):,} bytes)")
    print(f"Layout: {asm_path.name}")
    print(f"  in-place={result.stats.get('in_place', 0)}, "
          f"relocated={result.stats.get('relocated', 0)}, "
          f"skipped={result.stats.get('skipped', 0)}")

    return bin_path, asm_path, result.stats


# ------------------------------------------------------------------ #
#  internal helpers (copied/adapted from rom_writer)
# ------------------------------------------------------------------ #

def _find_free_space(rom: bytes, boundary: int, fill: int = 0x00) -> int:
    end = min(boundary, len(rom))
    pos = end - 1
    while pos >= 0 and rom[pos] == fill:
        pos -= 1
    return pos + 1


def _font_slots_end_offset(fp_cfg: dict[str, Any]) -> int:
    """File offset just past last font_slot (avoid Sym overwrite)."""
    end = 0
    for slot in fp_cfg.get("font_slots") or []:
        addr = slot.get("addr")
        if addr is None:
            continue
        a = int(addr)
        if a >= _POINTER_OFFSET:
            a -= _POINTER_OFFSET
        size = int(
            slot.get("slot_size")
            or int(slot.get("glyph_count") or 0)
            * int(slot.get("bytes_per_glyph") or 128)
        )
        if size > 0:
            end = max(end, a + size)
    return end


def _axvj_pad_relocated(encoded: bytes) -> bytes:
    """Pad relocated strings for the title-menu 26-byte blind copy."""
    body = encoded
    while body and body[-1] in (0xFA, 0xFF):
        body = body[:-1]
    return body + bytes([0xFF]) + bytes([0xFF] * 25)


def _prepare_zh_text(text: str, line_width: int = 20) -> str:
    from .text_wrap import wrap_text
    t = (
        text.replace("{\\n}", "\n")
        .replace("{\\p}", "\n\n")
        .replace("{\\l}", "\\l")
    )
    t = re.sub(r"(?<![\\])\{([^\\}]+)\}", r"\1", t)
    t = t.replace("\x00LSCROLL\x00", "\\l").replace("LSCROLL", "")
    t = t.replace("\\p", "\n\n").replace("\\n", "\n")
    return wrap_text(t, line_width=line_width, target_lang="zh-Hans")
