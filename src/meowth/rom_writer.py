"""ROM writer for injecting translated text."""

import json
from pathlib import Path
from typing import Optional

from .charmap import Charmap
from .config_loader import parse_int_addr


def _safe_truncate_encoded(encoded: bytes, maxlen: int) -> bytes:
    """Truncate an encoded stream at whole-unit boundaries.

    A CJK/phrase reference is a 4-byte F9 XX hi lo group. Cutting the raw
    stream mid-group leaves a dangling F9 whose following byte (often the
    slot terminator 0xFF) is then read as a bogus phrase code, making
    PrintNextChar redirect the PhraseTable offsets out of bounds (花屏/红字).
    """
    out = bytearray()
    i = 0
    n = len(encoded)
    while i < n:
        if encoded[i] == 0xF9:
            if i + 3 < n and len(out) + 4 <= maxlen:
                out += encoded[i:i + 4]
                i += 4
            else:
                break
            continue
        if len(out) + 1 <= maxlen:
            out.append(encoded[i])
            i += 1
        else:
            break
    return bytes(out) + b"\xFF"


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
            else parse_int_addr(self._fp.get("expansion_start"), 0x01000000)
        )
        self.FONT_BOUNDARY = (
            font_boundary
            if font_boundary is not None
            else parse_int_addr(self._fp.get("font_boundary"), 0x01FD3000)
        )
        self.MIN_POINTER_SOURCE = (
            min_pointer_source
            if min_pointer_source is not None
            else parse_int_addr(self._fp.get("min_pointer_source"), 0x0)
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

    def _font_slots_end_offset(self) -> int:
        """ROM file offset just past the last font_slot (Normal/Small/Sym).

        Prevents relocate from treating trailing 0x00 inside/after sparse glyph
        bins as free space and overwriting FontChsSym (全局红字).
        """
        end = 0
        for slot in self._fp.get("font_slots") or []:
            addr = slot.get("addr")
            if addr is None:
                continue
            a = parse_int_addr(addr)
            if a >= self.POINTER_OFFSET:
                a -= self.POINTER_OFFSET
            size = int(
                slot.get("slot_size")
                or int(slot.get("glyph_count") or 0)
                * int(slot.get("bytes_per_glyph") or 128)
            )
            if size > 0:
                end = max(end, a + size)
        return end

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
        """注入安全门（已被 rejects/allows 取代）。

        旧逻辑（should_skip_zh_inject / text_target_ok / 阈值评分）已统一由
        translate 阶段 ``rejects``/``allows`` 判定：被拒条目带 ``_reject``，
        不会被收集进 all_entries。此处恒 True。
        """
        return True

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

        注入前按 id 去重；同一 id 只处理一次。in_place/upgrade 若会覆盖
        其它条目的 relocate ``pointer_sources`` 则跳过（防 F9 写入指针槽）。
        """
        if not isinstance(rom, bytearray):
            rom = bytearray(rom)

        from .translate_plan import dedupe_entries_by_id

        entries = dedupe_entries_by_id(entries)

        # Auto-detect safe expansion start (never below config / font_slots end)
        font_end = self._font_slots_end_offset()
        floor = max(self.EXPANSION_START, font_end)
        if self._is_armips:
            free_start = self._find_free_space(rom, self.FONT_BOUNDARY, fill=0x00)
            free_start = max(free_start, floor)
            if free_start >= self.FONT_BOUNDARY - 0x1000:
                free_start = floor
        else:
            free_start = max(
                self._find_free_space(rom, self.FONT_BOUNDARY, fill=0xFF),
                floor,
            )
        available = self.FONT_BOUNDARY - free_start
        if available < self._MIN_FREE_BLOCK:
            print(f"Warning: only {available:,} bytes free before font boundary")
        self.write_offset = free_start
        print(
            f"Expansion region start: 0x{free_start:08X} "
            f"(floor=0x{floor:08X}, available={available:,})"
        )

        stats = {
            "in_place": 0, "relocated": 0, "errors": 0,
            "name_tables": {},
            "skipped_dup_id": 0,
            "skipped_ptr_clobber": 0,
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
        self._inject_ptr_slots = self._collect_relocate_pointer_slots(entries)
        self._inject_processed_ids: set[str] = set()
        baseline = bytes(rom) if self._is_armips else b""
        total = len(entries)

        for i, entry in enumerate(entries):
            try:
                if overrides and entry.get("id") in overrides:
                    entry["translated"] = overrides[entry["id"]]
                em = entry.get("module") or entry.get("_axvj_module") or entry.get("category") or ""
                if em in expanded_modules:
                    continue
                eid = str(entry.get("id") or "")
                if eid and eid in self._inject_processed_ids:
                    stats["skipped_dup_id"] += 1
                    continue
                if eid:
                    self._inject_processed_ids.add(eid)
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

        if stats.get("skipped_dup_id") or stats.get("skipped_ptr_clobber"):
            print(
                f"Inject guards: skipped_dup_id={stats.get('skipped_dup_id', 0)} "
                f"skipped_ptr_clobber={stats.get('skipped_ptr_clobber', 0)}"
            )

        return rom, stats

    def _collect_relocate_pointer_slots(self, entries: list[dict]) -> set[int]:
        """收集 relocate/hook 计划的 pointer_sources（ROM 文件偏移），供 in_place 避让。"""
        slots: set[int] = set()
        for e in entries:
            plan = e.get("_plan")
            ptrs: list = []
            if plan and (plan.get("type") or "") in ("relocate", "hook"):
                ptrs = (
                    plan.get("pointer_sources")
                    or e.get("pointer_addresses")
                    or e.get("pointer_sources")
                    or []
                )
            elif not plan:
                # 无 plan 的旧路径：有指针且会走 relocate 候选
                ptrs = e.get("pointer_addresses", e.get("pointer_sources", [])) or []
            for p in ptrs:
                try:
                    off = self._to_rom_offset(int(str(p).replace("0x", ""), 16))
                except (TypeError, ValueError):
                    continue
                if off >= 0:
                    slots.add(off)
        return slots

    def _body_covers_pointer_slot(
        self, address: int, byte_length: int, *, entry_id: str = ""
    ) -> list[int]:
        """若 [address, address+byte_length) 覆盖任一 relocate 指针槽，返回命中槽列表。"""
        slots = getattr(self, "_inject_ptr_slots", None) or set()
        if not slots or byte_length <= 0:
            return []
        end = address + byte_length
        hits = sorted(p for p in slots if address <= p < end)
        return hits

    def _process_planned_entry(
        self, rom: bytearray, entry: dict, plan: dict, stats: dict
    ) -> None:
        """按 translate.build.json 的 type 注入（翻译通路）。

        f980/upgrade → F9 80 短语引用写入原槽位（槽位不足则保留原文）
        in_place     → target_hex 写入原地址
        relocate     → target_hex 写入扩展区并改写指针（弱化指针验证）
        hook         → 跳过（armips pointer_redirect.asm 已写）
        keep         → 保留原文，日志打印
        """
        entry_id = entry.get("id", "?")
        ptype = plan.get("type") or "keep"
        category = plan.get("module") or entry.get("module") or ""
        original = entry.get("original", "")

        try:
            target = bytes.fromhex((plan.get("target_hex") or "").replace(" ", ""))
        except ValueError:
            target = b""

        address = int(entry.get("address", "0x0").replace("0x", ""), 16)
        if address >= self.POINTER_OFFSET:
            address -= self.POINTER_OFFSET
        byte_length = entry.get("byte_length", 0) or 0

        if ptype == "hook":
            # armips 已通过 pointer_redirect.asm 写扩展区 + 改指针；避免双写
            stats["hook_skipped"] = stats.get("hook_skipped", 0) + 1
            return

        if ptype in ("f980", "upgrade", "in_place"):
            clobber = self._body_covers_pointer_slot(
                address, byte_length, entry_id=str(entry_id)
            )
            if clobber:
                print(
                    f"  KEEP {entry_id} @ 0x{address:X} (cat={category}): "
                    f"保留原文（{ptype} 会覆盖 relocate 指针槽 "
                    f"{', '.join(f'0x{p:X}' for p in clobber[:4])}"
                    f"{'…' if len(clobber) > 4 else ''}）"
                )
                stats["skipped_ptr_clobber"] = stats.get("skipped_ptr_clobber", 0) + 1
                stats["kept"] = stats.get("kept", 0) + 1
                return

        if ptype in ("f980", "upgrade"):
            # F9 80 短语引用（5 字节），写入原槽位；槽位不足则保留原文
            if byte_length >= len(target):
                self._write_in_place_v2(rom, address, target, byte_length)
                stats["in_place"] += 1
            else:
                print(
                    f"  KEEP {entry_id} @ 0x{address:X} (cat={category}): "
                    f"保留原文（F9-80 短语 {len(target)}B 超槽位 {byte_length}B）"
                )
                stats["kept"] = stats.get("kept", 0) + 1
            return

        if ptype == "in_place":
            if len(target) <= byte_length:
                self._write_in_place_v2(rom, address, target, byte_length)
                stats["in_place"] += 1
            else:
                print(
                    f"  KEEP {entry_id} @ 0x{address:X} (cat={category}): "
                    f"保留原文（in_place {len(target)}B 超槽位 {byte_length}B）"
                )
                stats["kept"] = stats.get("kept", 0) + 1
            return

        if ptype == "relocate":
            ptrs = (
                plan.get("pointer_sources")
                or entry.get("pointer_addresses")
                or entry.get("pointer_sources")
                or []
            )
            if ptrs:
                try:
                    # expected_target=None → 走宽松指针改写（弱化 filter）
                    self._write_relocated(
                        rom, target, ptrs, category=category, original=original
                    )
                    stats["relocated"] += 1
                    return
                except RuntimeError as e:
                    # 细化 relocate 失败原因：统计被 MIN_POINTER_SOURCE 跳过的指针
                    skipped = sum(
                        1
                        for p in ptrs
                        if self._to_rom_offset(int(str(p).replace("0x", ""), 16))
                        < self.MIN_POINTER_SOURCE
                    )
                    detail = f"{e}"
                    if skipped:
                        detail += f"（其中 {skipped}/{len(ptrs)} 个指针低于 MIN_POINTER_SOURCE=0x{self.MIN_POINTER_SOURCE:X}）"
                    print(
                        f"  WARN {entry_id} @ 0x{address:X} (cat={category}): "
                        f"relocate failed: {detail}; 保留原文"
                    )
            else:
                print(
                    f"  WARN {entry_id} @ 0x{address:X} (cat={category}): "
                    f"relocate 计划但无指针源; 保留原文"
                )
            # 回退：relocate 失败/无指针 → F9 80 短语原地插入（需 phrase_code）
            if self._try_phrase_fallback(
                rom, address, byte_length, plan, stats, entry_id, category
            ):
                return
            stats["kept"] = stats.get("kept", 0) + 1
            return

        # keep / 未知类型：保留原文，带具体原因
        reason = plan.get("reason") or (f"类型[{ptype}]无法注入")
        print(
            f"  KEEP {entry_id} @ 0x{address:X} (cat={category}): "
            f"保留原文（{reason}）"
        )
        stats["kept"] = stats.get("kept", 0) + 1

    def _try_phrase_fallback(
        self,
        rom: bytearray,
        address: int,
        byte_length: int,
        plan: dict,
        stats: dict,
        entry_id: str,
        category: str,
    ) -> bool:
        """relocate 失败回退：F9 80 短语引用（5 字节）写入原槽位。

        优先级链：F900 原地 → relocate → F9 80 原地 → keep。
        仅当 plan 已预分配 phrase_code 且槽位 ≥ 5 字节才成功。
        """
        code = plan.get("phrase_code")
        if code is None:
            return False
        from .config_loader import F9_EOS, F9_PHRASE_DEFAULT

        target = bytes([0xF9, F9_PHRASE_DEFAULT, (int(code) >> 8) & 0xFF, int(code) & 0xFF, F9_EOS])
        if byte_length < len(target):
            return False
        clobber = self._body_covers_pointer_slot(address, byte_length, entry_id=entry_id)
        if clobber:
            print(
                f"  KEEP {entry_id} @ 0x{address:X} (cat={category}): "
                f"保留原文（F9-80 回退会覆盖指针槽）"
            )
            stats["skipped_ptr_clobber"] = stats.get("skipped_ptr_clobber", 0) + 1
            return False
        self._write_in_place_v2(rom, address, target, byte_length)
        stats["in_place"] = stats.get("in_place", 0) + 1
        print(
            f"  回退 F9-80 @ 0x{address:X} (cat={category}): {entry_id} "
            f"(relocate 失败/无指针，短语 {len(target)}B 原地)"
        )
        return True

    def _process_entry_v2(self, rom: bytearray, entry: dict, stats: dict) -> None:
        """Process a single entry. Raises ValueError on any write failure."""
        plan = entry.get("_plan")
        if plan:
            self._process_planned_entry(rom, entry, plan, stats)
            return

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
        # Only rewrite default phrase channel (F9 80); F9 00 side glyph stays.
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
                encoded = _safe_truncate_encoded(encoded, original_length - 1)
                print(f"    -> after truncation: {encoded.hex()}")
            clobber = self._body_covers_pointer_slot(
                address, original_length, entry_id=str(entry_id)
            )
            if clobber:
                print(
                    f"  KEEP {entry_id} @ 0x{address:X} (cat={category}): "
                    f"保留原文（in_place 会覆盖 relocate 指针槽）"
                )
                stats["skipped_ptr_clobber"] = stats.get("skipped_ptr_clobber", 0) + 1
                return
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
                encoded = _safe_truncate_encoded(encoded, original_length - 1)
                print(f"    -> after truncation: {encoded.hex()}")
            clobber = self._body_covers_pointer_slot(
                address, original_length, entry_id=str(entry_id)
            )
            if clobber:
                print(
                    f"  KEEP {entry_id} @ 0x{address:X} (cat={category}): "
                    f"保留原文（in_place 会覆盖 relocate 指针槽）"
                )
                stats["skipped_ptr_clobber"] = stats.get("skipped_ptr_clobber", 0) + 1
                return
            self._write_in_place_v2(rom, address, encoded, original_length)
            stats["in_place"] += 1
        else:
            raise ValueError(
                f"Entry {entry_id}: cannot write "
                f"(address=0x{address:X}, byte_length={original_length})"
            )
