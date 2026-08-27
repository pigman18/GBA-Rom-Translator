#!/usr/bin/env python3
"""从 AXVJ module_map + AXPJ ROM 实测生成/更新 RS 族 module_map JSON。

用法（仓库根）:
  python src/util/sync_rs_module_map.py POKEMON_SAPP_AXPJ00
"""
from __future__ import annotations

import copy
import json
import struct
import sys
from pathlib import Path

UTIL = Path(__file__).resolve().parent
REPO = UTIL.parent.parent
CONFIGS = UTIL / "configs"
TEMPLATE_JSON = CONFIGS / "POKEMON_RUBY_AXVJ00.json"
TEXTS_JSON = REPO / "configs/POKEMON_RUBY_AXVJ00/translate/texts.json"

GAMES = {
    "POKEMON_SAPP_AXPJ00": (
        "AXPJ",
        REPO / "roms/origin/POKEMON_SAPP_AXPJ00.gba",
    ),
}

BASE = 0x08000000


def _fo(gba_addr: int) -> int:
    return gba_addr - BASE


FIXED_DELTA = {
    "物种名": -0x70,
    "招式名": -0x70,
    "属性名": -0x70,
    "特性名": -0x70,
    "训练家类名": -0x70,
    "训练家个人名": 0,
    "特性说明": -0x70,
    "道具名": -0x1C,
    "道具说明": -0x1C,
    "招式说明": -0x1C,
    "性格名": -0x1C,
    "地点名": -0x1C,
    "图鉴说明": -0x8,
}

# title tile GBA addresses (file_offset = gba - BASE)
TITLE_TILES = {
    "title_logo": 0x0836D1F8,
    "title_banner": 0x0836ECF0,
    "title_tilemap": 0x0836CFC0,
    "title_palette": 0x0836D0D8,
    "type_icons_data": 0x087EE9C8,
    "type_icons_palette": 0x087EF450,
}


def parse_hex(s: str | int | None) -> int | None:
    if s is None:
        return None
    if isinstance(s, int):
        return s
    t = str(s).strip().lower()
    if t in ("", "0", "0x0"):
        return 0
    return int(t, 16)


def fmt_hex(v: int | None) -> str | None:
    if v is None:
        return None
    return f"0x{v:x}"


def slot_text(rom: bytes, off: int, stride: int) -> bytes:
    chunk = rom[off : off + stride]
    if 0xFF not in chunk:
        return b""
    return chunk[: chunk.index(0xFF) + 1]


def find_stride_table(
    ruby: bytes,
    sapp: bytes,
    ruby_start: int,
    stride: int,
    count: int,
    *,
    min_match: int = 5,
) -> tuple[int | None, int | None]:
    sig: list[bytes] = []
    for i in range(count):
        raw = slot_text(ruby, ruby_start + i * stride, stride)
        if len(raw) >= 3:
            sig.append(raw)
        if len(sig) >= min_match:
            break
    if not sig:
        return None, None
    needle = b"".join(sig)
    hits: list[int] = []
    pos = 0
    while True:
        idx = sapp.find(needle, pos)
        if idx < 0:
            break
        hits.append(idx)
        pos = idx + 1
    for h in hits:
        ok = all(
            slot_text(sapp, h + i * stride, stride) == raw for i, raw in enumerate(sig)
        )
        if ok:
            return h, h + count * stride - 1
    if hits:
        h = min(hits, key=lambda x: abs(x - ruby_start))
        return h, h + count * stride - 1
    return None, None


def find_bytes_region(
    ruby: bytes, sapp: bytes, ruby_start: int, ruby_end: int
) -> tuple[int | None, int | None]:
    span = ruby_end - ruby_start + 1
    if span <= 0 or span > 0x200000:
        return None, None
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
        return hits[0], hits[0] + span - 1
    if hits:
        best = min(hits, key=lambda x: abs(x - ruby_start))
        return best, best + span - 1
    return None, None


def shift_band(start: int | None, end: int | None, delta: int) -> tuple[int | None, int | None]:
    if start is None or end is None or start == 0:
        return start, end
    return start + delta, end + delta


def shift_ranges(ranges: list[dict] | None, delta: int) -> list[dict] | None:
    if not ranges or delta == 0:
        return ranges
    out = []
    for r in ranges:
        rs = parse_hex(r.get("start"))
        re_ = parse_hex(r.get("end"))
        if rs is None or re_ is None:
            out.append(r)
            continue
        out.append({"start": fmt_hex(rs + delta), "end": fmt_hex(re_ + delta)})
    return out


def find_type_icon_pointer(rom: bytes, data_gba: int) -> int | None:
    target = struct.pack("<I", data_gba)
    hits: list[int] = []
    pos = 0
    while True:
        idx = rom.find(target, pos)
        if idx < 0:
            break
        hits.append(idx + BASE)
        pos = idx + 1
    # RS 代码区常见单指针；取 0x0839xxxx 段
    code_hits = [h for h in hits if 0x08390000 <= h <= 0x083A0000]
    if len(code_hits) == 1:
        return code_hits[0]
    if code_hits:
        return min(code_hits)
    return hits[0] if len(hits) == 1 else None


TEXTS_JSON_OVERRIDES = frozenset({"招式说明", "特性说明"})


def measured_band(mid: str, ruby_mod: dict) -> tuple[int | None, int | None]:
    if mid in TEXTS_JSON_OVERRIDES and TEXTS_JSON.is_file():
        tj = json.loads(TEXTS_JSON.read_text(encoding="utf-8"))
        tm = (tj.get("modules") or {}).get(mid) or {}
        rs, re_ = parse_hex(tm.get("start")), parse_hex(tm.get("end"))
        if rs and re_:
            return rs, re_
    return parse_hex(ruby_mod.get("start")), parse_hex(ruby_mod.get("end"))


def resolve_module_span(
    mid: str,
    ruby_mod: dict,
    ruby: bytes,
    sapp: bytes,
) -> tuple[int | None, int | None, int, str]:
    """Return (start, end, delta_for_ranges, note)."""
    rs, re_ = measured_band(mid, ruby_mod)
    if rs is None or re_ is None or rs == 0:
        return rs, re_, 0, "unchanged zero"

    read = ruby_mod.get("read") or {}
    stride = read.get("stride")
    entry_size = read.get("entry_size")
    mtype = ruby_mod.get("type") or ""

    if mid in FIXED_DELTA:
        d = FIXED_DELTA[mid]
        if mtype == "stride" and stride:
            ss, se = find_stride_table(
                ruby, sapp, rs, stride, max(1, (re_ - rs + 1) // stride)
            )
            if ss is not None:
                return ss, se, ss - rs, "stride match"
        return rs + d, re_ + d, d, f"fixed delta {d:+d}"

    if mtype == "stride" and stride:
        count = max(1, (re_ - rs + 1) // stride)
        ss, se = find_stride_table(ruby, sapp, rs, stride, count)
        if ss is not None:
            return ss, se, ss - rs, "stride match"

    if mid == "性格名" or mtype == "stride_ptr":
        d = FIXED_DELTA.get("性格名", -0x1C)
        return rs + d, re_ + d, d, f"ptr table delta {d:+d}"

    if mid == "电脑与仓库":
        # 低地址带 −0x70；高 UI 串单独定址
        low_rs, low_re = 0x1804D9, 0x1809F7
        ss, se = find_bytes_region(ruby, sapp, low_rs, low_re)
        if ss is not None:
            d = ss - low_rs
            # 保持原 json 宽带，整体平移主 start/end
            return rs + d, re_ + d, d, "PC low band match"
        return shift_band(rs, re_, -0x70)[0], shift_band(rs, re_, -0x70)[1], -0x70, "PC delta -0x70"

    if mid == "默认名字":
        from meowth.jp_pcs import CHAR_TO_BYTE

        def anchor(text: str) -> int | None:
            buf = bytearray()
            for ch in text:
                b = CHAR_TO_BYTE.get(ch)
                if b is None:
                    return None
                buf.append(b)
            buf.append(0xFF)
            idx = sapp.find(bytes(buf))
            return idx if idx >= 0 else None

        offs = [anchor(t) for t in ("ユウキ", "ハルカ", "ミツル")]
        offs = [o for o in offs if o is not None]
        if offs:
            ss = min(offs)
            span = re_ - rs
            return ss, ss + span, ss - rs, "name anchors"
        return None, None, 0, "anchors missing"

    ss, se = find_bytes_region(ruby, sapp, rs, re_)
    if ss is not None:
        return ss, se, ss - rs, "region prefix"
    d = FIXED_DELTA.get(mid, 0)
    if d:
        return rs + d, re_ + d, d, f"fallback delta {d:+d}"
    return rs, re_, 0, "ruby copy (no match)"


def sync_game_json(game_id: str, game_code: str, rom_path: Path) -> Path:
    if not TEMPLATE_JSON.is_file():
        raise FileNotFoundError(TEMPLATE_JSON)
    if not rom_path.is_file():
        raise FileNotFoundError(rom_path)

    ruby = (REPO / "roms/origin/POKEMON_RUBY_AXVJ00.gba").read_bytes()
    sapp = rom_path.read_bytes()
    template = json.loads(TEMPLATE_JSON.read_text(encoding="utf-8"))
    out_doc = copy.deepcopy(template)

    meta = out_doc.setdefault("_meta", {})
    meta.update(
        {
            "rom_id": game_id,
            "game_codes": game_code,
            "source": f"sync_rs_module_map.py from {TEMPLATE_JSON.name} + {rom_path.name}",
            "measured_by": "sync_rs_module_map.py",
            "address_family": "RS",
        }
    )
    meta.pop("last_writeback", None)
    meta.pop("last_fold_autos", None)
    meta.pop("last_absorb_unassigned", None)

    stats = {"updated": 0, "unchanged": 0, "failed": 0}
    for mod in out_doc.get("modules") or []:
        mid = mod.get("id") or ""
        if not mid or mod.get("hidden"):
            continue
        rs = parse_hex(mod.get("start"))
        re_ = parse_hex(mod.get("end"))
        if rs == 0 and re_ == 0 and not mod.get("ranges"):
            stats["unchanged"] += 1
            continue

        ss, se, delta, note = resolve_module_span(mid, mod, ruby, sapp)
        if ss is None or ss == 0:
            stats["failed"] += 1
            continue
        mod["start"] = fmt_hex(ss)
        if se is not None:
            mod["end"] = fmt_hex(se)
        if mod.get("ranges"):
            mod["ranges"] = shift_ranges(mod["ranges"], delta)
        stats["updated"] += 1

    out_path = CONFIGS / f"{game_id}.json"
    out_path.write_text(
        json.dumps(out_doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {out_path.relative_to(REPO)}  updated={stats['updated']} failed={stats['failed']}")
    return out_path


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 1 or argv[0] not in GAMES:
        print("用法: python src/util/sync_rs_module_map.py POKEMON_SAPP_AXPJ00")
        return 2
    game_id = argv[0]
    code, rom = GAMES[game_id]
    sync_game_json(game_id, code, rom)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
