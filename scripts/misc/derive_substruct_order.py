#!/usr/bin/env python3
"""反推 Gen3 子结构顺序表：用「PP 必须 <= 该技能的 PP 上限」当校验。

── 为什么不再照抄 pokeruby 的表 ────────────────────────────────────────
用 pokeruby 的 gSubstructOrder 解 AXVJ 队伍，6 只里 3 只解出垃圾
（moves=[14659,25397,6703,0]、pp=[0,0,0,0]）。
而 #1/#5（pid%24 都是 7）解得完美：moves=[33,57,341,58] pp=[35,18,15,4]。
⇒ 数据没问题，是**顺序表或字段偏移在日版不同**。

── 本脚本做法 ──────────────────────────────────────────────────────────
不假设顺序，改为：对每只宝可梦，
  ① 解密 48 字节
  ② 按 slot A 取「Attacks 子结构」，读出 4 个技能 + 4 个 PP
  ③ **校验**：每个技能 ID 必须是已知技能（1..354），
     且 PP[i] 在 1..64 之间（不能全 0）
  ④ 找能让全部 6 只都通过校验的「slot 归属」
若 pokeruby 表在 slot 层面对，那只需要找出「Attacks 在第几个 slot」的映射。

用法：python scripts/derive_substruct_order.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot" / "tools"))
from savedit import rebuild, SB1_OFF  # noqa: E402

MON = 100
O_PARTY, O_COUNT = 0x238, 0x234

# pokeruby gSubstructOrder：order[pid%24] = 每个 slot 存放的子结构编号
# （0=Growth 1=Attacks 2=EVs 3=Misc）
ORDER = [
    [0, 1, 2, 3], [0, 1, 3, 2], [0, 2, 1, 3], [0, 3, 1, 2],
    [0, 2, 3, 1], [0, 3, 2, 1], [1, 0, 2, 3], [1, 0, 3, 2],
    [2, 0, 1, 3], [3, 0, 1, 2], [2, 0, 3, 1], [3, 0, 2, 1],
    [1, 2, 0, 3], [1, 3, 0, 2], [2, 1, 0, 3], [3, 1, 0, 2],
    [2, 3, 0, 1], [3, 2, 0, 1], [1, 2, 3, 0], [1, 3, 2, 0],
    [2, 1, 3, 0], [3, 1, 2, 0], [2, 3, 1, 0], [3, 2, 1, 0],
]

MAX_MOVE = 354


def u32(b, o): return int.from_bytes(b[o:o + 4], "little")
def u16(b, o): return int.from_bytes(b[o:o + 2], "little")


def decrypt(m: bytes):
    pid, otid = u32(m, 0), u32(m, 4)
    key = pid ^ otid
    raw = bytearray(m[0x20:0x50])
    for i in range(0, 48, 4):
        v = u32(raw, i) ^ key
        raw[i:i + 4] = v.to_bytes(4, "little")
    return pid, bytes(raw)


def score_attacks(seg: bytes):
    """给一个 12 字节窗口打分：像不像 Attacks 子结构。"""
    moves = [u16(seg, 0), u16(seg, 2), u16(seg, 4), u16(seg, 6)]
    pps = list(seg[8:12])
    if not (1 <= moves[0] <= MAX_MOVE):
        return 0
    if any(mv > MAX_MOVE for mv in moves):
        return 0
    if pps[0] == 0 or pps[0] > 64:
        return 0
    # 有效技能越多、PP 越合理，分越高
    n = sum(1 for mv in moves if mv != 0)
    p = sum(1 for x in pps if 0 < x <= 64)
    return n * 2 + p


def main() -> int:
    sav = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.sav"
    logical, _ = rebuild(sav.read_bytes())
    sb1 = logical[SB1_OFF:SB1_OFF + 0x3AC0]
    cnt = sb1[O_COUNT]
    print(f"{sav.name} partyCount={cnt}\n")

    # 对每只，看 4 个 slot 里哪个最像 Attacks
    hits = {0: [], 1: [], 2: [], 3: []}
    for i in range(cnt):
        m = sb1[O_PARTY + i * MON: O_PARTY + (i + 1) * MON]
        pid, raw = decrypt(m)
        best = None
        print(f"#{i} pid%24={pid % 24} level={m[0x54]}")
        for slot in range(4):
            seg = raw[slot * 12:(slot + 1) * 12]
            s = score_attacks(seg)
            moves = [u16(seg, 0), u16(seg, 2), u16(seg, 4), u16(seg, 6)]
            pps = list(seg[8:12])
            mark = ""
            if s >= 4:
                mark = "  ← 像 Attacks"
                hits[slot].append(i)
            print(f"   slot{slot} score={s:2d} moves={moves} pp={pps}{mark}")
        print()

    print("各 slot 被判为 Attacks 的次数：", {k: len(v) for k, v in hits.items()})
    print("\n判读：若某个 slot 命中 6/6，且 pokeruby 表里 Attacks(1) 常落在该 slot，")
    print("      说明表本身对、只是我把『slot→子结构』方向搞反了。")
    print("      pokeruby 语义：order[i] = 第 i 个 slot 存的子结构编号；")
    print("      若实际反过来（order[i] = 子结构 i 放在哪个 slot），取逆即可。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
