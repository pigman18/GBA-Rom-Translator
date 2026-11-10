#!/usr/bin/env python3
"""调研㊾ 用纯 ROM 数据验证 `F7 hi` 是 2 字节（不依赖反汇编解读）。

═══════════════════════════════════════════════════════════════════════════
【为什么还要验】
═══════════════════════════════════════════════════════════════════════════
㊽ 从反汇编读出 `F7 hi` 是 2 字节。但反汇编解读可能有偏差。
如果这个结论错了，「用原版字符拼中文」的整套理解就垮了。

必须用**独立的、不依赖代码解读**的方法从数据本身验证。

═══════════════════════════════════════════════════════════════════════════
【验证设计】
═══════════════════════════════════════════════════════════════════════════
若 `F7 hi` 是 2 字节：
  · 文本区里 F7 的出现必须落在**确定的奇偶偏移**上（对齐到 2）
  · 从一个串起点开始，按「F7+1 字节」或「普通 1 字节」交替推进，
    必须在合理步数内到达 0xFF

若 `F7 hi lo` 是 3 字节：
  · 按上面的 2 字节解码器推进，会**在极少步内撞进非法状态**
    （比如永远遇不到 0xFF，或者 hi 大量落在 0xFF）

判据：用两种解码器分别解析同一批中文段，统计「能否顺利解到 0xFF」。
2 字节解码器应几乎 100% 成功；3 字节解码器应经常卡住。

用法：python scripts/research/firered/49_verify_f7_width.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
ZONES = [(0x6D0000, 0x722000), (0xAF5000, 0xAFB000)]


def collect_segments(zh: bytes) -> list[bytes]:
    """按 0xFF 切出含 F7 的文本段（这是编码无关的，因为 FF 一定是串尾）。"""
    out = []
    for lo, hi in ZONES:
        seg = zh[lo:hi]
        pos = 0
        while pos < len(seg):
            e = seg.find(b"\xff", pos)
            if e < 0:
                break
            body = seg[pos:e]
            if body.count(0xF7) >= 2:
                out.append(body)
            pos = e + 1
    return out


def decode_walk(body: bytes, width: int) -> tuple[bool, int]:
    """按 width 字节（2 或 3）解 F7，看能否干净走到末尾。
    返回 (是否成功, 消耗位置)。成功 = 正好用完整段。"""
    i = 0
    n = len(body)
    steps = 0
    while i < n:
        steps += 1
        if steps > n + 10:
            return (False, i)
        b = body[i]
        if b == 0xF7:
            if i + width - 1 >= n:
                return (False, i)     # 越界
            if width == 3:
                # 3 字节语义下，hi lo 都必须在合理范围
                if body[i + 1] == 0xFF:
                    return (False, i)
            i += width
        elif b in (0xF6, 0xF8, 0xFB, 0xFC, 0xFD, 0xFE):
            # 已知识别为控制码，跳过后续字节（粗处理）
            i += 1
        else:
            i += 1
    return (i == n, i)


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()

    segs = collect_segments(zh)
    print("=" * 78)
    print(f"中文文本段（含 ≥2 个 F7）：{len(segs):,} 条")
    print("=" * 78)

    for width, label in ((2, "F7 hi  (2 字节)"), (3, "F7 hi lo (3 字节)")):
        ok = 0
        bad = 0
        for s in segs:
            good, _ = decode_walk(s, width)
            if good:
                ok += 1
            else:
                bad += 1
        print(f"  {label}: 顺利解到末尾 {ok:,}（{ok/len(segs)*100:>5.1f}%）"
              f"  卡住 {bad:,}")

    print("\n" + "=" * 78)
    print("② 对齐检验：F7 在段内的偏移 mod 2 / mod 3 分布")
    print("=" * 78)
    c2 = Counter()
    c3 = Counter()
    for s in segs[:2000]:
        for i, b in enumerate(s):
            if b == 0xF7:
                c2[i % 2] += 1
                c3[i % 3] += 1
    t2 = sum(c2.values())
    print(f"  F7 偏移 mod 2: " +
          ", ".join(f"{k}:{v/t2*100:.1f}%" for k, v in sorted(c2.items())))
    print(f"  F7 偏移 mod 3: " +
          ", ".join(f"{k}:{v/t2*100:.1f}%" for k, v in sorted(c3.items())))
    print(f"\n  ⇒ 若 mod 2 明显偏斜 ⇒ F7 对齐到 2 字节（2 字节编码）")
    print(f"     若 mod 3 偏斜 ⇒ 对齐到 3 字节")

    # ── ③ 直接看：F7 之后那一字节，是不是经常紧跟着另一个 F7 ──────
    print("\n" + "=" * 78)
    print("③ 「F7 x F7 y」序列占比（2 字节编码的强特征）")
    print("=" * 78)
    c = Counter()
    tot = 0
    for s in segs:
        for i in range(len(s) - 3):
            if s[i] == 0xF7:
                tot += 1
                if s[i + 2] == 0xF7:
                    c["F7 x F7"] += 1
                elif s[i + 1] == 0xF7:
                    c["F7 F7"] += 1
                else:
                    c["F7 x <其他>"] += 1
    print(f"  共 {tot:,} 个 F7 位置：")
    for k, v in c.most_common():
        print(f"    {k:<14} {v:>7,}（{v/tot*100:>5.1f}%）")
    print(f"\n  ⇒ 若「F7 x F7」占绝对多数 ⇒ 每个汉字 = F7 + 索引（2 字节）")

    # ── ④ 反证：若 3 字节，则 s[i+2] 应是「字形内偏移」，不该总是 F7 ─
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
