"""对照大字导出的成功逻辑，找出小字偏差在哪。

═══ 大字（207，已成功导出 2816 字）用的确切逻辑 ═══
    页表 PAGES4 @0x089D08A0（11 项）
    addr = PAGES4[hi] + lo * 64
    for k in 0..3:
        d = decode16(rom[addr + k*16 : addr + k*16 + 16])   # +0x00/+0x10/+0x20/+0x30
    2x2 拼接: [d0 d1]
              [d2 d3]  -> 16x16
    decode16: 读序 src[1],src[0],src[3],src[2]...（swap）
    IDX @0x081CDF40, PAL @0x03000A40
    PAL 来自 runtime205 快照（继续游戏菜单）

═══ 小字我做的（260）═══
    页表 @0x08B74000（11 项）
    addr = PAGES[hi] + lo * 64
    只取 1 段（16 字节）→ decode16 → 8x8
    读序试了 noshift
    PAL 来自 party232 快照（队伍界面）

═══ 本脚本：逐项对照，定位偏差 ═══
 ① 两张页表指向的数据是否相同？
 ② 用大字的确切逻辑（swap + 4段 + 2x2）解小字页表，出什么？
 ③ 用大字的确切逻辑解大字页表，验证脚本本身对不对
 ④ PAL 差异的影响
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
BASE = 0x08000000
N = len(zh)

# 两个快照的 PAL
IW205 = (ROOT / "work/_probe/runtime205/t000_prove_iwram.bin").read_bytes()
IW261 = (ROOT / "work/_probe/party261/s01_party01_iwram.bin").read_bytes()
PAL205 = IW205[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]
PAL261 = IW261[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]

IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]

PAGES_MAIN = [0x089C4230, 0x089555A0, 0x08B55564, 0x08A2725C, 0x08B333A0,
              0x08907C0C, 0x08AD690C, 0x08935A08, 0x08A72610, 0x08AB5404,
              0x089B2B0C]
PAGES_SMALL = [0x08B01000, 0x08B40000, 0x08B50000, 0x08B60000, 0x08B70000,
               0x08B80000, 0x08B90000, 0x08BA0000, 0x08BB0000,
               0x08B64000, 0x08B68000]

OUT = ROOT / "work" / "_probe" / "compare"
OUT.mkdir(parents=True, exist_ok=True)


def save_png(path, arr):
    h, w, _ = arr.shape
    raw = b''.join(b'\x00' + arr[y].tobytes() for y in range(h))

    def chunk(tag, data):
        c = tag + data
        return (struct.pack('>I', len(data)) + c
                + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF))

    path.write_bytes(b'\x89PNG\r\n\x1a\n'
                     + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(raw, 9))
                     + chunk(b'IEND', b''))


# ── ① 两张页表的数据是否相同 ─────────────────────────────
print("=" * 78)
print("① 小字页 vs 大字页 的数据是否重叠/相同")
print("=" * 78)
for i in range(11):
    sm, mn = PAGES_SMALL[i], PAGES_MAIN[i]
    o_s, o_m = sm - BASE, mn - BASE
    seg_s = zh[o_s:o_s + 64]
    seg_m = zh[o_m:o_m + 64]
    same = seg_s == seg_m
    print(f"  [{i}] 小字 0x{sm:08X}  vs  大字 0x{mn:08X}  前64B相同={same}")
    if not same:
        print(f"       小字: {seg_s[:16].hex(' ')}")
        print(f"       大字: {seg_m[:16].hex(' ')}")

# 小字页内容是否在 ROM 别处也出现
print("\n=== 小字页0 的前 64B 在 ROM 里还有哪 ==="
      )
seg = zh[PAGES_SMALL[0] - BASE:PAGES_SMALL[0] - BASE + 64]
pos = zh.find(seg)
hits = []
while pos >= 0:
    hits.append(BASE + pos)
    pos = zh.find(seg, pos + 1)
print(f"  {seg[:32].hex(' ')}")
print(f"  出现 {len(hits)} 处: {[hex(h) for h in hits[:8]]}")


# ── decode16（大字用的 swap 版）────────────────────────────
def decode16_swap(src, pal):
    out = bytearray()
    for r3 in range(16):
        p = (r3 // 2) * 2
        v = src[p] if (r3 & 1) else (src[p + 1] if p + 1 < len(src) else 0)
        i = IDX[v]
        off = i * 2
        out += pal[off:off + 2] if off + 1 < len(pal) else b'\x00\x00'
    return bytes(out)


def mat8(blob):
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob[y * 4 + x // 2]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    return m


def glyph16(page, lo, pal):
    """大字确切逻辑：4 段（+0x00/+0x10/+0x20/+0x30），2x2 拼 16x16。"""
    a = page + lo * 64
    o = a - BASE
    if o < 0 or o + 64 > N:
        return None
    parts = [mat8(decode16_swap(zh[o + k * 16:o + k * 16 + 16], pal))
             for k in range(4)]
    return np.vstack([np.hstack([parts[0], parts[1]]),
                      np.hstack([parts[2], parts[3]])])


# ── ②③ 用同一逻辑解两张页表 ──────────────────────────────
def render_codes(pages, pal, tags, name, codes=(0, 1, 2, 3, 4, 5, 6, 7)):
    print(f"\n  用 PAL={tags}:")
    for code in codes:
        hi, lo = code >> 8, code & 0xFF
        if hi >= len(pages):
            continue
        m = glyph16(pages[hi], lo, pal)
        if m is None:
            continue
        # 背景值 = 最常见值
        from collections import Counter
        c = Counter(int(v) for v in m.flatten())
        bg = c.most_common(1)[0][0]
        print(f"    码 0x{code:03X} (bg=0x{bg:02X}):")
        for y in range(16):
            print("      " + "".join("." if v == bg else
                                     ("#" if v > bg else "+") for v in m[y]))


print("\n" + "=" * 78)
print("② 用大字确切逻辑（swap + 4段 + 2x2）解【大字页表】→ 应能重现 207 的结果")
print("=" * 78)
render_codes(PAGES_MAIN, PAL205, "PAL205(菜单)", "main", codes=(0, 1, 2, 3))

print("\n" + "=" * 78)
print("③ 用同一逻辑解【小字页表】")
print("=" * 78)
render_codes(PAGES_SMALL, PAL261, "PAL261(队伍)", "small", codes=(0, 1, 2, 3))

print("\n" + "=" * 78)
print("④ 交叉：小字页表 + PAL205 / 大字页表 + PAL261")
print("=" * 78)
render_codes(PAGES_SMALL, PAL205, "PAL205", "small_p205", codes=(0, 1))
render_codes(PAGES_MAIN, PAL261, "PAL261", "main_p261", codes=(0, 1))

# ── ⑤ PAL 差异 ───────────────────────────────────────────
print("\n" + "=" * 78)
print("⑤ 两张 PAL 的前 16 项对比")
print("=" * 78)
print(f"  {'idx':<4} {'PAL205':<10} {'PAL261':<10}")
for k in range(16):
    a = f"{PAL205[k*2]:02x} {PAL205[k*2+1]:02x}"
    b = f"{PAL261[k*2]:02x} {PAL261[k*2+1]:02x}"
    print(f"  [{k:>2}] {a:<10} {b:<10}")
