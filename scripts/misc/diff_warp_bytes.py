#!/usr/bin/env python3
"""找出「商店门口 warp 的目标」到底存在内存哪里。

── 已知事实（三轮实测）────────────────────────────────────────────────
① 改 SaveBlock1.location(+0x04..) → 穿门后变 0:2（被门覆盖）
② 提前改 gWarpDestination(0x020297F8) → 穿门时被重写（002 帧有我的值，003 帧没了）
⇒ 门触发时会自己写目的地。所以要么改「门的数据源」，要么抢窗口。

── 本脚本要回答的问题 ─────────────────────────────────────────────────
城市地图是 **0:2**、坐标 (23,17)。商店内是 10:7。
在商店内的帧里，内存中哪些位置存着「0x0A,0x07」（10:7）或「0x00,0x02」（0:2）？
再对比穿门后的帧，找出**穿门前是 10:7、穿门后变成 0:2** 的地址 ——
那就是 warp 目标真正落盘的地方。

用法：
  python scripts/diff_warp_bytes.py <run_dir> <shop帧> <city帧>
"""
from __future__ import annotations

import sys
from pathlib import Path

EWRAM_BASE, EWRAM_LEN = 0x02000000, 0x40000
IWRAM_BASE = 0x03000000


def load(run: Path, key: str):
    side = run / "translated"
    if not side.is_dir():
        side = run / "origin"
    num, label = None, "?"
    for line in (side / "index.csv").read_text(encoding="utf-8", errors="replace").splitlines():
        p = line.split(",")
        if len(p) >= 4 and (p[2] == key or p[0] == key):
            num, label = p[3].replace(".png", ""), p[2]
            break
    if num is None:
        num = key.zfill(3)
    f = side / f"{num}.ram.bin"
    return (f.read_bytes() if f.is_file() else None), label


def addr_of(off: int) -> int:
    return (IWRAM_BASE + off - EWRAM_LEN) if off >= EWRAM_LEN else (EWRAM_BASE + off)


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    run = Path(sys.argv[1])
    a, la = load(run, sys.argv[2])
    b, lb = load(run, sys.argv[3])
    if a is None or b is None:
        print("[ERR] 缺 ram.bin")
        return 1
    print(f"商店帧 {la}  城市帧 {lb}")

    # 「商店 10:7」的字节对，以及「城市 0:2」的字节对
    shop_pat = bytes([0x0A, 0x07])
    city_pat = bytes([0x00, 0x02])

    # 找穿门前后**发生变化**、且变化方向是 10:7 -> 0:2 的 2 字节窗口
    print("\n穿门前 = 10:07 且穿门后 = 00:02 的地址（2 字节窗口）：")
    n = 0
    for off in range(0, min(len(a), len(b)) - 2):
        if a[off:off + 2] == shop_pat and b[off:off + 2] == city_pat:
            print(f"  0x{addr_of(off):08X}  (ram 0x{off:06X})")
            n += 1
            if n >= 30:
                print("  ...（只列前 30 个）")
                break
    if n == 0:
        print("  无")

    # 放宽：穿门后含 00 02、穿门前含 0A 07（不要求同位置相邻）
    print("\n更宽松：任何 4 字节窗口里含 0A 07 → 后续含 00 02 的位置不做要求")
    print("（这类命中太多，仅统计数量）")
    ca = sum(1 for o in range(len(a) - 1) if a[o:o + 2] == shop_pat)
    cb = sum(1 for o in range(len(b) - 1) if b[o:o + 2] == city_pat)
    print(f"  商店帧含 0A 07 的窗口数 = {ca}")
    print(f"  城市帧含 00 02 的窗口数 = {cb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
