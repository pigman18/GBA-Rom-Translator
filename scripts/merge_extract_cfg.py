#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merge extract/config.json + modules.inject.json into translate/modules.json (v2 schema).

v2 modules.json layout:
  _meta, scan{script_bank_min,script_text_ptr_opcodes,encoding,trusted_lz_bands},
  policy{reject,allow,content_classes}, modules_defaults, enrich,
  modules{ <id>: {offset,end,addr_bands,..., read, write, line_width} }

The old extract/config.json and modules.inject.json are left untouched for
compat fallback; the loader prefers v2 fields when present.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONFIGS = REPO / "configs"

SCAN_KEYS = ("script_bank_min", "script_text_ptr_opcodes", "encoding", "trusted_lz_bands")
POLICY_KEYS = ("reject", "allow", "content_classes")
INJECT_KEYS = ("read", "write", "layout", "line_width", "chs_stride", "patch_type", "widen_fn")


def merge_game(game_id: str, *, dry_run: bool = False) -> dict:
    base = CONFIGS / game_id
    ec = json.loads((base / "extract/config.json").read_text(encoding="utf-8"))
    mj = json.loads((base / "translate/modules.json").read_text(encoding="utf-8"))
    mi = json.loads((base / "translate/modules.inject.json").read_text(encoding="utf-8"))

    out: dict = {"_meta": dict(mj.get("_meta") or {})}
    out["_meta"]["schema"] = "v2"
    if mi.get("_meta"):
        out["_meta"]["inject_note"] = mi["_meta"].get("note", "")

    scan = {k: ec[k] for k in SCAN_KEYS if k in ec}
    if scan:
        out["scan"] = scan
    pol = {k: ec[k] for k in POLICY_KEYS if k in ec}
    if pol:
        out["policy"] = pol
    if "modules_defaults" in ec:
        out["modules_defaults"] = ec["modules_defaults"]
    if "enrich" in ec:
        out["enrich"] = ec["enrich"]

    mods: dict = {}
    for mid, meta in (mj.get("modules") or {}).items():
        m = dict(meta)
        inj = mi.get(mid)
        if isinstance(inj, dict):
            for k in INJECT_KEYS:
                if k in inj:
                    m[k] = inj[k]
        mods[mid] = m
    out["modules"] = mods

    if not dry_run:
        dst = base / "translate/modules.json"
        shutil.copy2(dst, dst.with_suffix(".json.bak_v1"))
        dst.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[merge] {game_id}: wrote {dst} (schema=v2, modules={len(mods)})")
    else:
        print(f"[merge] {game_id}: dry-run modules={len(mods)}")
    return out


def main() -> int:
    targets = sys.argv[1:] or ["POKEMON_RUBY_AXVJ00", "POKEMON_SAPP_AXPJ00"]
    for gid in targets:
        merge_game(gid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
