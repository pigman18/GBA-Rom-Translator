#!/usr/bin/env python3
"""调研(196) 用「同码位必同字形」反查：建立 码位 → 字形 的实证映射表。

═══════════════════════════════════════════════════════════════════════════
【(195) 之后的困境与出路】
═══════════════════════════════════════════════════════════════════════════
已确认 0x08B64A40 是 **F7 解码缓冲区**（值分布 FF 47.6%、54 种值、
前 64B 形如 `ff ff 55 f7 9a f7 9b 55 ...` 内含 f7 标记），不是字库。
0x081DB660 是文本转码器。0x0203F2C0 是 11 项 hi 页映射表。
0x08FE5100 是 108 项文本分派表。

⇒ **所有已找到的东西都是「文本处理」，字形查找在另一条路径上。**

【本脚本换一个不需要找到函数的办法：直接建立实证映射】
原理（无需求助反汇编）：
  · tilemap 给出了「屏幕上每个位置是哪个字形 tile」
  · F7 文本流给出了「屏幕上每个位置是哪个码位」
  · 两者按屏幕顺序对齐 ⇒ 得到 **(码位 → 字形 tile)** 的实证对照

只要这张对照表成立，就能：
  Q1 判断「同一码位是否总是同一字形」（验证码位是唯一的）
  Q2 统计已知多少码位（当前只有 144 个位置）
  Q3 **用码位去 ROM 里查**：若 码位i 与 码位j 的字形在 ROM 中相邻，
      则说明 ROM 里确有按码位排列的字库，只是偏移不同

【关键：如何拿到屏幕对应的 F7 文本】
 屏幕显示的是「继续游戏 / 主角 RED / 时间 22:04 / 图鉴 62只 / 徽章 7枚 /
 开始新游戏」，这些文本在 ROM 里都是 F7 串，可以搜到。
 用 ROM 里的 F7 串做锚，与 tilemap 的 144 个位置对齐。

用法：python scripts/research/firered/196_codepoint_glyph_map.py
"""
from __future__ import annotations

import struct
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SNAP = ROOT / "work" / "_probe" / "snap3"
OUT = ROOT / "work" / "_probe" / "codemap196"
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
BASE = 0x08000000
SCREEN_BASE = 0xF000


def tile_nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob[y * 4 + x // 2]
            m[y, x] = (v & 0x0F) if x % 2 == 0 else (v >> 4)
    return m


def entry(vr: bytes, r: int, c: int) -> int:
    return struct.unpack_from("<H", vr, SCREEN_BASE + (r * 32 + c) * 2)[0]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    vr = (SNAP / "vram.bin").read_bytes()

    # ── ① 从 tilemap 取 6 行文字，每行 24 字 ────────────
    text_rows = [r for r in range(20)
                 if any(((entry(vr, r, c) >> 12) & 0xF) == 15 for c in range(30))]
    print(f"文字行（tilemap 上排）：{text_rows}")
    start = text_rows[0]
    lines = []
    for r in range(start, 19, 2):
        tiles = []
        for c in range(30):
            et = entry(vr, r, c)
            if ((et >> 12) & 0xF) != 15:
                continue
            eb = entry(vr, r + 1, c)
            tiles.append((c, et & 0x3FF, eb & 0x3FF))
        if tiles:
            lines.append({"row": r, "tiles": tiles})
    print(f"共 {len(lines)} 行")
    for ln in lines:
        print(f"  行{ln['row']:>2}  {len(ln['tiles'])} 字  "
              f"tile上={ [t[1] for t in ln['tiles'][:8]] }")

    # ── ② 把每行渲染成可读字符画，人工识别内容 ───────────
    print("\n" + "=" * 78)
    print("② 每行文字按 8x16 渲染")
    print("=" * 78)
    for li, ln in enumerate(lines):
        print(f"\n  ── 行 {li} (tilemap row {ln['row']}) ──")
        canvas = np.full((16, len(ln["tiles"]) * 8), 10, dtype=np.uint8)
        for i, (c, tt, tb) in enumerate(ln["tiles"]):
            for half, t in ((0, tt), (1, tb)):
                o = t * 32
                if o + 32 <= len(vr):
                    canvas[half * 8:(half + 1) * 8, i * 8:(i + 1) * 8] = \
                        tile_nibs(vr[o:o + 32])
        for y in range(16):
            print("    " + "".join(
                {0: ".", 10: " ", 11: "+", 12: "#"}.get(int(v), "?")
                for v in canvas[y]))

    # ── ③ 搜索 ROM 里与这些行匹配的 F7 串 ────────────────
    print("\n" + "=" * 78)
    print("③ ROM 里的 F7 串（3 字节一字），按出现次数排序")
    print("=" * 78)
    zh = ROM_ZH.read_bytes()
    # 解出所有 F7 串
    strings = []
    i = 0
    N = len(zh)
    while i < N - 3:
        if zh[i] == 0xF7 and zh[i + 1] != 0xFF:
            s = []
            j = i
            while j < N - 3 and zh[j] == 0xF7 and zh[j + 1] != 0xFF:
                s.append((zh[j + 1], zh[j + 2]))
                j += 3
            if len(s) >= 2:
                strings.append({"off": i, "codes": s})
            i = max(j, i + 3)
        else:
            i += 1
    print(f"  长度>=2 的 F7 串：{len(strings):,}")
    len_counter = Counter(len(s["codes"]) for s in strings)
    print(f"  串长分布（Top 10）：{len_counter.most_common(10)}")

    # 找长度 = 24 的串（一行 24 字）
    l24 = [s for s in strings if len(s["codes"]) == 24]
    print(f"  长度正好 24 的串：{len(l24)}")
    for s in l24[:8]:
        print(f"    0x{BASE + s['off']:08X}  {s['codes'][:8]}")

    # ── ④ 码位集合统计 ──────────────────────────────────
    print("\n" + "=" * 78)
    print("④ 码位（hi,lo）统计")
    print("=" * 78)
    all_codes = Counter()
    for s in strings:
        for c in s["codes"]:
            all_codes[c] += 1
    print(f"  出现的不同码位：{len(all_codes):,}")
    hi_pages = Counter(h for h, _ in all_codes)
    print(f"  hi 页分布：{[(hex(k), v) for k, v in sorted(hi_pages.items())]}")

    # ── ⑤ tilemap 里 144 个字形 tile 的样式唯一性 ─────────
    print("\n" + "=" * 78)
    print("⑤ 同一 tile 序号是否被多次引用（同字必同 tile 的旁证）")
    print("=" * 78)
    tc = Counter()
    for ln in lines:
        for _, tt, tb in ln["tiles"]:
            tc[tt] += 1
            tc[tb] += 1
    dup = [(t, n) for t, n in tc.items() if n > 1]
    print(f"  被引用 >1 次的 tile：{len(dup)}  {sorted(dup)[:20]}")

    (OUT / "map.json").write_text(
        '{"note": "see console"}', encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
