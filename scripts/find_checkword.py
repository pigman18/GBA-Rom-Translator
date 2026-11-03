#!/usr/bin/env python3
"""定位日版队伍结构里的 checkword（校验子）与加密区边界。

── 已知 ────────────────────────────────────────────────────────────────
· XOR 加减密往返 6/6 通过（verify_mon_crypto.py）⇒ key = pid ^ otid 正确
· 加密区在 +0x20 起（实测 +0x20 是 `57 d9 40 ca` 重复三次，说明同 key）
· pokeruby 说 checkword 在 +0x1C..0x23（4 个 u16 同值）
  ⇒ 日版实测 +0x1C = `b3 01 00 00`，**不是** 4 个同值 u16

── 本脚本判定策略 ──────────────────────────────────────────────────────
候选偏移 = +0x0C..+0x20 的每个 2 字节位置，逐个检查：
  ① 该位置起 8 字节是否为「4 个相同的 u16」（pokeruby 的特征）
  ② 该 u16 是否等于「4 个子结构 u16 和的异或」（真实校验算法）
  ③ 该 u16 是否等于「4 个子结构 u16 和的累加」
命中任一条的偏移就是 checkword 的真实位置。

同时打印整个 100 字节的字段分布，把「头像/昵称/明文区」标出来，
方便后续定位技能区。

用法：python scripts/find_checkword.py
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


def decrypt(m: bytes):
    pid, otid = u32(m, 0), u32(m, 4)
    key = pid ^ otid
    raw = bytearray(m[0x20:0x50])
    for i in range(0, 48, 4):
        raw[i:i + 4] = (u32(raw, i) ^ key).to_bytes(4, "little")
    return pid, otid, key, bytes(raw)


def sums(raw: bytes):
    """4 个 slot 的 u16 和 与 异或 与 总和。"""
    per = []
    for slot in range(4):
        seg = raw[slot * 12:(slot + 1) * 12]
        s = sum(u16(seg, k) for k in range(0, 12, 2)) & 0xFFFF
        per.append(s)
    x = 0
    for s in per:
        x ^= s
    return per, x, sum(per) & 0xFFFF


def main() -> int:
    sav = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.sav"
    logical, _ = rebuild(sav.read_bytes())
    sb1 = logical[SB1_OFF:SB1_OFF + 0x3AC0]
    cnt = sb1[O_COUNT]
    print(f"partyCount={cnt}\n")

    for i in range(cnt):
        m = sb1[O_PARTY + i * MON: O_PARTY + (i + 1) * MON]
        pid, otid, key, raw = decrypt(m)
        per, x, tot = sums(raw)
        print(f"#{i} pid={pid:08X} otid={otid:08X} key={key:08X}")
        print(f"   子结构 u16 和 = {[hex(v) for v in per]}")
        print(f"   异或 = 0x{x:04X}   累加 = 0x{tot:04X}")

        # 候选：+0x00..+0x1F 里找 4 个相同 u16
        found = []
        for off in range(0, 0x20, 2):
            vals = [u16(m, off + k * 2) for k in range(4)]
            if len(set(vals)) != 1:
                continue
            v = vals[0]
            tag = []
            if v == x:
                tag.append("=异或")
            if v == tot:
                tag.append("=累加")
            found.append((off, v, tag))

        if found:
            for off, v, tag in found:
                mark = ("  ★ " + "，".join(tag)) if tag else ""
                print(f"   +0x{off:02X}: 四个同值 u16 = 0x{v:04X}{mark}")
        else:
            print("   +0x00..0x1F 里没有『四个相同 u16』的结构")

        # 把 +0x00..0x20 逐 4 字节打出来，便于人眼判读
        print("   头 32 字节:", " ".join(
            m[o:o + 4].hex(" ") for o in range(0, 0x20, 4)))
        print()

    print("判读：")
    print("  · 若某偏移的四个同值 u16 同时等于『异或』或『累加』⇒ 那就是 checkword")
    print("  · 若一个都没有 ⇒ 日版不做 checkword 校验（改数据更安全），")
    print("    或校验用别的算法，需要另找特征（比如 = pid ^ 某个和）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
