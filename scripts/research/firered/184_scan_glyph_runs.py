#!/usr/bin/env python3
"""调研(184) 直接扫 ROM：按「字形 4bpp 特征」找连续字模块。

═══════════════════════════════════════════════════════════════════════════
【为什么改这个方法】
═══════════════════════════════════════════════════════════════════════════
前几轮都是「拿已知字形去搜」——(181) 32 种组合 0 命中，(182) 上半表、
下半表分开存放也排出，(183) RAM 里也找不到。这说明**字形字节和 VRAM
里的不完全相同**（可能经过变换，也可能我提取的边界有偏差）。

⇒ 换方向：**不拿字形去搜，改为按「字模的固有特征」扫 ROM**。

【字模固有特征（从 (176)(180) 实测）】
一个 8x8 字形 tile 的 4bpp nibble 只出现少数几种值：
   0  = 透明（字格外）
   10 = 背景
   11 = 抗锯齿中间色
   12 = 笔画核心
实测 tile 1（"继"上半）的 nibble 集合 = {10, 11, 12}（无 0）。
⇒ 判据：**32 字节块里，nibble ⊆ {0,10,11,12} 且 12 的个数在 5..40**。

这是很强的约束：随机 32 字节满足概率约 (4/16)^64 ≈ 0。
所以任何长 run 都极可能是真字模表。

【本脚本】
 S1 全 ROM 扫描：每个 32B 对齐块是否满足上述判据
 S2 找出**连续满足的 run**，列出最长的 20 个（起点/长度/内容）
 S3 对最长 run，按 32B stride 提取并可视化成 PNG
 S4 交叉验证：把这些块与 VRAM 已知字形比对，算出最大重合度
 S5 顺便统计 (179) 里 4bpp 原样命中的 8 个位置，看是否聚在同一 run 里

【判定】
 找到一个 run 长度 ≥ 200 块（=200 个 8x8 = 100 个 8x16 汉字）
 且内容与 VRAM 字形重合度高 → 这就是字库

用法：python scripts/research/firered/184_scan_glyph_runs.py
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SNAP = ROOT / "work" / "_probe" / "snap3"
OUT = ROOT / "work" / "_probe" / "gscan184"
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_OR = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
SCREEN_BASE = 0xF000
VRAM = 0x06000000

OK_NIBS = {0, 10, 11, 12}


def nib_ok(blob: bytes) -> tuple[bool, int]:
    """32B 块是否像字模。返回 (是否合格, nibble==12 的个数)。"""
    n12 = 0
    gap = 0
    for b in blob:
        lo, hi = b & 0x0F, b >> 4
        for v in (lo, hi):
            if v not in OK_NIBS:
                return False, 0
            if v == 12:
                n12 += 1
            elif v == 10:
                gap += 1
    # 必须有笔画、也要有背景（排除全 10 或全 12）
    if n12 < 3 or n12 > 60:
        return False, 0
    if gap == 0:
        return False, 0
    return True, n12


def tile_nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob[y * 4 + x // 2]
            m[y, x] = (v & 0x0F) if x % 2 == 0 else (v >> 4)
    return m


def entry(vr: bytes, r: int, c: int) -> int:
    return struct.unpack_from("<H", vr, SCREEN_BASE + (r * 32 + c) * 2)[0]


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


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rom = ROM_ZH.read_bytes()
    rom_or = ROM_OR.read_bytes()
    vr = (SNAP / "vram.bin").read_bytes()

    # ── S1 全 ROM 扫描（4 字节对齐，stride 32 起步再微调）────────
    print("=" * 78)
    print("S1 全 ROM 扫描字模特征块（32B, nibble⊆{0,10,11,12}）")
    print("=" * 78)
    N = len(rom)
    ok = bytearray(N // 4)          # 每个 4B 位置是否有「合格 32B 块」起点
    n = 0
    for off in range(0, N - 32, 4):
        good, _ = nib_ok(rom[off:off + 32])
        if good:
            ok[off // 4] = 1
            n += 1
    print(f"  合格块起点（4B 对齐）：{n:,}")
    print(f"  占全 ROM 位置比例的 {n / (N / 4):.4%}")

    # ── S2 找连续 run（相邻块起点相差 32）───────────────
    print("\n" + "=" * 78)
    print("S2 连续 run（起点间隔恰好 32B 视为同一张表）")
    print("=" * 78)
    runs: list[dict] = []
    off = 0
    while off < N - 32:
        if not ok[off // 4]:
            off += 4
            continue
        start = off
        cur = off
        cnt = 1
        while True:
            nxt = cur + 32
            if nxt < N - 32 and ok[nxt // 4]:
                cur = nxt
                cnt += 1
            else:
                break
        if cnt >= 3:
            runs.append({"start": start, "blocks": cnt,
                         "bytes": cnt * 32, "end": start + cnt * 32})
        off = cur + 4 if cnt > 1 else off + 4

    runs.sort(key=lambda d: -d["blocks"])
    print(f"  run 数（≥3 块）：{len(runs)}")
    print(f"  最长 20 个：")
    for r in runs[:20]:
        add = sum(1 for b in rom_or[r["start"]:r["end"]]
                  if b == 0xFF) if r["end"] <= len(rom_or) else 0
        print(f"    0x{r['start']:08X}  {r['blocks']:>5} 块 "
              f"({r['bytes']:>7,} B)  原版该区 FF 字节={add:,}")

    # ── S3 最长 run 可视化 ──────────────────────────────
    if runs:
        top = runs[0]
        print("\n" + "=" * 78)
        print(f"S3 最长 run 可视化  0x{top['start']:08X}  {top['blocks']} 块")
        print("=" * 78)
        blocks = [rom[top["start"] + i * 32: top["start"] + (i + 1) * 32]
                  for i in range(min(top["blocks"], 96))]
        SCALE = 3
        cols = 16
        rows = (len(blocks) + cols - 1) // cols
        cw = 8 * SCALE + 2
        chh = 8 * SCALE + 2
        img = np.full((rows * chh, cols * cw, 3), 16, dtype=np.uint8)
        colors = {0: (60, 60, 60), 10: (16, 16, 16),
                  11: (150, 150, 150), 12: (245, 245, 245)}
        for i, blob in enumerate(blocks):
            m = tile_nibs(blob)
            ry, rx = divmod(i, cols)
            for y in range(8):
                for x in range(8):
                    img[ry * chh + y * SCALE:ry * chh + (y + 1) * SCALE,
                        rx * cw + x * SCALE:rx * cw + (x + 1) * SCALE] = \
                        colors.get(int(m[y, x]), (255, 0, 0))
        p = OUT / "LONGEST_RUN.png"
        save_png(p, img)
        print(f"  ✔ {p}  ({img.shape[1]}x{img.shape[0]})")

        # 打印前 8 块字符画
        for i, blob in enumerate(blocks[:8]):
            m = tile_nibs(blob)
            print(f"\n  块 {i}  +0x{i * 32:04X}:")
            for y in range(8):
                print("    " + "".join(
                    {0: ".", 10: " ", 11: "+", 12: "#"}.get(int(v), "?")
                    for v in m[y]))

    # ── S4 与 VRAM 已知字形的重合度 ──────────────────────
    print("\n" + "=" * 78)
    print("S4 最长 run 的块 vs VRAM 已知字形（逐字节重合度）")
    print("=" * 78)
    if runs:
        top = runs[0]
        vr_tiles = []
        for t in range(0, 600):
            blob = vr[t * 32:t * 32 + 32]
            if len(blob) < 32:
                break
            m = tile_nibs(blob)
            if int((m == 12).sum()) > 2:
                vr_tiles.append(blob)
        print(f"  VRAM 含笔画 tile：{len(vr_tiles)}")
        best = 0
        bestinfo = None
        for i in range(min(top["blocks"], 200)):
            blob = rom[top["start"] + i * 32: top["start"] + (i + 1) * 32]
            for j, vt in enumerate(vr_tiles):
                same = sum(1 for a, b in zip(blob, vt) if a == b)
                if same > best:
                    best = same
                    bestinfo = (i, j, same)
        if bestinfo:
            print(f"  最高重合：ROM 块 {bestinfo[0]} vs VRAM tile "
                  f"{bestinfo[1]}  字节相同 {bestinfo[2]}/32")
            if bestinfo[2] >= 28:
                print("  ★★ 高度吻合 —— 这就是字形来源")
            else:
                print("  ✘ 重合度低，run 不是字形（可能是原版图标/图形）")

    (OUT / "runs.json").write_text(
        json.dumps({"n_ok": n, "runs": runs[:60]}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"\n已写 {OUT / 'runs.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
