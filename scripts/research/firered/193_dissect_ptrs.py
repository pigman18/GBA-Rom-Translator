#!/usr/bin/env python3
"""调研(193) 逐个解剖渲染函数引用的 6 个汉化新增指针。

═══════════════════════════════════════════════════════════════════════════
【(192) 找到的、汉化改写进渲染函数的全部指针】
═══════════════════════════════════════════════════════════════════════════
  指令            字面量地址      值            被谁用
  0x081DB630      0x081DB648     0x08B64A40    字宽判定（喂给 0x081DB6B0）
  0x081DB644      0x081DB64C     0x03003E60    字宽函数的返回值
  0x081DB666      0x081DB6D8     0x0203F2C0    转码主函数（EWRAM）
  0x081DB6CA      0x081DB6DC     0x08FE5100    转码主函数
  0x081DB6D0      0x081DB6E0     0x08008901    转码主函数
  0x081DB6D4      0x081DB6E4     0x080C5FED    转码主函数
  0x081DB6EC      0x081DB758     0x00003190
  0x081DB6F0      0x081DB75C     0x08FE5C10
  0x081DB6F2      0x081DB760     0x08FE60F0
  0x081DB806      0x081DB85C     0x0203F2C0    F8 组合

原版这些字面量**全是 0x00000000** ⇒ 整个渲染逻辑是汉化新写的。

【重点假设】
H-A 0x08B64A40 是「字符 → 字宽」表：0x081DB630 用它查出每字宽度，
    再喂给 0x081DB6B0 计算步进。若真，这张表的长度应 >= 码位数（2299）。
H-B 0x08FE5100 / 0x08FE5C10 / 0x08FE60F0 在新增区，可能是字库/映射表。
H-C 0x0203F2C0 是 EWRAM 运行时缓冲（检查点已测 6 个状态全 0）。

【本脚本】
 对每个指针 dump 一段内容，做：
  A. 十六进制 + 字符画
  B. 若像字节表：统计分布，尝试当「字宽表」解释（值是否集中在 2/10/12）
  C. 若像 4bpp 位图：按 32B 一块画出 8x8 图
  D. 若像指针表：解析成地址列表，看是否指向另一块数据
  E. 与原版对比（原版这些区是不是 FF）

用法：python scripts/research/firered/193_dissect_ptrs.py
"""
from __future__ import annotations

import json
import struct
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "ptrs193"
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_OR = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000

TARGETS = [0x08B64A40, 0x03003E60, 0x08FE5100, 0x08FE5C10, 0x08FE60F0,
           0x081DB758, 0x0203F2C0]


def tile_nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob[y * 4 + x // 2]
            m[y, x] = (v & 0x0F) if x % 2 == 0 else (v >> 4)
    return m


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


def render_4bpp(seg: bytes, nblocks: int = 64, scale: int = 3) -> np.ndarray:
    blocks = [seg[i * 32:(i + 1) * 32] for i in range(nblocks)]
    blocks = [b for b in blocks if len(b) == 32]
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
    zh = ROM_ZH.read_bytes()
    ja = ROM_OR.read_bytes()

    for tgt in TARGETS:
        print("\n" + "=" * 78)
        print(f"目标 0x{tgt:08X}")
        print("=" * 78)

        if not (BASE <= tgt < BASE + len(zh)):
            print("  不在 ROM 内（RAM 地址，静态分析看不到内容）")
            continue

        off = tgt - BASE
        seg = zh[off:off + 512]
        oseg = ja[off:off + 512]

        # ── E. 原版对比 ────────────────────────────────
        n_ff = sum(1 for b in oseg if b == 0xFF)
        print(f"  原版该处 512B 中 FF 占 {n_ff}/512 ({n_ff / 512:.1%})")
        print(f"  原版前 32B: {oseg[:32].hex(' ')}")
        print(f"  汉化前 32B: {seg[:32].hex(' ')}")

        # ── A. 内容 ────────────────────────────────────
        print(f"\n  汉化 前 128B:")
        for i in range(0, 128, 16):
            row = seg[i:i + 16]
            hexs = " ".join(f"{b:02x}" for b in row)
            asc = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
            print(f"    +{i:03X}  {hexs:<48} {asc}")

        # ── B. 当「字节表」解释 ─────────────────────────
        c = Counter(seg)
        print(f"\n  值分布：种类={len(c)}  最常见="
              f"{[(f'0x{v:02X}', n) for v, n in c.most_common(8)]}")

        # 字宽表通常只有几个值
        few = [v for v, n in c.most_common() if n > 10]
        if 2 <= len(few) <= 6:
            print(f"  ★ 像「小值表」！主值 = {[f'0x{v:02X}' for v in few]}")
            if set(few) <= {2, 10, 12} or set(few) <= {0, 2, 10, 12}:
                print("  ★★★ 值域正好是 {2,10,12} —— 这就是**字宽表**！")

        # 当 u16 解释
        u16 = [struct.unpack_from("<H", seg, i)[0] for i in range(0, 128, 2)]
        print(f"  当 u16 前 32 个: {[hex(v) for v in u16[:16]]}")

        # 当 u32 指针解释
        u32 = [struct.unpack_from("<I", seg, i)[0] for i in range(0, 256, 4)]
        romp = [v for v in u32 if BASE <= v < BASE + len(zh)]
        print(f"  当 u32 前 64 个里指向 ROM 的：{len(romp)}  "
              f"{[hex(v) for v in romp[:8]]}")

        # ── C. 当 4bpp 位图画 ─────────────────────────
        img = render_4bpp(seg, nblocks=64, scale=3)
        p = OUT / f"P_{tgt:08X}_4bpp.png"
        save_png(p, img)
        print(f"  ✔ 4bpp 视图 {p.name}")

        # ── 若 u32 指向 ROM，继续跟 ────────────────────
        if romp:
            print(f"\n  ── 跟随指针 ──")
            for v in sorted(set(romp))[:6]:
                o2 = v - BASE
                s2 = zh[o2:o2 + 64]
                print(f"    → 0x{v:08X}: {s2[:32].hex(' ')}")

    # ── 特别：把 0x08B64A40 当字宽表完整验证 ─────────────
    print("\n" + "=" * 78)
    print("专项：0x08B64A40 是否是一张 2299 项的字宽表")
    print("=" * 78)
    off = 0x08B64A40 - BASE
    tab = zh[off:off + 4096]
    c = Counter(tab)
    print(f"  前 4096 字节值分布：{[(f'0x{v:02X}', n) for v, n in c.most_common(10)]}")
    print(f"  值种类：{len(c)}")
    # 检查是否 {2,10,12} 三值
    ok3 = set(c) <= {2, 10, 12}
    print(f"  值域 ⊂ {{2,10,12}} ? {ok3}")
    if ok3:
        print(f"  前 60 项：{list(tab[:60])}")
        print("  ★★★ 确认是字宽表")
    else:
        # 可能是 u16 或其它
        print(f"  前 64 字节: {tab[:64].hex(' ')}")

    (OUT / "done.txt").write_text("ok", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
