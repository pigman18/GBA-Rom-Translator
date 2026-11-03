#!/usr/bin/env python3
"""解出队伍的技能列表，看有没有「传送术 / 飞翔 / 潜水」这类野外传送技能。

── 为什么关心这个 ────────────────────────────────────────────────────
已实测：`SaveBlock1.lastHealLocation`(+0x1C) 写入**能保住**
（写 Route118 0:33 x68 y7 后走出商店门，值仍是 `00 21 ff 00 44 07`）。

而 Gen3 里「传送术（Teleport / テレポート）」的野外效果 =
**回到 lastHealLocation**（源码 `Overworld_ResetStateAfterTeleport`）。

⇒ 如果队伍里有会传送术的宝可梦，那么：
     poke lastHealLocation = 目标地图
     → 野外使用传送术
     → **直接落到目标地图**

这比「造白屏」干净得多：不用解密队伍、不用打仗、不改 HP。

── Gen3 队伍加密（解密后才能读技能）──────────────────────────────────
每只 100 字节：+0x00..0x1F 是头（pid/otid/昵称…），+0x20..0x4F 是
**加密的 48 字节数据区**（4 个 12 字节子结构，顺序由 pid%24 决定），
+0x50.. 是明文（status/level/hp/stats）。

解密：key = pid ^ otid，每 4 字节 XOR key；
再按 pid%24 查表确定 4 个子结构的真实顺序；
技能在 "Attacks" 子结构里（mov1,mov2,mov3,mov4 各 u16）。

本脚本按 pokeruby 的 gSubstructOrder 表实现解密，输出每只的技能 ID，
并标出哪些是传送/飞翔类。

用法：python scripts/dump_party_moves.py [sav路径]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot" / "tools"))
from savedit import rebuild, SB1_OFF  # noqa: E402

MON_SIZE = 100
O_PARTY_BLOCK = 0x238
O_COUNT = 0x234
LVL = 0x54

# pokeruby: gSubstructOrder[24][4]，值 0=Growth 1=Attacks 2=EVs 3=Misc
SUBSTRUCT_ORDER = [
    [0, 1, 2, 3], [0, 1, 3, 2], [0, 2, 1, 3], [0, 3, 1, 2],
    [0, 2, 3, 1], [0, 3, 2, 1], [1, 0, 2, 3], [1, 0, 3, 2],
    [2, 0, 1, 3], [3, 0, 1, 2], [2, 0, 3, 1], [3, 0, 2, 1],
    [1, 2, 0, 3], [1, 3, 0, 2], [2, 1, 0, 3], [3, 1, 0, 2],
    [2, 3, 0, 1], [3, 2, 0, 1], [1, 2, 3, 0], [1, 3, 2, 0],
    [2, 1, 3, 0], [3, 1, 2, 0], [2, 3, 1, 0], [3, 2, 1, 0],
]

# 只列与「野外传送」相关的招式 ID
FIELD_MOVES = {
    100: "テレポート Teleport（回 lastHealLocation）",
    19: "そらをとぶ Fly",
    291: "ダイビング Dive",
    57: "なみのり Surf",
    250: "うずしお Whirlpool",
}


def u32(b, o): return int.from_bytes(b[o:o + 4], "little")
def u16(b, o): return int.from_bytes(b[o:o + 2], "little")


def decrypt_mon(m: bytes):
    """返回 4 个子结构的字节（按真实顺序排好：Growth/Attacks/EVs/Misc）。"""
    pid, otid = u32(m, 0), u32(m, 4)
    key = pid ^ otid
    raw = bytearray(m[0x20:0x50])
    for i in range(0, 48, 4):
        v = u32(raw, i) ^ key
        raw[i:i + 4] = v.to_bytes(4, "little")
    order = SUBSTRUCT_ORDER[pid % 24]
    # order[slot] = 该 slot 存放的子结构编号
    subs = [None] * 4
    for slot, sub_id in enumerate(order):
        subs[sub_id] = bytes(raw[slot * 12:(slot + 1) * 12])
    return subs     # subs[0]=Growth [1]=Attacks [2]=EVs [3]=Misc


def main() -> int:
    sav = (Path(sys.argv[1]) if len(sys.argv) > 1
           else ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.sav")
    logical, _ = rebuild(sav.read_bytes())
    sb1 = logical[SB1_OFF:SB1_OFF + 0x3AC0]
    cnt = sb1[O_COUNT]
    print(f"{sav.name}  partyCount={cnt}")

    for i in range(cnt):
        m = sb1[O_PARTY_BLOCK + i * MON_SIZE: O_PARTY_BLOCK + (i + 1) * MON_SIZE]
        subs = decrypt_mon(m)
        atk = subs[1]
        moves = [u16(atk, 0), u16(atk, 2), u16(atk, 4), u16(atk, 6)]
        pp = list(atk[8:12])
        lvl = m[LVL]
        hits = [(mv, FIELD_MOVES[mv]) for mv in moves if mv in FIELD_MOVES]
        print(f"\n#{i} level={lvl}", end="")
        print(f"  moves={moves}  pp={pp}")
        if hits:
            for mv, name in hits:
                print(f"    ★ 有野外传送技能：{mv} {name}")

    print("\n下一步：若上面出现 100(Teleport)，则")
    print("  1) poke lastHealLocation = 目标地图")
    print("  2) 在野外对该宝可梦使用「传送术」")
    print("  ⇒ 直接落到目标地图（不用打仗、不用解密改 HP）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
