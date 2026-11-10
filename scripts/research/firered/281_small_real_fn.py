"""调研(281) 用小字真正的函数 0x080062B4 导出字库。

═══ 280 反汇编确证的公式 ═══
函数 0x080062B4（小字取字形）：

    080062B8  lsrs r4, r0, #0x14      r4 = code >> 4
    080062BA  lsls r4, r4, #9         r4 = (code>>4) * 512
    080062C0  ands r1, r0 (0xF0000)   高 4 位
    080062C2  lsrs r1, r1, #0xc       r1 = 页号
    080062C4  ldr  r0, [pc]           0x081CEDF4   ← 页表
    080062C6  adds r1, r1, r0
    080062C8  adds r4, r4, r1         r4 = 页表[页号] + (code>>4)*512
    080062CA  ldr  r5, [pc]           0x03003DE0   ← 输出缓冲
    080062D0  bl   0x08002F5C         解段1（源 addr+0x00）
    080062D4  movs r0, #0x80
    080062D6  lsls r0, r0, #1         r0 = 0x100
    080062D8  adds r4, r4, r0         源 +0x100
    080062DC  adds r1, #0x40          目标 +0x40
    080062E0  bl   0x08002F5C         解段2（源 addr+0x100）
    080062E8  movs r0, #8
    080062EA  strb r0, [r1]           宽 = 8
    080062EE  movs r0, #0xc
    080062F0  strb r0, [r5,#0x81]     高 = 0x0C

⇒ 与小字的配置：
    页表   0x081CEDF4（不是 0x08B74000！）
    步长   (code >> 4) * 512         （不是 lo * 64！）
    段     +0x00 和 +0x100
    输出   +0x00 和 +0x40（各 32 字节）
    宽 8，高 0x0C = 12

  8x12 需要 48 字节 = 1.5 个 8x8 tile，实际写两段共 64 字节
  （+0x00 起 32B，+0x40 起 32B），中间 +0x20..+0x40 空着

本脚本按此导出，并与 VRAM 实测比对。
"""
from __future__ import annotations

import struct
import zlib
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
IW261 = (ROOT / "work/_probe/party261/s01_party01_iwram.bin").read_bytes()
VR261 = (ROOT / "work/_probe/party261/s01_party01_vram.bin").read_bytes()
BASE = 0x08000000
N = len(zh)
OUT = ROOT / "work" / "_probe" / "smallfont_true"
OUT.mkdir(parents=True, exist_ok=True)

IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]
PAL = IW261[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]

PAGES_TBL = 0x081CEDF4


def rd32(a):
    o = a - BASE
    return struct.unpack_from('<I', zh, o)[0] if 0 <= o <= N - 4 else None


def save_png(path: Path, arr: np.ndarray) -> None:
    h, w, _ = arr.shape
    raw = b"".join(b"\x00" + arr[y].tobytes() for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = tag + data
        return (struct.pack('>I', len(data)) + c
                + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF))

    path.write_bytes(b'\x89PNG\r\n\x1a\n'
                     + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(raw, 9))
                     + chunk(b'IEND', b''))


def decode16(src: bytes) -> bytes:
    out = bytearray()
    for r3 in range(16):
        p = (r3 // 2) * 2
        v = src[p] if (r3 & 1) else (src[p + 1] if p + 1 < len(src) else 0)
        i = IDX[v]
        off = i * 2
        out += PAL[off:off + 2] if off + 1 < len(PAL) else b'\x00\x00'
    return bytes(out)


def mat8(b: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = b[y * 4 + x // 2]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    return m


print("=" * 78)
print(f"① 页表 @0x{PAGES_TBL:08X}")
print("=" * 78)
for k in range(8):
    a = PAGES_TBL + k * 4
    v = rd32(a)
    o = a - BASE
    old = struct.unpack_from('<I', ja, o)[0]
    ch = " *汉化改" if v != old else ""
    tag = ""
    if v and BASE <= v < BASE + N:
        oo = v - BASE
        nf = sum(1 for b in ja[oo:oo + 0x400] if b == 0xFF)
        tag = f"  原版该 1KB 中 FF={nf}"
    print(f"  [{k}] 0x{a:08X} = 0x{v:08X}{ch}{tag}")

# 页基址 = 页表项本身？还是页表项存的是指针？
# 看反汇编：r1 = 页表 + 页号（不是 [页表+页号]）
#   080062C4  ldr r0, [pc]       r0 = 页表地址
#   080062C6  adds r1, r1, r0    r1 = 页表地址 + 页号
#   080062C8  adds r4, r4, r1    r4 = 页号 + 页表地址 + offset
# ⇒ 页基址就是「页表地址 + 页号」，即页表本身就是连续的字节区！
print("\n  ⇒ 反汇编显示：r1 = 页表地址 + 页号（不是解引用）")
print("     所以「页表」其实是连续的数据区，页号只是偏移")
print(f"     addr = 0x{PAGES_TBL:08X} + 页号 + (code>>4)*512")

print("\n  " + "=" * 60)
print("  该区前 128 字节：")
o = PAGES_TBL - BASE
for i in range(0, 128, 16):
    print(f"    +{i:03X}  {zh[o+i:o+i+16].hex(' ')}")

# ── 按公式导出 ───────────────────────────────────────────
def small_glyph(code: int):
    """addr = PAGES_TBL + 页号 + (code>>4)*512，两段 +0x00/+0x100。"""
    page = (code >> 16) & 0xF
    off = (code >> 4) * 512
    a = PAGES_TBL + page + off
    o = a - BASE
    if o < 0 or o + 0x110 > N:
        return None
    o1 = o + 0x100
    return np.vstack([mat8(decode16(zh[o:o + 16])),
                      mat8(decode16(zh[o1:o1 + 16]))])


print("\n" + "=" * 78)
print("② 用公式解前 8 个码位")
print("=" * 78)
BG = PAL[0] & 0xF
for code in range(8):
    m = small_glyph(code)
    if m is None:
        print(f"  码 0x{code:03X}: 越界")
        continue
    print(f"\n  码 0x{code:03X}:")
    for y in range(16):
        print("    " + "".join("." if v == BG else "#" for v in m[y]))
