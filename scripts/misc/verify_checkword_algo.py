#!/usr/bin/env python3
"""确定 checkword 的精确算法（日版：+0x1C 的 u16 = ?）。

── 已实测 ────────────────────────────────────────────────────────────
6/6 只的 `+0x1C` 都等于「4 个 slot 的 u16 和在 slot 顺序下的**累加**」。
但还差一步：确认是
  ① 按 slot 顺序累加（slot0+slot1+slot2+slot3），还是
  ② 按子结构号顺序累加（Growth+Attacks+EVs+Misc）
两者只在顺序表非平凡时才有差别，本脚本把两种都算出来对比。

另外确认：
  ③ 是否要再 `& 0xFFFF`（u32 溢出）—— 用每组数据验证

用法：python scripts/verify_checkword_algo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot" / "tools"))
from savedit import rebuild, SB1_OFF  # noqa: E402

MON = 100
O_PARTY, O_COUNT = 0x238, 0x234

ORDER = [
    [0, 1, 2, 3], [0, 1, 3, 2], [0, 2, 1, 3], [0, 3, 1, 2],
    [0, 2, 3, 1], [0, 3, 2, 1], [1, 0, 2, 3], [1, 0, 3, 2],
    [2, 0, 1, 3], [3, 0, 1, 2], [2, 0, 3, 1], [3, 0, 2, 1],
    [1, 2, 0, 3], [1, 3, 0, 2], [2, 1, 0, 3], [3, 1, 0, 2],
    [2, 3, 0, 1], [3, 2, 0, 1], [1, 2, 3, 0], [1, 3, 2, 0],
    [2, 1, 3, 0], [3, 1, 2, 0], [2, 3, 1, 0], [3, 2, 1, 0],
]


def u32(b, o): return int.from_bytes(b[o:o + 4], "little")
def u16(b, o): return int.from_bytes(b[o:o + 2], "little")


def decrypt(m: bytes):
    pid, otid = u32(m, 0), u32(m, 4)
    key = pid ^ otid
    raw = bytearray(m[0x20:0x50])
    for i in range(0, 48, 4):
        raw[i:i + 4] = (u32(raw, i) ^ key).to_bytes(4, "little")
    return pid, otid, key, bytes(raw)


def slot_sums(raw: bytes):
    return [sum(u16(raw, s * 12 + k) for k in range(0, 12, 2)) & 0xFFFF
            for s in range(4)]


def main() -> int:
    sav = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.sav"
    logical, _ = rebuild(sav.read_bytes())
    sb1 = logical[SB1_OFF:SB1_OFF + 0x3AC0]
    cnt = sb1[O_COUNT]
    print(f"partyCount={cnt}\n")

    ok_slot = ok_sub = 0
    for i in range(cnt):
        m = sb1[O_PARTY + i * MON: O_PARTY + (i + 1) * MON]
        pid, _, _, raw = decrypt(m)
        per = slot_sums(raw)
        stored = u16(m, 0x1C)

        # ① 按 slot 顺序累加
        by_slot = sum(per) & 0xFFFF
        # ② 按子结构号顺序累加（order[m] = 每个 slot 存的子结构号 → 取逆）
        order = ORDER[pid % 24]
        by_sub = 0
        for sub_id in range(4):
            slot = order.index(sub_id)
            by_sub = (by_sub + per[slot]) & 0xFFFF

        s1 = "✓" if by_slot == stored else "✗"
        s2 = "✓" if by_sub == stored else "✗"
        ok_slot += (by_slot == stored)
        ok_sub += (by_sub == stored)
        print(f"#{i} pid%24={pid % 24:2d}  存储=0x{stored:04X}  "
              f"按slot=0x{by_slot:04X} {s1}   按子结构=0x{by_sub:04X} {s2}")

    print(f"\n按 slot 顺序命中 {ok_slot}/{cnt}")
    print(f"按子结构顺序命中 {ok_sub}/{cnt}")
    if ok_slot == cnt:
        print("\n⇒ 算法：checkword = (sum(四个 slot 的 u16 和)) & 0xFFFF")
        print("  写在 +0x1C（u16），+0x1E 固定 0。改任何子结构后按此重算。")
    elif ok_sub == cnt:
        print("\n⇒ 算法：checkword = 按子结构号顺序累加四个 slot 的和")
    else:
        print("\n⇒ 两种都不完全命中，需要继续找算法")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
