#!/usr/bin/env python3
"""Analyze RS table/UI tile offsets: Ruby vs Sapphire (file_offset space)."""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

UTIL = Path(__file__).resolve().parent
REPO = UTIL.parent.parent
sys.path.insert(0, str(UTIL))
sys.path.insert(0, str(REPO / "src"))

from _scan_tiles import scan, pal_near  # noqa: E402
from tiles_patcher import (  # noqa: E402
    detect_lz77,
    find_lz77_size,
    lz77_decompress,
    offset_to_gba_address,
    _detect_bpp,
)

RUBY = REPO / "roms/origin/POKEMON_RUBY_AXVJ00.gba"
SAPP = REPO / "roms/origin/POKEMON_SAPP_AXPJ00.gba"
RUBY_JSON = UTIL / "configs/POKEMON_RUBY_AXVJ00.json"
SAPP_JSON = UTIL / "configs/POKEMON_SAPP_AXPJ00.json"

BASE = 0x08000000


def fo(addr: int) -> int:
    """GBA ROM address -> file offset."""
    return addr - BASE


def gba(off: int) -> int:
    return BASE + off


def hx(off: int | None) -> str:
    if off is None:
        return "-"
    return f"0x{off:06X}"


def parse_hex(s: str | None) -> int | None:
    if not s:
        return None
    s = str(s).strip().lower()
    if s in ("0x0", "0", ""):
        return 0
    return int(s, 16)


def slot_text(rom: bytes, off: int, stride: int) -> bytes:
    chunk = rom[off : off + stride]
    if 0xFF not in chunk:
        return b""
    return chunk[: chunk.index(0xFF) + 1]


def decode_pcs_simple(data: bytes) -> str:
    from meowth.jp_pcs import decode_pcs

    return decode_pcs(data)


def find_stride_table(
    ruby: bytes,
    sapp: bytes,
    ruby_start: int,
    stride: int,
    count: int,
    *,
    min_match: int = 5,
) -> tuple[int | None, int | None, str]:
    """Match first N valid slots from ruby in sapphire."""
    sig_entries: list[bytes] = []
    for i in range(count):
        off = ruby_start + i * stride
        raw = slot_text(ruby, off, stride)
        if len(raw) >= 3:
            sig_entries.append(raw)
        if len(sig_entries) >= min_match:
            break
    if not sig_entries:
        return None, None, "no ruby signature"

    needle = b"".join(sig_entries)
    hits: list[int] = []
    pos = 0
    while True:
        idx = sapp.find(needle, pos)
        if idx < 0:
            break
        hits.append(idx)
        pos = idx + 1

    if not hits:
        # fallback: first entry only
        needle1 = sig_entries[0]
        pos = 0
        while True:
            idx = sapp.find(needle1, pos)
            if idx < 0:
                break
            hits.append(idx)
            pos = idx + 1

    valid: list[tuple[int, int]] = []
    for h in hits:
        ok = True
        for i, raw in enumerate(sig_entries):
            got = slot_text(sapp, h + i * stride, stride)
            if got != raw:
                ok = False
                break
        if ok:
            # extend count while slots look valid
            end_i = len(sig_entries)
            while end_i < count:
                nxt = slot_text(sapp, h + end_i * stride, stride)
                if len(nxt) < 2:
                    break
                end_i += 1
            valid.append((h, h + count * stride - 1))

    if len(valid) == 1:
        s, e = valid[0]
        return s, e, f"matched {len(sig_entries)} entries"
    if len(valid) > 1:
        # pick closest to ruby_start
        best = min(valid, key=lambda t: abs(t[0] - ruby_start))
        return best[0], best[1], f"ambiguous {len(valid)} hits, picked nearest ruby"
    return None, None, f"no valid hit ({len(hits)} raw)"


def find_bytes_region(ruby: bytes, sapp: bytes, ruby_start: int, ruby_end: int) -> tuple[int | None, int | None, str]:
    span = ruby_end - ruby_start + 1
    if span <= 0 or span > 0x200000:
        return None, None, "bad span"
    needle = ruby[ruby_start : ruby_start + min(span, 64)]
    hits: list[int] = []
    pos = 0
    while True:
        idx = sapp.find(needle, pos)
        if idx < 0:
            break
        hits.append(idx)
        pos = idx + 1
    if len(hits) == 1:
        return hits[0], hits[0] + span - 1, "unique prefix"
    if len(hits) > 1:
        best = min(hits, key=lambda x: abs(x - ruby_start))
        return best, best + span - 1, f"ambiguous {len(hits)}"
    return None, None, "not found"


def find_struct_table(
    ruby: bytes,
    sapp: bytes,
    ruby_start: int,
    entry_size: int,
    name_off: int,
    count: int,
) -> tuple[int | None, int | None, str]:
    sig: list[bytes] = []
    for i in range(min(5, count)):
        ent = ruby_start + i * entry_size
        raw = slot_text(ruby, ent + name_off, entry_size - name_off)
        if len(raw) >= 3:
            sig.append(raw)
    if not sig:
        return None, None, "no sig"
    needle = sig[0]
    hits: list[int] = []
    pos = 0
    while True:
        idx = sapp.find(needle, pos)
        if idx < 0:
            break
        # align to entry boundary
        ent_start = idx - name_off
        if ent_start >= 0 and (ent_start - ruby_start) % entry_size == 0:
            hits.append(ent_start)
        pos = idx + 1
    for h in hits:
        ok = True
        for i, raw in enumerate(sig):
            got = slot_text(sapp, h + i * entry_size + name_off, entry_size - name_off)
            if got != raw:
                ok = False
                break
        if ok:
            return h, h + count * entry_size - 1, f"struct {entry_size}B×{count}"
    if hits:
        h = min(hits, key=lambda x: abs(x - ruby_start))
        return h, h + count * entry_size - 1, f"weak match {len(hits)} hits"
    return None, None, "not found"


def find_text_anchor(sapp: bytes, text: str) -> int | None:
    from meowth.jp_pcs import CHAR_TO_BYTE

    buf = bytearray()
    for ch in text:
        b = CHAR_TO_BYTE.get(ch)
        if b is None:
            return None
        buf.append(b)
    buf.append(0xFF)
    idx = sapp.find(bytes(buf))
    return idx if idx >= 0 else None


def scan_title_lz(rom: bytes, lo: int, hi: int) -> list[dict]:
    out = []
    for off in range(lo, hi, 4):
        if rom[off] != 0x10:
            continue
        dst = rom[off + 1] | (rom[off + 2] << 8) | (rom[off + 3] << 16)
        comp = detect_lz77(rom, off)
        if comp == "none":
            continue
        csize = find_lz77_size(rom, off)
        dec = lz77_decompress(rom[off:], swap=(comp == "lz77_swap"))
        bpp = _detect_bpp(dec)
        pb = pal_near(rom, off)
        out.append(
            {
                "off": off,
                "gba": offset_to_gba_address(off),
                "csize": csize,
                "dsize": dst,
                "comp": comp,
                "bpp": bpp,
                "pal_off": pb[1] if pb else None,
                "pal_gba": offset_to_gba_address(pb[1]) if pb else None,
            }
        )
    return out


def json_mod(doc: dict) -> dict[str, dict]:
    return {m["id"]: m for m in doc.get("modules", []) if m.get("id")}


def main() -> int:
    ruby = RUBY.read_bytes()
    sapp = SAPP.read_bytes()
    rj = json.loads(RUBY_JSON.read_text(encoding="utf-8"))
    sj = json.loads(SAPP_JSON.read_text(encoding="utf-8"))
    rm = json_mod(rj)
    sm = json_mod(sj)

    # --- table modules to locate ---
    # Measured bands from configs/.../translate/texts.json override stale module_map scan spans.
    TEXTS_JSON = REPO / "configs/POKEMON_RUBY_AXVJ00/translate/texts.json"
    tj_mods = json.loads(TEXTS_JSON.read_text(encoding="utf-8")).get("modules", {})

    def measured(mid: str) -> tuple[int | None, int | None]:
        m = tj_mods.get(mid) or rm.get(mid) or {}
        return parse_hex(m.get("start")), parse_hex(m.get("end"))

    specs: list[dict] = [
        {"id": "物种名", "stride": 6, "count": 412, "finder": "stride"},
        {"id": "招式名", "stride": 8, "count": 355, "finder": "stride"},
        {"id": "属性名", "stride": 5, "count": 18, "finder": "stride"},
        {"id": "特性名", "stride": 8, "count": 78, "finder": "stride"},
        {
            "id": "道具名",
            "finder": "struct",
            "entry_size": 40,
            "name_off": 0,
            "count": 377,
            "ruby_start": 0x39A648,
            "ruby_end": 0x39DCA7,
            "sapp_delta": -0x1C,
        },
        {
            "id": "训练家类名",
            "finder": "fixed",
            "ruby_start": 0x1C4A10,
            "ruby_end": 0x1C4D00,
            "sapp_delta": -0x70,
        },
        {
            "id": "默认名字",
            "finder": "anchor",
            "anchors": ["ユウキ", "ハルカ"],
            "ruby_start": 0x1C9F1E,
            "ruby_end": 0x1CA008,
        },
        {
            "id": "电脑与仓库(PC低地址)",
            "finder": "fixed",
            "ruby_start": 0x1804D9,
            "ruby_end": 0x1809F7,
            "sapp_delta": -0x70,
        },
        {
            "id": "电脑与仓库(PC菜单UI)",
            "finder": "anchor",
            "anchors": ["ポケモンを つれていく", "だれかのパソコン", "ボックスを せいりする"],
        },
        {"id": "道具说明", "finder": "region"},
        {
            "id": "招式说明",
            "finder": "stride",
            "stride": 56,
            "count": 354,
            "ruby_start": measured("招式说明")[0],
            "ruby_end": measured("招式说明")[1],
        },
        {
            "id": "特性说明",
            "finder": "stride",
            "stride": 19,
            "count": 78,
            "ruby_start": measured("特性说明")[0],
            "ruby_end": measured("特性说明")[1],
        },
        {
            "id": "图鉴说明",
            "finder": "region",
            "ruby_start": measured("图鉴说明")[0],
            "ruby_end": measured("图鉴说明")[1],
        },
        {
            "id": "性格名",
            "finder": "ptr_stride",
            "stride": 4,
            "count": 25,
            "ruby_start": measured("性格名")[0] or parse_hex(rm.get("性格名", {}).get("start")),
            "ruby_end": measured("性格名")[0] or 0,
        },
        {
            "id": "地点名",
            "finder": "region",
            "ruby_start": measured("地点名")[0],
            "ruby_end": measured("地点名")[1],
        },
        {
            "id": "训练家个人名",
            "finder": "fixed",
            "ruby_start": 0x1C5040,
            "ruby_end": 0x1CA340,
            "sapp_delta": 0,
        },
    ]

    results: list[dict] = []

    for spec in specs:
        mid = spec["id"]
        rmod = rm.get(mid, {})
        smod = sm.get(mid, {})
        rs = spec.get("ruby_start") or parse_hex(rmod.get("start"))
        re_ = spec.get("ruby_end") or parse_hex(rmod.get("end"))
        ss_cfg = parse_hex(smod.get("start"))
        se_cfg = parse_hex(smod.get("end"))

        ss_found: int | None = None
        se_found: int | None = None
        note = ""

        if spec["finder"] == "fixed" and rs and re_:
            d = spec.get("sapp_delta", 0)
            ss_found, se_found = rs + d, re_ + d
            note = f"ruby delta {d:+d}"
        elif spec["finder"] == "stride" and rs:
            ss_found, se_found, note = find_stride_table(
                ruby, sapp, rs, spec["stride"], spec["count"]
            )
            if ss_found is None and spec.get("sapp_delta") is not None:
                d = spec["sapp_delta"]
                ss_found = rs + d
                se_found = (re_ + d) if re_ else rs + d + spec["count"] * spec["stride"] - 1
                note = f"fallback delta {d:+d}"
        elif spec["finder"] == "struct" and rs:
            if spec.get("sapp_delta") is not None:
                d = spec["sapp_delta"]
                ss_found = rs + d
                se_found = (re_ + d) if re_ else ss_found + spec["count"] * spec["entry_size"] - 1
                note = f"delta {d:+d}"
            else:
                ss_found, se_found, note = find_struct_table(
                    ruby, sapp, rs, spec["entry_size"], spec["name_off"], spec["count"]
                )
        elif spec["finder"] == "ptr_stride" and rs:
            best = (0, 0, 0)
            span = min(256, (re_ - rs + 1) if re_ and re_ > rs else 256)
            for d in range(-0x200, 0x201, 4):
                ss = rs + d
                if ss < 0:
                    continue
                m = sum(
                    1
                    for j in range(0, span, 4)
                    if ruby[rs + j : rs + j + 4] == sapp[ss + j : ss + j + 4]
                )
                if m > best[0]:
                    best = (m, d, ss)
            if best[0] >= 8:
                ss_found = best[2]
                se_found = ss_found + spec["count"] * spec["stride"] - 1
                note = f"ptr match {best[0]}/{span//4} delta {best[1]:+d}"
        elif spec["finder"] == "region" and rs and re_:
            ss_found, se_found, note = find_bytes_region(ruby, sapp, rs, re_)
        elif spec["finder"] == "anchor":
            offs = []
            for a in spec.get("anchors", []):
                o = find_text_anchor(sapp, a)
                if o is not None:
                    offs.append((a, o))
            if offs:
                ss_found = min(o for _, o in offs)
                # rough end from ruby span if available
                if rs and re_:
                    se_found = ss_found + (re_ - rs)
                note = "; ".join(f"{t}@{hx(o)}" for t, o in offs)
            else:
                note = "anchors not found"

        cfg_ok = ss_cfg not in (None, 0) and se_cfg not in (None, 0)
        cfg_wrong = ""
        if ss_cfg in (0, None) or se_cfg in (0, None):
            cfg_wrong = "config 0x0 band"
        elif ss_found is not None and (ss_cfg != ss_found or (se_cfg and se_found and abs(se_cfg - se_found) > 0x100)):
            cfg_wrong = f"config {hx(ss_cfg)}-{hx(se_cfg)} vs found {hx(ss_found)}-{hx(se_found)}"

        results.append(
            {
                "module_id": mid,
                "ruby_start": rs,
                "ruby_end": re_,
                "sapphire_start": ss_found,
                "sapphire_end": se_found,
                "sapp_config_start": ss_cfg,
                "sapp_config_end": se_cfg,
                "notes": note + ("; " + cfg_wrong if cfg_wrong else ""),
            }
        )

    # type_icons - same address check
    ti_ruby = fo(0x087EE9C8)
    ti_sapp_scan = None
    for off, _c, dsize, comp in scan(sapp):
        if dsize == 5888:
            ti_sapp_scan = off
            break
    results.append(
        {
            "module_id": "type_icons (tile)",
            "ruby_start": ti_ruby,
            "ruby_end": ti_ruby,
            "sapphire_start": ti_sapp_scan,
            "sapphire_end": ti_sapp_scan,
            "sapp_config_start": fo(0x087EE9C8),
            "sapp_config_end": fo(0x087EE9C8),
            "notes": "5888B LZ 32x16×23 4bpp scan",
        }
    )

    # title LZ scan 0x836000-0x837000 (file 0x36000-0x37000) — user asked this band;
    # also scan ruby-equivalent 0x36D000-0x36F000
    title_bands = [
        ("scan_836", fo(0x08360000), fo(0x08370000)),
        ("scan_ruby_title", fo(0x0836D000), fo(0x08370000)),
    ]
    title_hits: dict[str, list] = {}
    for name, lo, hi in title_bands:
        title_hits[name] = scan_title_lz(sapp, lo, hi)

    # identify logo vs banner by dsize heuristics (ruby: logo large, banner smaller)
    ruby_logo = fo(0x0836D268)
    ruby_banner = fo(0x0836EC6C)
    ruby_pal = fo(0x0836D148)
    ruby_tm = fo(0x0836D030)

    ruby_logo_hdr = ruby[ruby_logo : ruby_logo + 4]
    sapp_at_ruby_logo = sapp[ruby_logo : ruby_logo + 16].hex()

    print("=" * 100)
    print("TABLE: module_id | ruby_start | sapphire_start | sapphire_end | notes")
    print("=" * 100)
    for r in results:
        print(
            f"{r['module_id']:20} | {hx(r['ruby_start']):>10} | "
            f"{hx(r['sapphire_start']):>14} | {hx(r['sapphire_end']):>12} | {r['notes']}"
        )

    print("\n" + "=" * 100)
    print("SAPP CONFIG ISSUES (0x0 or wrong offset)")
    print("=" * 100)
    for mid, m in sorted(sm.items()):
        ss = parse_hex(m.get("start"))
        se = parse_hex(m.get("end"))
        if ss == 0 and se == 0:
            print(f"  ZERO: {mid}")
        elif mid in rm:
            # check if copy-pasted from ruby unchanged
            rs = parse_hex(rm[mid].get("start"))
            if ss == rs and mid in {x["module_id"] for x in results}:
                found = next(x for x in results if x["module_id"] == mid)
                if found["sapphire_start"] and found["sapphire_start"] != ss:
                    print(
                        f"  STALE-RUBY: {mid} config={hx(ss)} found={hx(found['sapphire_start'])}"
                    )

    print("\n" + "=" * 100)
    print("TITLE LZ77 in Sapphire (file_offset, gba_addr, dsize, bpp, comp, pal)")
    print("=" * 100)
    for band_name, hits in title_hits.items():
        print(f"\n--- {band_name} ({len(hits)} hits) ---")
        for h in hits:
            pal_s = hx(h["pal_off"]) if h["pal_off"] is not None else "-"
            print(
                f"  {hx(h['off'])} / 0x{h['gba']:08X}  dst={h['dsize']:5}  "
                f"csize={h['csize']:5}  {h['comp']:9}  {h['bpp']}bpp  pal={pal_s}"
            )

    print("\n--- Ruby title refs ---")
    print(f"  ruby_logo @ {hx(ruby_logo)} hdr={ruby_logo_hdr.hex()}")
    print(f"  sapp @ same offset bytes={sapp_at_ruby_logo} (LZ77 if starts 10 xx xx xx)")

    # Recommend tile presets
    title_region = title_hits.get("scan_ruby_title") or title_hits.get("scan_836") or []
    logo_cands = [h for h in title_region if h["dsize"] > 8000 and h["bpp"] == 8]
    banner_cands = [h for h in title_region if 500 < h["dsize"] < 4000 and h["bpp"] == 8]
    pal_cands = sorted(
        {h["pal_off"] for h in title_region if h["pal_off"]},
        key=lambda p: abs(p - ruby_pal) if p else 999999,
    )

    print("\n" + "=" * 100)
    print("RECOMMENDED SAPP TILE PRESETS")
    print("=" * 100)
    if logo_cands:
        lg = min(logo_cands, key=lambda h: abs(h["off"] - ruby_logo))
        print(
            f"  title_logo:   address=0x{lg['gba']:08X}  compression={lg['comp']}  "
            f"palette=0x{lg['pal_gba']:08X}" if lg.get("pal_gba") else ""
        )
    if banner_cands:
        bn = min(banner_cands, key=lambda h: abs(h["off"] - ruby_banner))
        print(
            f"  title_banner: address=0x{bn['gba']:08X}  compression={bn['comp']}  "
            f"palette=0x{bn['pal_gba']:08X}" if bn.get("pal_gba") else ""
        )
    if pal_cands:
        print(f"  title_palette candidate: 0x{offset_to_gba_address(pal_cands[0]):08X}")
    # tilemap: search for pointer near logo
    # tilemap: identical LZ header block shifted -0x70 from ruby
    tm_sapp = ruby_tm - 0x70
    if sapp[ruby_tm : ruby_tm + 16] != sapp[tm_sapp : tm_sapp + 16]:
        print(f"  title_tilemap:      0x{offset_to_gba_address(tm_sapp):08X}  (ruby delta -0x70)")
    else:
        print(f"  title_tilemap:      0x{offset_to_gba_address(tm_sapp):08X}")
    print(f"  title_palette:      0x{offset_to_gba_address(ruby_pal - 0x70):08X}  (raw GBA555, ruby delta -0x70)")

    print(f"\n  type_icons: address=0x{offset_to_gba_address(ti_sapp_scan or ti_ruby):08X}  (shared RS family)")

    # Species sanity: show first 3 names at found offset
    sp = next(r for r in results if r["module_id"] == "物种名")
    if sp["sapphire_start"]:
        print("\n--- Species table sample (Sapp) ---")
        for i in range(3):
            raw = slot_text(sapp, sp["sapphire_start"] + i * 6, 6)
            print(f"  [{i}] {decode_pcs_simple(raw)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
