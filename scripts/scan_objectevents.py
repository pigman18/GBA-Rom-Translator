#!/usr/bin/env python3
"""说明 gObjectEvents 的结构，供「金手指瞬移」用。

── 为什么必须改这个而不是 SaveBlock1.pos ─────────────────────────────────
2026-11-03 实测：
  · poke SaveBlock1+0x00/0x02（pos.x/pos.y）→ [POS] 日志立刻变，
    值也保持住了（(23,17)→(5,12)→(30,12) 都对）。
  · 但**画面几乎不动**、角色 sprite 还在原地。
  ⇒ 说明渲染（角色 sprite / 相机）不读 SaveBlock1.pos，
    它读的是运行时对象表 gObjectEvents 里的玩家对象。

符号表（KEEP-US，可信）：
    030048A0 g 00000240 gObjectEvents     ← 9 个 object event × 0x24? 或 0x40
    0202E844 g 0000000c gCamera
    0202E858 g 00000024 gPlayerAvatar

pokeruby 的 struct ObjectEvent 布局（美版）：
    +0x00 u8 active
    +0x01 u8 graphicsId
    +0x02 u8 movementType
    +0x03 u8 trainerType
    +0x04 u8 localId
    +0x05 u8 mapNum
    +0x06 u8 mapGroup
    +0x07 u8 filler
    +0x08 s16 currentCoords.x    ← 屏上位置（像素？格？）
    +0x0A s16 currentCoords.y
    +0x0C s16 previousCoords.x
    +0x0E s16 previousCoords.y
    +0x10 u16 facingDirection...
本脚本只做一件事：把这段 RAM **在运行时的真实内容**打印出来，
让"玩家对象是第几个、坐标在哪"有实证，而不是照抄美版结构。

⚠ 需要一份运行时 ram.bin（bot 截图带 .ram.bin）。用法：
    python scripts/scan_objectevents.py <run_dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

# EWRAM 0x02000000 + 0x40000 | IWRAM 0x03000000 + 0x8000（bot schema 3）
EWRAM_BASE = 0x02000000
EWRAM_LEN = 0x40000
IWRAM_BASE = 0x03000000

G_OBJECT_EVENTS = 0x030048A0
G_CAMERA = 0x0202E844
G_PLAYER_AVATAR = 0x0202E858
SIZE = 0x240


def read_ram(run_dir: Path, addr: int, n: int):
    """从某帧的 ram.bin 里取 [addr, addr+n)。"""
    side = run_dir / "translated"
    if not side.is_dir():
        side = run_dir / "origin"
    # 找第一份 ram.bin
    for p in sorted(side.glob("*.ram.bin")):
        data = p.read_bytes()
        if addr >= IWRAM_BASE:
            off = EWRAM_LEN + (addr - IWRAM_BASE)
        else:
            off = addr - EWRAM_BASE
        if 0 <= off and off + n <= len(data):
            return data[off:off + n], p.name
    return None, None


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    run = Path(sys.argv[1])

    blob, name = read_ram(run, G_OBJECT_EVENTS, SIZE)
    if blob is None:
        print("[ERR] 找不到 ram.bin，或地址越界")
        return 1
    print(f"gObjectEvents @0x{G_OBJECT_EVENTS:08X}  (来自 {name})")

    # 按 0x24 步长扫，找 active 且坐标合理的对象
    for step in (0x24, 0x28, 0x40):
        print(f"\n--- 假设步长 0x{step:02X} ---")
        for i in range(0, min(SIZE, step * 8), step):
            o = blob[i:i + step]
            if len(o) < 0x10:
                break
            active = o[0]
            if active == 0:
                continue
            x = int.from_bytes(o[8:10], "little", signed=True)
            y = int.from_bytes(o[10:12], "little", signed=True)
            print(f"  [{i // step}] +0x{i:03X} active={active} "
                  f"graphics={o[1]} move={o[2]} localId={o[4]} "
                  f"map={o[6]}:{o[5]} coord=({x},{y})")

    cam, _ = read_ram(run, G_CAMERA, 0x0C)
    if cam:
        vals = [int.from_bytes(cam[k:k + 2], "little", signed=True) for k in (0, 2, 4, 6)]
        print(f"\ngCamera @0x{G_CAMERA:08X}: {cam.hex(' ')}  int16={vals}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
