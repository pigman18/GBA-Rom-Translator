#!/usr/bin/env python3
"""从 RAM 里找出当前地图上所有 object（NPC）的坐标，不依赖符号表。

── 为什么不用 gObjectEvents 符号 ──────────────────────────────────────
本项目已反复验证：日版的 gObjectEvents(0x030048A0)、gCamera(0x0202E844)、
gBattleMons(0x02024A80)、gPlayerParty(0x03004360) **全部对不上**。
用符号读出来的是乱数据（实测 active=255、coord=(0,0)）。

── 本脚本的做法：按「玩家坐标锚定 + 结构特征」反查 ────────────────────
已知：玩家坐标 = SaveBlock1+0x00（u16 x, u16 y），运行时可从 prove 拿到
      SaveBlock1 地址（scene.log 里的 sb1=）。

思路：
  1) 在 RAM 里搜「玩家坐标」出现的位置，确认坐标系
  2) 在它附近（同一结构数组）找**成对出现的 s16 坐标**，
     且值落在当前地图尺寸范围内
  3) 通过「同一帧内这些坐标不变、而玩家走动时只有玩家那一条变」
     来区分「玩家」和「NPC」

本脚本处理离线 ram.bin，输出候选 NPC 坐标，供场景落点参考。

用法：
  python scripts/find_npc_coords.py <run_dir> [帧名]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

EWRAM_BASE, EWRAM_LEN = 0x02000000, 0x40000
IWRAM_BASE = 0x03000000


def load_frame(run: Path, key: str | None):
    side = run / "translated"
    if not side.is_dir():
        side = run / "origin"
    if key:
        for line in (side / "index.csv").read_text(encoding="utf-8", errors="replace").splitlines():
            p = line.split(",")
            if len(p) >= 4 and (p[2] == key or p[0] == key):
                f = side / f"{p[3].replace('.png', '')}.ram.bin"
                if f.is_file():
                    return f.read_bytes(), f.name, side
    for f in sorted(side.glob("*.ram.bin")):
        return f.read_bytes(), f.name, side
    return None, None, side


def find_sb1(run: Path):
    for side in ("translated", "origin"):
        log = run / side / "scene.log"
        if not log.is_file():
            continue
        m = re.search(r"sb1=0x([0-9A-Fa-f]{8})",
                      log.read_text(encoding="utf-8", errors="replace"))
        if m:
            return int(m.group(1), 16)
    return None


def off_of(addr: int) -> int:
    return (EWRAM_LEN + (addr - IWRAM_BASE)) if addr >= IWRAM_BASE else (addr - EWRAM_BASE)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    run = Path(sys.argv[1])
    key = sys.argv[2] if len(sys.argv) > 2 else None

    sb1 = find_sb1(run)
    if sb1 is None:
        print("[ERR] scene.log 里没有 sb1= 地址")
        return 1
    data, name, side = load_frame(run, key)
    if data is None:
        print("[ERR] 找不到 ram.bin")
        return 1
    print(f"帧 {name}  side={side}  SaveBlock1=0x{sb1:08X}")

    o = off_of(sb1)
    px = int.from_bytes(data[o:o + 2], "little", signed=True)
    py = int.from_bytes(data[o + 2:o + 4], "little", signed=True)
    print(f"玩家坐标 = ({px}, {py})")

    # 在这帧里找「(px,py) 的 s16 对」还出现在哪 —— 那就是 object 结构里的副本
    print("\n玩家坐标还在这些地址出现（可能是 object 结构里的 currentCoords）：")
    pat = px.to_bytes(2, "little", signed=True) + py.to_bytes(2, "little", signed=True)
    hits, i = [], data.find(pat)
    while i >= 0 and len(hits) < 20:
        off = i
        addr = addr_of(off)
        hits.append((addr, off))
        i = data.find(pat, i + 1)
    for addr, off in hits:
        print(f"  0x{addr:08X}")

    # 以每个命中点为锚，按 0x20 步长往两边看是否有一串「坐标像格子」的 s16 对
    print("\n以命中点为锚，检查 ±0x200 范围内是否有成串的坐标对：")
    for addr, off in hits[:4]:
        print(f"\n  锚点 0x{addr:08X}：")
        found = []
        for delta in range(-0x100, 0x120, 4):
            p = off + delta
            if p < 0 or p + 4 > len(data):
                continue
            x = int.from_bytes(data[p:p + 2], "little", signed=True)
            y = int.from_bytes(data[p + 2:p + 4], "little", signed=True)
            if 0 <= x <= 200 and 0 <= y <= 200:
                found.append((addr + delta, x, y))
        if found:
            print(f"    共 {len(found)} 个候选坐标对，前 20 个：")
            for a, x, y in found[:20]:
                mark = "  ← 玩家" if (x, y) == (px, py) else ""
                print(f"      0x{a:08X}  ({x},{y}){mark}")
        else:
            print("    无")
    return 0


def addr_of(off: int) -> int:
    return (IWRAM_BASE + off - EWRAM_LEN) if off >= EWRAM_LEN else (EWRAM_BASE + off)


if __name__ == "__main__":
    raise SystemExit(main())
