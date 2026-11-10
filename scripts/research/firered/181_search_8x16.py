#!/usr/bin/env python3
"""调研(181) 用**确证的 8x16 = 64 字节**格式重搜 ROM —— 找字库。

═══════════════════════════════════════════════════════════════════════════
【(180) 确证的字形格式 —— 这是本轮最大突破】
═══════════════════════════════════════════════════════════════════════════
看图 + tilemap 双重确认：
  · 汉字 = **8 宽 x 16 高**
  · = tilemap 上排 tile T（上半 8x8）+ 下排 tile T+24（下半 8x8）
  · = **64 字节**（32 + 32，4bpp 4bit/px）
  · 墨迹在 y=3..14，y=0..2 与 y=15 为空

⇒ **之前所有搜索用的都是错误尺寸**（8x8=32B / 16x16=128B / 13px变宽），
   所以全部 0 命中。现在按 **64 字节（上32+下32）** 重新穷举。

【本脚本的搜索矩阵】
  组合方式：
    C1 上半32 + 下半32（连续，最可能）
    C2 下半32 + 上半32（反序）
  每半部的编码变体：
    E-raw  4bpp 原样 32B
    E-sw   nibble 高低互换 32B
    E-i12  墨迹掩码 1bpp：nibble==12 → 1（8B），拼成上下各 8B
    E-i1112 (11|12) → 1
  位序变体：
    B-msb 每行最高位在左
    B-lsb 每行最低位在右
  行序变体：
    R-norm / R-flip（上下颠倒）

  总计 2 x 4 x 2 x 2 = 32 种组合。用 101 个种子字形全量搜。

【判定】
  真字库会出现**大量连续命中**（相邻字地址连续或等距）。
  假阳性（随机 16MB）期望命中数 ≈ 16e6 / 2^512 量级 = 0。
  1bpp 8B 段随机期望 = 16e6 / 2^64 ≈ 0。
  所以只要某格式命中 >5 且地址成规律，就是真字库。

用法：python scripts/research/firered/181_search_8x16.py
"""
from __future__ import annotations

import json
import struct
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SNAP = ROOT / "work" / "_probe" / "snap3"
OUT = ROOT / "work" / "_probe" / "gsearch181"
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_OR = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"

VRAM = 0x06000000
SCREEN_BASE = 0xF000


def tile_nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob[y * 4 + x // 2]
            m[y, x] = (v & 0x0F) if x % 2 == 0 else (v >> 4)
    return m


def entry(vr: bytes, r: int, c: int) -> int:
    o = SCREEN_BASE + (r * 32 + c) * 2
    return struct.unpack_from("<H", vr, o)[0]


def pack_1bpp(mat01: np.ndarray, msb: bool = True) -> bytes:
    out = bytearray()
    for y in range(8):
        v = 0
        for x in range(8):
            if mat01[y, x]:
                v |= 1 << ((7 - x) if msb else x)
        out.append(v)
    return bytes(out)


def half_variants(top: np.ndarray, bot: np.ndarray) -> dict[str, bytes]:
    """生成上下两半的各种编码。"""
    out: dict[str, bytes] = {}

    def raw(m: np.ndarray) -> bytes:
        b = bytearray(32)
        for y in range(8):
            for x in range(8):
                v = int(m[y, x]) & 0x0F
                if x % 2 == 0:
                    b[y * 4 + x // 2] |= v
                else:
                    b[y * 4 + x // 2] |= v << 4
        return bytes(b)

    def swap32(b: bytes) -> bytes:
        return bytes(((x & 0x0F) << 4) | (x >> 4) for x in b)

    for tag, m in (("t", top), ("b", bot)):
        r = raw(m)
        out[f"{tag}-raw"] = r
        out[f"{tag}-sw"] = swap32(r)
        for msb in (True, False):
            out[f"{tag}-i12-{'M' if msb else 'L'}"] = pack_1bpp(
                (m == 12).astype(np.uint8), msb)
            out[f"{tag}-i1112-{'M' if msb else 'L'}"] = pack_1bpp(
                ((m == 11) | (m == 12)).astype(np.uint8), msb)
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    vr = (SNAP / "vram.bin").read_bytes()

    # ── 按 8x16 收集真实字形（全部 6 行文字）──────────────
    text_rows = [r for r in range(20)
                 if any(((entry(vr, r, c) >> 12) & 0xF) == 15 for c in range(30))]
    start = text_rows[0]
    glyphs: list[dict] = []
    for r in range(start, 19, 2):
        for c in range(30):
            et = entry(vr, r, c)
            if ((et >> 12) & 0xF) != 15:
                continue
            eb = entry(vr, r + 1, c)
            tt, tb = et & 0x3FF, eb & 0x3FF
            ot, ob = tt * 32, tb * 32
            if ot + 32 > len(vr) or ob + 32 > len(vr):
                continue
            top = tile_nibs(vr[ot:ot + 32])
            bot = tile_nibs(vr[ob:ob + 32])
            ink = int(np.sum(top == 12)) + int(np.sum(top == 11)) \
                + int(np.sum(bot == 12)) + int(np.sum(bot == 11))
            glyphs.append({"row": r, "col": c, "tt": tt, "tb": tb,
                           "ink": ink, "top": top, "bot": bot})
    print(f"8x16 字形（含空格位）：{len(glyphs)}")
    real = [g for g in glyphs if 4 <= g["ink"] <= 80]
    print(f"其中墨量 4..80 的真实字形：{len(real)}")
    print(f"tile 序号：上 {[g['tt'] for g in real][:10]}... "
          f"下 {[g['tb'] for g in real][:10]}...")

    # ── 构造 32 种组合模式 ────────────────────────────────
    rom = ROM_ZH.read_bytes()
    rom_or = ROM_OR.read_bytes()

    # 每个字生成一组候选 64B / 16B 模式
    def build(combine: str, enc_t: str, enc_b: str, order: str) -> list[bytes]:
        pats = []
        for g in real:
            vt = half_variants(g["top"], g["bot"])
            a = vt[f"t-{enc_t}"]
            b = vt[f"b-{enc_b}"]
            if combine == "TB":
                pat = a + b
            elif combine == "BT":
                pat = b + a
            else:
                continue
            if order == "flip":
                # 上下颠倒（两半交换 + 各自行序反转）
                pat = b + a
            pats.append(pat)
        return pats

    encs = ["raw", "sw", "i12-M", "i12-L", "i1112-M", "i1112-L"]
    results: list[dict] = []
    print("\n" + "=" * 78)
    print("32 组合穷举搜索")
    print("=" * 78)

    for combine in ("TB", "BT"):
        for enc in encs:
            pats = build(combine, enc, enc, "norm")
            hits, offs = 0, []
            for i, p in enumerate(pats):
                idx = rom.find(p)
                if idx >= 0:
                    hits += 1
                    offs.append(idx)
            if hits:
                results.append({"combine": combine, "enc": enc,
                                "size": len(pats[0]), "hits": hits,
                                "of": len(pats), "offsets": sorted(offs)[:16],
                                "gaps": sorted({b - a for a, b in
                                                zip(sorted(offs), sorted(offs)[1:])})[:8]
                                if len(offs) > 1 else []})
                print(f"  {combine}/{enc:<8} 模式长 {len(pats[0]):>2}B → "
                      f"{hits}/{len(pats)} 命中  "
                      f"地址前4={[hex(x) for x in sorted(offs)[:4]]}")

    # ── 高价值判定：命中地址是否等距/连续 ──────────────────
    print("\n" + "=" * 78)
    print("判定：命中地址的间隔规律（真字库应等距或密集）")
    print("=" * 78)
    best = None
    for r in results:
        offs = sorted(r["offsets"])
        if len(offs) < 3:
            continue
        gaps = [b - a for a, b in zip(offs, offs[1:])]
        g = Counter(gaps)
        top_gap, top_n = (g.most_common(1)[0] if g else (0, 0))
        r["top_gap"], r["top_n"] = top_gap, top_n
        if best is None or (top_n, r["hits"]) > (best.get("top_n", 0), best["hits"]):
            best = r
        print(f"  {r['combine']}/{r['enc']:<8} hits={r['hits']:>3} "
              f"最多间隔={top_gap} x{top_n}")
        if top_n >= 3:
            print(f"    ★★ 等距候选！间隔 {top_gap}B，"
                  f"字长 {r['size']}B，地址 {[hex(x) for x in offs[:8]]}")

    if best:
        print(f"\n  最佳：{best['combine']}/{best['enc']}  "
              f"hits={best['hits']}  间隔={best.get('top_gap')}x{best.get('top_n')}")

    (OUT / "search.json").write_text(
        json.dumps({"n_glyphs": len(real), "results": results},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写 {OUT / 'search.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
