#!/usr/bin/env python3
"""鏂规 B锛欵xtract 鈫?Seed(ja鈫抸h) 鈫?Build(鍏?PCS 瀛楀簱鍐嶆敞鍏?."""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from meowth.seed_translate import seed_translate_file  # noqa: E402
from meowth.charmap import Charmap  # noqa: E402
from meowth.core.config import TranslationConfig  # noqa: E402
from meowth.core.engine import TranslationEngine, detect_game  # noqa: E402
from meowth.jp_pcs import decode_pcs  # noqa: E402

BASE = 0x08000000
# Curated high-value UI block (title / start menu / early UI)
UI_RANGE = (0x3E9440, 0x3E9820)


def extract_ui_block(rom: bytes) -> dict:
    entries = []
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
        if not (4 <= len(body) <= 36):
            a += 1
            continue
        if any(b >= 0xFA for b in body):
            a += 1
            continue
        text = decode_pcs(rom[a : eos + 1])
        if "<" in text:
            a = eos + 1
            continue
        needle = struct.pack("<I", BASE + a)
        ptrs = []
        pos = 0
        while len(ptrs) < 8:
            i = rom.find(needle, pos)
            if i < 0:
                break
            ptrs.append(f"0x{BASE + i:08X}")
            pos = i + 1
        if not ptrs:
            a = eos + 1
            continue
        entries.append(
            {
                "id": f"axvj_{BASE + a:08X}",
                "address": f"0x{BASE + a:08X}",
                "pointer_sources": ptrs,
                "pointer_addresses": ptrs,
                "is_pointer_based": True,
                "byte_length": eos - a + 1,
                "original_hex": rom[a : eos + 1].hex(" "),
                "original": text,
                "translated": "",
                "category": "jp_text",
            }
        )
        a = eos + 1
    return {
        "game": "AXVJ",
        "game_id": "ruby_jp",
        "source_lang": "ja",
        "count": len(entries),
        "entries": entries,
    }


def main() -> int:
    rom_path = Path(r"C:\code\gba\localization\ruby-jp-chs\baserom.gba")
    if not rom_path.exists():
        print("ERROR: missing", rom_path)
        return 1

    work = ROOT / "work"
    out_dir = ROOT / "outputs"
    work.mkdir(exist_ok=True)
    out_dir.mkdir(exist_ok=True)
    texts = work / "texts.json"
    translated = work / "texts_translated.json"
    out_rom = out_dir / "axvj_zh_demo.gba"

    print("detect:", detect_game(rom_path))
    rom = rom_path.read_bytes()

    print("=== 1/3 Extract (UI block) ===")
    data = extract_ui_block(rom)
    texts.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("extracted", data["count"])
    (work / "extract_preview.txt").write_text(
        "\n".join(f"{e['address']}\t{e['original']}" for e in data["entries"]),
        encoding="utf-8",
    )

    print("=== 2/3 Seed translate ===")
    n_seed, n_total = seed_translate_file(texts, translated, only_seeded=True)
    print(f"seeded {n_seed}/{n_total}")
    if n_seed < 3:
        print("ERROR: too few seeds")
        return 2
    td = json.loads(translated.read_text(encoding="utf-8"))
    (work / "seed_preview.txt").write_text(
        "\n".join(f"{e['original']} => {e['translated']}" for e in td["entries"]),
        encoding="utf-8",
    )

    print("=== 3/3 Build (PCS font then inject) ===")
    config = TranslationConfig(source_lang="ja", target_lang="zh-Hans", game="ruby_jp")
    engine = TranslationEngine(config)
    engine.charmap = Charmap(target_lang="zh-Hans", game="ruby_jp")
    engine.build_rom(rom_path, translated, out_rom)

    blob = out_rom.read_bytes()
    pool = int.from_bytes(blob[0x3374:0x3378], "little")
    # verify one menu pointer was redirected
    ptr = int.from_bytes(blob[0x7260:0x7264], "little")
    print("dispatch", hex(pool), "menu_ptr", hex(ptr))
    if pool & 1 == 0:
        print("ERROR: thumb bit missing")
        return 3
    if ptr == 0x083E945D:
        print("ERROR: menu pointer not relocated")
        return 4
    # show relocated string bytes
    off = ptr - BASE
    raw = blob[off : off + 32]
    end = raw.find(b"\xff")
    print("relocated hex", raw[: end + 1].hex(" ") if end >= 0 else raw.hex(" "))
    print("PASS:", out_rom)
    print("Preview:", work / "seed_preview.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
