"""Extract and classify AXVJ (Japanese Ruby) text for modular translation.

Inject/extract *policy* (bands, allow/deny, rewrite gates) lives in
``policy``. This module owns LZ scanning and extract walkers.
"""
from __future__ import annotations

import json
import re
import struct
from pathlib import Path

from .modules import DEFAULT_MODULES
from .config_loader import get_active_game_id
from .policy import (
    BASE as _BASE_fn,
    BIRCH_PTR_ALLOW as _EARLY_SCRIPT_PTR_ALLOWLIST,
    GFX_PTR_SOURCE_DENY as _GFX_PTR_SOURCE_DENY_fn,
    GFX_STRING_TARGET_DENY as _GFX_STRING_TARGET_DENY_fn,
    IME_RANGE as _IME_RANGE_fn,
    OPTION_MENU_BAND as _OPTION_MENU_BAND_fn,
    SCRIPT_BANK_MIN as SCRIPT_BANK_MIN_fn,
    TITLE_LZ_BAND as _TITLE_LZ_BAND_fn,
    TRAINER_UI_PTR_ALLOW as _TRAINER_UI_PTR_ALLOW,
    TRUSTED_LZ_BANDS as _TRUSTED_LZ_BANDS_fn,
    UI_RANGE as _UI_RANGE_fn,
    in_ranges as _in_ranges,
    is_garbage_jp as _is_garbage_jp,
    is_ime_gojuon_row as _is_ime_gojuon_row,
    is_loadword_text_ptr as _is_loadword_text_ptr,
    is_struct_like_pcs as _is_struct_like_pcs,
    looks_like_translatable as _looks_like_translatable,
    ptr_in_known_ui_band as _ptr_in_known_ui_band,
    ptr_source_ok as _axvj_ptr_source_ok,
    should_keep_relocated_local_pool,
    should_skip_zh_inject,
    string_in_ui_text_bank as _string_in_ui_text_bank,
    string_target_ok as _string_target_ok,
    ptr_site_in_danger,
)
from .tables import (
    extract_ability_names,
    extract_item_descriptions,
    extract_item_names,
    extract_move_names,
    extract_nature_names,
    extract_species_names,
    extract_type_names,
)
from .jp_pcs import decode_pcs, looks_like_jp_text

BASE = _BASE_fn()
GFX_PTR_SOURCE_DENY = _GFX_PTR_SOURCE_DENY_fn()
GFX_STRING_TARGET_DENY = _GFX_STRING_TARGET_DENY_fn()
IME_RANGE = _IME_RANGE_fn()
OPTION_MENU_BAND = _OPTION_MENU_BAND_fn()
SCRIPT_BANK_MIN = SCRIPT_BANK_MIN_fn()
TITLE_LZ_BAND = _TITLE_LZ_BAND_fn()
TRUSTED_LZ_BANDS = _TRUSTED_LZ_BANDS_fn()
UI_RANGE = _UI_RANGE_fn()

_RE_SORT_LABEL = re.compile(r"(ごじゅうおん|アイウエオ|じゅん|おとこ|おんな)")


def read_pcs(rom: bytes, off: int, maxlen: int = 256) -> bytes | None:
    if off < 0 or off >= len(rom):
        return None
    end = rom.find(b"\xFF", off, min(len(rom), off + maxlen))
    if end < 0:
        return None
    return rom[off : end + 1]


def _ptrs_to(rom: bytes, addr: int, limit: int = 16) -> list[int]:
    needle = struct.pack("<I", BASE + addr)
    out: list[int] = []
    pos = 0
    size = min(len(rom), 0x800000)
    while len(out) < limit:
        i = rom.find(needle, pos, size)
        if i < 0:
            break
        out.append(i)
        pos = i + 1
    return out


def _classify_ui(addr: int, text: str) -> str:
    """IME gojuon → ime module; chrome/buttons → ui module (from config)."""
    from .extract_pipeline import module_defaults

    md = module_defaults()
    if _is_ime_gojuon_row(text):
        return md["ime"] or md["ui"]
    if UI_RANGE[0] <= addr < UI_RANGE[1] or IME_RANGE[0] <= addr < IME_RANGE[1]:
        return md["ui"]
    return md["unclassified"]


def extract_ui_block(rom: bytes) -> list[dict]:
    entries: list[dict] = []
    start, end = UI_RANGE
    a = start
    while a < end:
        if rom[a] == 0xFF:
            a += 1
            continue
        if a > 0 and 0x01 <= rom[a - 1] < 0xFA and rom[a - 1] != 0x00:
            a += 1
            continue
        eos = rom.find(b"\xFF", a, a + 40)
        if eos < 0:
            a += 1
            continue
        body = rom[a:eos]
        # Gender labels like おとこ are only 3 PCS bytes.
        if not (3 <= len(body) <= 36):
            a += 1
            continue
        if any(b >= 0xFA for b in body):
            a += 1
            continue
        text = decode_pcs(rom[a : eos + 1])
        if "<" in text:
            a = eos + 1
            continue
        ptrs = _ptrs_to(rom, a, 8)
        if not ptrs:
            a = eos + 1
            continue
        cat = _classify_ui(a, text)
        entries.append(
            {
                "id": f"axvj_{BASE + a:08X}",
                "address": f"0x{BASE + a:08X}",
                "pointer_sources": [f"0x{BASE + p:08X}" for p in ptrs],
                "pointer_addresses": [f"0x{BASE + p:08X}" for p in ptrs],
                "is_pointer_based": True,
                "byte_length": eos - a + 1,
                "original_hex": rom[a : eos + 1].hex(" "),
                "original": text,
                "translated": "",
                "category": cat,
            }
        )
        a = eos + 1
    return entries


def extract_option_menu(rom: bytes) -> list[dict]:
    """Option screen labels/values: ``FC 05 xx`` + JP text + ``FF`` at option band."""
    entries: list[dict] = []
    start, end = OPTION_MENU_BAND
    a = start
    while a < end:
        if rom[a] != 0xFC or a + 4 >= end:
            a += 1
            continue
        # FC 05 09 / FC 05 0F (+ rare FC 05 08)
        if rom[a + 1] != 0x05:
            a += 1
            continue
        prefix_len = 3
        eos = rom.find(b"\xFF", a + prefix_len, a + 28)
        if eos < 0:
            a += 1
            continue
        body = rom[a + prefix_len : eos]
        if not (1 <= len(body) <= 16):
            a = eos + 1
            continue
        if any(b >= 0xFA for b in body):
            a = eos + 1
            continue
        text_body = decode_pcs(rom[a + prefix_len : eos + 1])
        if not text_body or "<" in text_body:
            a = eos + 1
            continue
        cc = f"\\CC05{rom[a + 2]:02X}"
        text = cc + text_body
        ptrs = _ptrs_to(rom, a, 8)
        if not ptrs:
            a = eos + 1
            continue
        from .extract_pipeline import module_defaults

        entries.append(
            {
                "id": f"axvj_{BASE + a:08X}",
                "address": f"0x{BASE + a:08X}",
                "pointer_sources": [f"0x{BASE + p:08X}" for p in ptrs],
                "pointer_addresses": [f"0x{BASE + p:08X}" for p in ptrs],
                "is_pointer_based": True,
                "byte_length": eos - a + 1,
                "original_hex": rom[a : eos + 1].hex(" "),
                "original": text,
                "translated": "",
                "category": module_defaults()["ui"],
            }
        )
        a = eos + 1
    return entries


def _lz10_span(data: bytes | bytearray, start: int) -> tuple[int, int] | None:
    """Return (start, end) for a plausible LZ10 blob, or None."""
    if start + 4 > len(data) or data[start] != 0x10:
        return None
    dec_size = data[start + 1] | (data[start + 2] << 8) | (data[start + 3] << 16)
    if dec_size < 0x100 or dec_size > 0x18000:
        return None
    i = start + 4
    out = 0
    end_lim = min(len(data), start + 4 + dec_size + dec_size // 2 + 256)
    while out < dec_size and i < end_lim:
        flags = data[i]
        i += 1
        for bit in range(8):
            if out >= dec_size or i >= end_lim:
                break
            if flags & (0x80 >> bit):
                if i + 1 >= end_lim:
                    return None
                i += 2
                out += (data[i - 2] >> 4) + 3
            else:
                i += 1
                out += 1
    if out < dec_size:
        return None
    return start, i


def trusted_lz_spans(rom: bytes | bytearray) -> list[tuple[int, int]]:
    """LZ10 spans in high graphics bands only (safe for pointer denylist)."""
    spans: list[tuple[int, int]] = []
    for band_lo, band_hi in TRUSTED_LZ_BANDS:
        off = max(band_lo, 0)
        end = min(band_hi, len(rom) - 8)
        while off < end:
            sp = _lz10_span(rom, off)
            if sp:
                spans.append(sp)
                off = sp[1]
            else:
                off += 1
    return spans


def ptr_in_trusted_lz(ptr_off: int, spans: list[tuple[int, int]]) -> bool:
    """True if ``ptr_off`` lies inside a trusted LZ10 span (binary search)."""
    lo, hi = 0, len(spans)
    while lo < hi:
        mid = (lo + hi) // 2
        s, e = spans[mid]
        if ptr_off < s:
            hi = mid
        elif ptr_off >= e:
            lo = mid + 1
        else:
            return True
    return False


def _string_in_fixed_ui_bank(so: int) -> bool:
    """String lives in a fixed UI extract band (not whole-ROM scan fodder)."""
    from .policy import string_in_option_band

    if _string_in_ui_text_bank(so) or string_in_option_band(so):
        return True
    if SPECIES_LIKE(so) or MOVE_LIKE(so):
        return True
    return False


def extract_script_pointers(
    rom: bytes,
    *,
    min_len: int = 2,
    max_len: int = 512,
    min_ptr_source: int = SCRIPT_BANK_MIN,
    limit: int = 0,
) -> list[dict]:
    """Pointer-scan all translatable JP strings (UI + story).

    Skips IME gojuon rows. ``max_len`` 512 covers long rival intros.
    """
    size = min(len(rom), 0x800000)
    hits: dict[int, list[int]] = {}
    lz_spans = trusted_lz_spans(rom)
    off = 0
    while off < size - 4:
        v = struct.unpack_from("<I", rom, off)[0]
        step = 1 if SCRIPT_BANK_MIN <= off < 0x200000 else 4
        if not (BASE <= v < BASE + size):
            off += step
            continue
        so = v - BASE
        allow = off in _EARLY_SCRIPT_PTR_ALLOWLIST or off in _TRAINER_UI_PTR_ALLOW
        if not _string_target_ok(so, allow=allow, lz_spans=lz_spans):
            off += step
            continue
        if SPECIES_LIKE(so) or MOVE_LIKE(so):
            off += step
            continue
        if UI_RANGE[0] <= so < UI_RANGE[1] and not allow:
            off += step
            continue
        # Reject mid-string hits (pointer into the middle of another line).
        # Real script loadword targets can sit after a raw FD arg byte (e.g.
        # mom truck @ 0x14B9A1 follows 0x03) — never reject those.
        if not allow and so > 0 and not _is_loadword_text_ptr(rom, off):
            prev = rom[so - 1]
            if prev not in (0x00, 0xFF, 0xFE, 0xFA, 0xFB) and prev < 0xF7:
                off += step
                continue
        if not _axvj_ptr_source_ok(rom, off, so, lz_spans=lz_spans):
            off += step
            continue
        s = read_pcs(rom, so, max_len + 1)
        if not s or not looks_like_jp_text(s):
            off += step
            continue
        if _is_struct_like_pcs(s):
            off += step
            continue
        body_len = len(s) - 1
        if not allow and (body_len < min_len or body_len > max_len):
            off += step
            continue
        if body_len > max_len:
            off += step
            continue
        if so <= off < so + len(s):
            off += step
            continue
        text = decode_pcs(s)
        if text.count("<") > 0:
            off += step
            continue
        if not allow and not _looks_like_translatable(text, body_len):
            off += step
            continue
        hits.setdefault(so, []).append(off)
        off += step
    _ = min_ptr_source

    from .extract_pipeline import module_defaults
    from .policy import enrich_default_module, is_enrich_seed_label

    entries: list[dict] = []
    md = module_defaults()
    ui_mod = enrich_default_module("短标菜单") or md["ui"]
    story_mod = md["story"]
    for so, ptrs in sorted(hits.items()):
        s = read_pcs(rom, so, max_len + 1)
        assert s
        if _is_struct_like_pcs(s):
            continue
        use = [p for p in ptrs if _axvj_ptr_source_ok(rom, p, so, lz_spans=lz_spans)]
        if not use:
            continue
        text = decode_pcs(s)
        if _is_ime_gojuon_row(text):
            continue
        body_len = len(s) - 1
        # Policy: include anything that is not false-text; categorize only.
        allow_so = any(p in _EARLY_SCRIPT_PTR_ALLOWLIST for p in use)
        if not allow_so and not _looks_like_translatable(text, body_len):
            continue
        if body_len <= 16 and text.count("\n") == 0 and "\\l" not in text:
            seed_hit = is_enrich_seed_label(text, "短标菜单", "选项菜单")
            ptr_ui = any(_ptr_in_known_ui_band(p, so) for p in use)
            cat = ui_mod if (seed_hit or ptr_ui) else story_mod
        else:
            cat = story_mod
        entries.append(
            {
                "id": f"axvj_{BASE + so:08X}",
                "address": f"0x{BASE + so:08X}",
                "pointer_sources": [f"0x{BASE + p:08X}" for p in use[:16]],
                "pointer_addresses": [f"0x{BASE + p:08X}" for p in use[:16]],
                "is_pointer_based": True,
                "byte_length": len(s),
                "original_hex": s.hex(" "),
                "original": text,
                "translated": "",
                "category": cat,
            }
        )
        if limit and len(entries) >= limit:
            break
    return entries


def extract_fc_prefixed_ui(rom: bytes) -> list[dict]:
    """Starter bag / battle / colored UI: ``FC ..`` + JP text."""
    from .policy import enrich_scan_bands

    bands = enrich_scan_bands("FC彩窗")
    if not bands:
        return []
    entries: list[dict] = []
    lz_spans = trusted_lz_spans(rom)
    for start, end in bands:
        # addr_bands hi is inclusive
        end_ex = min(end + 1, len(rom))
        a = start
        while a < end_ex - 4:
            if rom[a] != 0xFC:
                a += 1
                continue
            eos = rom.find(b"\xFF", a + 2, a + 96)
            if eos < 0:
                a += 1
                continue
            raw = rom[a : eos + 1]
            if len(raw) < 5 or len(raw) > 94:
                a += 1
                continue
            if not looks_like_jp_text(raw):
                a += 1
                continue
            text = decode_pcs(raw)
            if _is_ime_gojuon_row(text) or _is_garbage_jp(text):
                a = eos + 1
                continue
            if not re.search(r"[\u3040-\u30ff]", text):
                a = eos + 1
                continue
            ptrs = [
                p
                for p in _ptrs_to(rom, a, 8)
                if _axvj_ptr_source_ok(rom, p, a, lz_spans=lz_spans)
            ]
            if not ptrs:
                a = eos + 1
                continue
            # Battle / safari fight chrome vs generic colored UI — config rules
            from .policy import module_for_original

            cat = module_for_original(text, enrich_name="FC彩窗")
            entries.append(
                {
                    "id": f"axvj_{BASE + a:08X}",
                    "address": f"0x{BASE + a:08X}",
                    "pointer_sources": [f"0x{BASE + p:08X}" for p in ptrs],
                    "pointer_addresses": [f"0x{BASE + p:08X}" for p in ptrs],
                    "is_pointer_based": True,
                    "byte_length": len(raw),
                    "original_hex": raw.hex(" "),
                    "original": text,
                    "translated": "",
                    "category": cat,
                }
            )
            a = eos + 1
    return entries


def _hud_ptr_ok(rom: bytes, ptr_off: int, string_off: int, lz_spans) -> bool:
    """HUD string tables often sit in low ROM; accept aligned non-gfx ptrs."""
    from .policy import title_gfx_ptr_deny

    if _axvj_ptr_source_ok(rom, ptr_off, string_off, lz_spans=lz_spans):
        return True
    if ptr_off & 3:
        return False
    if ptr_off in title_gfx_ptr_deny():
        return False
    if TITLE_LZ_BAND[0] <= ptr_off < TITLE_LZ_BAND[1]:
        return False
    if _in_ranges(ptr_off, GFX_PTR_SOURCE_DENY):
        return False
    if ptr_in_trusted_lz(ptr_off, lz_spans):
        return False
    return True


def extract_battle_hud_labels(rom: bytes) -> list[dict]:
    """Short battle/status HUD labels (わざ / めいちゅう / …) with pointers.

    Chinese never fits the 3–6 byte JP slots — only emit pointer-backed hits
    so inject can relocate. Bands + needles: ``enrich.战斗HUD``.
    """
    from .jp_pcs import CHAR_TO_BYTE
    from .policy import enrich_scan_bands, enrich_seed_originals

    labels = enrich_seed_originals("战斗HUD")
    bands = enrich_scan_bands("战斗HUD")
    if not labels or not bands:
        return []
    out: list[dict] = []
    seen: set[int] = set()
    lz_spans = trusted_lz_spans(rom)
    find_lo = min(a for a, _ in bands)
    find_hi = min(max(b for _, b in bands) + 1, len(rom))
    for label in labels:
        raw = bytearray()
        ok = True
        for ch in label:
            b = CHAR_TO_BYTE.get(ch)
            if b is None:
                ok = False
                break
            raw.append(b)
        if not ok:
            continue
        raw.append(0xFF)
        needle = bytes(raw)
        start = find_lo
        while True:
            off = rom.find(needle, start, find_hi)
            if off < 0:
                break
            start = off + 1
            if off in seen:
                continue
            ptrs = [
                p
                for p in _ptrs_to(rom, off, 24)
                if _hud_ptr_ok(rom, p, off, lz_spans)
            ]
            if not ptrs:
                continue
            seen.add(off)
            out.append(
                {
                    "id": f"axvj_{BASE + off:08X}",
                    "address": f"0x{BASE + off:08X}",
                    "pointer_sources": [f"0x{BASE + p:08X}" for p in ptrs],
                    "pointer_addresses": [f"0x{BASE + p:08X}" for p in ptrs],
                    "is_pointer_based": True,
                    "byte_length": len(needle),
                    "original_hex": needle.hex(" "),
                    "original": label,
                    "translated": "",
                }
            )
    return out


def extract_summary_ui_pool(rom: bytes) -> list[dict]:
    """Summary / bag chrome via known label needles (pointer-backed).

    Bands + needles: ``enrich.状态背包``.
    """
    from .jp_pcs import CHAR_TO_BYTE
    from .policy import enrich_scan_bands, enrich_seed_originals

    labels = enrich_seed_originals("状态背包")
    bands = enrich_scan_bands("状态背包")
    if not labels or not bands:
        return []
    from .policy import module_for_original

    out: list[dict] = []
    seen: set[int] = set()
    find_lo = min(a for a, _ in bands)
    find_hi = min(max(b for _, b in bands) + 1, len(rom))
    for label in labels:
        raw = bytearray()
        ok = True
        for ch in label:
            b = CHAR_TO_BYTE.get(ch)
            if b is None:
                ok = False
                break
            raw.append(b)
        if not ok:
            continue
        raw.append(0xFF)
        needle = bytes(raw)
        start = find_lo
        while True:
            off = rom.find(needle, start, find_hi)
            if off < 0:
                break
            start = off + 1
            if off in seen:
                continue
            # Summary/bag label pools often sit in gfx-tagged bands — accept
            # any 4-aligned pointer that currently targets the needle.
            ptrs = [p for p in _ptrs_to(rom, off, 16) if (p & 3) == 0]
            if not ptrs:
                continue
            seen.add(off)
            cat = module_for_original(label, enrich_name="状态背包")
            out.append(
                {
                    "id": f"axvj_{BASE + off:08X}",
                    "address": f"0x{BASE + off:08X}",
                    "pointer_sources": [f"0x{BASE + p:08X}" for p in ptrs],
                    "pointer_addresses": [f"0x{BASE + p:08X}" for p in ptrs],
                    "is_pointer_based": True,
                    "byte_length": len(needle),
                    "original_hex": needle.hex(" "),
                    "original": label,
                    "translated": "",
                    "category": cat,
                }
            )
    return out


def extract_battle_prompt_pool(rom: bytes) -> list[dict]:
    """Battle prompt / move-type chrome (``enrich.战斗提示``)."""
    from .policy import (
        enrich_keep_any_contains,
        enrich_scan_bands,
        module_for_original,
        _text_compact,
    )

    bands = enrich_scan_bands("战斗提示")
    if not bands:
        return []
    keep_needles = enrich_keep_any_contains("战斗提示")
    out: list[dict] = []
    seen: set[int] = set()
    lz_spans = trusted_lz_spans(rom)
    start = min(a for a, _ in bands)
    end = min(max(b for _, b in bands) + 1, len(rom))
    a = start
    while a < end:
        if rom[a] == 0xFF:
            a += 1
            continue
        # Prefer FC-prefixed UI blocks
        if rom[a] == 0xFC:
            eos = rom.find(b"\xFF", a + 2, a + 96)
        else:
            if a > start and 0x01 <= rom[a - 1] < 0xFA and rom[a - 1] != 0x00:
                a += 1
                continue
            eos = rom.find(b"\xFF", a, a + 48)
        if eos < 0:
            a += 1
            continue
        raw = rom[a : eos + 1]
        if not (3 <= len(raw) <= 94):
            a += 1
            continue
        if rom[a] != 0xFC and any(b >= 0xFA for b in raw[:-1]):
            a += 1
            continue
        text = decode_pcs(raw)
        if "<" in text or _is_garbage_jp(text):
            a = eos + 1
            continue
        if not re.search(r"[\u3040-\u30ff]", text):
            a = eos + 1
            continue
        if keep_needles:
            compact = _text_compact(text)
            if not any(n in compact or n in text for n in keep_needles):
                a = eos + 1
                continue
        ptrs = [
            p
            for p in _ptrs_to(rom, a, 16)
            if _hud_ptr_ok(rom, p, a, lz_spans)
        ]
        if not ptrs:
            a = eos + 1
            continue
        if a in seen:
            a = eos + 1
            continue
        seen.add(a)
        cat = module_for_original(text, enrich_name="战斗提示")
        out.append(
            {
                "id": f"axvj_{BASE + a:08X}",
                "address": f"0x{BASE + a:08X}",
                "pointer_sources": [f"0x{BASE + p:08X}" for p in ptrs],
                "pointer_addresses": [f"0x{BASE + p:08X}" for p in ptrs],
                "is_pointer_based": True,
                "byte_length": len(raw),
                "original_hex": raw.hex(" "),
                "original": text,
                "translated": "",
                "category": cat,
            }
        )
        a = eos + 1
    return out


def SPECIES_LIKE(so: int) -> bool:
    from .tables import species_names_cfg

    c = species_names_cfg()
    end = c["offset"] + c["count"] * c["stride"]
    return c["offset"] <= so < end


def MOVE_LIKE(so: int) -> bool:
    from .tables import move_names_cfg

    c = move_names_cfg()
    end = c["offset"] + c["count"] * c["stride"]
    return c["offset"] <= so < end


def _looks_like_story(text: str, body_len: int) -> bool:
    """True for dialogue / NPC lines worth translating.

    Slightly relaxed vs early harden: many real lines lack 。！？
    (short town NPCs). Still reject code mojibake / fullwidth-latin spam.
    """
    cleaned = text.replace("\\l", "").replace("\\p", "")
    cleaned = re.sub(r"\\CC[0-9A-Fa-f]+", "", cleaned)
    cleaned = re.sub(r"\\[0-9A-Fa-f]{2}", "", cleaned)
    cleaned = cleaned.replace("\n", "")
    if "<" in cleaned or "[" in cleaned or "\\" in cleaned:
        return False
    if _is_garbage_jp(text):
        return False
    # Misaligned PCS decode spam (very common false positives)
    if text.count("とく") >= 2:
        return False
    if len(re.findall(r"[Ａ-Ｚａ-ｚ]", text)) >= 4:
        return False

    kana = sum(1 for ch in text if "\u3040" <= ch <= "\u30ff")
    has_punct = any(ch in text for ch in "。！？…‥!?")
    has_prompt = "\\l" in text or text.count("\n") >= 1
    has_speaker = "『" in text or "「" in text

    # Classic dialogue shape
    if has_punct or has_prompt or has_speaker:
        return kana >= 3

    # Relaxed NPC lines: kana-heavy, no period (e.g. がんばってね)
    if body_len >= 10 and kana >= 5:
        return True
    if body_len >= 18 and kana >= 4:
        return True
    if kana >= 8:
        return True
    return False


def extract_s1_registry_strings(rom: bytes) -> list[dict]:
    """Pull strings for S1 registry pointer sites (Birch + trainer/naming UI).

    These targets may sit inside gfx geography bands; S1 allow overrides S2 deny.
    """
    from .policy import BIRCH_PTR_ALLOW, TRAINER_UI_PTR_ALLOW

    entries: list[dict] = []
    seen: set[int] = set()
    for ptr_off in sorted(BIRCH_PTR_ALLOW | TRAINER_UI_PTR_ALLOW):
        if ptr_off + 4 > len(rom) or (ptr_off & 3):
            continue
        v = struct.unpack_from("<I", rom, ptr_off)[0]
        if not (BASE <= v < BASE + min(len(rom), 0x800000)):
            continue
        so = v - BASE
        if so in seen:
            # Still attach this pointer to an existing entry shape
            pass
        s = read_pcs(rom, so, 120)
        if not s or not looks_like_jp_text(s):
            continue
        if _is_struct_like_pcs(s):
            continue
        text = decode_pcs(s)
        if _is_ime_gojuon_row(text) or _is_garbage_jp(text):
            continue
        if so in seen:
            continue
        seen.add(so)
        # Gather all registry ptrs that currently point here
        ptrs = [
            p
            for p in (BIRCH_PTR_ALLOW | TRAINER_UI_PTR_ALLOW)
            if p + 4 <= len(rom)
            and struct.unpack_from("<I", rom, p)[0] == v
        ]
        if not ptrs:
            ptrs = [ptr_off]
        from .extract_pipeline import module_defaults

        md = module_defaults()
        cat = md["story"] if ptr_off in BIRCH_PTR_ALLOW else md["ui"]
        entries.append(
            {
                "id": f"axvj_{BASE + so:08X}",
                "address": f"0x{BASE + so:08X}",
                "pointer_sources": [f"0x{BASE + p:08X}" for p in ptrs],
                "pointer_addresses": [f"0x{BASE + p:08X}" for p in ptrs],
                "is_pointer_based": True,
                "byte_length": len(s),
                "original_hex": s.hex(" "),
                "original": text,
                "translated": "",
                "category": cat,
            }
        )
    return entries


def extract_short_menu_labels(rom: bytes) -> list[dict]:
    """はい / いいえ and similar short UI labels (local / mid-ROM pools only)."""
    from .jp_pcs import CHAR_TO_BYTE
    from .policy import enrich_default_module, enrich_seed_originals

    wanted = enrich_seed_originals("短标菜单")
    if not wanted:
        return []
    from .extract_pipeline import module_defaults

    cat = enrich_default_module("短标菜单") or module_defaults()["ui"]
    out: list[dict] = []
    seen: set[int] = set()
    lz_spans = trusted_lz_spans(rom)
    for label in wanted:
        raw = bytearray()
        ok = True
        for ch in label:
            b = CHAR_TO_BYTE.get(ch)
            if b is None:
                ok = False
                break
            raw.append(b)
        if not ok:
            continue
        raw.append(0xFF)
        needle = bytes(raw)
        start = 0
        while True:
            off = rom.find(needle, start, min(len(rom), 0x800000))
            if off < 0:
                break
            start = off + 1
            if off in seen:
                continue
            # Seed labels only: never ARM/code or title LZ string sites.
            # False LZ streams often swallow real UI banks — do not require
            # _string_target_ok here (script scan still enforces it).
            if off < SCRIPT_BANK_MIN or TITLE_LZ_BAND[0] <= off < TITLE_LZ_BAND[1]:
                continue
            # ptr_source_ok: UI-bank bodies may use gfx-deny / low-ROM tables.
            ptrs = [
                p
                for p in _ptrs_to(rom, off, limit=12)
                if _axvj_ptr_source_ok(rom, p, off, lz_spans=lz_spans)
            ]
            if not ptrs:
                continue
            seen.add(off)
            out.append(
                {
                    "id": f"axvj_{BASE + off:08X}",
                    "address": f"0x{BASE + off:08X}",
                    "pointer_sources": [f"0x{BASE + p:08X}" for p in ptrs],
                    "pointer_addresses": [f"0x{BASE + p:08X}" for p in ptrs],
                    "is_pointer_based": True,
                    "byte_length": len(needle),
                    "original_hex": needle.hex(" "),
                    "original": label,
                    "category": cat,
                }
            )
    return out


def _encode_decoded_jp_needle(text: str) -> bytes | None:
    """Encode Meowth-decoded JP text (real ``\\n``, ``\\01``, ``\\CC…``) to PCS+FF."""
    from .jp_pcs import CHAR_TO_BYTE
    from .pcs_codes import fc_arg_count

    raw = bytearray()
    i = 0
    n = len(text)
    while i < n:
        if text.startswith("\n\n", i):
            raw.append(0xFB)
            i += 2
            continue
        if text[i] == "\n":
            raw.append(0xFE)
            i += 1
            continue
        if text.startswith("\\l", i):
            raw.append(0xFA)
            i += 2
            continue
        if text.startswith("\\p", i):
            raw.append(0xFB)
            i += 2
            continue
        if text.startswith("\\CC", i):
            hexpart = text[i + 3 :]
            j = 0
            while j < len(hexpart) and hexpart[j] in "0123456789abcdefABCDEF":
                j += 1
            if j < 2 or j % 2:
                return None
            try:
                args = bytes.fromhex(hexpart[:j])
            except ValueError:
                return None
            if not args:
                return None
            cmd = args[0]
            need = 1 + fc_arg_count(cmd)
            if len(args) < need:
                return None
            raw.append(0xFC)
            raw.extend(args[:need])
            i += 3 + need * 2
            continue
        if text[i] == "\\" and i + 3 <= n and all(
            c in "0123456789abcdefABCDEF" for c in text[i + 1 : i + 3]
        ):
            raw.append(0xFD)
            raw.append(int(text[i + 1 : i + 3], 16))
            i += 3
            continue
        b = CHAR_TO_BYTE.get(text[i])
        if b is None:
            return None
        raw.append(b)
        i += 1
    raw.append(0xFF)
    return bytes(raw)


def extract_save_power_prompts(rom: bytes) -> list[dict]:
    """Save / battery / report-write prompts (UI pool + dialogue-bank copies).

    Scan bands + lexicon seed flag: ``extract/config.json`` → ``enrich.存档与电源``.
    Module id is left unset — Build stamps via ``modules.json`` geo_ranges.
    """
    from .config_loader import get_active_game_id, load_custom_translations
    from .policy import (
        enrich_block,
        enrich_scan_bands,
        enrich_seed_from_lexicon,
        matches_content_class,
    )

    enrich_name = "存档与电源"
    bands = enrich_scan_bands(enrich_name)
    if not bands:
        return []
    content_class = str(enrich_block(enrich_name).get("content_class") or enrich_name)

    out: list[dict] = []
    seen: set[int] = set()
    lz_spans = trusted_lz_spans(rom)

    def _add(off: int, text: str, needle: bytes) -> None:
        if off in seen:
            return
        if off < SCRIPT_BANK_MIN or TITLE_LZ_BAND[0] <= off < TITLE_LZ_BAND[1]:
            return
        ptrs = [
            p
            for p in _ptrs_to(rom, off, limit=16)
            if _axvj_ptr_source_ok(rom, p, off, lz_spans=lz_spans)
        ]
        if not ptrs:
            return
        seen.add(off)
        out.append(
            {
                "id": f"axvj_{BASE + off:08X}",
                "address": f"0x{BASE + off:08X}",
                "pointer_sources": [f"0x{BASE + p:08X}" for p in ptrs],
                "pointer_addresses": [f"0x{BASE + p:08X}" for p in ptrs],
                "is_pointer_based": True,
                "byte_length": len(needle),
                "original_hex": needle.hex(" "),
                "original": text,
            }
        )

    if enrich_seed_from_lexicon(enrich_name):
        game_id = get_active_game_id() or ""
        ct = load_custom_translations(game_id) if game_id else {}
        seeds = [k for k in ct if matches_content_class(k, content_class)]
        for label in seeds:
            needle = _encode_decoded_jp_needle(label)
            if not needle:
                continue
            start = 0
            limit = min(len(rom), 0x800000)
            while True:
                off = rom.find(needle, start, limit)
                if off < 0:
                    break
                start = off + 1
                _add(off, label, needle)

    for lo, hi in bands:
        a = lo
        end = min(hi + 1, len(rom))
        while a < end:
            if rom[a] == 0xFF:
                a += 1
                continue
            raw = read_pcs(rom, a, 512)
            if not raw:
                a += 1
                continue
            text = decode_pcs(raw)
            if matches_content_class(text, content_class):
                _add(a, text, raw)
            a += len(raw)

    return out


def _clear_failed_zh(entry: dict) -> bool:
    """Clear known failed LLM stubs. Returns True if cleared."""
    from .seed_translate import looks_like_failed_zh_translation

    original = entry.get("original") or ""
    translated = entry.get("translated") or ""
    if not translated:
        return False
    if looks_like_failed_zh_translation(original, translated):
        entry["translated"] = ""
        return True
    if any(
        marker in translated
        for marker in ("无法处理", "我无法", "看起来像是乱码", "无法翻译")
    ):
        entry["translated"] = ""
        return True
    return False


def axvj_entry_is_garbage(entry: dict) -> bool:
    """True only for false-text / low-address / title-LZ — keep the rest."""
    from .policy import (
        entry_has_registry_ptr,
        is_item_desc_table_ptr,
        is_local_pool_ptr,
        is_nature_name_table_ptr,
        iter_entry_ptr_offs,
    )

    addr_s = entry.get("address") or "0"
    try:
        addr = int(str(addr_s).replace("0x", ""), 16)
    except ValueError:
        return True
    rom_off = addr - BASE if addr >= BASE else addr

    allowlisted = entry_has_registry_ptr(entry)
    if not allowlisted:
        for ptr_off in iter_entry_ptr_offs(entry):
            if (
                is_local_pool_ptr(ptr_off, rom_off)
                or is_nature_name_table_ptr(ptr_off)
                or is_item_desc_table_ptr(ptr_off)
            ):
                allowlisted = True
                break

    if not allowlisted and rom_off < SCRIPT_BANK_MIN:
        return True
    if TITLE_LZ_BAND[0] <= rom_off < TITLE_LZ_BAND[1]:
        return True

    hex_str = (entry.get("original_hex") or "").replace(" ", "")
    if hex_str:
        try:
            raw = bytes.fromhex(hex_str)
            if not raw.endswith(b"\xFF"):
                raw = raw + b"\xFF"
            if _is_struct_like_pcs(raw):
                return True
        except ValueError:
            return True

    original = entry.get("original") or ""
    if _is_garbage_jp(original):
        return True
    return False


def filter_axvj_garbage_entries(entries: list[dict]) -> tuple[list[dict], int]:
    """Drop structural garbage; clear failed ZH stubs. Return (kept, skipped)."""
    kept: list[dict] = []
    skipped = 0
    for e in entries:
        _clear_failed_zh(e)
        # S4: gender-select dialogue must stay JP (UI freezes if Chinese).
        if should_skip_zh_inject(e.get("original") or ""):
            e["translated"] = ""
        if axvj_entry_is_garbage(e):
            skipped += 1
            continue
        kept.append(e)
    return kept, skipped


def restore_false_gfx_pointers(
    rom: bytearray,
    baseline: bytes,
    *,
    lz_spans: list[tuple[int, int]] | None = None,
) -> int:
    """S6: undo expansion retargets in graphics bands / LZ.

    Keeps intentional local-pool rewrites for UI/option strings.
    ``baseline`` = ROM bytes from *before* text inject.
    """
    import struct

    spans = lz_spans if lz_spans is not None else trusted_lz_spans(baseline)
    nfix = 0
    limit = min(len(rom), len(baseline), 0x800000)

    for off in range(0, limit - 3, 4):
        if off in _EARLY_SCRIPT_PTR_ALLOWLIST or off in _TRAINER_UI_PTR_ALLOW:
            continue
        if _is_loadword_text_ptr(baseline, off):
            continue
        old = baseline[off : off + 4]
        new = bytes(rom[off : off + 4])
        if old == new:
            continue
        a = struct.unpack_from("<I", old, 0)[0]
        b = struct.unpack_from("<I", new, 0)[0]
        if not (0x08800000 <= b < 0x09000000):
            continue
        if not (BASE <= a < BASE + 0x800000):
            continue
        old_tgt = a - BASE
        if should_keep_relocated_local_pool(baseline, off, old_tgt):
            continue
        if not ptr_site_in_danger(off, lz_spans=spans):
            continue
        rom[off : off + 4] = old
        nfix += 1
    return nfix


def extract_axvj(
    rom_path: Path,
    output_path: Path,
    *,
    game_id: str = "",
    modules: list[str] | None = None,
    include_scripts: bool = True,
    script_limit: int = 0,
) -> Path:
    """Extract texts via ``extract/config.json`` pipeline and write JSON.

    ``modules`` is ignored and kept only for call-site compatibility.
    """
    from .extract_pipeline import run_extract_pipeline

    rom = Path(rom_path).read_bytes()
    gid = game_id or get_active_game_id() or "AXVJ"
    entries = run_extract_pipeline(
        rom,
        game_id=gid,
        include_scripts=include_scripts,
        script_limit=script_limit,
    )

    from .modules import stamp_entry_module

    for e in entries:
        stamp_entry_module(e, game_id=gid)

    payload = {
        "game": gid,
        "game_id": gid,
        "source_lang": "ja",
        "modules": list(DEFAULT_MODULES),
        "count": len(entries),
        "entries": entries,
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
