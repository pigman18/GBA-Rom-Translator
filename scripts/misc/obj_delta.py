#!/usr/bin/env python3
"""用「玩家坐标 vs object 坐标」的差值，定出两者坐标系的关系。

── 为什么要这一步 ──────────────────────────────────────────────────────
gym_dewford 帧实测：
  玩家 SaveBlock1.pos = (8,15)
  object 表里 obj[1]   = (8,17)
截图（warp 到 (8,18) 后）显示 NPC 在主角**正下方一格**，
即视觉上 NPC 在玩家原位置 (8,15) 的**下方 2 格** = (8,17)。
⇒ **object 坐标与 SaveBlock1.pos 是同一个坐标系，不需要偏移。**

那上一轮为什么 talk 打不到？因为 warp 到 (8,18) 时，
NPC 在 (8,17)，玩家在 (8,18) —— 玩家在 NPC **下方**，
朝 UP 应该能打到。除非…… (8,17) 那个 object 不是 NPC。

本脚本做一件事：把**同一张地图里多个帧**的 object 坐标列出来，
看哪些坐标**始终不动**（NPC/建筑）以及哪些随玩家变（跟随对象）。

用法：
  python scripts/obj_delta.py <run_dir> <帧A> <帧B>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

EWRAM_BASE, EWRAM_LEN = 0x02000000, 0x40000
IWRAM_BASE = 0x03000000
BASE = 0x03004800
STEP = 0x24
COUNT = 20


def off_of(addr: int) -> int:
    return (EWRAM_LEN + (addr - IWRAM_BASE)) if addr >= IWRAM_BASE else (addr - EWRAM_BASE)


def load(run: Path, key: str):
    side = run / "translated"
    if not side.is_dir():
        side = run / "origin"
    num = None
    for line in (side / "index.csv").read_text(encoding="utf-8", errors="replace").splitlines():
        p = line.split(",")
        if len(p) >= 4 and (p[2] == key or p[0] == key):
            num = p[3].replace(".png", "")
            break
    if num is None:
        num = key.zfill(3)
    f = side / f"{num}.ram.bin"
    return (f.read_bytes() if f.is_file() else None), num


def sb1_of(run: Path):
    for side in ("translated", "origin"):
        log = run / side / "scene.log"
        if log.is_file():
            m = re.search(r"sb1=0x([0-9A-Fa-f]{8})",
                          log.read_text(encoding="utf-8", errors="replace"))
            if m:
                return int(m.group(1), 16)
    return None


def player(data: bytes, sb1: int):
    o = off_of(sb1)
    return (int.from_bytes(data[o:o + 2], "little", signed=True),
            int.from_bytes(data[o + 2:o + 4], "little", signed=True))


def objects(data: bytes):
    a = off_of(BASE)
    out = []
    for i in range(COUNT):
        p = a + i * STEP
        if p + 0x14 > len(data):
            break
        cx = int.from_bytes(data[p + 4:p + 6], "little", signed=True)
        cy = int.from_bytes(data[p + 6:p + 8], "little", signed=True)
        if 0 < cx <= 120 and 0 < cy <= 120:
            out.append((i, cx, cy))
    return out


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    run = Path(sys.argv[1])
    a_key, b_key = sys.argv[2], sys.argv[3]
    sb1 = sb1_of(run)
    if sb1 is None:
        print("[ERR] 无 sb1")
        return 1

    da, na = load(run, a_key)
    db, nb = load(run, b_key)
    if da is None or db is None:
        print("[ERR] 缺 ram.bin")
        return 1

    pa, pb = player(da, sb1), player(db, sb1)
    oa, ob = objects(da), objects(db)
    print(f"A = {na} ({a_key})  玩家={pa}")
    print(f"B = {nb} ({b_key})  玩家={pb}")

    print("\nA 的 object：")
    for i, x, y in oa:
        print(f"  [{i}] ({x},{y})")
    print("\nB 的 object：")
    for i, x, y in ob:
        print(f"  [{i}] ({x},{y})")

    # 前后两帧都在的 object（坐标不变 ⇒ 固定 NPC/建筑）
    sa = {(x, y) for _, x, y in oa}
    sb = {(x, y) for _, x, y in ob}
    same = sorted(sa & sb)
    print(f"\n两帧坐标相同的 object（{len(same)} 个，多半是固定 NPC）：")
    for x, y in same:
        print(f"  ({x},{y})")
    print("\n判读：这些坐标与玩家坐标同系。")
    print("      要对话就 warp 到它的**相邻格**，再朝它的方向按 A。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
