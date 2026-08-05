#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
text_patcher.py
==============
从日版 Gen3 GBA ROM 导出文本 addr_bands，并按 configs/{ROM_ID}.json 归类 modules
（产出 schema v3，与 Meowth translate/modules.json 同构）。

用法：
  python text_patcher.py <rom.gba>                     # 兼容：等同 export
  python text_patcher.py export <rom.gba>              # 全 ROM 密扫 + modules v3
  python text_patcher.py export <rom.gba> --fast       # 指针步长 4
  python text_patcher.py export <rom.gba> --no-update-map
                                                       # 不写回 configs
  python text_patcher.py diff --new <a.json> --ref <b.json>
  python text_patcher.py status <rom.gba> [--ref <ref.json>]
                       [--texts <texts.json>] [--samples N]
  python text_patcher.py classify <rom.gba> --texts <texts.json> --out <suggestions.json>

配置：
  configs/POKEMON_RUBY_AXVJ00.json   ← module_map（发现新空间/模块会追加写回）

输出：
  works/POKEMON_RUBY_AXVJ00/addr_bands.json
  works/POKEMON_RUBY_AXVJ00/modules.json   ← schema v3
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from assign_modules import assign_bands, load_module_map

SUPPORTED = {
    b"AXVJ": "Pokemon Ruby (JP)",
    b"AXPJ": "Pokemon Sapphire (JP)",
    b"BPEJ": "Pokemon Emerald (JP)",
    b"BPRJ": "Pokemon FireRed (JP)",
    b"BPGJ": "Pokemon LeafGreen (JP)",
}

# game_code → 标准 ROM id（与 configs / works 目录名一致）
ROM_ID_BY_CODE = {
    "AXVJ": "POKEMON_RUBY_AXVJ00",
    "AXPJ": "POKEMON_SAPP_AXPJ00",
    "BPRJ": "POKEMON_FIRE_BPRJ00",
    "BPGJ": "POKEMON_LEAF_BPGJ00",
    "BPEJ": "POKEMON_EMERALD_BPEJ00",
}

BASE = 0x08000000
EOS = 0xFF
CTRL = {0xFA, 0xFB, 0xFC, 0xFD, 0xFE, 0xFF}
BODY_LO = 0  # 全 ROM：不再砍掉低址串
MIN_LEN = 2
MAX_LEN = 512
PTR_ALIGN = 4
MERGE_GAP = 0
# module_map 回写：邻接扩 ranges / 未归类聚类成新模块
MAP_ADJACENT_GAP = 0x1000
MAP_CLUSTER_GAP = 0x10000
MAP_CLUSTER_MIN_BANDS = 8
MAP_CLUSTER_MIN_SPAN = 0x2000
UNASSIGNED_ID = "未归类"

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIGS_DIR = SCRIPT_DIR / "configs"
WORKS_DIR = SCRIPT_DIR / "works"
REPO_ROOT = Path(__file__).resolve().parents[2]
# Desktop util 镜像（若存在则与仓库 configs 同步回写）
DESKTOP_CONFIGS_DIR = Path(r"C:\Users\Administrator\Desktop\util\util\configs")

# PCS 控制字节（不参与文本字符）
PCS_CTRL = frozenset([0x00, 0xF7, 0xF8, 0xF9, 0xFA, 0xFB, 0xFC, 0xFD, 0xFE, 0xFF])


# --------------------------------------------------------------------------
# 基础 ROM 扫描（与旧版一致）
# --------------------------------------------------------------------------

def identify(rom: bytes) -> Tuple[bytes, str]:
    if len(rom) < 0xB0:
        raise ValueError("ROM too small")
    code = rom[0xAC:0xB0]
    if code not in SUPPORTED:
        raise ValueError(
            f"Unsupported game code {code!r}; need "
            + ", ".join(k.decode() for k in SUPPORTED)
        )
    return code, SUPPORTED[code]


def resolve_rom_id(rom_path: Path, game_code: str) -> str:
    """优先用已知文件名 stem，否则按 game code 映射。"""
    stem = rom_path.stem
    if stem in ROM_ID_BY_CODE.values():
        return stem
    rid = ROM_ID_BY_CODE.get(game_code)
    if not rid:
        raise ValueError(f"no ROM id for game code {game_code}")
    return rid


def u32(rom: bytes, off: int) -> int:
    return struct.unpack_from("<I", rom, off)[0]


def read_pcs(rom: bytes, start: int, max_len: int = 512) -> Optional[bytes]:
    if start < 0 or start >= len(rom):
        return None
    i = start
    n = len(rom)
    while i < n and i - start < max_len:
        b = rom[i]
        i += 1
        if b == EOS:
            raw = rom[start:i]
            return bytes(raw) if len(raw) >= 2 else None
        if b == 0xFC and i < n:
            i += 1
            continue
        if b == 0xFD and i < n:
            i += 1
            continue
    return None


def pcs_looks_plausible(raw: bytes) -> bool:
    if not raw or raw[-1] != EOS:
        return False
    body = raw[:-1]
    if not body:
        return False
    if body.count(0x00) > len(body) * 0.4:
        return False
    if len(body) >= 8 and len(set(body)) == 1 and body[0] not in CTRL:
        return False
    printable = sum(1 for b in body if b not in CTRL and 0x01 <= b <= 0xF6)
    return (printable / len(body)) >= 0.45


def prev_ok_for_string_start(rom: bytes, so: int) -> bool:
    if so <= 0:
        return True
    prev = rom[so - 1]
    if prev in (0x00, 0xFF, 0xFE, 0xFA, 0xFB, 0xAA, 0xBB):
        return True
    if prev >= 0xF7:
        return True
    return False


def collect_pointer_targets(
    rom: bytes, body_hi: int, *, ptr_step: int = 1
) -> Dict[int, List[int]]:
    """全 ROM 解指针找 PCS 串。默认 ptr_step=1；--fast 用 PTR_ALIGN。"""
    body_hi = min(body_hi, len(rom))
    step = max(1, int(ptr_step))
    hits: Dict[int, List[int]] = {}
    off = 0
    while off + 4 <= len(rom):
        v = u32(rom, off)
        if not (BASE <= v < BASE + len(rom)):
            off += step
            continue
        so = v - BASE
        if not (BODY_LO <= so < body_hi):
            off += step
            continue
        if so <= off < so + 2:
            off += step
            continue
        if not prev_ok_for_string_start(rom, so):
            off += step
            continue
        raw = read_pcs(rom, so, MAX_LEN + 1)
        if raw is None:
            off += step
            continue
        body_len = len(raw) - 1
        if body_len < MIN_LEN or body_len > MAX_LEN:
            off += step
            continue
        if not pcs_looks_plausible(raw):
            off += step
            continue
        hits.setdefault(so, []).append(off)
        off += step
    return hits


def blocks_from_hits(
    rom: bytes, hits: Dict[int, List[int]]
) -> List[Tuple[int, int]]:
    blocks: List[Tuple[int, int]] = []
    for so in sorted(hits):
        raw = read_pcs(rom, so, MAX_LEN + 1)
        if not raw:
            continue
        blocks.append((so, so + len(raw) - 1))
    return blocks


def merge_bands(
    blocks: Sequence[Tuple[int, int]], gap: int
) -> List[Tuple[int, int]]:
    if not blocks:
        return []
    ordered = sorted(blocks)
    out: List[Tuple[int, int]] = []
    cs, ce = ordered[0]
    for s, e in ordered[1:]:
        if s <= ce + 1 + gap:
            ce = max(ce, e)
        else:
            out.append((cs, ce))
            cs, ce = s, e
    out.append((cs, ce))
    return out


def config_path_for(rom_id: str) -> Path:
    return CONFIGS_DIR / f"{rom_id}.json"


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def scan_rom(rom_path: Path, rom_id: str, *, fast: bool = False):
    rom = rom_path.read_bytes()
    code, name = identify(rom)
    game_code = code.decode("ascii")
    ptr_step = PTR_ALIGN if fast else 1
    hits = collect_pointer_targets(rom, body_hi=len(rom), ptr_step=ptr_step)
    blocks = blocks_from_hits(rom, hits)
    bands = merge_bands(blocks, MERGE_GAP)
    return rom, game_code, name, blocks, bands, hits


def scan_table_region(rom: bytes, lo: int, hi: int) -> List[Tuple[int, int]]:
    """固定表区域扫描：按 PCS 串切分，返回 (lo, hi) 闭区间 band 列表。

    - 0xFF (EOS) 结束一个串；串内允许 0xFC/0xFD 换行
    - 0xFA/0xFB/0xFE 视为数据中断（非文本）
    - 用 pcs_looks_plausible 过滤噪声/二进制字段
    """
    out: List[Tuple[int, int]] = []
    i = lo
    n = min(hi, len(rom))
    while i <= n - MIN_LEN:
        b = rom[i]
        if b in CTRL or b == 0x00:
            i += 1
            continue
        j = i
        while j < n and rom[j] != EOS and j - i < MAX_LEN:
            c = rom[j]
            if c in (0xFA, 0xFB, 0xFE):
                break
            j += 1
        if j >= n or rom[j] != EOS or j - i < MIN_LEN:
            i = j + 1 if j < n else n
            continue
        if pcs_looks_plausible(rom[i:j + 1]):
            out.append((i, j))
        i = j + 1
    return out


def inject_table_bands(
    rom: bytes, module_map: dict
) -> List[Tuple[int, int]]:
    """对 config 中 ``table: true`` 的模块，从其 ranges 扫描固定表 band。

    覆盖 dump 指针扫描不到的固定表（物种名/招式名/属性名/特性名/道具名/
    训练家类名/特性说明）。返回的 band 可能与 dump band 重叠，调用方自行去重。
    """
    extra: List[Tuple[int, int]] = []
    for m in module_map.get("modules") or []:
        if not m.get("table"):
            continue
        ranges = m.get("ranges")
        segs: List[Tuple[int, int]] = []
        if ranges:
            for r in ranges:
                if isinstance(r, dict):
                    segs.append((parse_addr(r["start"]), parse_addr(r["end"])))
                elif isinstance(r, (list, tuple)) and len(r) >= 2:
                    segs.append((parse_addr(r[0]), parse_addr(r[1])))
        else:
            segs.append(
                (parse_addr(m.get("start") or 0), parse_addr(m.get("end") or 0))
            )
        for lo, hi in segs:
            if lo > 0 and hi > lo:
                extra.extend(scan_table_region(rom, lo, hi))
    return extra


def subtract_bands(
    bands: Sequence[Tuple[int, int]],
    remove: Sequence[Tuple[int, int]],
) -> List[Tuple[int, int]]:
    """从 bands 中去掉与 remove 中任一区间重叠的部分（保持 dump band 不变）。"""
    if not bands or not remove:
        return list(bands)
    others = sorted(remove)
    out: List[Tuple[int, int]] = []
    for bs, be in bands:
        segs = [(bs, be)]
        for os_, oe in others:
            nxt: List[Tuple[int, int]] = []
            for slo, shi in segs:
                ilo, ihi = max(slo, os_), min(shi, oe)
                if ilo <= ihi:
                    if slo < ilo:
                        nxt.append((slo, ilo - 1))
                    if ihi < shi:
                        nxt.append((ihi + 1, shi))
                else:
                    nxt.append((slo, shi))
            segs = nxt
            if not segs:
                break
        out.extend(segs)
    return out


def apply_table_inject(
    rom: bytes,
    bands: List[Tuple[int, int]],
    module_map: dict,
) -> List[Tuple[int, int]]:
    """把 config 中 table:true 模块扫描出的固定表 band 合并进 dump bands。"""
    extra = inject_table_bands(rom, module_map)
    if extra:
        extra = subtract_bands(extra, bands)
        if extra:
            bands = sorted(bands + extra)
    return bands


def export(
    rom_path: Path,
    rom_id: str,
    *,
    fast: bool = False,
    update_map: bool = True,
) -> Tuple[Path, dict]:
    rom, game_code, name, blocks, bands, hits = scan_rom(
        rom_path, rom_id, fast=fast
    )
    work_dir = WORKS_DIR / rom_id
    bands_path = work_dir / "addr_bands.json"
    bands_doc = {
        "_meta": {
            "rom_id": rom_id,
            "source_rom_path": str(rom_path.resolve()),
            "source_rom": name,
            "game_code": game_code,
            "address_space": "file_offset",
            "string_blocks": len(blocks),
            "band_count": len(bands),
            "ptr_backed_starts": len(hits),
            "ptr_step": PTR_ALIGN if fast else 1,
            "exported_by": "text_patcher.py",
        },
        "addr_bands": [[f"0x{s:08X}", f"0x{e:08X}"] for s, e in bands],
    }
    write_json(bands_path, bands_doc)
    print(f"[ok] {len(blocks)} strings -> {len(bands)} addr_bands -> {bands_path}")

    map_path = config_path_for(rom_id)
    modules_path = work_dir / "modules.json"
    if not map_path.is_file():
        print(
            f"[!] missing config {map_path}; skip modules.json "
            f"(copy configs/_template.json -> configs/{rom_id}.json)",
            file=sys.stderr,
        )
        return bands_path, {}

    mmap = load_module_map(map_path)
    bands = apply_table_inject(rom, bands, mmap)
    result = assign_bands(bands, mmap)
    result["_meta"]["rom_id"] = rom_id
    result["_meta"]["source_rom_path"] = str(rom_path.resolve())
    result["_meta"]["game_code"] = game_code
    result["_meta"]["module_map"] = str(map_path.resolve())
    result["_meta"]["exported_by"] = "text_patcher.py"

    if update_map:
        n_exp, n_add = update_module_map_from_result(map_path, result, rom_id)
        print(f"[ok] module_map writeback: expanded {n_exp} ranges, added {n_add} modules")
        if n_exp or n_add:
            # re-assign so works/modules.json reflects updated map
            mmap = load_module_map(map_path)
            result = assign_bands(bands, mmap)
            result["_meta"]["rom_id"] = rom_id
            result["_meta"]["source_rom_path"] = str(rom_path.resolve())
            result["_meta"]["game_code"] = game_code
            result["_meta"]["module_map"] = str(map_path.resolve())
            result["_meta"]["exported_by"] = "text_patcher.py"
            result["_meta"]["map_writeback"] = {
                "expanded_ranges": n_exp,
                "added_modules": n_add,
            }

    write_json(modules_path, result)
    sync_modules_to_product(rom_id, modules_path)

    counts = result["_meta"]["module_band_counts"]
    nonempty = sum(1 for v in counts.values() if v)
    print(f"[ok] modules ({nonempty} nonempty) via {map_path.name} -> {modules_path}")
    return modules_path, result


def sync_modules_to_product(rom_id: str, modules_path: Path) -> Path | None:
    """Copy generated works/modules.json to configs/<rom_id>/translate/modules.json."""
    dest = REPO_ROOT / "configs" / rom_id / "translate" / "modules.json"
    if not modules_path.is_file():
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(modules_path.read_bytes())
    print(f"[ok] synced modules -> {dest}")
    return dest


# --------------------------------------------------------------------------
# modules.json 读写（v3: read.scan_addr_bands；兼容顶层 addr_bands）
# --------------------------------------------------------------------------

def parse_addr(v: object) -> int:
    if isinstance(v, int):
        return v
    s = str(v).strip()
    return int(s, 16) if s.lower().startswith("0x") else int(s, 0)


def entry_scan_bands(entry: dict) -> List[Tuple[int, int]]:
    read = entry.get("read") or {}
    bands = (
        read.get("scan_addr_bands")
        or read.get("addr_bands")
        or entry.get("addr_bands")
        or []
    )
    out: List[Tuple[int, int]] = []
    for pair in bands:
        if isinstance(pair, (list, tuple)) and len(pair) >= 2:
            out.append((parse_addr(pair[0]), parse_addr(pair[1])))
    return out


def load_modules(path: Path) -> Tuple[dict, Dict[str, List[Tuple[int, int]]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    mods = data.get("modules") or {}
    out: Dict[str, List[Tuple[int, int]]] = {}
    for mid, entry in mods.items():
        out[mid] = entry_scan_bands(entry)
    return data, out


def band_list(bands: Sequence[Tuple[int, int]]) -> List[List[str]]:
    return [[f"0x{lo:X}", f"0x{hi:X}"] for lo, hi in sorted(bands)]


# --------------------------------------------------------------------------
# module_map 回写：扩 ranges / 追加新模块
# --------------------------------------------------------------------------

def _map_module_participates(m: dict) -> bool:
    if m.get("assign") is False:
        return False
    if m.get("hidden"):
        return False
    return True


def _is_auto_catchall_module(mid: str) -> bool:
    """Plan-era dump catch-alls: 自动区_* / 扩展对话库_* / 地图脚本对话."""
    if mid.startswith("自动区_"):
        return True
    if mid.startswith("扩展对话库_"):
        return True
    if mid == "地图脚本对话":
        return True
    return False


def _map_segs(m: dict) -> List[Tuple[int, int]]:
    ranges = m.get("ranges")
    segs: List[Tuple[int, int]] = []
    if ranges:
        for r in ranges:
            if isinstance(r, dict):
                segs.append((parse_addr(r["start"]), parse_addr(r["end"])))
            elif isinstance(r, (list, tuple)) and len(r) >= 2:
                segs.append((parse_addr(r[0]), parse_addr(r[1])))
    if not segs:
        segs.append(
            (parse_addr(m.get("start") or 0), parse_addr(m.get("end") or 0))
        )
    return [(a, b) for a, b in segs if b >= a and not (a == 0 and b == 0)]


def _merge_seg_into_module(m: dict, lo: int, hi: int) -> bool:
    """Merge [lo,hi] into module ranges/envelope. Return True if changed."""
    segs = _map_segs(m)
    if not segs:
        m["start"] = f"0x{lo:X}"
        m["end"] = f"0x{hi:X}"
        return True
    # try merge into adjacent segment
    changed = False
    merged: List[Tuple[int, int]] = []
    placed = False
    for a, b in sorted(segs):
        if placed:
            merged.append((a, b))
            continue
        if hi < a - MAP_ADJACENT_GAP - 1:
            merged.append((lo, hi))
            merged.append((a, b))
            placed = True
            changed = True
            continue
        if lo > b + MAP_ADJACENT_GAP + 1:
            merged.append((a, b))
            continue
        # adjacent / overlap
        na, nb = min(a, lo), max(b, hi)
        if na != a or nb != b:
            changed = True
        merged.append((na, nb))
        placed = True
    if not placed:
        merged.append((lo, hi))
        changed = True
    # coalesce merged list
    merged.sort()
    out: List[Tuple[int, int]] = []
    for a, b in merged:
        if not out:
            out.append((a, b))
            continue
        pa, pb = out[-1]
        if a <= pb + MAP_ADJACENT_GAP + 1:
            out[-1] = (pa, max(pb, b))
        else:
            out.append((a, b))
    final = out
    env_lo = min(a for a, _ in final)
    env_hi = max(b for _, b in final)
    old_env = (parse_addr(m.get("start") or 0), parse_addr(m.get("end") or 0))
    m["start"] = f"0x{env_lo:X}"
    m["end"] = f"0x{env_hi:X}"
    if len(final) == 1 and not m.get("ranges"):
        if old_env != (env_lo, env_hi):
            changed = True
        return changed
    m["ranges"] = [{"start": f"0x{a:X}", "end": f"0x{b:X}"} for a, b in final]
    return changed


def _cluster_bands(
    bands: Sequence[Tuple[int, int]], gap: int
) -> List[Tuple[int, int, int]]:
    """Return clusters as (lo, hi, band_count)."""
    if not bands:
        return []
    ordered = sorted(bands)
    out: List[List[int]] = []
    for lo, hi in ordered:
        if not out or lo > out[-1][1] + gap:
            out.append([lo, hi, 1])
        else:
            out[-1][1] = max(out[-1][1], hi)
            out[-1][2] += 1
    return [(a, b, n) for a, b, n in out]


def _best_named_for_seg(
    lo: int,
    hi: int,
    named: Sequence[dict],
) -> Optional[dict]:
    """Smallest-span named module that overlaps or is within MAP_ADJACENT_GAP."""
    hits: List[Tuple[int, dict]] = []
    for m in named:
        for a, b in _map_segs(m):
            if hi < a - MAP_ADJACENT_GAP - 1 or lo > b + MAP_ADJACENT_GAP + 1:
                continue
            span = b - a + 1
            hits.append((span, m))
            break
    if not hits:
        return None
    hits.sort(key=lambda t: (t[0], t[1]["id"]))
    return hits[0][1]


def _nearest_named_for_seg(
    lo: int,
    hi: int,
    named: Sequence[dict],
) -> Optional[dict]:
    """Nearest named module by address distance (0 if overlap); then smallest span."""
    best: Optional[Tuple[int, int, str, dict]] = None
    for m in named:
        segs = _map_segs(m)
        if not segs:
            continue
        dist = min(
            0
            if not (hi < a or lo > b)
            else (a - hi if hi < a else lo - b)
            for a, b in segs
        )
        span = min(b - a + 1 for a, b in segs)
        key = (dist, span, m["id"], m)
        if best is None or key[:3] < best[:3]:
            best = key
    return best[3] if best else None


def _named_by_id(named: Sequence[dict], mid: str) -> Optional[dict]:
    for m in named:
        if m["id"] == mid:
            return m
    return None


def absorb_unassigned_bands_into_named(
    mmap: dict,
    un_bands: Sequence[Tuple[int, int]],
) -> Tuple[dict, int]:
    """Expand existing named module ranges to cover 未归类 bands.

    - Prefer adjacent/overlapping (small span).
    - Else nearest module by address; low-ROM and far clusters prefer 高风险混杂
      when present (default:false), so we change addresses without creating new ids.
    """
    mods: List[dict] = [
        m for m in (mmap.get("modules") or []) if not _is_auto_catchall_module(m["id"])
    ]
    named = [m for m in mods if _map_module_participates(m)]
    risky = _named_by_id(named, "高风险混杂")
    expanded = 0

    for lo, hi in sorted(un_bands):
        if hi < lo:
            lo, hi = hi, lo
        target = _best_named_for_seg(lo, hi, named)
        if target is None:
            # 低址或离现有模块很远：优先高风险混杂（可改地址、默认不勾）
            near = _nearest_named_for_seg(lo, hi, named)
            if risky is not None and (hi < 0x100000 or near is None):
                target = risky
            elif near is not None:
                # 距离过大也进高风险，避免把 0x67xxxx 整坨并进剧情小模块
                segs = _map_segs(near)
                dist = min(
                    0
                    if not (hi < a or lo > b)
                    else (a - hi if hi < a else lo - b)
                    for a, b in segs
                )
                if risky is not None and dist > MAP_CLUSTER_GAP:
                    target = risky
                else:
                    target = near
            elif risky is not None:
                target = risky
            else:
                continue
        if _merge_seg_into_module(target, lo, hi):
            expanded += 1

    mmap = dict(mmap)
    mmap["modules"] = mods
    meta = dict(mmap.get("_meta") or {})
    meta["last_absorb_unassigned"] = {
        "bands": len(un_bands),
        "expanded": expanded,
        "by": "text_patcher.absorb_unassigned_bands_into_named",
    }
    mmap["_meta"] = meta
    return mmap, expanded


def fold_auto_modules_into_named(mmap: dict) -> Tuple[dict, int, int]:
    """Merge auto catch-all ranges into adjacent named modules; drop auto ids.

    Returns (updated_map, expanded_count, removed_count).
    Segments with no adjacent named module are dropped (→ 未归类 on next assign).
    Low-ROM auto blobs (hi < 0x100000) are never merged into named modules.
    """
    mods: List[dict] = list(mmap.get("modules") or [])
    autos = [m for m in mods if _is_auto_catchall_module(m["id"])]
    named = [
        m
        for m in mods
        if _map_module_participates(m) and not _is_auto_catchall_module(m["id"])
    ]
    expanded = 0
    for auto in autos:
        for lo, hi in _map_segs(auto):
            # 低址代码/数据海：不并入剧情模块，删除后进未归类
            if hi < 0x100000:
                continue
            target = _best_named_for_seg(lo, hi, named)
            if target is None:
                continue
            if _merge_seg_into_module(target, lo, hi):
                expanded += 1
    kept = [m for m in mods if not _is_auto_catchall_module(m["id"])]
    removed = len(mods) - len(kept)
    mmap = dict(mmap)
    mmap["modules"] = kept
    meta = dict(mmap.get("_meta") or {})
    meta["last_fold_autos"] = {
        "expanded_into_named": expanded,
        "removed_modules": removed,
        "by": "text_patcher.fold_auto_modules_into_named",
    }
    mmap["_meta"] = meta
    return mmap, expanded, removed


def update_module_map_from_result(
    map_path: Path,
    result: dict,
    rom_id: str,
) -> Tuple[int, int]:
    """Expand ranges on existing named modules only. Never create 自动区_*.

    Returns (expanded, added) where added is always 0.
    """
    mmap = load_module_map(map_path)
    # Drop any leftover auto catch-alls if still present
    mmap, fold_exp, fold_rm = fold_auto_modules_into_named(mmap)
    mods: List[dict] = list(mmap.get("modules") or [])
    by_id = {m["id"]: m for m in mods}
    expanded = fold_exp
    added = 0

    # 1) Expand existing modules when their assigned bands sit just outside envelope
    for mid, entry in (result.get("modules") or {}).items():
        if mid == UNASSIGNED_ID or _is_auto_catchall_module(mid):
            continue
        m = by_id.get(mid)
        if not m or not _map_module_participates(m):
            continue
        rtype = str(m.get("type") or entry.get("type") or "scan")
        if rtype not in ("scan", "addr_bands", ""):
            continue
        for lo, hi in entry_scan_bands(entry):
            segs = _map_segs(m)
            if any(lo >= a and hi <= b for a, b in segs):
                continue
            if any(
                not (hi < a - MAP_ADJACENT_GAP - 1 or lo > b + MAP_ADJACENT_GAP + 1)
                for a, b in segs
            ):
                if _merge_seg_into_module(m, lo, hi):
                    expanded += 1

    # 2) 未归类：改已有模块地址 ranges 吃掉（不新建自动区_*）
    un_entry = (result.get("modules") or {}).get(UNASSIGNED_ID) or {}
    un_bands = entry_scan_bands(un_entry)
    if un_bands:
        mmap, n_abs = absorb_unassigned_bands_into_named(mmap, un_bands)
        mods = list(mmap.get("modules") or [])
        expanded += n_abs

    if expanded or fold_rm:
        mmap["modules"] = mods
        meta = mmap.setdefault("_meta", {})
        meta["last_writeback"] = {
            "rom_id": rom_id,
            "expanded_ranges": expanded,
            "added_modules": added,
            "removed_auto_modules": fold_rm,
            "by": "text_patcher.py",
        }
        text = json.dumps(mmap, indent=2, ensure_ascii=False) + "\n"
        map_path.write_text(text, encoding="utf-8")
        mirrors: List[Path] = []
        if CONFIGS_DIR.resolve() != DESKTOP_CONFIGS_DIR.resolve():
            if DESKTOP_CONFIGS_DIR.is_dir():
                mirrors.append(DESKTOP_CONFIGS_DIR / map_path.name)
        repo_cfg = REPO_ROOT / "src" / "util" / "configs" / map_path.name
        if repo_cfg.resolve() != map_path.resolve() and repo_cfg.parent.is_dir():
            mirrors.append(repo_cfg)
        for mp in mirrors:
            try:
                mp.write_text(text, encoding="utf-8")
                print(f"[ok] mirrored module_map -> {mp}")
            except OSError as exc:
                print(f"[!] mirror failed {mp}: {exc}", file=sys.stderr)

    return expanded, added

# --------------------------------------------------------------------------
# diff
# --------------------------------------------------------------------------

def cmd_diff(new_path: Path, ref_path: Path) -> int:
    _, new_mods = load_modules(new_path)
    _, ref_mods = load_modules(ref_path)

    mids = sorted(set(new_mods) | set(ref_mods))
    regress = []
    print(f"{'module':<14} {'ref':>5} {'new':>5} {'+add':>5} {'-del':>5}")
    print("-" * 44)
    for mid in mids:
        ref = ref_mods.get(mid, [])
        new = new_mods.get(mid, [])
        rs, ns = set(ref), set(new)
        added = sorted(ns - rs)
        removed = sorted(rs - ns)
        rc, nc = len(ref), len(new)
        flag = ""
        if mid == UNASSIGNED_ID:
            # 未归类计数下降是精确归类导致的预期结果，不视为回归
            pass
        elif rc > 0 and nc == 0:
            flag = "  <<< EMPTY"
        elif nc < rc:
            flag = "  <<< REGRESS"
        if flag:
            regress.append((mid, rc, nc))
        print(
            f"{mid:<14} {rc:>5} {nc:>5} {len(added):>5} {len(removed):>5}{flag}"
        )
        for a, b in removed[:8]:
            print(f"      - {mid} 0x{a:X}-0x{b:X}")
        if len(removed) > 8:
            print(f"      ... and {len(removed) - 8} more removed")
    print("-" * 44)
    if regress:
        print("[FAIL] regression detected:")
        for mid, rc, nc in regress:
            print(f"  - {mid}: ref={rc} new={nc}")
        return 1
    print("[PASS] no module emptied and no module count decreased")
    return 0


# --------------------------------------------------------------------------
# 解码（由 texts 条目推导 byte→字符 表）
# --------------------------------------------------------------------------

def _parse_hex(hx: str) -> List[int]:
    out = []
    for x in (hx or "").split():
        try:
            out.append(int(x, 16))
        except ValueError:
            pass
    return out


def build_charmap(entries: Sequence[dict]) -> Dict[int, str]:
    """从 extract 条目的 original_hex/original 推导单字节→字符 表。"""
    votes: Dict[int, Counter] = defaultdict(Counter)
    for e in entries:
        hx = _parse_hex(e.get("original_hex") or "")
        orig = e.get("original") or ""
        ci = 0
        for b in hx:
            if b in PCS_CTRL:
                continue
            if ci >= len(orig):
                break
            ch = orig[ci]
            ci += 1
            if ch:
                votes[b][ch] += 1
    return {b: cnt.most_common(1)[0][0] for b, cnt in votes.items()}


def decode_band(rom: bytes, lo: int, hi: int, cm: Dict[int, str]) -> str:
    out = []
    i = lo
    n = min(hi + 1, len(rom))
    while i < n:
        b = rom[i]
        i += 1
        if b in (0xFA, 0xFB, 0xFC, 0xFD, 0xFE, 0xFF):
            out.append(f"[{b:02X}]")
        elif b == 0xF7:
            out.append("[F7]")
        elif b in cm:
            out.append(cm[b])
        else:
            out.append(f"?{b:02X}")
    return "".join(out)


# --------------------------------------------------------------------------
# status
# --------------------------------------------------------------------------

def cmd_status(
    rom_path: Path,
    rom_id: str,
    ref_path: Optional[Path],
    texts_path: Optional[Path],
    samples: int,
) -> int:
    rom, game_code, name, blocks, bands, _hits = scan_rom(rom_path, rom_id)
    map_path = config_path_for(rom_id)
    if not map_path.is_file():
        print(f"[!] missing config {map_path}", file=sys.stderr)
        return 1
    mmap = load_module_map(map_path)
    result = assign_bands(apply_table_inject(rom, bands, mmap), mmap)
    counts = result["_meta"]["module_band_counts"]
    ref_counts = None
    if ref_path and ref_path.is_file():
        _, ref_mods = load_modules(ref_path)
        ref_counts = {mid: len(b) for mid, b in ref_mods.items()}

    mids = sorted(counts)
    print(f"{'module':<14} {'new':>5}" + (f" {'ref':>5}" if ref_counts else "") )
    print("-" * 30)
    for mid in mids:
        if ref_counts is None:
            print(f"{mid:<14} {counts[mid]:>5}")
        else:
            rc = ref_counts.get(mid, 0)
            nc = counts[mid]
            flag = ""
            if rc > 0 and nc == 0:
                flag = "  <<< EMPTY"
            elif nc < rc:
                flag = "  <<< REGRESS"
            print(f"{mid:<14} {nc:>5} {rc:>5}{flag}")

    un = entry_scan_bands(result["modules"].get("未归类") or {})
    print(f"\n未归类 bands: {len(un)}")
    if samples > 0:
        cm = None
        if texts_path and texts_path.is_file():
            tdata = json.loads(texts_path.read_text(encoding="utf-8"))
            cm = build_charmap(tdata.get("entries") or [])
        print("decoded preview (first %d):" % samples)
        for lo, hi in un[:samples]:
            text = decode_band(rom, lo, hi, cm) if cm else "(no --texts)"
            print(f"  0x{lo:X}-0x{hi:X} | {text[:80]}")
    return 0


# --------------------------------------------------------------------------
# classify
# --------------------------------------------------------------------------

# lexicon 文件 → 候选模块
LEXICON_MODULES = {
    "招式.json": ["招式名", "招式说明"],
    "道具.json": ["道具名", "道具说明"],
    "特性.json": ["特性名", "特性说明"],
    "性格.json": ["性格名"],
    "属性.json": ["属性名"],
    "地点.json": ["地点名", "道路与洞窟"],
    "图鉴.json": ["图鉴条目", "图鉴界面"],
    "界面短标.json": ["标题与主菜单", "背包界面", "开始菜单", "状态界面", "设置选项"],
}

# 模块 → 强特征关键词（去空白后子串匹配；越靠前越强）
KEYWORD_RULES: List[Tuple[str, List[str]]] = [
    ("存档与电源", [
        "でんげんをきらない", "ポケモンレポート", "レポートをかきこみ",
        "バックアップ", "カートリッジ", "リセット", "きえてしまう", "じかん",
    ]),
    ("商店", [
        "いらっしゃいませ", "ごようきょう", "ひろい ほんてん", "まいど",
        "またのごりよう", "おきにいり", "なにか おさがし", "どうぞ",
        "きにいって", "かいますか", "うりますか", "かわないよ",
    ]),
    ("宝可梦中心", [
        "ずいぶん げんきが ない", "けがは なおった", "ゆっくり やすんで",
        "ポケモンセンター", "おつかれさまでした", "またの ごりようを",
        "なおして", "じゅもん", "おいきり ちからのみ",
    ]),
    ("电脑与仓库", [
        "パソコン", "ボックス", "あずける", "ひきだす", "そろえる",
        "いどう", "とじる", "ようきの けいさん",
    ]),
    ("缆线与通信", [
        "つうしん", "でんわ", "あいでんてぃ", "きおく", "いんたーねっと",
        "つうしんたいせん", "おくりもの", "もらう",
    ]),
    ("战斗报文", [
        "こうげき", "ぼうぎょ", "めいちゅう", "ばつぐん", "こうかは いまひとつ",
        "いみを なさない", "きめた", "まもりを かためた", "はやくなった",
        "はやさが", "つよくなった", "わるくなった", "の こうげき",
    ]),
    ("登场与胜负白", [
        "しょうぶ", "たおした", "まけた", "たたかう", "せんとう",
        "みごと", "しょうり", "ちからを あわせて",
    ]),
    ("图鉴界面", [
        "ずかん", "けんさく", "みずから", "モード", "エリア",
    ]),
    ("训练家类名", [
        "トレーナー", "ジムリーダー", "エリート", "ビューティ", "やまおとこ",
        "キャンプボーイ", "たんパンこぞう", "ミニスカート", "かいパンやろう",
        "サイキッカー", "たびびと", "ふたごちゃん", "スイマー",
    ]),
    ("岛屿或通关后", [
        "とうなんのしま", "さいごの しま", "チャンピオン", "バトルフロンティア",
        "かんとう", "ジョウト",
    ]),
    ("标准脚本串", [
        "じゅんびは いいですか", "それで いいですか", "〜を つかう",
        "を みつけた", "をもらった", "はいけません",
    ]),
    ("标题与主菜单", [
        "さいしょから はじめる", "つづきから はじめる", "オプション",
        "せってい", "けってい", "はい", "いいえ",
    ]),
    ("背包界面", [
        "バッグ", "にもつ", "どうぐ", "せつめい", "つかう", "いれる",
        "すてる", "たかさ", "ひろい", "せいとん",
    ]),
    ("开始菜单", [
        "ずかん", "ポケモン", "セーブ", "にげる", "メニュー", "しゅうり",
    ]),
    ("状态界面", [
        "ステータス", "なまえ", "せいかく", "とくせい", "もちもの",
        "つよさ", "レベル", "タイプ",
    ]),
    ("设置选项", [
        "テキスト", "はやさ", "せってい", "ふつう", "おそい", "はやい",
        "こうかん", "ぴんく", "いろ",
    ]),
    ("姓名输入", [
        "ひらがな", "カタカナ", "えいご", "きごう", "まちがい",
    ]),
    ("赛事娱乐", [
        "コンテスト", "ビューティ", "かっこよさ", "かわいさ", "かしこさ",
        "ポケモンコンテスト", "エントリー",
    ]),
    ("对战设施", [
        "バトルタワー", "たんぱつ", "フロア", "れんしょう", "かいだん",
    ]),
]


def load_lexicons(rom_id: str) -> Dict[str, dict]:
    lex_dir = REPO_ROOT / "configs" / rom_id / "translate" / "lexicon"
    out: Dict[str, dict] = {}
    if lex_dir.is_dir():
        for p in sorted(lex_dir.glob("*.json")):
            out[p.name] = json.loads(p.read_text(encoding="utf-8"))
    return out


def classify_band(
    text: str,
    cm: Dict[int, str],
    lexicons: Dict[str, dict],
) -> List[Tuple[str, str, int]]:
    """返回 [(module, reason, score)]，score 3=精确/强 2=前缀 1=子串/关键词。"""
    compact = re.sub(r"\s", "", text)
    hits: Dict[str, Tuple[str, int]] = {}

    for fname, mods in LEXICON_MODULES.items():
        lex = lexicons.get(fname)
        if not lex:
            continue
        for jp, _zh in lex.items():
            jc = re.sub(r"\s", "", str(jp))
            if not jc:
                continue
            if compact == jc:
                for m in mods:
                    hits.setdefault(m, ("lexicon-exact", 3))
                break
            if compact.startswith(jc):
                for m in mods:
                    hits.setdefault(m, ("lexicon-prefix", 2))
                continue
            if jc in compact:
                for m in mods:
                    hits.setdefault(m, ("lexicon-substr", 1))

    for mid, kws in KEYWORD_RULES:
        for kw in kws:
            kc = re.sub(r"\s", "", kw)
            if kc and kc in compact:
                hits.setdefault(mid, ("keyword", 2))
                break

    return sorted(hits.items(), key=lambda x: (-x[1][1], x[0]))


def cmd_classify(rom_path: Path, rom_id: str, texts_path: Path, out_path: Path) -> int:
    rom, game_code, name, blocks, bands, _hits = scan_rom(rom_path, rom_id)
    map_path = config_path_for(rom_id)
    if not map_path.is_file():
        print(f"[!] missing config {map_path}", file=sys.stderr)
        return 1
    mmap = load_module_map(map_path)
    result = assign_bands(apply_table_inject(rom, bands, mmap), mmap)
    un = entry_scan_bands(result["modules"].get(UNASSIGNED_ID) or {})

    tdata = json.loads(texts_path.read_text(encoding="utf-8"))
    cm = build_charmap(tdata.get("entries") or [])
    lexicons = load_lexicons(rom_id)

    suggestions = []
    n_cand = 0
    for lo, hi in un:
        text = decode_band(rom, lo, hi, cm)
        cands = classify_band(text, cm, lexicons)
        if cands:
            n_cand += 1
        suggestions.append(
            {
                "band": [f"0x{lo:X}", f"0x{hi:X}"],
                "text": text,
                "candidates": [
                    {"module": m, "reason": r, "score": s} for m, (r, s) in cands
                ],
            }
        )

    doc = {
        "_meta": {
            "rom_id": rom_id,
            "source_rom_path": str(rom_path.resolve()),
            "texts_source": str(texts_path.resolve()),
            "module_map": str(map_path.resolve()),
            "unassigned_count": len(un),
            "bands_with_candidates": n_cand,
            "exported_by": "text_patcher.py classify",
        },
        "suggestions": suggestions,
    }
    write_json(out_path, doc)
    print(
        f"[ok] {len(un)} unassigned bands; {n_cand} with candidates -> {out_path}"
    )
    return 0


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="text_patcher: export/diff/status/classify")
    sub = ap.add_subparsers(dest="cmd")

    p_export = sub.add_parser("export", help="导出 addr_bands + modules.json")
    p_export.add_argument("rom", type=Path)
    p_export.add_argument(
        "--fast",
        action="store_true",
        help="指针扫描步长 4（更快，覆盖略少）",
    )
    p_export.add_argument(
        "--no-update-map",
        action="store_true",
        help="不把新空间/新模块写回 configs/{ROM_ID}.json",
    )

    p_diff = sub.add_parser("diff", help="对比两个 modules.json（回归检测）")
    p_diff.add_argument("--new", required=True, type=Path)
    p_diff.add_argument("--ref", required=True, type=Path)

    p_status = sub.add_parser("status", help="覆盖表 + 未归类解码预览")
    p_status.add_argument("rom", type=Path)
    p_status.add_argument("--ref", type=Path, default=None)
    p_status.add_argument("--texts", type=Path, default=None)
    p_status.add_argument("--samples", type=int, default=0)

    p_classify = sub.add_parser("classify", help="未归类 band 分类建议")
    p_classify.add_argument("rom", type=Path)
    p_classify.add_argument("--texts", type=Path, default=None)
    p_classify.add_argument("--out", type=Path, required=True)

    args = ap.parse_args()

    if args.cmd is None:
        # 兼容旧用法：python text_patcher.py <rom.gba>
        if len(sys.argv) == 2 and not sys.argv[1].startswith("-"):
            rom_path = Path(sys.argv[1])
            if not rom_path.is_file():
                print(f"[x] not found: {rom_path}", file=sys.stderr)
                sys.exit(1)
            code, _ = identify(rom_path.read_bytes())
            rom_id = resolve_rom_id(rom_path, code.decode("ascii"))
            export(rom_path, rom_id)
            sys.exit(0)
        ap.print_help(sys.stderr)
        sys.exit(1)

    if args.cmd == "export":
        if not args.rom.is_file():
            print(f"[x] not found: {args.rom}", file=sys.stderr)
            sys.exit(1)
        code, _ = identify(args.rom.read_bytes())
        rom_id = resolve_rom_id(args.rom, code.decode("ascii"))
        export(
            args.rom,
            rom_id,
            fast=bool(args.fast),
            update_map=not bool(args.no_update_map),
        )
    elif args.cmd == "diff":
        sys.exit(cmd_diff(args.new, args.ref))
    elif args.cmd == "status":
        if not args.rom.is_file():
            print(f"[x] not found: {args.rom}", file=sys.stderr)
            sys.exit(1)
        code, _ = identify(args.rom.read_bytes())
        rom_id = resolve_rom_id(args.rom, code.decode("ascii"))
        sys.exit(cmd_status(args.rom, rom_id, args.ref, args.texts, args.samples))
    elif args.cmd == "classify":
        if not args.rom.is_file():
            print(f"[x] not found: {args.rom}", file=sys.stderr)
            sys.exit(1)
        code, _ = identify(args.rom.read_bytes())
        rom_id = resolve_rom_id(args.rom, code.decode("ascii"))
        if args.texts is None:
            default = REPO_ROOT / "work" / "texts_translated.json"
            args.texts = default
        sys.exit(cmd_classify(args.rom, rom_id, args.texts, args.out))
    else:
        ap.print_help(sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
