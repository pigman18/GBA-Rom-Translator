#!/usr/bin/env python3
"""输出当前地图上所有 object 的坐标（按 0x24 步长解 0x03004800 起的结构）。

── 已解出的结构（实测两帧对照，城市/道馆都成立）──────────────────────
    obj[i] = 0x03004800 + i * 0x24
      +0x00  s16 prevX, +0x02  s16 prevY
      +0x04  s16 curX,  +0x06  s16 curY
      +0x08  s16 initX, +0x0A  s16 initY
      +0x0C  u32 (0x22 / 0x33 / 0x11 之类，像 flags/graphicsId 组合)
      ...
  实测：城市帧 obj[0]=(36,23)/(35,23)，道馆帧 obj[0]=(9,24)
  ⇒ **坐标随地图变化**，是当前地图上的对象（含 NPC）。

用法：
  python scripts/list_objects.py <run_dir> [帧名]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

EWRAM_BASE, EWRAM_LEN = 0x02000000, 0x40000
IWRAM_BASE = 0x03000000
BASE = 0x03004800
STEP = 0x24
COUNT = 16


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
                    return f.read_bytes(), f.name
    for f in sorted(side.glob("*.ram.bin")):
        return f.read_bytes(), f.name
    return None, None


def off_of(addr: int) -> int:
    return (EWRAM_LEN + (addr - IWRAM_BASE)) if addr >= IWRAM_BASE else (addr - EWRAM_BASE)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    run = Path(sys.argv[1])
    key = sys.argv[2] if len(sys.argv) > 2 else None
    data, name = load_frame(run, key)
    if data is None:
        print("[ERR] 找不到 ram.bin")
        return 1

    sb1 = None
    for side in ("translated", "origin"):
        log = run / side / "scene.log"
        if log.is_file():
            m = re.search(r"sb1=0x([0-9A-Fa-f]{8})",
                          log.read_text(encoding="utf-8", errors="replace"))
            if m:
                sb1 = int(m.group(1), 16)
                break
    o = off_of(sb1)
    px = int.from_bytes(data[o:o + 2], "little", signed=True)
    py = int.from_bytes(data[o + 2:o + 4], "little", signed=True)
    print(f"帧 {name}  玩家=({px},{py})")
    print(f"\n{'i':>2} {'cur':>12} {'prev':>12} {'init':>12}  {'+0C':>10} {'+10':>8}")
    print("-" * 74)

    a = off_of(BASE)
    found = []
    for i in range(COUNT):
        p = a + i * STEP
        if p + 0x14 > len(data):
            break
        def s16(q):
            return int.from_bytes(data[p + q:p + q + 2], "little", signed=True)
        cx, cy = s16(4), s16(6)
        if not (0 < cx <= 120 and 0 < cy <= 120):
            continue
        u32c = int.from_bytes(data[p + 0x0C:p + 0x10], "little")
        u32d = int.from_bytes(data[p + 0x10:p + 0x14], "little")
        mark = "  ★玩家?" if (cx, cy) == (px, py) else ""
        print(f"{i:>2} ({s16(4)},{s16(6)})  ({s16(0)},{s16(2)})  "
              f"({s16(8)},{s16(10)})  0x{u32c:08X} 0x{u32d:08X}{mark}")
        found.append((i, s16(4), s16(6)))

    print(f"\n共 {len(found)} 个有效 object")
    if found:
        print("可直接用作 warp 落点的候选（= 贴到某个 NPC 身上）：")
        for i, x, y in found[:12]:
            print(f"  api.warp{{ map = \"<g:n>\", x = {x}, y = {y} }}   -- obj[{i}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
