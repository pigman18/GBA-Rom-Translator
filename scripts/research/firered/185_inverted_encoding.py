#!/usr/bin/env python3
"""调研(185) H2：字形是否以「反色 / 异或 / 低值编码」形式存在 ROM。

═══════════════════════════════════════════════════════════════════════════
【(184) 的结论与缺口】
═══════════════════════════════════════════════════════════════════════════
(184) 按「nibble ⊆ {0,10,11,12}」扫全 16MB ROM，合格块仅 38 个、
连续 run 最长 3 块。⇒ **按正色 4bpp 直存的形式不存在字库。**

但有一种常见汉化做法会被这条判据漏掉：
  **ROM 里存「低值编码」（0/1/2/3），绘制时乘/查表放大成 10/11/12**
或 **存反色（笔画=0/1，背景=3）**。

⇒ 本脚本对这些变换后的形态重新扫全 ROM。
   判据不再依赖具体 nibble 值，而用**结构特征**：
     一个 32B 块若像「两种值的图」——即 nibble 只出现 2~4 种值，
     且最常见值占 40%~96%（背景），次常见值占 3%~40%（笔画）。

【变换矩阵】
  T-norm012   10→0, 11→1, 12→2（其余保持 0）        —— 低值归一
  T-norm123   10→1, 11→2, 12→3
  T-inv       15-nibble                              —— 反色
  T-invnorm   norm012 后 3-v                       —— 低值反色
  T-xorF      nibble ^ 0x0F
  T-xorFbyte  字节 ^ 0xFF
  T-swap      nibble 高低互换
  T-nib12to2  只把 12→2、11→1、10→0 并 4bpp 重打包

每种变换都用**结构判据**扫，再核对命中是否成连续 run。

【为什么这样能命中】
若字库确实以低值直存，则连续几千个 32B 块都会满足「2~4 种值 + 背景占多数」
这一结构特征，形成超长 run。随机数据无法形成这种 run。

用法：python scripts/research/firered/185_inverted_encoding.py
"""
from __future__ import annotations

import json
import struct
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SNAP = ROOT / "work" / "_probe" / "snap3"
OUT = ROOT / "work" / "_probe" / "inv185"
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_OR = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
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


def structural_ok(blob: bytes) -> bool:
    """结构判据：像一张「背景占多数 + 少数笔画」的双色图。"""
    vals = []
    for b in blob:
        vals.append(b & 0x0F)
        vals.append(b >> 4)
    c = Counter(vals)
    if not (2 <= len(c) <= 4):
        return False
    total = len(vals)
    top_v, top_n = c.most_common(1)[0]
    frac_bg = top_n / total
    if not (0.40 <= frac_bg <= 0.96):
        return False
    # 次常见值（笔画）占比
    rest = total - top_n
    if rest < 3 or rest > 40:
        return False
    # 必须至少两种非背景值（核心+抗锯齿）或单一笔画也接受
    return True


def transform(blob: bytes, kind: str) -> bytes:
    out = bytearray()
    if kind == "raw":
        return blob
    if kind == "xorFbyte":
        return bytes(b ^ 0xFF for b in blob)
    for b in blob:
        lo, hi = b & 0x0F, b >> 4
        if kind == "inv":
            lo, hi = 15 - lo, 15 - hi
        elif kind == "xorF":
            lo, hi = lo ^ 0x0F, hi ^ 0x0F
        elif kind == "swap":
            lo, hi = hi, lo
        elif kind == "norm012":
            lo = {10: 0, 11: 1, 12: 2}.get(lo, 0)
            hi = {10: 0, 11: 1, 12: 2}.get(hi, 0)
        elif kind == "invnorm":
            lo = 3 - {10: 0, 11: 1, 12: 2}.get(lo, 0)
            hi = 3 - {10: 0, 11: 1, 12: 2}.get(hi, 0)
        elif kind == "norm123":
            lo = {10: 1, 11: 2, 12: 3}.get(lo, 0)
            hi = {10: 1, 11: 2, 12: 3}.get(hi, 0)
        else:
            raise ValueError(kind)
        out.append((hi << 4) | lo)
    return bytes(out)


def scan_runs(hay: bytes, okfn, stride: int = 32) -> list[dict]:
    """在 hay 上按 stride 找连续合格块。"""
    N = len(hay)
    flags = bytearray(N // 4 + 1)
    for off in range(0, N - 32, 4):
        if okfn(hay[off:off + 32]):
            flags[off // 4] = 1
    runs = []
    off = 0
    while off < N - 32:
        if not flags[off // 4]:
            off += 4
            continue
        start = off
        cur = off
        cnt = 1
        while cur + stride < N - 32 and flags[(cur + stride) // 4]:
            cur += stride
            cnt += 1
        if cnt >= 3:
            runs.append({"start": start, "blocks": cnt, "bytes": cnt * 32})
        off = cur + 4
    runs.sort(key=lambda d: -d["blocks"])
    return runs


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rom = ROM_ZH.read_bytes()
    rom_or = ROM_OR.read_bytes()
    vr = (SNAP / "vram.bin").read_bytes()

    print("=" * 78)
    print("基准：VRAM 已知字形是否满足结构判据")
    print("=" * 78)
    text_rows = [r for r in range(20)
                 if any(((entry(vr, r, c) >> 12) & 0xF) == 15 for c in range(30))]
    gs = []
    for r in range(text_rows[0], 19, 2):
        for c in range(30):
            et = entry(vr, r, c)
            if ((et >> 12) & 0xF) != 15:
                continue
            eb = entry(vr, r + 1, c)
            ot, ob = (et & 0x3FF) * 32, (eb & 0x3FF) * 32
            if ot + 32 > len(vr) or ob + 32 > len(vr):
                continue
            gs.append((vr[ot:ot + 32], vr[ob:ob + 32]))
    n_ok = sum(1 for t, b in gs if structural_ok(t) and structural_ok(b))
    print(f"  8x16 字形 {len(gs)} 个，上下半都满足结构判据的：{n_ok}"
          f"  ({n_ok / max(len(gs), 1):.1%})")

    results = {}
    print("\n" + "=" * 78)
    print("全 ROM 扫描（原始 + 6 种变换）")
    print("=" * 78)
    for kind in ("raw", "inv", "xorF", "xorFbyte", "swap",
                 "norm012", "invnorm", "norm123"):
        if kind == "raw":
            hay = rom
        else:
            hay = transform(rom, kind) if False else rom  # 变换应在块级别做
        # 块级变换扫描
        N = len(rom)
        flags = bytearray(N // 4 + 1)
        for off in range(0, N - 32, 4):
            blk = transform(rom[off:off + 32], kind)
            if structural_ok(blk):
                flags[off // 4] = 1
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
            if cnt >= 3:
                runs.append({"start": start, "blocks": cnt, "bytes": cnt * 32})
            off = cur + 4
        runs.sort(key=lambda d: -d["blocks"])
        nblk = sum(flags)
        results[kind] = {"blocks": nblk, "runs": runs[:20]}
        print(f"  {kind:<10} 合格块 {nblk:>6,}   run≥3: {len(runs):>4}   "
              f"最长 {runs[0]['blocks'] if runs else 0:>5} 块 "
              f"@0x{runs[0]['start']:08X}" if runs else
              f"  {kind:<10} 合格块 {nblk:>6,}   run≥3: 0")

    # 重点看最长 run 是否在汉化新增区
    print("\n" + "=" * 78)
    print("最值得追的 run（长度 >= 50 块 = 50 个 8x8 = 25 个字）")
    print("=" * 78)
    hits = []
    for kind, r in results.items():
        for run in r["runs"]:
            if run["blocks"] >= 50:
                s, e = run["start"], run["start"] + run["blocks"] * 32
                ff_or = sum(1 for b in rom_or[s:e] if b == 0xFF) if e <= len(rom_or) else -1
                hits.append({"kind": kind, **run, "orig_ff": ff_or})
                print(f"  {kind:<10} 0x{s:08X}  {run['blocks']:>5} 块  "
                      f"原版该区 FF={ff_or}")
    if not hits:
        print("  ✘ 没有任何变换能产生 ≥50 块的连续 run")
        print("  ⇒ 字库不是「低值编码 / 反色 / 异或」形式")

    (OUT / "inv_scan.json").write_text(
        json.dumps({"n_glyphs": len(gs), "n_ok_glyphs": n_ok,
                    "results": results, "long_runs": hits},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写 {OUT / 'inv_scan.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
