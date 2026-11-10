#!/usr/bin/env python3
"""调研㉑ 定案：火红的中文到底「写在哪、原文哪去了、指针怎么改」。

═══════════════════════════════════════════════════════════════════════════
【要解决的矛盾】
═══════════════════════════════════════════════════════════════════════════
⑳ 得到两个看似冲突的结果：
  A) 主文本区 0x6D0000 起 304KB，与原版差异 **94.2%**（整块被换）
  B) 原版 0..0x6D0000 里的 56,910 条日文串，**97.9% 原样保留**

若「文本全部搬走+改指针」，B 成立（原文成为孤儿数据）。
那 A 就必须解释：0x6D0000 在原版里**是什么**？能整块换成文本，
说明那块在原版是**可覆盖区**（填充/无用数据）。

本脚本一次性查清：
  ① 原版 0x6D0000..0x722000 是什么内容（文本？位图？填充？）
  ② 原版真正的日文文本区在哪（全 ROM 区域密度图）
  ③ 汉化把中文写在哪（全 ROM 区域密度图）
  ④ 指针普查：原版指向日文文本的指针槽位，在汉化版里改成了什么
     —— 这是「写新区改指针」的直接量化证据
  ⑤ 是否存在「就地改写」（原文位置变成中文）与「缩短补 00」

用法：python scripts/research/firered/21_layout_verdict.py
"""
from __future__ import annotations

import numpy as np

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"

BASE = 0x08000000
SEG = 0x10000          # 64KB 统计格
BIN = 0x4000           # 16KB 细分格


def load(p: Path) -> np.ndarray:
    return np.frombuffer(p.read_bytes(), dtype=np.uint8)


def jp_char_mask(a: np.ndarray) -> np.ndarray:
    """Gen3 日文字符：0x01–0xDF 视为可打印（含假名/数字/符号），0xFF 串尾。"""
    return (a >= 0x01) & (a <= 0xDF)


def cn_f7_mask(a: np.ndarray) -> np.ndarray:
    return a == 0xF7


def density(mask: np.ndarray, bin_size: int) -> np.ndarray:
    n = len(mask) // bin_size
    return mask[:n * bin_size].reshape(n, bin_size).mean(axis=1)


def top_bins(mask: np.ndarray, bin_size: int, label: str, thresh: float,
             limit: int = 25) -> list[tuple[int, float]]:
    d = density(mask, bin_size)
    idx = np.argsort(d)[::-1]
    out = []
    print(f"\n  {label}（{bin_size//1024}KB 格，密度 ≥{thresh:.0%}）")
    for i in idx:
        if d[i] < thresh or len(out) >= limit:
            break
        out.append((int(i) * bin_size, float(d[i])))
        print(f"    0x{BASE+int(i)*bin_size:08X}  密度 {d[i]:>6.1%}")
    return out


def main() -> int:
    zh = load(FR_ZH)
    ja = load(FR_JA)
    print("=" * 78)
    print(f"汉化 {FR_ZH.name}  {len(zh):,} B")
    print(f"原版 {FR_JA.name}  {len(ja):,} B")
    print(f"长度相同: {len(zh) == len(ja)}")
    print("=" * 78)

    n = min(len(zh), len(ja))

    # ── ① 原版 0x6D0000..0x722000 是什么 ─────────────────────────────
    print("\n" + "=" * 78)
    print("① 原版 0x6D0000..0x722000 的内容性质")
    print("=" * 78)
    seg_ja = ja[0x6D0000:0x722000]
    seg_zh = zh[0x6D0000:0x722000]
    diff = int((seg_ja != seg_zh).sum())
    print(f"  区间大小 {len(seg_ja):,} B，与原版不同 {diff:,} B（{diff/len(seg_ja):.1%}）")

    for nm, arr in (("原版", seg_ja), ("汉化", seg_zh)):
        uniq = len(np.unique(arr))
        zero = float((arr == 0).mean())
        ff = float((arr == 0xFF).mean())
        f7 = float((arr == 0xF7).mean())
        jpr = float(jp_char_mask(arr).mean())
        print(f"  {nm}: 不同字节值 {uniq:>3}  00={zero:>6.1%}  FF={ff:>6.1%}  "
              f"F7={f7:>6.1%}  日文字符比例={jpr:>6.1%}")

    print(f"\n  原版前 64 字节: {seg_ja[:64].tobytes().hex(' ')}")
    print(f"  汉化前 64 字节: {seg_zh[:64].tobytes().hex(' ')}")
    # 判读
    ja_uniq = len(np.unique(seg_ja))
    if ja_uniq < 64:
        print(f"  ⇒ 原版该区间只有 {ja_uniq} 种字节值 ⇒ **填充/无用区，可安全覆盖**")
    else:
        print(f"  ⇒ 原版该区间有 {ja_uniq} 种字节值 ⇒ 是实数据（需看是不是文本）")

    # ── ② 原版日文文本区在哪 ─────────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 原版（BPRJ）日文文本密度图")
    print("=" * 78)
    ja_mask = jp_char_mask(ja)
    top_bins(ja_mask, SEG, "64KB 格 top", 0.60, 30)

    # ── ③ 汉化中文分布 ───────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 汉化（2.2）中文 F7 密度图")
    print("=" * 78)
    zh_mask = cn_f7_mask(zh)
    top_bins(zh_mask, SEG, "64KB 格 top", 0.05, 30)

    # ── ④ 指针普查 ───────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("④ 指针普查：原版指向日文文本的槽位，汉化改成了什么")
    print("=" * 78)

    def u32arr(a: np.ndarray) -> np.ndarray:
        m = len(a) // 4 * 4
        return a[:m].view(np.uint32).astype(np.uint64)

    pa = u32arr(ja)
    pz = u32arr(zh)

    def is_rom(p: np.ndarray) -> np.ndarray:
        return (p >= BASE) & (p < BASE + n)

    # 「文本起点」集合：日文串起点（前一字节是 FF 或 00 或非日文字符）
    def text_starts(a: np.ndarray) -> np.ndarray:
        mask = jp_char_mask(a)
        prev = np.zeros_like(mask)
        prev[1:] = mask[:-1]
        # 起点 = 自己是日文字符，前一个不是
        st = mask & ~prev
        # 并且往后至少 6 个都是日文字符（排除偶然）
        valid = st.copy()
        for k in range(1, 6):
            valid[k:] &= mask[:-k] if k else mask
        # 简化：检查 st 位置后 6 字节全为日文
        ok = np.zeros(len(a), dtype=bool)
        run = np.ones(len(a), dtype=bool)
        for k in range(6):
            r = np.zeros(len(a), dtype=bool)
            r[:len(a) - k] = mask[k:]
            run &= r
        ok = st & run
        return ok

    ja_starts = text_starts(ja)
    ja_start_idx = np.flatnonzero(ja_starts)
    print(f"  原版日文文本起点（≥6 连续日文字符）：{len(ja_start_idx):,} 个")

    # 指针落在这些起点上的槽位
    start_set = np.zeros(n, dtype=bool)
    start_set[ja_start_idx] = True
    ptr_ok = is_rom(pa)
    off_idx = np.clip(pa - BASE, 0, n - 1).astype(np.int64)
    hits_jp_text = ptr_ok & start_set[off_idx]
    # 只取实际用到文本区的（< 0x800000 范围太宽，收敛到有文本的区）
    slots = np.flatnonzero(hits_jp_text)
    print(f"  原版里「指向日文文本起点」的 u32 槽位：{len(slots):,} 个")

    if len(slots):
        old = pa[slots]
        new = pz[slots] if len(pz) > slots.max() else None
        same = int((old == new).sum()) if new is not None else 0
        print(f"\n  这些槽位在汉化版里：")
        print(f"    值不变：      {same:>7,}（{same/len(slots):>5.1%}）")
        print(f"    值被改：      {len(slots)-same:>7,}"
              f"（{(len(slots)-same)/len(slots):>5.1%}）")

        # 改到了哪
        moved = slots[(old != new)]
        nt = pz[moved]
        tgt_rom = (nt >= BASE) & (nt < BASE + n)
        print(f"\n  被改的 {len(moved):,} 个槽位，新值性质：")
        print(f"    仍是 ROM 指针：{int(tgt_rom.sum()):>7,}"
              f"（{tgt_rom.mean():>5.1%}）")
        if tgt_rom.any():
            nt_off = (nt[tgt_rom] - BASE).astype(np.int64)
            in_new_text = ((nt_off >= 0x6D0000) & (nt_off < 0x722000)) | \
                          ((nt_off >= 0xAF5000) & (nt_off < 0xAFB000))
            print(f"    其中指向已知中文文本区：{int(in_new_text.sum()):,}"
                  f"（{in_new_text.mean():>5.1%}）")
            # 分布
            bins = (nt_off // SEG)
            u, c = np.unique(bins, return_counts=True)
            order = np.argsort(c)[::-1][:12]
            print(f"    新目标分布 top12（64KB 格）：")
            for i in order:
                print(f"      0x{BASE+int(u[i])*SEG:08X}  {int(c[i]):>6,}")
        # 新值不是 ROM 指针的，看看是什么
        not_rom = nt[~tgt_rom]
        if len(not_rom):
            print(f"    非 ROM 值示例：{[f'0x{x:08X}' for x in not_rom[:8]]}")

    # ── ⑤ 就地改写与缩短补 00 ────────────────────────────────────────
    print("\n" + "=" * 78)
    print("⑤ 「就地改写 / 缩短补 00」实测量")
    print("=" * 78)
    # 对每个原版文本起点，看汉化同偏移处
    idx = ja_start_idx
    step = max(1, len(idx) // 25000)
    sample = idx[::step]
    print(f"  抽样 {len(sample):,} 个原版文本起点")
    cat = {"原样未动": 0, "整段清 00": 0, "原位是中文": 0, "其他改动": 0}
    ex_clear, ex_cn = [], []
    for o in sample:
        o = int(o)
        a = ja[o:o + 64]
        b = zh[o:o + 64]
        if np.array_equal(a, b):
            cat["原样未动"] += 1
            continue
        # 该位置起汉化是否中文
        if b[0] == 0xF7 and len(ex_cn) < 6:
            ex_cn.append(o)
            cat["原位是中文"] += 1
            continue
        if np.all(b[:16] == 0) and len(ex_clear) < 6:
            ex_clear.append(o)
            cat["整段清 00"] += 1
            continue
        cat["其他改动"] += 1

    for k, v in cat.items():
        print(f"    {k:<10} {v:>7,}（{v/len(sample):>5.1%}）")
    for o in ex_cn:
        print(f"    原位中文示例 0x{BASE+o:08X}")
        print(f"      原: {ja[o:o+40].tobytes().hex(' ')}")
        print(f"      汉: {zh[o:o+40].tobytes().hex(' ')}")
    for o in ex_clear:
        print(f"    清 00 示例 0x{BASE+o:08X}")
        print(f"      原: {ja[o:o+40].tobytes().hex(' ')}")
        print(f"      汉: {zh[o:o+40].tobytes().hex(' ')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
