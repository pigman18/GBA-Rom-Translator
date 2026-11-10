#!/usr/bin/env python3
"""调研(176) 从 snap3/vram.bin 反推「中文文字 tile」的确切 VRAM 地址。

═══════════════════════════════════════════════════════════════════════════
【为什么先做这一步（离线，不启模拟器）】
═══════════════════════════════════════════════════════════════════════════
(152) 把 watchpoint 设在 0x06000000 / 0x06004000 / 0x06008000 / 0x0600C000
四个「charBase 起点」，抓到的是 **画地图 tileset 的 DMA**（r3=0x020047F0
是 tileset 数据），不是画字。

要抓「谁写字形」，必须先知道**中文字形 tile 落在哪个 VRAM 地址**。
这件事 snap3/vram.bin 里已有答案（(83) 验证过：pal=15 的 tile 就是文字）。

本脚本（纯离线）：
 ① 读 snap3/vram.bin 的 BG1 tilemap（0xF000）
 ② 收集所有 pal=15（文字）tile 序号
 ③ 换算成 VRAM 字节地址 = 0x06000000 + tile*32
 ④ 按 tile 内容做「是否真的是汉字笔画」的复核
 ⑤ 输出 watchpoint 目标地址清单（按连续区间合并，减少 watchpoint 数量）
 ⑥ 顺便在同一份 vram.bin 的 charBase 里找「ASCII 字形」作为对照

【输出】
  work/_probe/fontwatch/targets.json  —— 给 (177) 直接喂地址
  控制台打印合并后的区间（数量少，才能一次设完）

用法：python scripts/research/firered/176_text_tile_addrs.py
"""
from __future__ import annotations

import json
import struct
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SNAP = ROOT / "work" / "_probe" / "snap3"
OUT = ROOT / "work" / "_probe" / "fontwatch"

VRAM = 0x06000000
SCREEN_BASE = 0xF000          # BG1 tilemap 偏移（(76)(83) 已证）


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def tile_nibs(blob: bytes) -> np.ndarray:
    """8x8 4bpp tile → 矩阵。"""
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob[y * 4 + x // 2]
            m[y, x] = (v & 0x0F) if x % 2 == 0 else (v >> 4)
    return m


def show(m: np.ndarray) -> list[str]:
    tbl = {0: ".", 10: " ", 11: "+", 12: "#", 13: "*", 14: "%", 15: "@"}
    return ["".join(tbl.get(int(v), "?") for v in row) for row in m]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    vr = (SNAP / "vram.bin").read_bytes()
    print(f"vram.bin = {len(vr):,} B")

    # ── ① 扫 tilemap，按 pal 归类 ────────────────────────────
    pal_count: Counter[int] = Counter()
    text_tiles: list[int] = []
    tile_usage: Counter[int] = Counter()
    for r in range(20):
        for c in range(30):
            e = rd16(vr, SCREEN_BASE + (r * 32 + c) * 2)
            p = (e >> 12) & 0xF
            t = e & 0x3FF
            pal_count[p] += 1
            if p == 15:
                text_tiles.append(t)
                tile_usage[t] += 1
    print(f"\n① pal 分布（出现项）: {dict(sorted(pal_count.items()))}")

    uniq = sorted(set(text_tiles))
    print(f"   pal=15 项数={len(text_tiles)}  不同 tile 数={len(uniq)}")
    print(f"   tile 序号范围：{min(uniq) if uniq else '-'} .. {max(uniq) if uniq else '-'}")
    print(f"   序号连续？{uniq == list(range(uniq[0], uniq[-1] + 1)) if uniq else 'n/a'}")

    # ── ② 复核：这些 tile 内容是否真是汉字笔画 ──────────────
    print("\n② 逐个文字 tile 的内容复核（nibble 统计 + 预览）")
    print("-" * 78)
    good: list[int] = []
    for t in uniq:
        off = t * 32
        if off + 32 > len(vr):
            print(f"  tile {t:>4} 越界")
            continue
        blob = vr[off:off + 32]
        m = tile_nibs(blob)
        vals, cnts = np.unique(m, return_counts=True)
        d = {int(v): int(c) for v, c in zip(vals, cnts)}
        ink = d.get(12, 0) + d.get(11, 0)
        bg = d.get(10, 0)
        ok = ink > 0 and bg > 0
        if ok:
            good.append(t)
        tag = "OK " if ok else "非字"
        print(f"  tile {t:>4} @0x{VRAM + off:08X} {tag} "
              f"墨={ink:>2} 底={bg:>2} 其他={ {k: v for k, v in d.items() if k not in (10, 11, 12)} }")
        for line in show(m):
            print(f"           {line}")
        print()

    # ── ③ 换算地址 ─────────────────────────────────────────
    print("③ 中文文字 tile 的 VRAM 字节地址")
    print("-" * 78)
    addrs = [VRAM + t * 32 for t in good]
    for t, a in zip(good, addrs):
        print(f"  tile {t:>4} → 0x{a:08X} .. 0x{a + 32:08X}")

    # ── ④ 合并成连续区间（watchpoint 数量要少）────────────
    print("\n④ 合并连续区间")
    print("-" * 78)
    spans: list[list[int]] = []
    for a in addrs:
        if spans and a == spans[-1][1]:
            spans[-1][1] = a + 32
        else:
            spans.append([a, a + 32])
    for s, e in spans:
        print(f"  0x{s:08X} .. 0x{e:08X}   ({e - s} B)")

    # ── ⑤ 对照：找 ASCII / 半角字形 ────────────────────────
    print("\n⑤ 对照：tilemap 里其它 pal 的 tile（看有没有半角字）")
    print("-" * 78)
    for p in sorted(pal_count):
        if p == 15:
            continue
        ts = sorted({rd16(vr, SCREEN_BASE + (r * 32 + c) * 2) & 0x3FF
                     for r in range(20) for c in range(30)
                     if ((rd16(vr, SCREEN_BASE + (r * 32 + c) * 2) >> 12) & 0xF) == p})
        print(f"  pal={p:>2} tile 数={len(ts):>3} 前10={ts[:10]}")

    # ── ⑥ 存 targets.json 给 (177) ─────────────────────────
    targets = {
        "vram_base": VRAM,
        "screen_base": SCREEN_BASE,
        "text_tiles": good,
        "addr_ranges": [{"start": s, "end": e, "len": e - s} for s, e in spans],
        "watch": [{"addr": s, "len": e - s} for s, e in spans],
    }
    (OUT / "targets.json").write_text(
        json.dumps(targets, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n⑥ 已写 {OUT / 'targets.json'}")
    print(f"   watchpoint 目标区间 {len(spans)} 个，共 {sum(e - s for s, e in spans)} B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
