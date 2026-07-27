"""Full AXVJ ZH rebuild: font patch + all CJK translations (safe inject).

Uses work/texts_translated.json when present; merges fresh UI/options extract
and seed overrides. Protects title logo graphics pointers.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from meowth.extract import extract_option_menu, extract_ui_block
from meowth.seed_translate import seed_translate_entry
from meowth.charmap import Charmap
from meowth.font_patch import apply_font_patch
from meowth.rom_writer import RomWriter

ROOT = Path(r"C:\code\gba")
BASE = ROOT / "localization" / "ruby-jp-chs" / "baserom.gba"
JSON = ROOT / "work" / "texts_translated.json"
OUT = ROOT / "roms" / "Pokemon_Ruby_JP_zh_full.gba"
OUT2 = ROOT / "tools" / "Meowth-AXVJ" / "outputs" / "baserom_zh_full.gba"
TMP = ROOT / "tools" / "Meowth-AXVJ" / "outputs" / "temp_fontpatch_full.gba"

_TITLE_GFX_PTRS = (
    0x78EA4,
    0x79240,
    0x79250,
    0x79258,
    0x79260,
    0x1214B8,
)


def _has_cjk(s: str) -> bool:
    return any("\u4e00" <= c <= "\u9fff" for c in s)


def _merge_entry(bucket: dict[str, dict], e: dict) -> None:
    addr = e.get("address") or ""
    if not addr:
        return
    prev = bucket.get(addr)
    if prev is None:
        bucket[addr] = dict(e)
        return
    # Prefer richer pointer lists + keep better translation
    for k in ("pointer_sources", "pointer_addresses", "original_hex", "byte_length", "category"):
        if e.get(k) and (not prev.get(k) or k.startswith("pointer")):
            if k.startswith("pointer"):
                old = list(prev.get(k) or [])
                new = list(e.get(k) or [])
                prev[k] = list(dict.fromkeys(old + new))
            else:
                prev[k] = e[k]
    tr = e.get("translated") or ""
    if tr and (not prev.get("translated") or tr != prev.get("original")):
        if _has_cjk(tr) or tr.startswith("\\CC"):
            prev["translated"] = tr


def main() -> None:
    cm = Charmap(target_lang="zh-Hans", game="ruby_jp")
    page = cm.encode("鐢瞈\p涔?)
    assert 0xFB in page and 0xFA not in page, page.hex()

    rom_bytes = BASE.read_bytes()
    bucket: dict[str, dict] = {}

    if JSON.exists():
        data = json.loads(JSON.read_text(encoding="utf-8"))
        for e in data.get("entries") or []:
            _merge_entry(bucket, e)
        for e in data.get("free_texts") or []:
            _merge_entry(bucket, e)
        for table in data.get("tables") or []:
            for e in table.get("entries") or []:
                _merge_entry(bucket, e)
        print("loaded json entries", len(bucket))
    else:
        print("WARNING: no", JSON)

    for e in extract_ui_block(rom_bytes):
        zh = seed_translate_entry(e.get("original") or "") or ""
        if zh:
            e = dict(e)
            e["translated"] = zh
        _merge_entry(bucket, e)

    for e in extract_option_menu(rom_bytes):
        zh = seed_translate_entry(e.get("original") or "") or ""
        if zh:
            e = dict(e)
            e["translated"] = zh
        _merge_entry(bucket, e)

    # Re-apply seeds on everything (house cleanup, options, menu pads)
    for e in bucket.values():
        zh = seed_translate_entry(e.get("original") or "")
        if zh:
            e["translated"] = zh

    inject: list[dict] = []
    for e in bucket.values():
        tr = (e.get("translated") or "").strip()
        orig = e.get("original") or ""
        if not tr or tr == orig:
            continue
        if not (_has_cjk(tr) or tr.startswith("\\CC")):
            continue
        inject.append(e)

    print(
        "inject",
        len(inject),
        "menu_ui",
        sum(1 for e in inject if e.get("category") == "menu_ui"),
        "scripts",
        sum(1 for e in inject if e.get("category") == "scripts"),
        "options",
        sum(1 for e in inject if (e.get("original") or "").startswith("\\CC")),
    )

    w = RomWriter(cm, game="ruby_jp", target_lang="zh-Hans")
    buf = w.load_rom(BASE)
    TMP.parent.mkdir(parents=True, exist_ok=True)
    w.save_rom(buf, TMP)
    apply_font_patch(TMP, TMP, game="ruby_jp")
    buf = w.load_rom(TMP)
    TMP.unlink(missing_ok=True)
    buf, stats = w.inject_texts(buf, inject)
    print(
        "stats",
        {
            k: stats[k]
            for k in ("relocated", "in_place", "skipped", "unsafe_ptrs", "errors")
        },
    )

    for path in (OUT, OUT2):
        try:
            w.save_rom(buf, path)
            print("saved", path)
        except OSError as exc:
            print("skip save", path, exc)

    ba = BASE.read_bytes()
    z = bytes(buf)
    ok = True
    for po in _TITLE_GFX_PTRS:
        same = ba[po : po + 4] == z[po : po + 4]
        print("logo_ptr", hex(po), "same", same)
        ok = ok and same
    # House cleanup line
    v = struct.unpack_from("<I", z, 0x18E669)[0]
    print("house_ptr", hex(v), "exp" if v >= 0x08800000 else "ORIG")
    # Options first label
    v2 = struct.unpack_from("<I", z, 0x88710)[0]
    print("option_speed_ptr", hex(v2), "exp" if v2 >= 0x08800000 else "ORIG")
    if not ok:
        raise SystemExit("logo pointer corrupted")


if __name__ == "__main__":
    main()
