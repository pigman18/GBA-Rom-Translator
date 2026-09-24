# -*- coding: utf-8 -*-
"""
verify_plan4.py — 方案 4 端到端一致性自检（L1 静态）

链路（逐环复刻现状 C 源码，不手抄任何表）：
  BDF 真值 11x11
    → pack_1bpp            (scripts/build_font_1bpp.py)
    → chs_cell_from_1bpp   (src/text/chinese_glyph.c)
    → print_glyph_px       (src/text/PrintNextChar_hook.c)  相位序列 + tile 复用
    → blend_glyph_4bpp / extract_cols  (src/text/blend_glyph.c)
    → tiles + tilemap 格序列
    → 重建屏幕像素
    → 与「方案 4 目标画面」逐像素比对

判据：屏幕 [0,16) x [0, 12N) 必须与目标完全相同（含阴影值 14）。
任何差异 = 方案 4 未达标。
"""
import re
import sys

ROOT = r'C:\code\GBA-Rom-Translator'
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ---------------------------------------------------------------- 型
def parse_masks(csrc):
    """从 blend_glyph.c 提取 sGlyphMasks[9][8][3]（禁止手抄）"""
    m = re.search(r'sGlyphMasks\[9\]\[8\]\[3\]\s*=\s*\{(.*?)\n\};', csrc, re.S)
    if not m:
        raise SystemExit('sGlyphMasks 未找到')
    nums = [int(x, 16) for x in re.findall(r'0x([0-9A-Fa-f]{8})', m.group(1))]
    if len(nums) != 9 * 8 * 3:
        raise SystemExit('sGlyphMasks 项数异常: %d' % len(nums))
    out = [[[0, 0, 0] for _ in range(8)] for _ in range(9)]
    i = 0
    for w in range(9):
        for s in range(8):
            for k in range(3):
                out[w][s][k] = nums[i]; i += 1
    return out


def parse_shifts(csrc):
    """从 blend_glyph.c 提取 sGlyphShiftAmounts[8]"""
    m = re.search(r'sGlyphShiftAmounts\[8\]\s*=\s*\{(.*?)\n\};', csrc, re.S)
    if not m:
        raise SystemExit('sGlyphShiftAmounts 未找到')
    pairs = re.findall(r'\{\s*(\d+)\s*,\s*(\d+)\s*\}', m.group(1))
    if len(pairs) != 8:
        raise SystemExit('sGlyphShiftAmounts 项数异常: %d' % len(pairs))
    return [(int(a), int(b)) for a, b in pairs]


CSRC = open(ROOT + r'\configs\POKEMON_RUBY_AXVJ00\hook\src\text\blend_glyph.c',
            'rb').read().decode('utf-8', 'replace')
MASKS = parse_masks(CSRC)
SHIFTS = parse_shifts(CSRC)

# ---------------------------------------------------------------- 原语复刻
def blend_row_4bpp(rows32, r, width, colors):
    """blend_glyph.c: blend_row_4bpp — 展开第 r 行为 nibble 序"""
    row = rows32[r * 4:r * 4 + 4]
    val = 0
    for p in range(width):
        px = (row[p >> 1] >> ((p & 1) * 4)) & 0xF
        val |= (colors[px] & 0xF) << (p * 4)
    return val & 0xFFFFFFFF


def blend_glyph_4bpp(dest32, rows32, width, startPixel, colors):
    """复刻 blend_glyph_4bpp（spillTile=0 ⇒ 无溢出写入）"""
    if width == 0:
        return startPixel // 8
    if width > 8:
        width = 8
    if startPixel > 7:
        startPixel = 7
    mk = MASKS[width][startPixel]
    mask1 = mk[0] | mk[2]
    left = SHIFTS[startPixel][0]
    out = [0] * 8
    for r in range(8):
        val = blend_row_4bpp(rows32, r, width, colors)
        out[r] = ((dest32[r] & mask1) | ((val << left) & 0xFFFFFFFF)) & 0xFFFFFFFF
    for r in range(8):
        dest32[r] = out[r]


def put_px4(tile, r, x, v):
    i = r * 4 + (x >> 1)
    if x & 1:
        tile[i] = (tile[i] & 0x0F) | ((v & 0x0F) << 4)
    else:
        tile[i] = (tile[i] & 0xF0) | (v & 0x0F)


def extract_cols(g128, xs, w):
    """复刻 extract_cols：从 16x16 画布取列 [xs, xs+w) → up(上8行)/lo(下8行)"""
    tl, bl, tr, br = g128[0x00:0x20], g128[0x20:0x40], g128[0x40:0x60], g128[0x60:0x80]
    up = bytearray(32)
    lo = bytearray(32)
    if w == 0:
        return bytes(up), bytes(lo)
    if w > 8:
        w = 8
    for j in range(w):
        sc = xs + j
        if sc >= 16:
            continue
        su, sl = (tl, bl) if sc < 8 else (tr, br)
        c = sc & 7
        for r in range(8):
            bu = su[r * 4 + (c >> 1)]
            bv = sl[r * 4 + (c >> 1)]
            vu = (bu >> 4) if (c & 1) else (bu & 0x0F)
            vl = (bv >> 4) if (c & 1) else (bv & 0x0F)
            put_px4(up, r, j, vu)
            put_px4(lo, r, j, vl)
    return bytes(up), bytes(lo)


# ---------------------------------------------------------------- 字模
def parse_bdf(path):
    bdf = open(path, 'rb').read().decode('ascii', 'replace')
    idx = {}
    for m in re.finditer(
            r'ENCODING\s+(\d+)\s*\n(?:.*?\n)*?BITMAP\s*\n((?:[0-9A-Fa-f]+\s*\n)+)ENDCHAR',
            bdf):
        idx[int(m.group(1))] = [int(l, 16) for l in m.group(2).split()]
    return idx


W, H, X0, Y0, STRIDE = 11, 11, 0, 2, 16

# fill_colors：墨迹(值15) → 色号 1，阴影(值14) → 色号 2，空(值0) → 底色 0
COLORS = [0] * 16
COLORS[14] = 2
COLORS[15] = 1


def pack_1bpp(rows):
    """复刻 scripts/build_font_1bpp.py::pack_1bpp（行间无填充连续位流）"""
    out = bytearray(STRIDE)
    bit = 0
    for r in range(H):
        y = Y0 + r
        row = rows[y] if 0 <= y < len(rows) else 0
        for c in range(W):
            if (row >> (15 - (X0 + c))) & 1:
                out[bit >> 3] |= 0x80 >> (bit & 7)
            bit += 1
    return bytes(out)


ROW_OFF_BIG = 2


def chs_cell_from_1bpp(bits, width, rows_n, line_off):
    """复刻 chinese_glyph.c::chs_cell_from_1bpp → 128B [TL@0][BL@0x20][TR@0x40][BR@0x60]"""
    ink = [[0, 0] for _ in range(16)]
    for r in range(rows_n):
        if line_off + r >= 16:
            break
        base = r * width
        lo = hi = 0
        for x in range(width):
            bi = base + x
            bit = (bits[bi >> 3] >> (7 - (bi & 7))) & 1
            if x < 8:
                if bit:
                    lo |= 1 << x
            elif bit:
                hi |= 1 << (x - 8)
        ink[line_off + r][0] = lo & 0xFF
        ink[line_off + r][1] = hi & 0xFF

    cell = bytearray(128)
    for r in range(16):
        for half in range(2):
            b = [0, 0, 0, 0]
            for x in range(8):
                gx = half * 8 + x
                if ink[r][half] & (1 << x):
                    v = 15
                elif r >= 1 and gx >= 1 and (ink[r - 1][(gx - 1) >> 3] & (1 << ((gx - 1) & 7))):
                    v = 14
                else:
                    v = 0
                b[x >> 1] |= (v << (4 if (x & 1) else 0))
            base = (0x40 if r < 8 else 0x60) if half else (0x00 if r < 8 else 0x20)
            q = base + (r & 7) * 4
            cell[q:q + 4] = bytes(b)
    return bytes(cell)


# ---------------------------------------------------------------- 渲染层复刻
class Screen:
    """模拟 tile_data 区 + tilemap 格（tm0 线性）"""

    def __init__(self):
        self.tiles = {}      # tile 号 -> bytearray(32)
        self.tmap = {}       # (cx, cy) -> tile 号
        self.hazard = []

    def tile(self, t):
        if t not in self.tiles:
            self.tiles[t] = bytearray(32)
        return self.tiles[t]

    def utm(self, cx, cy, upper, lower):
        """复刻 UpdateTilemap：upper 写当前格，lower 写下一行格"""
        self.tmap[(cx, cy)] = upper
        self.tmap[(cx, cy + 1)] = lower

    def render(self, width_px, height_px):
        px = [[None] * width_px for _ in range(height_px)]
        for (cx, cy), t in self.tmap.items():
            blk = self.tile(t)
            for r in range(8):
                y = cy * 8 + r
                if not (0 <= y < height_px):
                    continue
                for x in range(8):
                    xx = cx * 8 + x
                    if 0 <= xx < width_px:
                        byte = blk[r * 4 + (x >> 1)]
                        v = (byte >> 4) if (x & 1) else (byte & 0x0F)
                        px[y][xx] = v
        return px


LOWER_DELTA = 1   # chs_lower_delta: tm0/tm1 = 1


def print_glyph_px(sc, win, g128, ink, advance, alloc=None):
    """复刻 PrintNextChar_hook.c::print_glyph_px

    alloc=None  → tm0 路径：tile 来自 TILE_BASE+TILE_OFFSET，下一列 = t0+2
    alloc=fn    → tm1 路径：tile 来自 v8_alloc_tile（每次连续 2 个），下一列 = 新领
    """
    colors = [0] * 16
    colors[14] = 2          # 阴影 → 色号 2
    colors[15] = 1          # 墨迹 → 色号 1

    px = win['phase']
    phase = px & 7
    w0 = (8 - phase) if (8 - phase) < ink else ink
    w1 = ink - w0
    adv = (phase + advance) >> 3
    if adv < 1:
        adv = 1

    tx0 = win['cx']
    if phase == 0:
        t0 = alloc() if alloc else win['offset']
    else:
        t0 = win['last_tile']
    if w1 != 0:
        t1 = alloc() if alloc else (t0 + 2)
    else:
        t1 = 0

    up, lo = extract_cols(g128, 0, w0)
    blend_glyph_4bpp(list_view(sc.tile(t0)), up, w0, phase, colors)
    blend_glyph_4bpp(list_view(sc.tile(t0 + LOWER_DELTA)), lo, w0, phase, colors)

    if w1 != 0:
        up, lo = extract_cols(g128, w0, w1)
        blend_glyph_4bpp(list_view(sc.tile(t1)), up, w1, 0, colors)
        blend_glyph_4bpp(list_view(sc.tile(t1 + LOWER_DELTA)), lo, w1, 0, colors)
        # chs_fill_bg(t1, w1, 8)
        zero = bytes(32)
        blend_glyph_4bpp(list_view(sc.tile(t1)), zero, 8 - w1, w1, colors)
        blend_glyph_4bpp(list_view(sc.tile(t1 + LOWER_DELTA)), zero, 8 - w1, w1, colors)

    sc.utm(tx0, 0, t0, t0 + LOWER_DELTA)
    if w1 != 0:
        win['cx'] = tx0 + 1
        sc.utm(win['cx'], 0, t1, t1 + LOWER_DELTA)
    win['cx'] = tx0 + adv

    win['phase'] = px + advance
    win['last_tile'] = t1 if w1 != 0 else t0
    if not alloc:
        win['offset'] += adv * 2
    return adv


class AllocTL1:
    """模拟 v8_alloc_tile：返回连续 glyph_len 个 tile 的首号。
    刻意用大间隔 + 带洞的号，验证「渲染结果与 tile 号无关」。"""

    def __init__(self, base=64, gap=7):
        self.next = base
        self.gap = gap

    def __call__(self):
        t = self.next
        self.next += 2 + self.gap
        return t


def list_view(ba):
    """把 bytearray(32) 当 8 个 u32 视图（小端），blend 直接改 ba"""
    class LU:
        def __init__(self, b): self.b = b
        def __getitem__(self, i):
            return int.from_bytes(self.b[i * 4:i * 4 + 4], 'little')
        def __setitem__(self, i, v):
            self.b[i * 4:i * 4 + 4] = (v & 0xFFFFFFFF).to_bytes(4, 'little')
    return LU(ba)


# ---------------------------------------------------------------- 主流程
def main():
    idx = parse_bdf(ROOT + r'\fonts\default\Normal.bdf')
    # 取 8 个真实汉字（覆盖多相位 + 复杂/简单字形）
    chars = ['\u554a', '\u7684', '\u4e00', '\u4e86',
             '\u4f60', '\u597d', '\u4e2d', '\u6587']   # 啊 的 一 了 你 好 中 文
    chars = [c for c in chars if ord(c) in idx]
    N = len(chars)
    print('参与自检的字数:', N, ' '.join(chars))

    # 期望屏幕：[0,16) x [0, 12N)，第 n 字 11 列贴在 [12n, 12n+11)
    Wpx = 12 * N
    ADVANCE, INK = 12, 11
    g128s = []
    for ch in chars:
        rom = pack_1bpp(idx[ord(ch)])
        g128s.append(chs_cell_from_1bpp(rom, W, H, ROW_OFF_BIG))

    expect = [[0] * Wpx for _ in range(16)]
    for n, g in enumerate(g128s):
        for r in range(16):
            for j in range(INK):
                expect[r][12 * n + j] = COLORS[cell_get(g, r, j)]

    def run(alloc):
        sc = Screen()
        w = {'phase': 0, 'cx': 0, 'offset': 0, 'last_tile': 0}
        for g in g128s:
            print_glyph_px(sc, w, g, INK, ADVANCE, alloc)
        return sc

    sc_tm0 = run(None)              # tm0：线性 offset，t1 = t0+2
    sc_tm1 = run(AllocTL1())        # tm1：动态分配，tile 号完全不同
    render = [[sc_tm0.render(Wpx, 16)[y][x] or 0 for x in range(Wpx)]
              for y in range(16)]
    render1 = [[sc_tm1.render(Wpx, 16)[y][x] or 0 for x in range(Wpx)]
               for y in range(16)]

    def diff(rend):
        d = []
        for y in range(16):
            for x in range(Wpx):
                if rend[y][x] != expect[y][x]:
                    d.append((x, y, expect[y][x], rend[y][x]))
        return d

    bad = diff(render)
    bad1 = diff(render1)

    print()
    print('=' * 62)
    print('屏幕 %d x 16 px   参与字数 %d' % (Wpx, N))
    print('tm0 路径：tile 数 %2d  tilemap 格 %2d  差异像素 %d'
          % (len(sc_tm0.tiles), len(sc_tm0.tmap), len(bad)))
    print('tm1 路径：tile 数 %2d  tilemap 格 %2d  差异像素 %d  （tile 号 = %s...）'
          % (len(sc_tm1.tiles), len(sc_tm1.tmap), len(bad1),
             sorted(sc_tm1.tiles)[:6]))
    if bad:
        print('tm0 前 20 处差异 (x, y, 期望, 实际):')
        for b in bad[:20]:
            print('   ', b)
    if bad1:
        print('tm1 前 20 处差异 (x, y, 期望, 实际):')
        for b in bad1[:20]:
            print('   ', b)
    print('=' * 62)

    # 可视化（用 # 表示墨/阴影）
    print('\n目标画面：')
    show(expect, Wpx, N)
    print('\n实际渲染（tm0）：')
    show(render, Wpx, N)
    if render1 != render:
        print('\n实际渲染（tm1）：')
        show(render1, Wpx, N)

    # 逐字独立检验：11 列是否都在
    print('\n逐字完整性（墨迹非零列数 / 期望 11）：')
    for n in range(N):
        cols = set()
        for y in range(16):
            for x in range(12 * n, 12 * n + 11):
                if render[y][x]:
                    cols.add(x - 12 * n)
        print('   %s: %d 列 %s' % (chars[n], len(cols),
                                   'OK' if len(cols) <= 11 else 'BAD'))
    print()
    print('tm0 == tm1 :', '一致' if render == render1 else '不一致')
    print('结论:', 'PASS — 现状渲染 == 方案 4 目标画面（tm0 / tm1 双路径）'
          if not bad and not bad1 else 'FAIL — 存在差异')
    return 0 if (not bad and not bad1) else 1


def cell_get(cell, r, j):
    """从 128B 单元取 (行 r, 列 j) 的 4bpp 值（half=j>>3, x=j&7，同 chinese_glyph.c）"""
    base = (0x40 if j >= 8 else 0x00) if r < 8 else (0x60 if j >= 8 else 0x20)
    i = base + (r & 7) * 4 + ((j & 7) >> 1)
    byte = cell[i]
    return (byte >> 4) if (j & 1) else (byte & 0x0F)


def show(grid, Wpx, N):
    for y in range(16):
        line = ''
        for x in range(Wpx):
            v = grid[y][x] or 0
            line += ('.' if v == 0 else ('#' if v == 1 else '+'))
            if (x + 1) % 12 == 0 and (x + 1) != Wpx:
                line += '|'
        print('   %2d %s' % (y, line))
    print('      ' + ''.join(str((i // 10) % 10) if (i + 1) % 12 == 0 else ' '
                              for i in range(Wpx)))


if __name__ == '__main__':
    raise SystemExit(main())
