"""ROM writer for injecting translated text."""

import json
from pathlib import Path
from typing import Optional

from .charmap import Charmap


class RomWriter:
    """Writes translated text to GBA ROM with pointer redirection."""

    POINTER_OFFSET = 0x08000000

    _MIN_FREE_BLOCK = 512 * 1024  # 512 KB

    def __init__(self, charmap: Optional[Charmap] = None, game: str = "firered",
                 target_lang: str = "zh-Hans",
                 expansion_start: int | None = None,
                 font_boundary: int | None = None,
                 min_pointer_source: int | None = None,
                 fp_cfg: dict | None = None,
                 line_width_default: int | None = None,
                 line_width_modules: dict[str, int] | None = None):
        self.charmap = charmap or Charmap(target_lang=target_lang)
        self.target_lang = target_lang
        self.game = game
        self._fp = fp_cfg or {}
        self._is_armips = bool(self._fp.get("expands_rom", False))
        # ARMIPS expand path uses 0x00 free space; otherwise 0xFF
        self._fill_byte = self._fp.get(
            "fill_byte", 0x00 if self._is_armips else 0xFF
        )
        self.EXPANSION_START = (
            expansion_start
            if expansion_start is not None
            else int(self._fp.get("expansion_start", 0x01000000))
        )
        self.FONT_BOUNDARY = (
            font_boundary
            if font_boundary is not None
            else int(self._fp.get("font_boundary", 0x01FD3000))
        )
        self.MIN_POINTER_SOURCE = (
            min_pointer_source
            if min_pointer_source is not None
            else int(self._fp.get("min_pointer_source", 0x6000))
        )
        self.write_offset = self.EXPANSION_START  # updated in inject_texts()
        self._line_width_default = line_width_default or 20
        self._line_width_modules = line_width_modules or {}

    def _to_rom_offset(self, addr: int) -> int:
        """Convert GBA pointer (0x08xxxxxx) to ROM file offset if needed."""
        if addr >= self.POINTER_OFFSET:
            return addr - self.POINTER_OFFSET
        return addr

    @staticmethod
    def _find_free_space(rom: bytes, boundary: int, fill: int = 0xFF) -> int:
        """Find the start of the largest contiguous free block before boundary."""
        end = min(boundary, len(rom))
        pos = end - 1
        while pos >= 0 and rom[pos] == fill:
            pos -= 1
        return pos + 1

    def _axvj_expected_pointer(self, text_address: int) -> int:
        """GBA pointer word for a ROM file offset or already-absolute address."""
        if text_address >= self.POINTER_OFFSET:
            return text_address
        return self.POINTER_OFFSET + text_address

    def _filter_axvj_pointer_sources(
        self,
        rom: bytearray,
        pointer_sources: list,
        text_address: int,
        *,
        category: str = "",
        original: str = "",
        lz_spans: list | None = None,
    ) -> list[int]:
        """S5 rewrite gate."""
        from .extract import trusted_lz_spans
        from .policy import filter_pointer_sources

        spans = lz_spans if lz_spans is not None else trusted_lz_spans(rom)
        return filter_pointer_sources(
            rom,
            pointer_sources,
            text_address,
            category=category,
            original=original,
            expected_pointer=self._axvj_expected_pointer(text_address),
            lz_spans=spans,
            min_pointer_source=self.MIN_POINTER_SOURCE,
        )

    def _axvj_text_target_ok(self, rom: bytearray, address: int, entry: dict) -> bool:
        """S2+S3 inject gate."""
        from .extract import trusted_lz_spans
        from .policy import should_skip_zh_inject, text_target_ok

        if should_skip_zh_inject(entry.get("original") or ""):
            return False
        spans = getattr(self, "_axvj_lz_spans", None)
        if spans is None:
            spans = trusted_lz_spans(rom)
            self._axvj_lz_spans = spans
        return text_target_ok(rom, address, entry, lz_spans=spans)

    def _axvj_prepare_zh_text(self, text: str, line_width: int | None = None) -> str:
        """Normalize LLM artifacts and re-wrap for narrow AXVJ boxes."""
        import re
        from .text_wrap import wrap_text

        t = (
            text.replace("{\\n}", "\n")
            .replace("{\\p}", "\n\n")
            .replace("{\\l}", "\\l")
        )
        t = re.sub(r"(?<![\\])\{([^\\}]+)\}", r"\1", t)
        t = t.replace("\x00LSCROLL\x00", "\\l").replace("LSCROLL", "")
        t = t.replace("\\p", "\n\n").replace("\\n", "\n")
        return wrap_text(t, line_width=line_width, target_lang=self.target_lang)

    def _axvj_pad_relocated(self, encoded: bytes) -> bytes:
        """Pad AXVJ relocated strings for the title-menu 26-byte blind copy."""
        if not self._is_armips:
            return encoded
        body = encoded
        while body and body[-1] in (0xFA, 0xFF):
            body = body[:-1]
        return body + bytes([0xFF]) + bytes([0xFF] * 25)

    def _write_relocated(
        self, rom: bytearray, encoded: bytes, pointer_sources: list,
        *, expected_target: int | None = None, category: str = "",
        original: str = "", lz_spans: list | None = None,
    ) -> None:
        """Write text to expansion area and update pointers (raises on failure)."""
        encoded = self._axvj_pad_relocated(encoded)
        if self.write_offset + len(encoded) >= self.FONT_BOUNDARY:
            raise RuntimeError(f"Approaching font boundary at 0x{self.write_offset:X}")
        need = self.write_offset + len(encoded)
        if need > len(rom):
            rom.extend(b"\x00" * (need - len(rom) + 0x1000))

        if self._is_armips and expected_target is not None:
            ptr_addrs = self._filter_axvj_pointer_sources(
                rom,
                pointer_sources,
                expected_target,
                category=category,
                original=original,
                lz_spans=lz_spans,
            )
            if not ptr_addrs:
                raise RuntimeError(
                    f"no verified AXVJ pointer sources for 0x{expected_target:X}: "
                    f"{pointer_sources}"
                )
            rom[self.write_offset : self.write_offset + len(encoded)] = encoded
            new_pointer = self.POINTER_OFFSET + self.write_offset
            for ptr_addr in ptr_addrs:
                rom[ptr_addr : ptr_addr + 4] = new_pointer.to_bytes(4, "little")
            self.write_offset += len(encoded)
            return

        rom[self.write_offset : self.write_offset + len(encoded)] = encoded
        new_pointer = self.POINTER_OFFSET + self.write_offset
        wrote_ptr = False
        for ptr_src in pointer_sources:
            ptr_addr = self._to_rom_offset(int(str(ptr_src).replace("0x", ""), 16))
            if ptr_addr < self.MIN_POINTER_SOURCE:
                continue
            if ptr_addr + 4 <= len(rom):
                rom[ptr_addr : ptr_addr + 4] = new_pointer.to_bytes(4, "little")
                wrote_ptr = True
        if not wrote_ptr:
            raise RuntimeError(f"no valid pointer sources updated: {pointer_sources}")
        self.write_offset += len(encoded)

    def _write_in_place_v2(
        self, rom: bytearray, address: int, encoded: bytes, max_length: int
    ) -> None:
        """Write text in place (raises on error)."""
        if address + max_length > len(rom):
            raise RuntimeError(f"Address 0x{address:X} + {max_length} exceeds ROM")

        orig_text_end = max_length
        for j in range(max_length):
            if rom[address + j] == 0xFF:
                orig_text_end = j + 1
                break

        safe_length = min(max_length, max(orig_text_end, len(encoded)))
        write_len = min(len(encoded), safe_length)
        rom[address : address + write_len] = encoded[:write_len]

        if write_len < orig_text_end:
            rom[address + write_len : address + orig_text_end] = b"\xFF" * (
                orig_text_end - write_len
            )

    # ------------------------------------------------------------------
    # High-level API used by Pipeline.build_rom
    # ------------------------------------------------------------------

    @staticmethod
    def load_rom(path: Path) -> bytearray:
        """Load a ROM file into a mutable bytearray."""
        return bytearray(Path(path).read_bytes())

    @staticmethod
    def expand_rom(rom: bytearray, target_size: int = 0x02000000) -> bytearray:
        """Expand ROM to target size (default 32MB) by padding with 0xFF."""
        if len(rom) < target_size:
            rom.extend(b"\xFF" * (target_size - len(rom)))
        return rom

    @staticmethod
    def save_rom(rom: bytearray, path: Path) -> None:
        """Write ROM bytearray to file."""
        Path(path).write_bytes(rom)

    def inject_texts(
        self,
        rom: bytearray,
        entries: list[dict],
        overrides: Optional[dict[str, str]] = None,
        on_progress=None,
    ) -> tuple[bytearray, dict]:
        """Inject translated entries directly into a ROM bytearray.

        Returns (rom, stats).
        Raises ValueError on any write failure — never silently skips.
        """
        if not isinstance(rom, bytearray):
            rom = bytearray(rom)

        # Auto-detect safe expansion start
        if self._is_armips:
            free_start = self._find_free_space(rom, self.FONT_BOUNDARY, fill=0x00)
            free_start = max(free_start, self.EXPANSION_START)
            if free_start >= self.FONT_BOUNDARY - 0x1000:
                free_start = self.EXPANSION_START
        else:
            free_start = self._find_free_space(rom, self.FONT_BOUNDARY, fill=0xFF)
        available = self.FONT_BOUNDARY - free_start
        if available < self._MIN_FREE_BLOCK:
            print(f"Warning: only {available:,} bytes free before font boundary")
        self.write_offset = free_start
        print(f"Expansion region start: 0x{free_start:08X} ({available:,} bytes available)")

        stats = {
            "in_place": 0, "relocated": 0, "errors": 0,
            "name_tables": {},
        }

        lz_spans = None
        if self._is_armips:
            from .extract import trusted_lz_spans
            lz_spans = trusted_lz_spans(rom)
            self._axvj_lz_spans = lz_spans

        # Expanded name tables (config-driven — processes whatever has chs_stride)
        expanded_modules: set[str] = set()
        if self._is_armips:
            from .table_patch import inject_name_tables
            from .config_loader import load_game_config

            game_cfg = load_game_config(self.game)
            tables_cfg = game_cfg.get("tables", {})
            self.write_offset, table_stats = inject_name_tables(
                rom,
                entries,
                charmap=self.charmap,
                write_offset=self.write_offset,
                tables_cfg=tables_cfg,
            )
            stats["name_tables"] = table_stats
            # Modules handled by table_patch — skip them from main pointer loop
            for patch_key, tbl in tables_cfg.items():
                if isinstance(tbl, dict) and tbl.get("chs_stride"):
                    expanded_modules.add(tbl.get("module") or patch_key)
                    # legacy english table key as well
                    expanded_modules.add(patch_key)

        self._axvj_lz_spans = lz_spans
        baseline = bytes(rom) if self._is_armips else b""
        total = len(entries)

        for i, entry in enumerate(entries):
            try:
                if overrides and entry.get("id") in overrides:
                    entry["translated"] = overrides[entry["id"]]
                em = entry.get("module") or entry.get("_axvj_module") or entry.get("category") or ""
                if em in expanded_modules:
                    continue
                self._process_entry_v2(rom, entry, stats)
            except Exception as e:
                print(f"Error processing {entry.get('id', '?')}: {e}")
                stats["errors"] += 1
            if on_progress and (i % 200 == 0 or i + 1 == total):
                on_progress(i + 1, total)

        if self._is_armips and baseline:
            from .extract import restore_false_gfx_pointers

            n_rest = restore_false_gfx_pointers(
                rom, baseline, lz_spans=lz_spans
            )
            stats["gfx_ptrs_restored"] = n_rest
            if n_rest:
                print(f"Restored {n_rest} false gfx/LZ pointer rewrites")

        return rom, stats

    def _process_entry_v2(self, rom: bytearray, entry: dict, stats: dict) -> None:
        """Process a single entry. Raises ValueError on any write failure."""
        original = entry.get("original", "").strip('"')
        translated = entry.get("translated", "").strip('"')

        address = int(entry.get("address", "0x0").replace("0x", ""), 16)
        if address >= self.POINTER_OFFSET:
            address -= self.POINTER_OFFSET
        pointer_sources = entry.get("pointer_addresses", entry.get("pointer_sources", []))

        entry_id = entry.get("id", "?")

        if not translated:
            raise ValueError(f"Entry {entry_id}: no translated text")
        if translated == original:
            raise ValueError(f"Entry {entry_id}: translated == original '{original}'")

        if self._is_armips and self.target_lang.startswith("zh"):
            module_id = entry.get("_axvj_module")
            lw = self._line_width_modules.get(module_id, self._line_width_default) if module_id else self._line_width_default
            translated = self._axvj_prepare_zh_text(translated, line_width=lw)

        try:
            encoded = self.charmap.encode(translated)
        except Exception as e:
            raise ValueError(f"Entry {entry_id}: encoding failed for '{translated}': {e}") from e

        # write.type=op → phrase channel byte is the op (F9 <op> hi lo).
        # Only rewrite default phrase channel (F9 7F); F9 00 side glyph stays.
        if self._is_armips and self.target_lang.startswith("zh") and len(encoded) >= 4:
            from .config_loader import F9_PHRASE_DEFAULT, module_write_op

            mid = entry.get("_axvj_module") or entry.get("module")
            code = module_write_op(self.game, mid)
            if (
                code is not None
                and encoded[0] == 0xF9
                and encoded[1] == F9_PHRASE_DEFAULT
            ):
                encoded = bytes([0xF9, code & 0xFF]) + encoded[2:]

        is_pointer_based = entry.get("is_pointer_based", bool(pointer_sources))
        original_length = entry.get("byte_length", 0)
        category = (
            entry.get("module")
            or entry.get("_axvj_module")
            or entry.get("category")
            or ""
        )

        if self._is_armips:
            if not self._axvj_text_target_ok(rom, address, entry):
                raise ValueError(
                    f"Entry {entry_id} @ 0x{address:X} (cat={category}): "
                    f"text_target_ok rejected (LZ band / unsafe address)"
                )
            if is_pointer_based and pointer_sources:
                try:
                    self._write_relocated(
                        rom, encoded, pointer_sources,
                        expected_target=address,
                        category=category,
                        original=original,
                        lz_spans=getattr(self, "_axvj_lz_spans", None),
                    )
                    stats["relocated"] += 1
                    return
                except RuntimeError as e:
                    # Pointer in LZ/gfx-deny region (policy refuses relocate):
                    # fall back to in-place so the text still lands instead of skip.
                    print(
                        f"  WARN {entry_id} @ 0x{address:X} (cat={category}): "
                        f"relocate rejected ({e}); trying in-place"
                    )

            # No verified pointers: in-place if it fits; never blanket search
            if address <= 0:
                raise ValueError(
                    f"Entry {entry_id}: invalid address 0x{address:X} for in-place write"
                )
            if original_length <= 0:
                raise ValueError(
                    f"Entry {entry_id} @ 0x{address:X}: "
                    f"byte_length={original_length} invalid for in-place write"
                )
            if len(encoded) > original_length:
                # Slot too small even for a 5-byte F9 80 reference (<5B): keep the
                # original text rather than truncting into a broken F9 sequence.
                if original_length < 5:
                    print(
                        f"  SKIP {entry_id} @ 0x{address:X} (cat={category}): "
                        f"slot {original_length}B < 5, auto-F9-80 cannot fit; keeping original"
                    )
                    stats["in_place"] += 1
                    return
                print(
                    f"  WARN {entry_id} @ 0x{address:X} (cat={category}): "
                    f"'{translated}' encoded {len(encoded)}B > slot {original_length}B, "
                    f"truncating"
                )
                encoded = encoded[: original_length - 1] + b"\xFF"
                print(f"    -> after truncation: {encoded.hex()}")
            self._write_in_place_v2(rom, address, encoded, original_length)
            stats["in_place"] += 1
            return

        # Non-ARMIPS path
        if is_pointer_based and pointer_sources:
            self._write_relocated(rom, encoded, pointer_sources)
            stats["relocated"] += 1
        elif address > 0 and original_length > 0:
            if len(encoded) > original_length:
                if original_length < 5:
                    print(
                        f"  WRITE {entry_id} @ 0x{address:X} (cat={category}): "
                        f"slot {original_length}B < 5, keeping original"
                    )
                    stats["in_place"] += 1
                    return
                print(
                    f"  WARN {entry_id} @ 0x{address:X} (cat={category}): "
                    f"'{translated}' encoded {len(encoded)}B > slot {original_length}B, "
                    f"truncating"
                )
                encoded = encoded[: original_length - 1] + b"\xFF"
                print(f"    -> after truncation: {encoded.hex()}")
            self._write_in_place_v2(rom, address, encoded, original_length)
            stats["in_place"] += 1
        else:
            raise ValueError(
                f"Entry {entry_id}: cannot write "
                f"(address=0x{address:X}, byte_length={original_length})"
            )
