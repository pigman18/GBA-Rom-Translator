#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assign_modules.py
=================
把 dump 出的 addr_bands 按「模块地图」归类，生成与 Meowth game.json
``modules`` 同构的 JSON。

匹配规则：从小区间开始（模糊 [start,end] 跨度升序）；dump 带完全落入的模块优先。

模块字段：``default`` / ``offset`` / ``end`` 会写入产出的 ``modules.json``。
``offset``/``end`` 来自 module_map 的 ``start``/``end``（名表闭区间），供 Meowth 推导 count。
``line_width`` 不在 dump 侧；由 Meowth ``translate/modules.inject.json`` 配置（默认 20）。

后缀约定：
  *.addr_bands.json   — dump_addr_bands.py 产物（仅 addr_bands 与 configs 对齐）
  *.module_map.json   — 人工/总结的模糊模块地图（本目录配置）
  *.modules.json      — 本脚本输出（可粘进 game.json 的 modules）

日常请用：python dump_addr_bands.py rom.gba（自动写 addr_bands + modules）。

本脚本仅用于从 game.json 总结 module_map：
  python assign_modules.py --from-gamejson configs/.../game.json -o xxx.module_map.json
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


def summarize_gamejson_to_map(game_path: Path) -> dict:
    """从现有 game.json 总结模糊 module_map（span = min/max of addr_bands）。"""
    data = json.loads(game_path.read_text(encoding="utf-8"))
    modules_out: List[dict] = []
    for mid, mod in (data.get("modules") or {}).items():
        bands = mod.get("addr_bands") or []
        if not bands:
            continue
        lo = min(parse_addr(a) for a, _ in bands)
        hi = max(parse_addr(b) for _, b in bands)
        modules_out.append(
            {
                "id": mid,
                "label": mod.get("label") or mid,
                "group": mod.get("group") or "",
                "default": bool(mod.get("default", False)),
                "description": mod.get("description")
                or f"从 {data.get('game_id', game_path.stem)} 总结；"
                f"原 {len(bands)} 条 addr_bands 的外包络",
                "start": f"0x{lo:X}",
                "end": f"0x{hi:X}",
            }
        )
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
            "game_id": data.get("game_id"),
            "game_code": data.get("game_code"),
            "label": data.get("label"),
            "exported_by": "assign_modules.py --from-gamejson",
            "match_rule": "smallest fuzzy span first; band fully inside",
        },
        "modules": modules_out,
        "unassigned": {
            "id": "未分类",
            "label": "未匹配区间",
            "group": "其他",
            "default": False,
            "description": "dump 带未完全落入任何模块模糊区间",
        },
    }


def assign_bands(
    bands: Sequence[Tuple[int, int]],
    module_map: dict,
) -> Dict[str, Any]:
    specs: List[dict] = []
    for m in module_map["modules"]:
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
            lo = parse_addr(m["start"])
            hi = parse_addr(m["end"])
            if hi < lo:
                raise ValueError(f"module {m.get('id')}: end < start")
            parsed = [(lo, hi)]
        # One matching spec per range (span = that range); same module id
        for lo, hi in parsed:
            specs.append(
                {
                    "id": m["id"],
                    "label": m.get("label") or m["id"],
                    "group": m.get("group") or "",
                    "default": bool(m.get("default", False)),
                    "description": m.get("description") or m.get("intro") or "",
                    "lo": lo,
                    "hi": hi,
                    "span": hi - lo + 1,
                }
            )
        # Remember primary envelope for offset/end (tables / display)
        m["_all_lo"] = min(p[0] for p in parsed)
        m["_all_hi"] = max(p[1] for p in parsed)
    # 小区间优先
    specs.sort(key=lambda s: (s["span"], s["lo"], s["id"]))

    buckets: Dict[str, List[List[str]]] = {m["id"]: [] for m in module_map["modules"]}
    meta_by_id: Dict[str, dict] = {}
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
            "span": 0,
        }
    unassigned_cfg = module_map.get("unassigned") or {
        "id": "未分类",
        "label": "未匹配区间",
        "group": "其他",
        "default": False,
    }
    uid = unassigned_cfg["id"]
    buckets[uid] = []
    meta_by_id[uid] = {
        "id": uid,
        "label": unassigned_cfg.get("label") or uid,
        "group": unassigned_cfg.get("group") or "其他",
        "default": bool(unassigned_cfg.get("default", False)),
        "description": unassigned_cfg.get("description")
        or unassigned_cfg.get("intro")
        or "",
        "lo": 0,
        "hi": 0,
        "span": 0,
    }

    def _append_band(mid: str, lo: int, hi: int) -> None:
        if hi < lo:
            return
        buckets[mid].append([f"0x{lo:X}", f"0x{hi:X}"])

    # Skip inert 0x0..0x0 placeholders so they never steal clips.
    active_specs = [s for s in specs if not (s["lo"] == 0 and s["hi"] == 0)]

    for bs, be in bands:
        if be < bs:
            bs, be = be, bs
        # Prefer whole-band containment (legacy); else clip dump merges against
        # tight ranges so UI pools like 存档与电源 still get addr_bands.
        chosen: Optional[str] = None
        for s in active_specs:
            if bs >= s["lo"] and be <= s["hi"]:
                chosen = s["id"]
                break
        if chosen is not None:
            _append_band(chosen, bs, be)
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
    # stable-ish order: assigned specs by original map order, then unassigned
    order = [m["id"] for m in module_map["modules"]]
    if uid not in order:
        order.append(uid)
    for mid in order:
        if mid not in buckets:
            continue
        bands_out = buckets[mid]
        if not bands_out and mid == uid:
            continue
        meta = meta_by_id[mid]
        entry = {
            "label": meta["label"],
            "group": meta["group"],
            "default": meta["default"],
            "description": meta.get("description") or "",
            "addr_bands": bands_out,
        }
        # Keep configured multi-ranges for Meowth geo (string bands alone miss
        # empty UI pools / nurse slices that lost the contiguous dump merge).
        src = next((m for m in module_map["modules"] if m["id"] == mid), None)
        if src and src.get("ranges"):
            geo = []
            for r in src["ranges"]:
                if isinstance(r, dict):
                    lo, hi = parse_addr(r["start"]), parse_addr(r["end"])
                elif isinstance(r, (list, tuple)) and len(r) >= 2:
                    lo, hi = parse_addr(r[0]), parse_addr(r[1])
                else:
                    continue
                if hi >= lo:
                    geo.append([f"0x{lo:X}", f"0x{hi:X}"])
            if geo:
                entry["geo_ranges"] = geo
        # Table geo from module_map (Meowth inject layout no longer carries offset/count)
        if meta.get("lo"):
            entry["offset"] = int(meta["lo"])
            entry["end"] = int(meta["hi"])
        modules_out[mid] = entry

    stats = {
        mid: len(buckets.get(mid) or [])
        for mid in order
        if mid in buckets
    }
    return {
        "_meta": {
            "exported_by": "assign_modules.py",
            "match_rule": (
                "smallest span first; full-band inside, else clip intersection "
                "against ranges (dump merges)"
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
        help="existing Meowth game.json",
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
