#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assign_modules.py
=================
把 dump 出的 addr_bands 按「模块地图」归类，生成与 Meowth
``translate/modules.json`` 同构的 schema v3 JSON。

匹配规则：从小区间开始（模糊 [start,end] 跨度升序）；dump 带完全落入的模块优先。
``hidden`` / ``assign: false`` 模块不参与区间抢占，但仍写入产出（模板原样）。

日常请用：python text_patcher.py export rom.gba
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


def parse_addr(v: Any) -> int:
    if isinstance(v, int):
        return v
    s = str(v).strip()
    return int(s, 16) if s.lower().startswith("0x") else int(s, 0)


def load_module_map(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    mods = data.get("modules")
    if not isinstance(mods, list):
        raise ValueError(f"{path}: modules must be a list")
    return data


def _module_participates(m: dict) -> bool:
    """Whether this map entry claims dump bands."""
    if m.get("assign") is False:
        return False
    if m.get("hidden"):
        return False
    return True


def _parse_ranges(m: dict) -> List[Tuple[int, int]]:
    ranges = m.get("ranges")
    parsed: List[Tuple[int, int]] = []
    if ranges:
        for r in ranges:
            if isinstance(r, dict):
                lo, hi = parse_addr(r["start"]), parse_addr(r["end"])
            elif isinstance(r, (list, tuple)) and len(r) >= 2:
                lo, hi = parse_addr(r[0]), parse_addr(r[1])
            else:
                continue
            if hi >= lo:
                parsed.append((lo, hi))
    if not parsed:
        lo = parse_addr(m.get("start") or 0)
        hi = parse_addr(m.get("end") or 0)
        if hi < lo:
            raise ValueError(f"module {m.get('id')}: end < start")
        parsed = [(lo, hi)]
    return parsed


def summarize_gamejson_to_map(game_path: Path) -> dict:
    """从现有 game.json / modules.json 总结模糊 module_map。"""
    data = json.loads(game_path.read_text(encoding="utf-8"))
    modules_src = data.get("modules") or {}
    modules_out: List[dict] = []
    for mid, mod in modules_src.items():
        read = mod.get("read") or {}
        bands = (
            read.get("scan_addr_bands")
            or read.get("addr_bands")
            or mod.get("addr_bands")
            or []
        )
        if not bands and mod.get("start") is not None and mod.get("end") is not None:
            lo = parse_addr(mod["start"])
            hi = parse_addr(mod["end"])
        elif bands:
            lo = min(parse_addr(a) for a, _ in bands)
            hi = max(parse_addr(b) for _, b in bands)
        else:
            continue
        entry: Dict[str, Any] = {
            "id": mid,
            "label": mod.get("label") or mid,
            "group": mod.get("group") or "",
            "default": bool(mod.get("default", False)),
            "description": mod.get("description")
            or f"从 {data.get('game_id', game_path.stem)} 总结",
            "type": mod.get("type") or "scan",
            "start": f"0x{lo:X}",
            "end": f"0x{hi:X}",
        }
        if read:
            r = {k: v for k, v in read.items() if k not in ("scan_addr_bands", "addr_bands")}
            if r:
                entry["read"] = r
        if mod.get("hidden"):
            entry["hidden"] = True
            entry["assign"] = False
        if mod.get("enrich"):
            entry["enrich"] = mod["enrich"]
        modules_out.append(entry)
    modules_out.sort(
        key=lambda m: (
            parse_addr(m["end"]) - parse_addr(m["start"]),
            parse_addr(m["start"]),
            m["id"],
        )
    )
    return {
        "_meta": {
            "source_gamejson": str(game_path.resolve()),
            "game_id": data.get("game_id") or data.get("_meta", {}).get("rom_id"),
            "exported_by": "assign_modules.py --from-gamejson",
            "match_rule": "smallest fuzzy span first; band fully inside",
        },
        "modules": modules_out,
        "unassigned": {
            "id": "未归类",
            "label": "其它·未归类",
            "group": "其它",
            "default": False,
            "description": "dump 带未完全落入任何模块模糊区间",
        },
    }


def _geo_from_src(src: dict) -> Optional[List[List[str]]]:
    if not src.get("ranges"):
        return None
    geo: List[List[str]] = []
    for r in src["ranges"]:
        if isinstance(r, dict):
            lo, hi = parse_addr(r["start"]), parse_addr(r["end"])
        elif isinstance(r, (list, tuple)) and len(r) >= 2:
            lo, hi = parse_addr(r[0]), parse_addr(r[1])
        else:
            continue
        if hi >= lo:
            geo.append([f"0x{lo:X}", f"0x{hi:X}"])
    return geo or None


def _copy_byte_length_bounds(entry: Dict[str, Any], src: Optional[dict]) -> None:
    """Copy non-empty min_byte_length / max_byte_length from module_map src."""
    if not src:
        return
    for key in ("min_byte_length", "max_byte_length"):
        val = src.get(key)
        if val is None or val == "":
            continue
        try:
            entry[key] = int(val)
        except (TypeError, ValueError):
            continue


def _emit_scan_entry(
    meta: dict,
    bands_out: List[List[str]],
    src: Optional[dict],
) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "label": meta["label"],
        "group": meta["group"],
        "default": meta["default"],
        "description": meta.get("description") or "",
        "type": "scan",
        "read": {"scan_addr_bands": bands_out},
    }
    if bands_out:
        entry["start"] = bands_out[0][0]
    elif src and src.get("start"):
        entry["start"] = src["start"] if isinstance(src["start"], str) else f"0x{parse_addr(src['start']):X}"
    geo = _geo_from_src(src) if src else None
    if geo:
        entry["geo_ranges"] = geo
    # write.relocate / write.replace / write.slot — 默认 true
    write: dict = {}
    write["relocate"] = bool(src["relocate"]) if src and "relocate" in src else True
    write["replace"] = bool(src["replace"]) if src and "replace" in src else True
    write["slot"] = bool(src["slot"]) if src and "slot" in src else True
    entry["write"] = write
    if src is not None and "hook" in src:
        entry["hook"] = bool(src["hook"])
    else:
        entry["hook"] = False
    _copy_byte_length_bounds(entry, src)
    return entry


def _emit_typed_entry(src: dict, bands_out: List[List[str]]) -> Dict[str, Any]:
    """stride / stride_ptr / struct / prefix / needle / pointer — keep map templates."""
    rtype = str(src.get("type") or "scan")
    entry: Dict[str, Any] = {
        "label": src.get("label") or src["id"],
        "group": src.get("group") or "",
        "default": bool(src.get("default", False)),
        "description": src.get("description") or src.get("intro") or "",
        "type": rtype,
    }
    if src.get("hidden"):
        entry["hidden"] = True
    if src.get("enrich"):
        entry["enrich"] = src["enrich"]
    # write.relocate / write.replace / write.slot — 默认 true
    write: dict = {}
    write["relocate"] = bool(src["relocate"]) if "relocate" in src else True
    write["replace"] = bool(src["replace"]) if "replace" in src else True
    write["slot"] = bool(src["slot"]) if "slot" in src else True
    entry["write"] = write
    if "hook" in src:
        entry["hook"] = bool(src["hook"])
    else:
        entry["hook"] = False
    if src.get("start") is not None:
        st = src["start"]
        entry["start"] = st if isinstance(st, str) else f"0x{parse_addr(st):X}"
    if src.get("end") is not None and rtype in ("stride", "stride_ptr", "struct", "ptr_stride"):
        en = src["end"]
        entry["end"] = en if isinstance(en, str) else f"0x{parse_addr(en):X}"

    read = dict(src.get("read") or {})
    if rtype in ("scan", "addr_bands"):
        read["scan_addr_bands"] = bands_out
        if bands_out and "start" not in entry:
            entry["start"] = bands_out[0][0]
    elif rtype in ("prefix", "needle") and bands_out:
        # refresh spatial window from dump if we somehow got bands
        read["scan_addr_bands"] = bands_out
    # strip legacy addr_bands key
    read.pop("addr_bands", None)
    if read:
        entry["read"] = read
    elif rtype in ("scan", "addr_bands"):
        entry["read"] = {"scan_addr_bands": bands_out}

    geo = _geo_from_src(src)
    if geo:
        entry["geo_ranges"] = geo
    _copy_byte_length_bounds(entry, src)
    return entry


def assign_bands(
    bands: Sequence[Tuple[int, int]],
    module_map: dict,
) -> Dict[str, Any]:
    specs: List[dict] = []
    for m in module_map["modules"]:
        if not _module_participates(m):
            continue
        parsed = _parse_ranges(m)
        for lo, hi in parsed:
            specs.append(
                {
                    "id": m["id"],
                    "lo": lo,
                    "hi": hi,
                    "span": hi - lo + 1,
                }
            )
        m["_all_lo"] = min(p[0] for p in parsed)
        m["_all_hi"] = max(p[1] for p in parsed)

    specs.sort(key=lambda s: (s["span"], s["lo"], s["id"]))

    buckets: Dict[str, List[List[str]]] = {m["id"]: [] for m in module_map["modules"]}
    meta_by_id: Dict[str, dict] = {}
    src_by_id: Dict[str, dict] = {m["id"]: m for m in module_map["modules"]}
    for m in module_map["modules"]:
        mid = m["id"]
        meta_by_id[mid] = {
            "id": mid,
            "label": m.get("label") or mid,
            "group": m.get("group") or "",
            "default": bool(m.get("default", False)),
            "description": m.get("description") or m.get("intro") or "",
            "lo": int(m.get("_all_lo") or parse_addr(m.get("start") or 0)),
            "hi": int(m.get("_all_hi") or parse_addr(m.get("end") or 0)),
        }

    unassigned_cfg = module_map.get("unassigned") or {
        "id": "未归类",
        "label": "其它·未归类",
        "group": "其它",
        "default": False,
        "description": "dump 带未完全落入任何模块模糊区间",
    }
    uid = unassigned_cfg["id"]
    buckets[uid] = []
    meta_by_id[uid] = {
        "id": uid,
        "label": unassigned_cfg.get("label") or uid,
        "group": unassigned_cfg.get("group") or "其它",
        "default": bool(unassigned_cfg.get("default", False)),
        "description": unassigned_cfg.get("description")
        or unassigned_cfg.get("intro")
        or "",
        "lo": 0,
        "hi": 0,
    }

    def _append_band(mid: str, lo: int, hi: int) -> None:
        if hi < lo:
            return
        buckets[mid].append([f"0x{lo:X}", f"0x{hi:X}"])

    active_specs = [s for s in specs if not (s["lo"] == 0 and s["hi"] == 0)]

    for bs, be in bands:
        if be < bs:
            bs, be = be, bs
        # Whole-band assign only when no smaller module *partially* overlaps.
        # Otherwise a large catch-all (e.g. 扩展对话库_2A) would swallow a
        # merged dump band and starve nested modules like 图鉴条目.
        full_hits = [
            s for s in active_specs if bs >= s["lo"] and be <= s["hi"]
        ]
        partial_hits = [
            s
            for s in active_specs
            if not (be < s["lo"] or bs > s["hi"])
            and not (bs >= s["lo"] and be <= s["hi"])
        ]
        if full_hits and not partial_hits:
            _append_band(full_hits[0]["id"], bs, be)
            continue
        remaining: List[Tuple[int, int]] = [(bs, be)]
        for s in active_specs:
            nxt: List[Tuple[int, int]] = []
            for rlo, rhi in remaining:
                ilo, ihi = max(rlo, s["lo"]), min(rhi, s["hi"])
                if ilo <= ihi:
                    _append_band(s["id"], ilo, ihi)
                    if rlo < ilo:
                        nxt.append((rlo, ilo - 1))
                    if ihi < rhi:
                        nxt.append((ihi + 1, rhi))
                else:
                    nxt.append((rlo, rhi))
            remaining = nxt
            if not remaining:
                break
        for rlo, rhi in remaining:
            _append_band(uid, rlo, rhi)

    modules_out: Dict[str, Any] = {}
    order = [m["id"] for m in module_map["modules"]]
    if uid not in order:
        order.append(uid)

    for mid in order:
        if mid not in buckets and mid != uid:
            continue
        bands_out = buckets.get(mid) or []
        src = src_by_id.get(mid)
        meta = meta_by_id[mid]

        if mid == uid:
            if not bands_out:
                continue
            modules_out[mid] = _emit_scan_entry(meta, bands_out, None)
            continue

        if src is None:
            continue

        rtype = str(src.get("type") or "scan")
        if not _module_participates(src):
            # hidden / assign:false — emit enrich 模板；其 scan_addr_bands 是
            # 采集搜索窗，不参与 dump 带互斥归属（见 meowth.modules.assign）。
            modules_out[mid] = _emit_typed_entry(src, bands_out)
            continue

        if rtype in ("scan", "addr_bands") or rtype == "":
            if not bands_out and rtype in ("scan", "addr_bands"):
                # keep empty scan module only if map had explicit placeholder
                continue
            modules_out[mid] = _emit_scan_entry(meta, bands_out, src)
        else:
            modules_out[mid] = _emit_typed_entry(src, bands_out)

    stats = {mid: len(buckets.get(mid) or []) for mid in order if mid in buckets}
    return {
        "_meta": {
            "schema": "v3",
            "exported_by": "assign_modules.py",
            "match_rule": (
                "smallest span first; full-band inside, else clip intersection "
                "against ranges (dump merges); hidden/assign:false skipped"
            ),
            "band_count": len(bands),
            "module_band_counts": stats,
            "source_module_map_meta": module_map.get("_meta"),
        },
        "modules": modules_out,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Summarize game.json into *.module_map.json"
    )
    ap.add_argument(
        "--from-gamejson",
        required=True,
        help="existing Meowth game.json or translate/modules.json",
    )
    ap.add_argument(
        "-o",
        "--out",
        required=True,
        help="output *.module_map.json",
    )
    args = ap.parse_args()

    out_path = Path(args.out)
    result = summarize_gamejson_to_map(Path(args.from_gamejson))
    out_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"[ok] module_map {len(result['modules'])} modules -> {out_path}")


if __name__ == "__main__":
    main()
