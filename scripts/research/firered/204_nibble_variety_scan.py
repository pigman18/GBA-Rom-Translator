#!/usr/bin/env python3
"""调研(204) 用「nibble 种类数」强判据在全 ROM 定位字形区。

═══════════════════════════════════════════════════════════════════════════
【VRAM 与 ROM 的实测差异（这是判据的来源）】
═══════════════════════════════════════════════════════════════════════════
VRAM tile 1（中文「继」的上半，确定无疑）：
  aa aa aa aa aa aa aa aa aa aa aa aa aa aa cb cb
  aa ba cc bb aa ba ac cb aa cb bc cb aa bb cb bb

展开成 64 个 nibble 后，**只出现 a / b / c 三种值**，
且 a(背景) 占绝大多数。

而 ROM 页 0 (0x08B01000) 的值域：
  F 69.87% / 0 6.65% / 7 4.18% / A 3.09% / 6 3.01% / 5 2.49% ...
  共 16 种 nibble 全部出现 ⇒ **不是字形，是编码/压缩数据**

⇒ 判据：**真字形区的每个 32 字节块，nibble 种类数应 <= 4**
   （4bpp 抗锯齿字模最多用 4 个色号：透明/背景/抗锯齿/笔画）

【本脚本】
 S1 全 ROM 扫所有 32B 对齐块，统计 nibble 种类数 <= 4 的块
 S2 找连续 run（相邻块都合格）
 S3 对最长 run 做可视化
 S4 用 VRAM tile 1 的「nibble 集合 + 出现频次」做二次确认：
    真字库的块应大量呈现「一个主导色 + 2~3 个次色」的形状

【与 (184) 的区别】
(184) 要求 nibble ⊆ {0,10,11,12}（写死具体值）⇒ 若汉化用别的色号就漏掉。
本脚本**不预设色号**，只要求「种类数少」⇒ 覆盖所有色号组合。

用法：python scripts/research/firered/204_nibble_variety_scan.py
"""
from __future__ import annotations

import json
import struct
import zlib
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SNAP = ROOT / "work" / "_probe" / "snap3"
OUT = ROOT / "work" / "_probe" / "variety204"
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_OR = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def save_png(path: Path, arr: np.ndarray) -> None:
    h, w, _ = arr.shape
    raw = b"".join(b"\x00" + arr[y].tobytes() for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = tag + data
        return (struct.pack(">I", len(data)) + c
                + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF))

    path.write_bytes(b"\x89PNG\r\n\x1a\n"
                     + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 9))
                     + chunk(b"IEND", b""))


def nibset(blob: bytes) -> set[int]:
    s = set()
    for b in blob:
        s.add(b & 0x0F)
        s.add(b >> 4)
        if len(s) > 5:
            break
    return s


def tile_nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob[y * 4 + x // 2]
            m[y, x] = (v & 0x0F) if x % 2 == 0 else (v >> 4)
    return m


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    zh = ROM_ZH.read_bytes()
    ja = ROM_OR.read_bytes()
    vr = (SNAP / "vram.bin").read_bytes()
    N = len(zh)

    # ── 基准：VRAM 真字形的 nibble 种类数 ──────────────
    print("=" * 78)
    print("基准：VRAM 已知字形的 nibble 种类数分布")
    print("=" * 78)
    vc = Counter()
    for t in range(0, 400):
        blob = vr[t * 32:t * 32 + 32]
        if len(blob) < 32:
            break
        vc[len(nibset(blob))] += 1
    print(f"  种类数分布：{dict(sorted(vc.items()))}")

    # ── S1 全 ROM 扫描 ────────────────────────────────
    print("\n" + "=" * 78)
    print("S1 全 ROM 扫描：32B 块里 nibble 种类数 <= 4")
    print("=" * 78)
    flags = bytearray(N // 4 + 1)
    n_ok = 0
    for off in range(0, N - 32, 4):
        s = nibset(zh[off:off + 32])
        if len(s) <= 4:
            flags[off // 4] = 1
            n_ok += 1
    print(f"  合格块起点（4B 对齐）：{n_ok:,}  ({n_ok / (N / 4):.4%})")

    # ── S2 连续 run ───────────────────────────────────
    print("\n" + "=" * 78)
    print("S2 连续 run（起点间隔 32B）")
    print("=" * 78)
    runs = []
    off = 0
    while off < N - 32:
        if not flags[off // 4]:
            off += 4
            continue
        start = off
        cur = off
        cnt = 1
        while cur + 32 < N - 32 and flags[(cur + 32) // 4]:
            cur += 32
            cnt += 1
        if cnt >= 4:
            runs.append({"start": start, "blocks": cnt, "bytes": cnt * 32})
        off = cur + 4
    runs.sort(key=lambda d: -d["blocks"])
    print(f"  run 数（>=4 块）：{len(runs)}")

    # 排除全 FF / 全 00 的「平凡块」（它们也只有 1 种 nibble）
    real = []
    for r in runs:
        seg = zh[r["start"]:r["start"] + r["bytes"]]
        c = Counter(seg)
        if len(c) <= 2:      # 全 FF 或全 00
            continue
        r["nvals"] = len(c)
        r["top"] = c.most_common(3)
        real.append(r)
    print(f"  排除平凡块后：{len(real)}")
    print(f"  最长 20 个：")
    for r in real[:20]:
        s, e = r["start"], r["start"] + r["bytes"]
        nf = sum(1 for b in ja[s:e] if b == 0xFF) if e <= len(ja) else -1
        print(f"    0x{r['start']:08X}  {r['blocks']:>5} 块 ({r['bytes']:>7,}B)  "
              f"值种类={r['nvals']:>3}  原版FF={nf:>6}")

    # ── S3 可视化前 3 个 ──────────────────────────────
    print("\n" + "=" * 78)
    print("S3 可视化最长的 3 个 run")
    print("=" * 78)
    for ri, r in enumerate(real[:3]):
        blocks = min(r["blocks"], 128)
        imgs = []
        for k in range(blocks):
            blob = zh[r["start"] + k * 32:r["start"] + (k + 1) * 32]
            imgs.append(tile_nibs(blob))
        cols = 16
        rows = (len(imgs) + cols - 1) // cols
        SCALE = 3
        cw, chh = 8 * SCALE + 2, 8 * SCALE + 2
        img = np.full((rows * chh, cols * cw, 3), 16, dtype=np.uint8)
        for i, m in enumerate(imgs):
            lo, hi = int(m.min()), int(m.max())
            rng = max(1, hi - lo)
            ry, rx = divmod(i, cols)
            for y in range(8):
                for x in range(8):
                    g = int((int(m[y, x]) - lo) * 255 / rng)
                    img[ry * chh + y * SCALE:ry * chh + (y + 1) * SCALE,
                        rx * cw + x * SCALE:rx * cw + (x + 1) * SCALE] = (g, g, g)
        p = OUT / f"RUN{ri}_0x{r['start']:08X}.png"
        save_png(p, img)
        print(f"  ✔ {p.name}  ({img.shape[1]}x{img.shape[0]}, {blocks} 块)")

    # ── S4 专项：页表区域 0x08B40000..0x08BC0000 ─────────
    print("\n" + "=" * 78)
    print("S4 专项：页表指向的区域（0x08B01000 / 0x08B40000..0x08BB0000）")
    print("=" * 78)
    pages = [0x08B01000, 0x08B40000, 0x08B50000, 0x08B60000, 0x08B70000,
             0x08B80000, 0x08B90000, 0x08BA0000, 0x08BB0000,
             0x08B64000, 0x08B68000]
    for pg in pages:
        o = pg - BASE
        if o < 0 or o + 0x8000 > N:
            continue
        seg = zh[o:o + 0x8000]
        c = Counter(seg)
        nset = Counter()
        for k in range(0, 0x8000 - 32, 32):
            nset[len(nibset(seg[k:k + 32]))] += 1
        nf = c.get(0xFF, 0) / 0x8000
        print(f"  0x{pg:08X}: FF={nf:>5.1%} 值种类={len(c):>3}  "
              f"32B块种类数分布={dict(sorted(nset.items())[:5])}")

    (OUT / "runs.json").write_text(
        json.dumps({"n_ok": n_ok, "real_runs": real[:80],
                    "pages": [hex(p) for p in pages]},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写 {OUT / 'runs.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
