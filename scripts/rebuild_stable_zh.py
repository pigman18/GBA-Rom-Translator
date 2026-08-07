"""Clean rebuild: font patch + stable inject (menu + Birch + Mom only)."""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from meowth.extract import extract_script_pointers, extract_ui_block
from meowth.policy import keep_for_stable_inject
from meowth.seed_translate import seed_translate_entry
from meowth.charmap import Charmap
from meowth.font_patch import apply_font_patch
from meowth.rom_writer import RomWriter

ROOT = Path(r"C:\code\gba")
BASE = ROOT / "localization" / "ruby-jp-chs" / "baserom.gba"
JSON = ROOT / "work" / "texts_translated.json"
OUT = ROOT / "roms" / "Pokemon Ruby Version(JP)_zh.gba"
OUT2 = ROOT / "tools" / "Meowth-AXVJ" / "outputs" / "baserom_zh.gba"
TMP = ROOT / "tools" / "Meowth-AXVJ" / "outputs" / "temp_fontpatch.gba"


def _is_stable_script(e: dict) -> bool:
    from meowth.policy import is_stable_script_original

    return is_stable_script_original(e.get("original") or "")


def main() -> None:
    # Encode assertion: 锛?must be JP 0xAB, not Western 0x3C
    cm = Charmap(target_lang="zh-Hans", game="ruby_jp")
    sample = "濡堝銆嶾\01 杈涜嫤浜嗭紒"
    enc = cm.encode(sample)
    assert 0x3C not in enc, f"Western bang leaked: {enc.hex()}"
    assert 0xAB in enc, f"JP bang missing: {enc.hex()}"
    assert 0xB1 in enc, f"銆?missing: {enc.hex()}"
    assert enc.count(0xF9) >= 2, f"expected Chinese F9: {enc.hex()}"
    pad = cm.encode("璁剧疆銆€")
    assert pad.count(0xF9) == 3, f"menu pad need 3 Hanzi: {pad.hex()}"
    assert 0xF7 in pad, f"blank glyph trail missing: {pad.hex()}"
    page = cm.encode("鐢瞈\p涔?)
    assert 0xFB in page, f"page break must be FB: {page.hex()}"
    assert 0xFA not in page, f"FA must not be page break: {page.hex()}"
    print("encode OK", enc.hex(), "menu pad", pad.hex(), "page", page.hex())

    data = json.loads(JSON.read_text(encoding="utf-8"))
    entries = list(data.get("entries") or [])

    rom_bytes = BASE.read_bytes()

    # Merge title-menu / gender UI labels (銇娿仺銇?銇娿倱銇?etc.)
    for e in extract_ui_block(rom_bytes):
        o = e.get("original") or ""
        zh = seed_translate_entry(o) or ""
        if not zh:
            continue
        existing = next((x for x in entries if x.get("address") == e["address"]), None)
        if existing:
            existing.update(
                {
                    "pointer_sources": e["pointer_sources"],
                    "pointer_addresses": e.get("pointer_addresses") or e["pointer_sources"],
                    "original": e["original"],
                    "original_hex": e["original_hex"],
                    "byte_length": e["byte_length"],
                    "category": e.get("category") or "menu_ui",
                    "translated": zh,
                }
            )
        else:
            e = dict(e)
            e["translated"] = zh
            entries.append(e)

    # Merge full Birch new-game speech from fresh extract (early allowlist)
    birch_prefixes = (
        "銇勩倓銉?銇娿伨銇熴仜",
        "銉濄偙銉冦儓銉兂銈广偪銉?,
        "銇撱伄 銇涖亱銇勩伀銇?,
        "銇ㄣ亾銈嶃仹 銇嶃伩銇?,
        "鈥モ€ャ仢銇嗐亱锛?,
        "銈堛兗銇?銇樸倕銈撱伋銇?,
    )
    for e in extract_script_pointers(rom_bytes, limit=0):
        o = e.get("original") or ""
        is_birch = any(o.startswith(p) for p in birch_prefixes) or (
            "銇犮伃锛? in o and "\\01" in o
        )
        if not is_birch:
            continue
        zh = seed_translate_entry(o) or ""
        existing = next((x for x in entries if x.get("address") == e["address"]), None)
        if existing:
            existing.update(
                {
                    "pointer_sources": e["pointer_sources"],
                    "pointer_addresses": e["pointer_addresses"],
                    "original": e["original"],
                    "original_hex": e["original_hex"],
                    "byte_length": e["byte_length"],
                    "category": "scripts",
                }
            )
            if zh:
                existing["translated"] = zh
        else:
            e = dict(e)
            e["translated"] = zh
            entries.append(e)

    for e in entries:
        zh = seed_translate_entry(e.get("original") or "")
        if zh:
            e["translated"] = zh

    # Stable inject set only (shared policy with GUI build_rom)
    inject: list[dict] = [e for e in entries if keep_for_stable_inject(e)]

    print(
        "inject set",
        len(inject),
        "menu",
        sum(1 for e in inject if e.get("category") == "menu_ui"),
        "scripts",
        sum(1 for e in inject if e.get("category") == "scripts"),
    )
    for e in inject:
        if e.get("category") == "scripts":
            print(" ", e.get("address"), (e.get("original") or "")[:28].replace("\n", "/"))

    w = RomWriter(cm, game="ruby_jp", target_lang="zh-Hans")
    buf = w.load_rom(BASE)
    TMP.parent.mkdir(parents=True, exist_ok=True)
    w.save_rom(buf, TMP)
    apply_font_patch(TMP, TMP, game="ruby_jp")
    buf = w.load_rom(TMP)
    TMP.unlink(missing_ok=True)
    buf, stats = w.inject_texts(buf, inject)
    print("stats", {k: stats[k] for k in ("relocated", "skipped", "unsafe_ptrs", "errors")})
    outs = [
        OUT,
        OUT2,
        ROOT / "roms" / "Pokemon_Ruby_JP_zh_stable.gba",
    ]
    for path in outs:
        try:
            w.save_rom(buf, path)
            print("saved", path)
        except OSError as e:
            print("skip save", path, e)

    ba = BASE.read_bytes()
    z = bytes(buf)
    # Logo brand ptr must stay
    print(
        "pokemon brand ptr same",
        ba[0x1214B8 : 0x1214B8 + 4] == z[0x1214B8 : 0x1214B8 + 4],
    )
    for po, name in [
        (0x7260, "newgame"),
        (0x7968, "birch_welcome"),
        (0x79B8, "birch_namely"),
        (0x7AFC, "birch_world"),
        (0x7B44, "birch_who"),
        (0x8454, "birch_ready"),
        (0x14B2A3, "mom"),
    ]:
        v = struct.unpack_from("<I", z, po)[0]
        print(name, hex(po), "->", hex(v), "exp" if v >= 0x08800000 else "ORIG")


if __name__ == "__main__":
    main()
