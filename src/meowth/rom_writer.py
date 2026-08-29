"""ROM writer for injecting translated text."""

import json
import struct
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
                 word_count_default: int | None = None,
                 word_count_modules: dict[str, int] | None = None):
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
        from .config_loader import DEFAULT_WORD_COUNT
        self._word_count_default = word_count_default or DEFAULT_WORD_COUNT
        self._word_count_modules = word_count_modules or {}

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

    def _axvj_pointer_sites(self, rom: bytearray, old_pointer: int) -> list[int]:
        """全 ROM 中值==old_pointer 的位置 = 对旧文本的全部引用。

        2026-08-29 去掉旧的 S5 指针安全过滤（policy.ptr_source_ok 按
        对齐/区域黑白名单静默丢弃指针源——脚本字节码里的奇地址内嵌指针
        全被丢，重定位只补了 1/6，消息仍读日文原文，见 .workbuddy 记忆）。
        重定位语义本来就应该是：值==旧地址的位置一律改指新址。
        rom.find 为 C 级实现，每条一次全 ROM 扫描开销可接受。"""
        needle = old_pointer.to_bytes(4, "little")
        out: list[int] = []
        pos = self.MIN_POINTER_SOURCE
        while True:
            pos = rom.find(needle, pos)
            if pos < 0:
                break
            out.append(pos)
            pos += 1
        return out

    def _axvj_text_target_ok(self, rom: bytearray, address: int, entry: dict) -> bool:
        """注入安全门（已被 rejects/allows 取代）。

        旧逻辑（should_skip_zh_inject / text_target_ok / 阈值评分）已统一由
        translate 阶段 ``rejects``/``allows`` 判定：被拒条目带 ``_reject``，
        不会被收集进 all_entries。此处恒 True。
        """
        return True

    def _axvj_prepare_zh_text(
        self, text: str, word_count: int | None = None, module_id: str | None = None
    ) -> str:
        """Normalize LLM artifacts and re-wrap for narrow AXVJ boxes."""
        import re
        from .config_loader import module_wrap_kwargs
        from .text_wrap import wrap_text

        t = (
            text.replace("{\\n}", "\n")
            .replace("{\\p}", "\n\n")
            .replace("{\\l}", "\\l")
        )
        t = re.sub(r"(?<![\\])\{([^\\}]+)\}", r"\1", t)
        t = t.replace("\x00LSCROLL\x00", "\\l").replace("LSCROLL", "")
        t = t.replace("\\p", "\n\n").replace("\\n", "\n")
        kwargs = module_wrap_kwargs(self.game, module_id)
        if word_count is not None:
            kwargs["word_count"] = word_count
        return wrap_text(t, target_lang=self.target_lang, **kwargs)

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
        *, expected_target: int | None = None,
    ) -> None:
        """写入扩展区并把全 ROM 引用统一改指新址（raises on failure）。

        旧地址来源：expected_target（ARMIPS 主路径）或 pointer_sources 首址
        处的现值（非 ARMIPS 兼容路径）。指针源列表仅作回退，实际补丁点由
        _axvj_pointer_sites 全 ROM 发现（不再做任何静默过滤）。"""
        encoded = self._axvj_pad_relocated(encoded)
        if self.write_offset + len(encoded) >= self.FONT_BOUNDARY:
            raise RuntimeError(f"Approaching font boundary at 0x{self.write_offset:X}")
        need = self.write_offset + len(encoded)
        if need > len(rom):
            rom.extend(b"\x00" * (need - len(rom) + 0x1000))

        if expected_target is not None:
            old_pointer = self._axvj_expected_pointer(expected_target)
        elif pointer_sources:
            first = self._to_rom_offset(
                int(str(pointer_sources[0]).replace("0x", ""), 16)
            )
            if first + 4 > len(rom):
                raise RuntimeError(f"pointer source out of range: {pointer_sources[0]}")
            old_pointer = int.from_bytes(rom[first : first + 4], "little")
        else:
            old_pointer = None

        if old_pointer is None:
            raise RuntimeError(f"relocate without pointer info: {pointer_sources}")

        # 先扫描后写文本:新写的字形流里不应被本条扫描覆盖
        ptr_addrs = self._axvj_pointer_sites(rom, old_pointer)
        if not ptr_addrs and self._is_armips:
            raise RuntimeError(
                f"no pointer sites for 0x{old_pointer:X}: {pointer_sources}"
            )

        rom[self.write_offset : self.write_offset + len(encoded)] = encoded
        new_pointer = self.POINTER_OFFSET + self.write_offset

        for ptr_addr in ptr_addrs:
            rom[ptr_addr : ptr_addr + 4] = new_pointer.to_bytes(4, "little")
        self.write_offset += len(encoded)

    def _write_in_place_v2(
        self, rom: bytearray, address: int, encoded: bytes, max_length: int
    ) -> None:
        """Write text in place: fill slot with FF, then write encoded (≤ max_length)."""
        if max_length <= 0:
            raise RuntimeError(f"in-place max_length={max_length} @ 0x{address:X}")
        if address + max_length > len(rom):
            raise RuntimeError(f"Address 0x{address:X} + {max_length} exceeds ROM")

        body = bytes(encoded)
        if not body.endswith(b"\xFF"):
            body += b"\xFF"
        if len(body) > max_length:
            body = body[: max_length - 1] + b"\xFF"
        # 整槽先 FF，再写入，杜绝尾部残留原文假名
        rom[address : address + max_length] = b"\xFF" * max_length
        rom[address : address + len(body)] = body

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
    def align_rom(rom: bytearray, min_size: int = 0x02000000) -> bytearray:
        """Pad ROM up to a power-of-two size (default floor 32MB) with 0xFF.

        Flash carts (EZ Flash Omega etc.) size the ROM window by power of two
        and need trailing free space to inject their own patch code. The armips
        path (``expands_rom: true``) skips the up-front :meth:`expand_rom`, so
        the result stops at the last written byte — not a power of two, and with
        zero trailing free space. The cart then mis-sizes the save area and can
        clobber live data when it injects its patch.

        Call this immediately before saving. Never call it before armips:
        0xFF padding breaks armips free-space detection.

        Note: padding is applied **in place** and the same object is returned
        (same contract as :meth:`expand_rom`). Callers that need to know whether
        anything changed must capture ``len(rom)`` *before* calling — comparing
        the return value against the argument afterwards is always false.
        """
        size = max(len(rom), min_size)
        aligned = 1 << max((size - 1).bit_length(), 9)  # floor 512 (SD sector)
        if len(rom) < aligned:
            rom.extend(b"\xFF" * (aligned - len(rom)))
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

        注入前按 id 去重；同一 id 只处理一次。in_place 若会覆盖
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
            # ARMIPS 已先把 ROM 扩到 32MB 并写好 game.bin/字库/hook 池(0x09E00000)。
            # 此刻若用 _find_free_space(..., fill=0x00) 往回扫，会把 hook 池之后
            # 的 0x00 填充当成空闲区 → relocate 正文从 0x09E00000 起写，与 hook
            # 池紧邻/挤到 ROM 末尾，遇敌战斗访问 ROM 高区时数据被破坏 → PC 跑飞
            # (0x04002FE8)。故必须固定从 floor (= expansion_start, 字库 Sym 之后、
            # hook 池之前的安全空隙) 开始，不再"猜"空闲。
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
            "replace": 0, "relocated": 0, "errors": 0,
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
            # Only modules that actually widened — relocate:false stays in main loop
            for patch_key in table_stats:
                tbl = tables_cfg.get(patch_key) if isinstance(tables_cfg, dict) else None
                if isinstance(tbl, dict):
                    expanded_modules.add(tbl.get("module") or patch_key)
                expanded_modules.add(patch_key)

        self._axvj_lz_spans = lz_spans
        from .policy import collect_entry_text_spans

        self._inject_text_spans = collect_entry_text_spans(entries)
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
        """收集 relocate 计划的 pointer_sources（ROM 文件偏移），供 in_place 避让。

        丢弃落在语料正文区间内的站点（PCS 巧合假指针）。
        """
        from .policy import ptr_site_in_text_body

        text_spans = getattr(self, "_inject_text_spans", None)
        slots: set[int] = set()
        for e in entries:
            plan = e.get("_plan")
            ptrs: list = []
            if plan and (plan.get("type") or "") == "relocate":
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
                if off < 0:
                    continue
                if ptr_site_in_text_body(off, text_spans):
                    continue
                slots.add(off)
        return slots

    def _body_covers_pointer_slot(
        self, address: int, write_length: int, *, entry_id: str = ""
    ) -> list[int]:
        """若 [address, address+write_length) 覆盖任一 relocate 指针槽，返回命中槽列表。

        ``write_length`` 应为实际写入字节数（不要用整槽 byte_length 虚高误判）。
        """
        slots = getattr(self, "_inject_ptr_slots", None) or set()
        if not slots or write_length <= 0:
            return []
        end = address + write_length
        hits = sorted(p for p in slots if address <= p < end)
        return hits

    def _process_planned_entry(
        self, rom: bytearray, entry: dict, plan: dict, stats: dict
    ) -> None:
        """按 translate.build.json 的 type 注入（翻译通路）。

        in_place     → target_hex 写入原地址（含 F900 整串或 F9 80 短语引用）
        upgrade/f980 → 旧 build 别名，按 in_place 处理
        relocate     → target_hex 写入扩展区并改写 plan.pointer_sources（不再校验/回退）
        keep         → 保留原文，日志打印
        """
        entry_id = entry.get("id", "?")
        ptype = plan.get("type") or "keep"
        if ptype in ("f980", "upgrade"):
            ptype = "replace"
        category = plan.get("module") or entry.get("module") or ""
        original = entry.get("original", "")

        try:
            target = bytes.fromhex((plan.get("target_hex") or "").replace(" ", ""))
        except ValueError:
            target = b""

        address = int(
            (plan.get("address") or entry.get("address") or "0x0").replace("0x", ""),
            16,
        )
        if address >= self.POINTER_OFFSET:
            address -= self.POINTER_OFFSET
        byte_length = int(
            plan.get("byte_length")
            if plan.get("byte_length") is not None
            else (entry.get("byte_length", 0) or 0)
        )

        if ptype == "slot":
            # translated_slot.asm 由 armips 写入查找表；PrintNextChar 运行时拦截
            stats["slot_skipped"] = stats.get("slot_skipped", 0) + 1
            return

        if ptype == "replace":
            # translate.build.json 已编排好；此处只按 target_hex 直写。
            # 指针槽避让已在 plan finalize；若仍撞上，属 build.json 过期，记 keep。
            write_len = min(len(target), byte_length) if target else 0
            clobber = self._body_covers_pointer_slot(
                address, write_len, entry_id=str(entry_id)
            )
            if clobber:
                print(
                    f"  KEEP {entry_id} @ 0x{address:X} (cat={category}): "
                    f"保留原文（in_place 会覆盖 relocate 指针槽 "
                    f"{', '.join(f'0x{p:X}' for p in clobber[:4])}"
                    f"{'…' if len(clobber) > 4 else ''}；请重跑 translate）"
                )
                stats["skipped_ptr_clobber"] = stats.get("skipped_ptr_clobber", 0) + 1
                stats["kept"] = stats.get("kept", 0) + 1
                return
            if len(target) <= byte_length:
                self._write_in_place_v2(rom, address, target, byte_length)
                stats["replace"] += 1
            else:
                print(
                    f"  KEEP {entry_id} @ 0x{address:X} (cat={category}): "
                    f"保留原文（in_place {len(target)}B 超槽位 {byte_length}B；"
                    f"build.json 与槽不一致，请重跑 translate）"
                )
                stats["kept"] = stats.get("kept", 0) + 1
            return

        if ptype == "relocate":
            # 指针已在编排期校验并写入 plan.pointer_sources；不再 expand/回退改路径
            ptrs = plan.get("pointer_sources") or []
            if not ptrs:
                print(
                    f"  WARN {entry_id} @ 0x{address:X} (cat={category}): "
                    f"relocate 计划但无 pointer_sources；保留原文（请重跑 translate）"
                )
                stats["kept"] = stats.get("kept", 0) + 1
                return
            try:
                self._write_relocated(
                    rom,
                    target,
                    ptrs,
                    expected_target=None,
                )
                stats["relocated"] += 1
            except RuntimeError as e:
                print(
                    f"  WARN {entry_id} @ 0x{address:X} (cat={category}): "
                    f"relocate failed: {e}; 保留原文（build.json 与 ROM 不一致，请重跑 translate）"
                )
                stats["kept"] = stats.get("kept", 0) + 1
            return

        # keep / 未知类型：保留原文，带具体原因
        reason = plan.get("reason") or (f"类型[{ptype}]无法注入")
        print(
            f"  KEEP {entry_id} @ 0x{address:X} (cat={category}): "
            f"保留原文（{reason}）"
        )
        stats["kept"] = stats.get("kept", 0) + 1

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
            module_id = entry.get("_axvj_module") or entry.get("module")
            wc = self._word_count_modules.get(module_id, self._word_count_default) if module_id else self._word_count_default
            translated = self._axvj_prepare_zh_text(
                translated, word_count=wc, module_id=module_id
            )

        try:
            encoded = self.charmap.encode(translated)
        except Exception as e:
            raise ValueError(f"Entry {entry_id}: encoding failed for '{translated}': {e}") from e

        # F901/F981 直接通道已移除：短语恒 F9 80，不再重写通道字节。

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
                    stats["replace"] += 1
                    return
                print(
                    f"  WARN {entry_id} @ 0x{address:X} (cat={category}): "
                    f"'{translated}' encoded {len(encoded)}B > slot {original_length}B, "
                    f"truncating"
                )
                encoded = _safe_truncate_encoded(encoded, original_length - 1)
                print(f"    -> after truncation: {encoded.hex()}")
            clobber = self._body_covers_pointer_slot(
                address, len(encoded), entry_id=str(entry_id)
            )
            if clobber:
                print(
                    f"  KEEP {entry_id} @ 0x{address:X} (cat={category}): "
                    f"保留原文（in_place 会覆盖 relocate 指针槽）"
                )
                stats["skipped_ptr_clobber"] = stats.get("skipped_ptr_clobber", 0) + 1
                return
            self._write_in_place_v2(rom, address, encoded, original_length)
            stats["replace"] += 1
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
                    stats["replace"] += 1
                    return
                print(
                    f"  WARN {entry_id} @ 0x{address:X} (cat={category}): "
                    f"'{translated}' encoded {len(encoded)}B > slot {original_length}B, "
                    f"truncating"
                )
                encoded = _safe_truncate_encoded(encoded, original_length - 1)
                print(f"    -> after truncation: {encoded.hex()}")
            clobber = self._body_covers_pointer_slot(
                address, len(encoded), entry_id=str(entry_id)
            )
            if clobber:
                print(
                    f"  KEEP {entry_id} @ 0x{address:X} (cat={category}): "
                    f"保留原文（in_place 会覆盖 relocate 指针槽）"
                )
                stats["skipped_ptr_clobber"] = stats.get("skipped_ptr_clobber", 0) + 1
                return
            self._write_in_place_v2(rom, address, encoded, original_length)
            stats["replace"] += 1
        else:
            raise ValueError(
                f"Entry {entry_id}: cannot write "
                f"(address=0x{address:X}, byte_length={original_length})"
            )
