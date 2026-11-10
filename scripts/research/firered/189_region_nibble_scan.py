#!/usr/bin/env python3
"""调研(189) 用「区域级 nibble 集中度」扫全 ROM —— 不预设字形内容。

═══════════════════════════════════════════════════════════════════════════
【为什么要换判据（用户的反驳点醒了我）】
═══════════════════════════════════════════════════════════════════════════
用户指出：若每字靠运行时代码生成，2299 字就是 2299 段绘制逻辑，
无论怎么算都极其庞大，不可能塞进 16MB 还看不出痕迹。
且空间账完全对得上：
    新增字节 648,263 B
    字库需求 2299 x 64 B = 147,136 B   （8x16 4bpp）
    完全放得下。

⇒ **字库必然在 ROM 里。错的是我的搜索判据。**

之前所有搜索的致命问题：
  ① (181)(182)(186) 都是「拿 VRAM 里某个具体字形当模板去搜」。
     只要 ROM 里的位图与 VRAM 里有**任何**差异（边界、抗锯齿取值、
     行序、是否含空行），就必然 0 命中。
  ② (184) 的区域判据要求「块内必须出现 nibble==12」，
     把取值 0/1/2 或 0/B/C/D 的编码全部排除了。
  ③ 所有搜索都在**小块**上做，噪声与稀疏性都会掩盖真信号。

【本脚本的判据：区域级 nibble 集中度（与字形内容无关）】
一个 4bpp 字模区，无论用哪几个 palette 索引，其字节必然满足：
    高 nibble ∈ S、低 nibble ∈ S，|S| <= 4
随机数据满足该条件的概率 ≈ (4/16)^2 = 6.25%。
字模区应接近 100%。

⇒ 对每 4KB 窗口算：
    hi_cov = 前 4 个高频高 nibble 的覆盖率
    lo_cov = 前 4 个高频低 nibble 的覆盖率
    joint  = 高 nibble ∈ hi4 且 低 nibble ∈ lo4 的字节占比
    ent    = 字节熵（区分压缩数据）
再按 joint 排序，并区分「汉化新增窗口」与「原版已有窗口」。

【判定】
 joint >= 0.95 且窗口位于汉化新增区 → 4bpp 字模区候选
 若出现一条连续几十个窗口 joint≈1.0 → 就是字库

【附带】
 对 top 候选输出可视化 PNG（自适应灰度拉伸），可直接看图确认。

用法：python scripts/research/firered/189_region_nibble_scan.py
"""
from __future__ import annotations

import json
import math
import struct
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "nibscan189"
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_OR = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
W = 0x1000


def analyze(seg: bytes) -> dict:
    n = len(seg)
    if n == 0:
        return {}
    hi = Counter(b >> 4 for b in seg)
    lo = Counter(b & 0x0F for b in seg)
    hi4 = [v for v, _ in hi.most_common(4)]
    lo4 = [v for v, _ in lo.most_common(4)]
    hs, ls = set(hi4), set(lo4)
    joint = sum(1 for b in seg if (b >> 4) in hs and (b & 0x0F) in ls) / n
    hi_cov = sum(c for _, c in hi.most_common(4)) / n
    lo_cov = sum(c for _, c in lo.most_common(4)) / n
    ent = -sum((c / n) * math.log2(c / n) for c in Counter(seg).values())
    return {"joint": joint, "hi_cov": hi_cov, "lo_cov": lo_cov,
            "ent": ent, "hi4": hi4, "lo4": lo4, "nvals": len(set(seg))}


def save_png(path: Path, arr: np.ndarray) -> None:
    import zlib
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


def tile_nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob[y * 4 + x // 2]
            m[y, x] = (v & 0x0F) if x % 2 == 0 else (v >> 4)
    return m


def render(seg: bytes, nblocks: int = 128, scale: int = 2,
           vert: bool = False) -> np.ndarray:
    blocks = [seg[i * 32:(i + 1) * 32] for i in range(nblocks)]
    blocks = [b for b in blocks if len(b) == 32]
    if vert:
        pairs = list(zip(blocks[0::2], blocks[1::2]))
        cols = 12
        rows = (len(pairs) + cols - 1) // cols
        cw, chh = 8 * scale + 2, 16 * scale + 2
        img = np.full((rows * chh, cols * cw, 3), 16, dtype=np.uint8)
        for i, (a, b) in enumerate(pairs):
            m = np.vstack([tile_nibs(a), tile_nibs(b)])
            lo, hi = int(m.min()), int(m.max())
            rng = max(1, hi - lo)
            ry, rx = divmod(i, cols)
            g = ((m.astype(np.int32) - lo) * 255 // rng).astype(np.uint8)
            g3 = np.repeat(g[:, :, None], 3, axis=2)
            g3 = np.repeat(np.repeat(g3, scale, axis=0), scale, axis=1)
            img[ry * chh:ry * chh + 16 * scale,
                rx * cw:rx * cw + 8 * scale] = g3
        return img
    cols = 16
    rows = (len(blocks) + cols - 1) // cols
    cw, chh = 8 * scale + 2, 8 * scale + 2
    img = np.full((rows * chh, cols * cw, 3), 16, dtype=np.uint8)
    for i, b in enumerate(blocks):
        m = tile_nibs(b)
        lo, hi = int(m.min()), int(m.max())
        rng = max(1, hi - lo)
        ry, rx = divmod(i, cols)
        g = ((m.astype(np.int32) - lo) * 255 // rng).astype(np.uint8)
        g3 = np.repeat(g[:, :, None], 3, axis=2)
        g3 = np.repeat(np.repeat(g3, scale, axis=0), scale, axis=1)
        img[ry * chh:ry * chh + 8 * scale, rx * cw:rx * cw + 8 * scale] = g3
    return img


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rom = bytearray(ROM_ZH.read_bytes())
    rom_or = ROM_OR.read_bytes()
    N = len(rom)
    print(f"ROM {N:,} B")

    rows = []
    for off in range(0, N - W, W):
        seg = bytes(rom[off:off + W])
        a = analyze(seg)
        if not a:
            continue
        oseg = rom_or[off:off + W]
        added = sum(1 for x, y in zip(seg, oseg) if y == 0xFF and x != 0xFF)
        a.update({"off": off, "added": added})
        rows.append(a)

    print(f"窗口数 {len(rows)}")

    # ── 按 joint 排序 ─────────────────────────────────────
    rows.sort(key=lambda d: -d["joint"])
    print("\n" + "=" * 78)
    print("joint 最高的 40 个窗口（高/低 nibble 都集中在 4 个值内）")
    print("=" * 78)
    print("  地址         joint  hi4        lo4        ent  值种类  新增B")
    for r in rows[:40]:
        h4 = ",".join(f"{v:X}" for v in r["hi4"])
        l4 = ",".join(f"{v:X}" for v in r["lo4"])
        print(f"  0x{r['off']:08X}  {r['joint']:.3f}  {h4:<12} {l4:<12} "
              f"{r['ent']:>4.1f}  {r['nvals']:>4}  {r['added']:>5}")

    # ── 只看「高度集中 + 有新增」的 ────────────────────────
    print("\n" + "=" * 78)
    print("joint>=0.95 的窗口，按地址排列（找连续区）")
    print("=" * 78)
    hi_j = [r for r in rows if r["joint"] >= 0.95]
    hi_j.sort(key=lambda d: d["off"])
    print(f"  共 {len(hi_j)} 个窗口")
    if hi_j:
        # 合并连续窗口
        runs = []
        cur = [hi_j[0]]
        for r in hi_j[1:]:
            if r["off"] == cur[-1]["off"] + W:
                cur.append(r)
            else:
                runs.append(cur)
                cur = [r]
        runs.append(cur)
        runs.sort(key=lambda c: -len(c))
        print(f"  连续区段 {len(runs)} 个，最长的 15 个：")
        for c in runs[:15]:
            s, e = c[0]["off"], c[-1]["off"] + W
            add = sum(r["added"] for r in c)
            print(f"    0x{s:08X}..0x{e:08X}  {len(c):>3} 窗口 "
                  f"({e - s:>7,} B)  新增 {add:>7,} B  "
                  f"joint均值 {sum(r['joint'] for r in c) / len(c):.3f}")

    # ── 这些窗口在原版里是什么 ────────────────────────────
    print("\n" + "=" * 78)
    print("top 候选的可视化（joint 高 且 新增多）")
    print("=" * 78)
    cands = [r for r in rows if r["joint"] >= 0.9 and r["added"] >= 1000][:6]
    if not cands:
        cands = rows[:3]
    for r in cands:
        off = r["off"]
        seg = bytes(rom[off:off + W])
        p1 = OUT / f"N_{off:08X}_8x16.png"
        save_png(p1, render(seg, vert=True))
        print(f"  0x{off:08X} joint={r['joint']:.3f} ent={r['ent']:.1f} "
              f"新增={r['added']}  → {p1.name}")

    # ── 反向：最像字模的「高集中 + 低熵」 ──────────────────
    print("\n" + "=" * 78)
    print("按「joint 高 且 熵低（2~4 bit）」筛，这些最像纯字模")
    print("=" * 78)
    fontlike = [r for r in rows if r["joint"] >= 0.93 and 1.0 <= r["ent"] <= 4.2]
    fontlike.sort(key=lambda d: -d["joint"])
    print(f"  共 {len(fontlike)} 个窗口")
    for r in fontlike[:25]:
        h4 = ",".join(f"{v:X}" for v in r["hi4"])
        l4 = ",".join(f"{v:X}" for v in r["lo4"])
        print(f"  0x{r['off']:08X}  joint={r['joint']:.3f} ent={r['ent']:>4.1f} "
              f"hi4={h4:<12} lo4={l4:<12} 新增={r['added']}")

    (OUT / "scan.json").write_text(
        json.dumps({"top": [{k: v for k, v in r.items()} for r in rows[:200]]},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写 {OUT / 'scan.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
