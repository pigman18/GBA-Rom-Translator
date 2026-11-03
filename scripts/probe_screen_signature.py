#!/usr/bin/env python3
"""找「界面判别特征」：比较各帧 io.bin 的寄存器组合。

为什么要做：探针跑完发现「按 6 次 B 回野外」并不可靠 ——
在某个界面里 START 打不开菜单，后面的 UP/DOWN 就全落在旧界面上，
于是 p3 进去的其实是领航员。要修这个问题，必须先有一条
**机器可判的「我在哪个界面」信号**，不能靠截图肉眼看。

本脚本把若干帧的 IO 寄存器逐项列出并找出差异位，作为候选判别式。
用法：python scripts/probe_screen_signature.py <run_dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

# IO 寄存器（与 bot/bot.lua 的 IO_REGS / 常规 GBA 寄存器表一致）
REG = [
    (0x00, "DISPCNT"), (0x04, "DISPSTAT"), (0x06, "VCOUNT"),
    (0x08, "BG0CNT"), (0x0A, "BG1CNT"), (0x0C, "BG2CNT"), (0x0E, "BG3CNT"),
    (0x10, "BG0HOFS"), (0x12, "BG0VOFS"),
    (0x14, "BG1HOFS"), (0x16, "BG1VOFS"),
    (0x18, "BG2HOFS"), (0x1A, "BG2VOFS"),
    (0x1C, "BG3HOFS"), (0x1E, "BG3VOFS"),
    (0x40, "WIN0H"), (0x42, "WIN0V"), (0x44, "WIN1H"), (0x46, "WIN1V"),
    (0x48, "WININ"), (0x4A, "WINOUT"),
    (0x50, "BLDCNT"), (0x52, "BLDALPHA"), (0x54, "BLDY"),
]


def read_io(p: Path):
    b = p.read_bytes()
    return {name: (b[o] | (b[o + 1] << 8)) for o, name in REG if o + 1 < len(b)}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    run = Path(sys.argv[1])
    side = run / "translated"
    if not side.is_dir():
        side = run / "origin"

    idx = []
    csv = side / "index.csv"
    for line in csv.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split(",")
        if len(parts) >= 3 and parts[0].isdigit():
            idx.append((int(parts[0]), parts[2]))

    rows = []
    for num, name in idx:
        f = side / f"{num:03d}.io.bin"
        if not f.is_file():
            continue
        rows.append((num, name, read_io(f)))

    if not rows:
        print("[ERR] 没有 io.bin（老批次没有导出 IO？）")
        return 1

    # 逐帧打印关键寄存器
    keys = ["DISPCNT", "BG0CNT", "BG1CNT", "BG2CNT", "BG3CNT",
            "WININ", "WINOUT", "BLDCNT", "BLDY"]
    print(f"{'#':>4} {'name':<16} " + " ".join(f"{k:>8}" for k in keys))
    for num, name, io in rows:
        print(f"{num:>4} {name:<16} "
              + " ".join(f"{io.get(k, 0):08X}" for k in keys))

    # 哪些寄存器组合**唯一**区分帧 → 就是可用的判别式
    print("\n—— 各寄存器取值分布（取值种类越少越适合当判别式）——")
    for k in keys:
        vals = {}
        for _, _, io in rows:
            vals.setdefault(io.get(k, 0), []).append(_)
        if 1 < len(vals) <= 12:
            print(f"\n{k}: {len(vals)} 种取值")
            for v, frames in sorted(vals.items()):
                print(f"  0x{v:04X}  x{len(frames):<3} 例: {frames[:8]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
