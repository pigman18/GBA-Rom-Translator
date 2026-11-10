"""火红字库完整导出器 —— 算法经反汇编逐条确证。

═══════════════════════════════════════════════════════════════════════════
火红 PrintNextChar 渲染链路（完整还原）
═══════════════════════════════════════════════════════════════════════════

【入口】0x089D13E0 - PrintNextChar(码, 标志)

    cmp   r1, #0                  ; 第二参数非 0？
    bne   0x089D1426              ; -> 走另一条路径
    ldr   r2, [pc]  ; 0x0AFF
    cmp   r0, r2
    bhi   0x089D1426              ; 码 > 0x0AFF -> 走另一条路径

  ── 主路径（码 <= 0x0AFF，即中文/符号表）──
    lsrs  r2, r0, #8              ; r2 = hi
    lsls  r2, r2, #2              ; hi * 4
    ldr   r3, [pc] ; 0x089D08A0   ; PAGES4 表
    ldr   r4, [r3, r2]            ; r4 = PAGES4[hi]     ← 页基址
    ands  r0, #0xFF               ; lo
    lsls  r0, r0, #6              ; lo * 64            ← 每字 64 字节
    adds  r4, r4, r0              ; r4 = 字形地址
    ldr   r5, [pc] ; 0x03003DE0   ; IWRAM 输出缓冲
    movs  r6, #0
  loop:                            ; 4 次
    movs  r0, r4
    movs  r1, r5
    bl    0x089D142A -> 0x08002F5C  ; 解码 1 段（16B 源 -> 32B 输出）
    adds  r4, #0x10               ; 源 +16
    adds  r5, #0x20               ; 目标 +32
    adds  r6, #1
    cmp   r6, #4
    bne   loop
  ── 收尾 ──
    ldr   r1, [pc] ; 0x089D08D0   ; WIDTH 表
    ldrb  r0, [r1, r7]            ; 字宽（按码索引）
    ldr   r1, [pc] ; 0x03003E60
    strb  r0, [r1]                ; 存宽度
    movs  r0, #0xD
    strb  r0, [r1, #1]            ; 存 0x0D

  ── 另一条路径（码 > 0x0AFF 或 r1!=0）──
    bx    0x081DB3EE              ; 见下

【另一条路径】0x081DB3EE

    lsrs  r7, r7, #8              ; r7 = hi
    cmp   r7, #0xA
    bhi   0x081DB408              ; hi > 10 -> 用默认页 0x08B6C000
    lsls  r7, r7, #2
    ldr   r5, [pc] ; 0x08B74000   ; 另一张页表
    ldr   r5, [r5, r7]            ; r5 = 页基址
    ands  r4, #0xFF               ; lo
    lsrs  r7, r4, #3
    lsls  r7, r7, #9              ; (lo>>3)*512
    ands  r4, #7
    lsls  r4, r4, #5              ; (lo&7)*32
    adds  r4, r4, r7              ; 偏移
    adds  r4, r4 + r5             ; r4 = 页基址 + 偏移
    ... 同样 4 段解码到 0x03003DE0

【解码函数】0x08002F5C  decode16(src) -> 32 字节

    r2 = src, r3 = 0
    r5 = 0x03000A40              ; PAL 表（运行时填）
    r4 = 0x081CDF40              ; IDX 索引表（ROM 静态）
  loop 16 次:
    if r3 & 1:                   ; 奇数
        v = *r2                  ; ldrb
        r2 += 2
    else:                        ; 偶数（注意：不加 r2！）
        v = (*(u16*)r2) >> 8     ; ldrh + lsrs #8  => src[+1]
    v = IDX[v]
    *(u16*)r1 = PAL[v]           ; 写 2 字节
    r1 += 2

  ⇒ 读序是 src[1], src[0], src[3], src[2], ... （**每对字节交换**）
  ⇒ 16 次读 16 源字节，写 32 字节 = 1 个 8x8 4bpp tile

【为什么之前一直找不到】
  1. 字库页在原版里**全是 0xFF**，汉化把数据写进去 —— 但数据是
     「IDX 索引 + PAL 调色板」两段式压缩，不是直接的 4bpp 位图。
  2. 直接拿 VRAM/EWRAM 的渲染结果去 ROM 搜，永远 0 命中，
     因为 ROM 里存的是**索引**（0..0x50），不是像素值。
  3. 每字 64 字节源 -> 4 段 -> 128 字节中间结果 -> 2x2 拼成 16x16，
     有效区是 12x16（字宽表现在只剩 10/12 两档）。
═══════════════════════════════════════════════════════════════════════════
"""
import struct
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
ROM_ZH = ROOT / 'roms/translated/宝可梦火红日版汉化2.2.gba'
ROM_OR = ROOT / 'roms/origin/POKEMON_FIRE_BPRJ00.gba'
IWRAM_SNAP = ROOT / 'work/_probe/runtime205/t000_prove_iwram.bin'
OUT = ROOT / 'work/_probe/font_final'
BASE = 0x08000000
IWR = 0x03000000

# ── 关键地址 ─────────────────────────────────────────────
PAGES4_TBL = 0x089D08A0      # 页基址表（11 项，PrintNextChar 用）
WIDTH_TBL = 0x089D08D0       # 字宽表（按码索引）
IDX_TBL = 0x081CDF40         # 索引表（ROM 静态）
PAL_TBL = 0x03000A40         # 调色板（IWRAM，运行时）
PAGES_FALLBACK = 0x08B74000  # 另一条路径的页表
MAXCODE = 0x0AFF


def save_png(path: Path, arr: np.ndarray) -> None:
    h, w, _ = arr.shape
    raw = b''.join(b'\x00' + arr[y].tobytes() for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = tag + data
        return (struct.pack('>I', len(data)) + c
                + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF))

    path.write_bytes(b'\x89PNG\r\n\x1a\n'
                     + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(raw, 9))
                     + chunk(b'IEND', b''))


class FireRedFont:
    def __init__(self, rom_zh: Path = ROM_ZH,
                 iwram_snap: Path = IWRAM_SNAP):
        self.rom = rom_zh.read_bytes()
        iw = iwram_snap.read_bytes()
        self.idx = self.rom[IDX_TBL - BASE:IDX_TBL - BASE + 256]
        self.pal = iw[PAL_TBL - IWR:PAL_TBL - IWR + 1024]
        self.widths = self.rom[WIDTH_TBL - BASE:WIDTH_TBL - BASE + 0xB00]
        self.pages = [struct.unpack_from('<I', self.rom,
                                         PAGES4_TBL - BASE + k * 4)[0]
                      for k in range(11)]

    def glyph_addr(self, code: int) -> int | None:
        hi, lo = code >> 8, code & 0xFF
        if hi >= len(self.pages) or self.pages[hi] == 0xFFFFFFFF:
            return None
        return self.pages[hi] + lo * 64

    def source_bytes(self, code: int) -> bytes | None:
        a = self.glyph_addr(code)
        if a is None:
            return None
        o = a - BASE
        if o < 0 or o + 64 > len(self.rom):
            return None
        return self.rom[o:o + 64]

    def decode16(self, src: bytes) -> bytes:
        out = bytearray()
        for r3 in range(16):
            p = (r3 // 2) * 2
            if r3 & 1:
                v = src[p] if p < len(src) else 0
            else:
                v = src[p + 1] if p + 1 < len(src) else 0
            i = self.idx[v]
            off = i * 2
            out += self.pal[off:off + 2] if off + 1 < len(self.pal) else b'\xaa\xaa'
        return bytes(out)

    @staticmethod
    def _tile_nibs(blob: bytes) -> np.ndarray:
        m = np.zeros((8, 8), dtype=np.uint8)
        for y in range(8):
            for x in range(8):
                v = blob[y * 4 + x // 2]
                m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
        return m

    def glyph_16x16(self, code: int) -> np.ndarray | None:
        """返回 16x16 nibble 矩阵（有效区 12x16，其余为 0）。"""
        b = self.source_bytes(code)
        if not b:
            return None
        ms = [self._tile_nibs(self.decode16(b[k * 16:(k + 1) * 16]))
              for k in range(4)]
        return np.vstack([np.hstack([ms[0], ms[1]]),
                          np.hstack([ms[2], ms[3]])])

    def width(self, code: int) -> int:
        return int(self.widths[code]) if code < len(self.widths) else 12

    def export_all(self) -> tuple[list[int], np.ndarray]:
        codes, mats = [], []
        for code in range(0, MAXCODE + 1):
            m = self.glyph_16x16(code)
            if m is None:
                continue
            ink = int(((m >= 10) & (m <= 12)).sum())
            if ink < 4:
                continue
            codes.append(code)
            mats.append(m)
        return codes, np.array(mats, dtype=np.uint8)

    def render_png(self, codes: list[int], mats: np.ndarray,
                   path: Path, cols: int = 32, scale: int = 3) -> None:
        cw, chh = 16 * scale + 2, 16 * scale + 2
        rows = (len(codes) + cols - 1) // cols
        img = np.full((rows * chh, cols * cw, 3), 14, dtype=np.uint8)
        cmap = {0: (14, 14, 14), 10: (30, 30, 30),
                11: (150, 150, 150), 12: (250, 250, 250)}
        for i, m in enumerate(mats):
            ry, rx = divmod(i, cols)
            y0 = ry * chh + 1
            x0 = rx * cw + 1
            for y in range(16):
                for x in range(16):
                    g = cmap.get(int(m[y, x]), (90, 90, 90))
                    img[y0 + y * scale:y0 + (y + 1) * scale,
                        x0 + x * scale:x0 + (x + 1) * scale] = g
        save_png(path, img)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    f = FireRedFont()
    print('页表：')
    for i, p in enumerate(f.pages):
        print(f'  [{i:>2}] 0x{p:08X}')

    codes, mats = f.export_all()
    print(f'\n有效码位 {len(codes)} 个')
    wc = {}
    for c in codes:
        wc[f.width(c)] = wc.get(f.width(c), 0) + 1
    print(f'字宽分布 {wc}')

    f.render_png(codes, mats, OUT / 'FONT_ALL.png')
    print(f'✔ {OUT / "FONT_ALL.png"}')

    for pi, pg in enumerate(f.pages):
        sel = [i for i, c in enumerate(codes) if (c >> 8) == pi]
        if not sel:
            continue
        f.render_png([codes[i] for i in sel], mats[sel],
                     OUT / f'PAGE{pi:02d}.png')
        print(f'✔ 页{pi} 0x{pg:08X}: {len(sel)} 字')

    np.save(OUT / 'glyphs.npy', mats)
    np.save(OUT / 'codes.npy', np.array(codes, dtype=np.int32))
    print(f'✔ glyphs.npy {mats.shape}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
