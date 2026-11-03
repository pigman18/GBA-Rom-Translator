#!/usr/bin/env python3
"""验证 Gen3 队伍「解密→加密」是否严格往返，以及 checkword 算法。

── 为什么要单测这一步 ──────────────────────────────────────────────────
改技能时必须保证：
  ① decrypt(encrypt(x)) == x   否则写回去游戏会看到乱码
  ② checkword 算法正确         否则游戏判存档/宝可梦数据损坏

上一版 set_teleport_move.py 回读得到一个荒谬的技能 ID（60040），
说明这两步里至少一步错了。先把它们单独验证清楚，再去改数据。

用法：python scripts/verify_mon_crypto.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot" / "tools"))
from savedit import rebuild, SB1_OFF  # noqa: E402

MON = 100
O_PARTY, O_COUNT = 0x238, 0x234


def u32(b, o): return int.from_bytes(b[o:o + 4], "little")
def u16(b, o): return int.from_bytes(b[o:o + 2], "little")


def decrypt(m: bytes) -> tuple[int, int, int, bytes]:
    pid, otid = u32(m, 0), u32(m, 4)
    key = pid ^ otid
    raw = bytearray(m[0x20:0x50])
    for i in range(0, 48, 4):
        raw[i:i + 4] = (u32(raw, i) ^ key).to_bytes(4, "little")
    return pid, otid, key, bytes(raw)


def encrypt(raw: bytes, key: int) -> bytes:
    out = bytearray(raw)
    for i in range(0, 48, 4):
        out[i:i + 4] = (u32(raw, i) ^ key).to_bytes(4, "little")
    return bytes(out)


def checkword_sums(raw: bytes):
    """返回 4 个 slot 各自的 u16 和，以及它们的异或。"""
    sums = []
    for slot in range(4):
        seg = raw[slot * 12:(slot + 1) * 12]
        s = 0
        for k in range(0, 12, 2):
            s = (s + u16(seg, k)) & 0xFFFF
        sums.append(s)
    w = 0
    for s in sums:
        w ^= s
    return sums, w


def main() -> int:
    sav = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.sav"
    logical, _ = rebuild(sav.read_bytes())
    sb1 = logical[SB1_OFF:SB1_OFF + 0x3AC0]
    cnt = sb1[O_COUNT]
    print(f"partyCount={cnt}\n")

    ok_all = True
    for i in range(cnt):
        m = sb1[O_PARTY + i * MON: O_PARTY + (i + 1) * MON]
        pid, otid, key, raw = decrypt(m)
        enc = encrypt(raw, key)
        same = (enc == m[0x20:0x50])
        sums, w = checkword_sums(raw)
        stored = [u16(m, 0x1C + k * 2) for k in range(4)]
        cw_match = all(s == stored[0] for s in stored) and stored[0] == w
        ok_all &= same
        print(f"#{i} pid={pid:08X} key={key:08X}")
        print(f"   往返一致: {same}")
        print(f"   slot 和 = {[hex(s) for s in sums]}  异或=0x{w:04X}")
        print(f"   文件里存 = {[hex(s) for s in stored]}"
              f"  {'✓ 与异或一致' if cw_match else '✗ 不一致'}")
        print()

    print("结论：")
    print(f"  往返一致：{'全部通过' if ok_all else '有失败 → 加密实现有错'}")
    print("  若『文件里存』= 四个相同的值且等于异或 ⇒ checkword 算法无误，")
    print("  改数据时按同一算法重算即可。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
