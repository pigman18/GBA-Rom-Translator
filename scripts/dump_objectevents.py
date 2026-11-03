#!/usr/bin/env python3
"""从指定帧的 ram.bin 里把 gObjectEvents 的真实内容读出来。

⚠ 上一版直接读第 1 帧，全是 active=255 / coord=(0,0) —— 那时对象还没初始化，
   结论完全无效。**必须读"已经站在地图上"的帧**（比如出门后的那张 shot）。

用法：
  python scripts/dump_objectevents.py <run_dir> <帧名或序号>
  例：python scripts/dump_objectevents.py work/.../run pw_out
      python scripts/dump_objectevents.py work/.../run 002
"""
from __future__ import annotations

import sys
from pathlib import Path

EWRAM_BASE, EWRAM_LEN = 0x02000000, 0x40000
IWRAM_BASE = 0x03000000
G_OBJECT_EVENTS = 0x030048A0
G_CAMERA = 0x0202E844
SIZE = 0x240


def find_ram(run_dir: Path, key: str):
    side = run_dir / "translated"
    if not side.is_dir():
        side = run_dir / "origin"

    target = None
    csv = side / "index.csv"
    if csv.is_file():
        for line in csv.read_text(encoding="utf-8", errors="replace").splitlines():
            p = line.split(",")
            if len(p) >= 4 and (p[2] == key or p[0] == key):
                target = p[3].replace(".png", "")   # 000
                label = p[2]
                break
    if target is None:
        # 当作序号
        target = key.zfill(3)
        label = "?"
    f = side / f"{target}.ram.bin"
    return (f if f.is_file() else None), label


def slice_ram(data: bytes, addr: int, n: int):
    off = (EWRAM_LEN + (addr - IWRAM_BASE)) if addr >= IWRAM_BASE else (addr - EWRAM_BASE)
    if off < 0 or off + n > len(data):
        return None
    return data[off:off + n]


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    f, label = find_ram(Path(sys.argv[1]), sys.argv[2])
    if f is None:
        print(f"[ERR] 没有对应帧的 ram.bin（key={sys.argv[2]}）")
        return 1
    data = f.read_bytes()
    print(f"帧 {f.name}  ({label})  {len(data)}B")

    blob = slice_ram(data, G_OBJECT_EVENTS, SIZE)
    print(f"\ngObjectEvents @0x{G_OBJECT_EVENTS:08X}")
    # 逐个候选步长都看一遍，找「active=1 且坐标合理」的那个
    for step in (0x24, 0x28, 0x40):
        rows = []
        for i in range(0, SIZE, step):
            o = blob[i:i + step]
            if len(o) < 0x10:
                break
            if o[0] != 1:
                continue
            x = int.from_bytes(o[8:10], "little", signed=True)
            y = int.from_bytes(o[10:12], "little", signed=True)
            rows.append((i, step, o[1], o[2], o[4], o[6], o[5], x, y))
        if rows:
            print(f"\n  步长 0x{step:02X}：active=1 的对象 {len(rows)} 个")
            for i, st, gfx, mv, lid, mg, mn, x, y in rows:
                print(f"    +0x{i:03X} gfx={gfx:3d} move={mv:3d} localId={lid:3d} "
                      f"map={mg}:{mn} coord=({x},{y})")

    cam = slice_ram(data, G_CAMERA, 0x0C)
    if cam:
        v = [int.from_bytes(cam[k:k + 2], "little", signed=True) for k in (0, 2, 4, 6)]
        print(f"\ngCamera raw={cam.hex(' ')} int16={v}")

    # 顺便看一眼 SaveBlock1.pos 在同一帧的值，做对照
    print("\n对照：本帧的 [POS] 记录请看 scene.log 的同名行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
