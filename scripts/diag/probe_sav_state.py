#!/usr/bin/env python3
"""一次性探针：解出 AXVJ 存档里「能用金手指跳场景」所需的状态。

为什么需要它：要覆盖战斗/大赛/图鉴这些场景，必须先知道存档里
有没有队伍、徽章、道具、图鉴旗标 —— 没有就得先用 poke 造出来。

── 队伍结构的关键事实（不需要解密）──────────────────────────────────────
Gen3 的 struct Pokemon 共 100 字节，**后 20 字节（party 数据）不加密**：
    +0x54 u32 status
    +0x58 u8  level        ← ★ 明文可读，用它定位队伍
所以只要在 SaveBlock1 里找「count ∈ 1..6 且随后每只 level ∈ 1..100」的
位置，就能确定 partyCount / playerParty 的真实偏移。

用法：python scripts/probe_sav_state.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot" / "tools"))
from savlib import rebuild, SB1_OFF, SB1_SIZE, SB2_OFF, SB2_SIZE, s8, s16, u16, u32  # noqa

SAV = ROOT / "bot" / "scenes" / "POKEMON_RUBY_AXVJ00" / "saves" / "Route118_68-7.sav"
MON = 100
LVL_OFF = 0x54


def find_party(sb1: bytes):
    """暴力定位 partyCount（count 之后紧跟 count 只 level 合法的宝可梦）。

    偏移可以是 +0x00（count 紧贴 party）或 +0x04（有对齐填充），两种都试。
    """
    hits = []
    for gap in (1, 4):
        for o in range(0, len(sb1) - (MON * 6) - gap, 4):
            cnt = sb1[o]
            if not (1 <= cnt <= 6):
                continue
            base = o + gap
            lv = [sb1[base + i * MON + LVL_OFF] for i in range(6)]
            if all(1 <= v <= 100 for v in lv[:cnt]) and all(v == 0 for v in lv[cnt:]):
                hits.append((o, gap, cnt, lv[:cnt]))
    return hits


def main() -> int:
    logical, info = rebuild(SAV.read_bytes())
    print(f"sav={SAV.name} info={info}")
    sb1 = logical[SB1_OFF:SB1_OFF + SB1_SIZE]
    sb2 = logical[SB2_OFF:SB2_OFF + SB2_SIZE]

    print(f"\nSV1 pos=({s16(sb1,0)},{s16(sb1,2)}) "
          f"loc={s8(sb1,4)}:{s8(sb1,5)} warp={s8(sb1,6)}")
    print(f"SB2+0x00 name bytes = {sb2[:8].hex(' ')}")

    hits = find_party(sb1)
    print(f"\npartyCount 候选 {len(hits)} 个：")
    for o, gap, cnt, lv in hits[:12]:
        print(f"  SB1+0x{o:04X} gap={gap} count={cnt} levels={lv}")

    # 队伍详情（等级 + 加密头里的 species 不可读，先看 level/HP）
    if hits:
        o, gap, cnt, _ = hits[0]
        base = o + gap
        print(f"\n队伍（按 SB1+0x{o:04X}/gap{gap}）：")
        for i in range(cnt):
            m = sb1[base + i * MON: base + (i + 1) * MON]
            print(f"  #{i} pid={u32(m,0):08X} otid={u32(m,4):08X} "
                  f"level={m[LVL_OFF]} hp={u16(m,LVL_OFF+4)}/{u16(m,LVL_OFF+6)} "
                  f"maxhp={u16(m,LVL_OFF+6)} atk={u16(m,LVL_OFF+8)}")

    # 徽章 / 图鉴 / 金钱：先按美版偏移探，值不合理就说明偏移不同
    print("\n存档头 0x000..0x080（找 flags / money / pokedex 线索）：")
    for r in range(0, 0x80, 16):
        print(f"  SB1+0x{r:03X}: {sb1[r:r+16].hex(' ')}")

    print("\nSB2 关键字段（options / 图鉴 / 徽章常在这里）：")
    for r in range(0, 0x20, 16):
        print(f"  SB2+0x{r:03X}: {sb2[r:r+16].hex(' ')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
