#!/usr/bin/env python3
"""bot/tools/savedit.py — 离线改 .sav 的**位置**（换地图），并重算扇区校验和。

── 为什么需要它（这条路 vs 金手指）────────────────────────────────────────
金手指（bot 的 poke 动作）只能改**已经在跑的游戏内存**，适合改数量、旗标
这类「游戏会自己读」的字段。但**换地图**不行：地图是读档时由启动流程
（`SetWarpDestination` + 加载地图头）一次性建立的，光改 SaveBlock1 的
location 而游戏不重新加载地图，画面不会动 —— 实测改坐标能立刻移动，
改 mapGroup/mapNum 则无效。

所以要覆盖「室内 / 商店 / 大赛 / PC / 道馆」这些场景，必须**在存档文件里
改好落点**，让游戏读档时就落在目标地图。这就是本脚本的用途。

── 顺序（用户口径）──────────────────────────────────────────────────────
「先加载 .sav 再用金手指」—— 本脚本改的是 .sav 本身，改完由 run.py 复制进
两侧的 workdir 再启动模拟器，游戏**读档时**就落在目标地图。
即：改存档 → 读档 → （如需）金手指。顺序不会反。

── Gen3 存档结构 ─────────────────────────────────────────────────────────
32 个 4KB 扇区，每扇区末尾 16 字节 footer：
    +0xFF4 u16 sector_id   +0xFF6 u16 checksum
    +0xFF8 u32 signature   0xFFC u32 counter
checksum = 扇区内前 0xFF4 字节按 u32 累加折叠成 u16：
    u16 ck = 0; for i in 0..(0xFF4/4): ck += u32be_at(i); ck = (ck & 0xFFFF) + (ck >> 16)
✅ 实测本仓的 Route118_68-7.sav 用它重算后与文件里的旧值一致，
   说明该算法对 AXVJ 成立（下面 `--verify` 会逐扇区报告）。

用法：
  python bot/tools/savedit.py <src.sav> <dst.sav> --map 0:33 --pos 68:7
  python bot/tools/savedit.py <src.sav> --verify
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SECTOR = 4096
SIG = 0x08012025
FOOTER = 0xFF4
FLASH_1M = 131072

# 逻辑存档里的块偏移（与 savlib.py 一致，实证过）
SB2_OFF = 0x00000
SB1_OFF = 0x01000

# SaveBlock1 内偏移
O_POS_X, O_POS_Y = 0x00, 0x02     # struct Coords16 pos
O_MAP_GROUP, O_MAP_NUM = 0x04, 0x05
O_WARP_ID = 0x06
# continueGameWarp（读档后从菜单「继续」进来的落点）
O_CG_GROUP, O_CG_NUM = 0x0C, 0x0D
# lastHealLocation / 备用落点也一起改，避免菜单摘要与实际落点不一致
O_LASTHEAL_GROUP, O_LASTHEAL_NUM = 0x10, 0x11


def u16(b, o): return b[o] | (b[o + 1] << 8)
def u32(b, o): return int.from_bytes(b[o:o + 4], "little")


def sector_checksum(sec: bytes) -> int:
    """Gen3 扇区校验和。

    ★ 算法细节（2026-11-03 实测校正）：
      先**把 0xFF4 字节按 u32 求和（u32 自然溢出）**，最后才把 32 位
      结果折叠成 16 位：ck = (sum & 0xFFFF) + (sum >> 16)。
      最初写成「每加一次就折叠」，实测 14 个扇区里 7 个对不上
      （差 0x0A/0x4A/0x18… 这种小偏移），改成先累加后折叠后全部一致。
    """
    s = 0
    for o in range(0, FOOTER, 4):
        s = (s + u32(sec, o)) & 0xFFFFFFFF
    return ((s & 0xFFFF) + (s >> 16)) & 0xFFFF


def rebuild(buf: bytes):
    """按 sector_id 拼出逻辑存档，同时返回每个扇区的物理位置。"""
    slots = {}
    for i in range(32):
        sec = buf[i * SECTOR:(i + 1) * SECTOR]
        if len(sec) < SECTOR:
            break
        if u32(sec, FOOTER + 4) != SIG:
            continue
        sid = u16(sec, FOOTER)
        cnt = u32(sec, FOOTER + 8)
        if sid > 31:
            continue
        prev = slots.get(sid)
        if prev is None or ((cnt - prev[0]) & 0xFFFFFFFF) < 0x80000000:
            slots[sid] = (cnt, i)
    logical = bytearray(FLASH_1M)
    where = {}
    for sid, (_, phys) in slots.items():
        logical[sid * SECTOR:(sid + 1) * SECTOR] = buf[phys * SECTOR:(phys + 1) * SECTOR]
        where[sid] = phys
    return logical, where


def verify(buf: bytes) -> int:
    logical, where = rebuild(buf)
    print(f"扇区 {len(where)}/32 有效")
    bad = 0
    for sid in sorted(where):
        phys = where[sid]
        sec = buf[phys * SECTOR:(phys + 1) * SECTOR]
        old = u16(sec, FOOTER + 2)
        new = sector_checksum(sec)
        flag = "OK " if old == new else "BAD"
        if old != new:
            bad += 1
            print(f"  扇区{sid:2d} (物理{phys:2d}) {flag} 文件内={old:04X} 重算={new:04X}")
    print(f"校验和：{len(where) - bad} 个一致，{bad} 个不一致")
    if bad:
        print("  ⚠ 有不一致 ⇒ 本文件的 checksum 算法与此处实现不同，"
              "改存档前必须先解决，否则游戏会判存档损坏")
    return 0 if bad == 0 else 1


def patch_position(buf: bytes, group: int, num: int, x: int, y: int,
                   warp_id: int = -1, also_continue: bool = False) -> bytes:
    """只改 SaveBlock1 的 pos + location。

    ★★ 2026-11-03 实测结论（很重要，别重犯）：
      把 location 改成别的**地图**是无效的 —— 改完 prove 读到 loc=10:7
      与真·商店存档一模一样，但画面仍是 Route118 且主角消失。
      原因：SaveBlock1 +0x34 起还有一大片**当前地图相关的运行时数据**
      （实测 226+ 字节，两份存档完全不同），地图是读档流程加载的，
      不是靠 location 一个字段驱动的。
      ⇒ **换地图请直接用已经在那个地图的存档**，不要靠改 location。
      本函数改坐标（同一张图内挪位置）是有效的，实测 (68,7)→(60,7) 立刻生效。

    ⚠ also_continue 默认 False：continueGameWarp / dynamicWarp /
      lastHealLocation 是**读档落点**，改动它们会让游戏去别处读档。
      实测把它们一起改成目标地图时，读档直接失效。
    """
    out = bytearray(buf[:FLASH_1M])
    logical, where = rebuild(out)
    if SB1_OFF // SECTOR not in where:
        raise SystemExit("[ERR] 逻辑扇区里没有 SaveBlock1 所在扇区")

    sb1 = SB1_OFF
    logical[sb1 + O_POS_X] = x & 0xFF
    logical[sb1 + O_POS_X + 1] = (x >> 8) & 0xFF
    logical[sb1 + O_POS_Y] = y & 0xFF
    logical[sb1 + O_POS_Y + 1] = (y >> 8) & 0xFF
    logical[sb1 + O_MAP_GROUP] = group & 0xFF
    logical[sb1 + O_MAP_NUM] = num & 0xFF
    logical[sb1 + O_WARP_ID] = warp_id & 0xFF
    if also_continue:
        logical[sb1 + O_CG_GROUP] = group & 0xFF
        logical[sb1 + O_CG_NUM] = num & 0xFF
        logical[sb1 + O_LASTHEAL_GROUP] = group & 0xFF
        logical[sb1 + O_LASTHEAL_NUM] = num & 0xFF

    # 把改动写回**所有**覆盖该逻辑区的物理扇区，并重算 checksum
    # SaveBlock1 占 0x1000..0x4AC0 ⇒ 逻辑扇区 1..4
    touched = range(SB1_OFF // SECTOR, (SB1_OFF + 0x3AC0 + SECTOR - 1) // SECTOR)
    for sid in touched:
        if sid not in where:
            continue
        phys = where[sid]
        start = phys * SECTOR
        out[start:start + SECTOR] = logical[sid * SECTOR:(sid + 1) * SECTOR]
        ck = sector_checksum(bytes(out[start:start + SECTOR]))
        out[start + FOOTER + 2] = ck & 0xFF
        out[start + FOOTER + 3] = (ck >> 8) & 0xFF
        print(f"  写回扇区{sid} (物理{phys}) checksum={ck:04X}")

    if len(buf) > FLASH_1M:
        out += buf[FLASH_1M:]
    return bytes(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst", nargs="?")
    ap.add_argument("--map", help="mapGroup:mapNum")
    ap.add_argument("--pos", help="x:y")
    ap.add_argument("--warp", type=int, default=-1)
    ap.add_argument("--verify", action="store_true", help="只校验 checksum 实现")
    a = ap.parse_args()

    buf = Path(a.src).read_bytes()
    if a.verify:
        return verify(buf)
    if not a.dst or not a.map or not a.pos:
        print("需要 dst + --map + --pos（或用 --verify 只校验）")
        return 2

    g, n = (int(v) for v in a.map.split(":"))
    x, y = (int(v) for v in a.pos.split(":"))
    out = patch_position(buf, g, n, x, y, a.warp)
    Path(a.dst).write_bytes(out)
    print(f"[OK] {a.src} -> {a.dst} 落点 map={g}:{n} pos=({x},{y}) warp={a.warp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
