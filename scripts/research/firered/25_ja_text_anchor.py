#!/usr/bin/env python3
"""调研㉕ 用「被改指针的旧值」反推原版日文文本区 —— 拿到可靠锚点。

═══════════════════════════════════════════════════════════════════════════
【㉓ 为什么错了】
═══════════════════════════════════════════════════════════════════════════
㉓ 用 `0x01–0xDF` 当日文字符，这覆盖了 87% 的字节空间，
于是把二进制数据全切成「日文串」→ 824,230 条，示例是随机字节。

**必须换根本不同的办法：不去猜字符集，而是找「已知是文本」的地址。**

═══════════════════════════════════════════════════════════════════════════
【锚点法】
═══════════════════════════════════════════════════════════════════════════
已知事实（㉑ ④ 实测）：
  · 原版里指向「日文文本」的 u32 槽位 6,607 个
  · 其中 989 个在汉化版被**改指向中文文本区**（0x6D0000 / 0xAF5000）
  · 这 989 个槽位的**旧值**，就是原版日文文本的真实地址

⇒ 这 989 个旧值 = **100% 保真的「这里是文本」样本**，
   用它们的分布就能确定原版日文文本集中在哪些区，
   再用这些区的实际字节反推字符集，而不是瞎猜 0x01–0xDF。

本脚本：
  ① 列出 989 个旧值的分布（按 4KB 细格），确定日文文本区
  ② 在这些区里统计字节频率，反推真实日文字符集
  ③ 用推出来的字符集重新切串，看真正有多少条日文文本
  ④ 交叉验证：切出来的串里有多少起点被指针引用

用法：python scripts/research/firered/25_ja_text_anchor.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"

BASE = 0x08000000
NEW_TEXT = [(0x6D0000, 0x722000), (0xAF5000, 0xAFB000)]


def in_new_text(off: int) -> bool:
    return any(lo <= off < hi for lo, hi in NEW_TEXT)


def main() -> int:
    zh_b = FR_ZH.read_bytes()
    ja_b = FR_JA.read_bytes()
    n = min(len(zh_b), len(ja_b))
    m = n // 4 * 4

    pa = np.frombuffer(ja_b[:m], dtype=np.uint32).astype(np.uint64)
    pz = np.frombuffer(zh_b[:m], dtype=np.uint32).astype(np.uint64)
    is_rom = (pa >= BASE) & (pa < BASE + n) & (pz >= BASE) & (pz < BASE + n)
    changed = (pa != pz) & is_rom

    old_off = (pa - BASE).astype(np.int64)
    new_off = (pz - BASE).astype(np.int64)

    # 新值在中文区、旧值不在
    new_in_cn = np.array([in_new_text(int(x)) for x in new_off])
    old_in_cn = np.array([in_new_text(int(x)) for x in old_off])
    sel = np.flatnonzero(changed & new_in_cn & ~old_in_cn)

    print("=" * 78)
    print("① 锚点：原指向日文、汉化改指向中文区的指针槽位")
    print("=" * 78)
    print(f"  命中 {len(sel):,} 个槽位  ← 这些旧值 100% 是原版日文文本地址")

    olds = old_off[sel]
    news = new_off[sel]

    print(f"\n  旧值分布（4KB 细格，只列 ≥5 个的）：")
    ub, uc = np.unique(olds // 0x1000, return_counts=True)
    for cnt, b in sorted(zip(uc.tolist(), ub.tolist()), reverse=True):
        if cnt < 5:
            break
        print(f"    0x{BASE+b*0x1000:08X}  {cnt:>4} 个")

    print(f"\n  新值分布（64KB 格）：")
    ub2, uc2 = np.unique(news // 0x10000, return_counts=True)
    for cnt, b in sorted(zip(uc2.tolist(), ub2.tolist()), reverse=True):
        print(f"    0x{BASE+b*0x10000:08X}  {cnt:>4} 个")

    # ── ② 在这些旧值处反推字符集 ────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 从锚点处 dump 真实日文串，反推字符集")
    print("=" * 78)
    segs = []
    for o in olds.tolist()[:400]:
        e = ja_b.find(b"\xff", o, o + 300)
        if e < 0:
            continue
        segs.append(ja_b[o:e])
    print(f"  取到 {len(segs)} 条真实日文串")
    print(f"  长度：均值 {np.mean([len(s) for s in segs]):.1f} "
          f"中位 {np.median([len(s) for s in segs]):.0f} "
          f"最大 {max(len(s) for s in segs)}")

    cnt = Counter()
    for s in segs:
        cnt.update(s)
    print(f"\n  字节频率 top 40（字符集候选）：")
    tot = sum(cnt.values())
    items = cnt.most_common(40)
    for k in range(0, 40, 4):
        row = "  ".join(f"{b:02X}:{c/tot*100:4.1f}%" for b, c in items[k:k + 4])
        print(f"    {row}")

    used = sorted(cnt)
    print(f"\n  不同字节值：{len(used)} 种")
    print(f"    0x{min(used):02X} .. 0x{max(used):02X}")
    # 找最大空隙，推断字符集边界
    gaps = [(used[i + 1] - used[i], used[i], used[i + 1])
            for i in range(len(used) - 1)]
    gaps.sort(reverse=True)
    print(f"  最大字节空隙 top 6（可推断字符集分段）：")
    for g, a, b in gaps[:6]:
        print(f"    0x{a:02X} → 0x{b:02X}  间隙 {g}")

    print(f"\n  采样 10 条原文：")
    for s in segs[:10]:
        print(f"    [{len(s):>3}] {s[:48].hex(' ')}")

    # ── ③ 用推出来的字符集重新切串 ──────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 用锚点推出的字符集重新切分全 ROM")
    print("=" * 78)
    # 字符集 = 锚点串里出现过的字节（去掉 FF）
    charset = set(used) - {0xFF}
    print(f"  字符集大小 {len(charset)}")

    jp = np.zeros(n, dtype=bool)
    for b in charset:
        jp |= (np.frombuffer(ja_b[:n], dtype=np.uint8) == b)

    print(f"  日文字节占比 {jp.mean():.1%}（之前瞎猜的 0x01–0xDF 判据是 "
          f"{((np.frombuffer(ja_b[:n],dtype=np.uint8)>=1)&(np.frombuffer(ja_b[:n],dtype=np.uint8)<=0xDF)).mean():.1%}）")

    prev = np.zeros(n, dtype=bool)
    prev[1:] = jp[:-1]
    cand = np.flatnonzero(jp & ~prev)
    print(f"  候选起点 {len(cand):,}")

    # 校验：长度 2..200、以 FF 结尾、且**字节多样性低**（真文本只用字符集）
    good = []
    for o in cand.tolist():
        e = ja_b.find(b"\xff", o, o + 202)
        if e < 0:
            continue
        L = e - o
        if L < 2:
            continue
        seg = ja_b[o:e]
        if len(set(seg)) <= 0.55 * len(seg) + 3:   # 文本重复率高
            good.append((o, L))
    print(f"  通过多样性校验：{len(good):,} 条")
    gl = np.array([g[1] for g in good])
    if len(gl):
        print(f"    长度：均值 {gl.mean():.1f} 中位 {np.median(gl):.0f} "
              f"≤6 的 {int((gl <= 6).sum()):,}（{(gl <= 6).mean():.1%}）")

    gt = np.array([g[0] for g in good])
    print(f"\n  分布（64KB 格，只列 ≥100 条）：")
    gb, gc = np.unique(gt // 0x10000, return_counts=True)
    for cnt2, b in sorted(zip(gc.tolist(), gb.tolist()), reverse=True):
        if cnt2 < 100:
            break
        print(f"    0x{BASE+b*0x10000:08X}  {cnt2:>6,} 条")

    # ── ④ 交叉验证：这些串起点被指针引用多少 ────────────────────────
    print("\n" + "=" * 78)
    print("④ 交叉验证：串起点被 u32 指针直接引用的比例")
    print("=" * 78)
    start_set = set(gt.tolist())
    ptr_ok = np.flatnonzero(is_rom[:m])
    ptr_vals = old_off[ptr_ok]
    hit = sum(1 for v in ptr_vals.tolist() if v in start_set)
    print(f"  原版指向「校验通过串起点」的 u32 槽位：{hit:,}")
    print(f"  覆盖率：{hit/max(1,len(gt))*100:.1f}%")
    print(f"  ⇒ 覆盖率低说明大部分文本不靠 u32 指针直达（对应「无指针」类）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
