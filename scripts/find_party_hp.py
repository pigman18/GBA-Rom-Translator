#!/usr/bin/env python3
"""实测 gPlayerParty 里「当前 HP」的偏移，供「清零触发白屏」用。

── 为什么要实测而不是照抄 pokeruby ──────────────────────────────────────
本项目已多次踩到「日版结构 ≠ 美版」的坑（WindowTemplate、struct Window、
SaveBlock1 队伍偏移都不同）。所以队伍 HP 的偏移必须从**运行时内存**
反推，不能照美版头文件写。

── 已知（本项目实证）──────────────────────────────────────────────────
    SB1+0x234 = partyCount（u8），SB1+0x238 起 playerParty[6]
    每只 struct Pokemon 100 字节；+0x54 = level（明文，不加密）
    → 本次会话早期用这条定位到 6 只，等级 36/36/4/10/18/5

── 本脚本做什么 ────────────────────────────────────────────────────────
读一帧 ram.bin，把队伍每只 100 字节里 **明文区（+0x50 之后）** 的 u16 值
列出来，找出「hp <= maxhp 且都合理」的那一对 —— 那就是 hp / maxHp。

pokeruby 的 party 子结构顺序固定为：status, level, mail, hp, stats...
  +0x50 u32 status
  +0x54 u8  level
  +0x55 u8  mail
  +0x56 u16 hp        ← 候选
  +0x58 u16 maxHP     ← 候选
  +0x5A u16 attack
  ... 共 20 字节（+0x54..+0x67），之后是 4 个 12 字节战斗子结构

用法：python scripts/find_party_hp.py <run_dir> [帧名]
"""
from __future__ import annotations

import sys
from pathlib import Path

EWRAM_BASE, EWRAM_LEN = 0x02000000, 0x40000
IWRAM_BASE = 0x03000000
G_PLAYER_PARTY = 0x03004360
MON = 100
COUNT = 6


def load_ram(run: Path, key: str | None):
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


def slice_ram(data: bytes, addr: int, n: int):
    off = (EWRAM_LEN + (addr - IWRAM_BASE)) if addr >= IWRAM_BASE else (addr - EWRAM_BASE)
    if off < 0 or off + n > len(data):
        return None
    return data[off:off + n]


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    run = Path(sys.argv[1])
    key = sys.argv[2] if len(sys.argv) > 2 else None
    data, name = load_ram(run, key)
    if data is None:
        print("[ERR] 找不到 ram.bin")
        return 1
    print(f"帧 {name}")

    blob = slice_ram(data, G_PLAYER_PARTY, MON * COUNT)
    if blob is None:
        print("[ERR] gPlayerParty 越界")
        return 1

    # partyCount 从 SaveBlock1 读不方便，这里按「level 非 0」判断有效只数
    print("\n每只宝可梦的明文区（+0x50..0x67），u16 逐个列出：")
    for i in range(COUNT):
        m = blob[i * MON:(i + 1) * MON]
        lvl = m[0x54]
        if lvl == 0:
            print(f"  #{i}: level=0 ⇒ 空位")
            continue
        status = int.from_bytes(m[0x50:0x54], "little")
        hp = int.from_bytes(m[0x56:0x58], "little")
        mx = int.from_bytes(m[0x58:0x5A], "little")
        atk = int.from_bytes(m[0x5A:0x5C], "little")
        print(f"  #{i}: level={lvl:3d} status=0x{status:08X}")
        print(f"      +0x56={hp:5d}  +0x58={mx:5d}  +0x5A={atk:5d}"
              f"   {'✓ hp<=maxhp' if hp <= mx and mx > 0 else '✗ 不合理'}")

    print("\n判读：若 +0x58 >= +0x56 > 0 且数值像血量（十几到几百），")
    print("      则 +0x56 = 当前 HP、+0x58 = 最大 HP。")
    print(f"      『清零 HP』就是把这些 #i 的 gPlayerParty+{MON}*i+0x56 写 0。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
