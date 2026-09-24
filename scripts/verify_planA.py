# -*- coding: utf-8 -*-
"""
verify_planA.py — 「同窗多块」定号方案 L1 端到端判据

场景（复刻设置页真实形态，见 docs/20260921_真问题定位_*.md §1.4/1.5）：
    一个窗口实例 + N 个独立文本块，每块各自走一次 InitTextPrinter，
    全部共享同一 TILE_BASE —— 也就是 22 块写同一批号的场景。

三套定号同时跑，同一份 BDF 真值，逐像素比：

  P  现状「位置定号」   tile = TILE_BASE + win[0x18]（TILE_OFFSET，每块复位 = 0）
  A  字形槽定号         tile = TILE_BASE + 4*slot(code, phase)
  S  屏幕格定号         tile = TILE_BASE + ty*30 + tx

判据：整屏逐像素 == BDF 真值。任何差异即该方案不成立。

禁止手抄：掩码表/位移表从 blend_glyph.c 正则提取，字模从 BDF 真值走
pack_1bpp → chs_cell_from_1bpp（全部 import 自 verify_plan4.py）。
"""
import importlib.util
import sys

ROOT = r'C:\code\GBA-Rom-Translator'
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

_spec = importlib.util.spec_from_file_location('v4', ROOT + r'\scripts\verify_plan4.py')
v4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v4)

parse_bdf = v4.parse_bdf
pack_1bpp = v4.pack_1bpp
chs_cell_from_1bpp = v4.chs_cell_from_1bpp
extract_cols = v4.extract_cols
blend_glyph_4bpp = v4.blend_glyph_4bpp
cell_get = v4.cell_get
list_view = v4.list_view

# ------------------------------------------------------------------ 常量
SCR_W, SCR_H = 240, 160          # 像素
TILES_X, TILES_Y = 30, 20        # tile 格
BASE = 1                         # TILE_BASE（设置页实测 tb=1）
ADVANCE, INK = 12, 11            # 大库：步进 12 / 墨宽 11
LOWER_P = 1                      # 方案 P/A：下半 = 同列下一 tile 号（+1）
LOWER_S = 30                     # 方案 S：下半 = 下一 tile 行的同列（+30）
ARROW_TILE = 0xFE                # 引擎箭头固定落点（TILE_BASE + 0xFE）

COLORS = [0] * 16
COLORS[14] = 2
COLORS[15] = 1


# ------------------------------------------------------------------ 屏幕模型
class Screen:
    def __init__(self):
        self.tiles = {}
        self.tmap = {}

    def tile(self, t):
        if t not in self.tiles:
            self.tiles[t] = bytearray(32)
        return self.tiles[t]

    def utm(self, cx, cy, upper, lower):
        self.tmap[(cx, cy)] = upper
        self.tmap[(cx, cy + 1)] = lower

    def render(self):
        px = [[0] * SCR_W for _ in range(SCR_H)]
        for (cx, cy), t in self.tmap.items():
            blk = self.tiles.get(t)
            if blk is None:
                continue
            for r in range(8):
                y = cy * 8 + r
                if not (0 <= y < SCR_H):
                    continue
                for x in range(8):
                    xx = cx * 8 + x
                    if not (0 <= xx < SCR_W):
                        continue
                    b = blk[r * 4 + (x >> 1)]
                    px[y][xx] = (b >> 4) if (x & 1) else (b & 0x0F)
        return px


# ------------------------------------------------------------------ 定号方案
class SchemeP:
    """现状：tile = TILE_BASE + TILE_OFFSET，每块 InitTextPrinter 复位为 0"""
    name = 'P 现状(位置定号)'
    lower = LOWER_P
    spacing = 12

    def layout(self, blk, n, px):
        return (blk['tx'], px & 7)

    def advance(self, blk, adv):
        blk['tx'] += adv
        blk['offset'] += adv * 2     # C 源码：win[0x18] += adv * 2

    def claim(self, blk, tx, ty, code, phase, tail, half=0):
        return BASE + blk['offset'] + (2 if tail else 0) + half

    def stats(self, sc):
        used = sorted(t for t in sc.tiles if any(sc.tiles[t]))
        return len(used), (max(used) if used else 0)


class SchemeA:
    """字形槽定号：tile = TILE_BASE + 4*slot(code,phase)；每槽 = 2 列 × 2 行。
    🔴 槽与屏幕列解耦 ⇒ 相邻字符无法共享尾列 ⇒ 每字必须独占 2 个 tile 列（16px 步进）。"""
    name = 'A 字形槽定号'
    lower = LOWER_P
    spacing = 16

    def __init__(self, cap=192):
        self.cap = cap
        self.tbl = {}
        self.next = 0
        self.overflow = 0

    def layout(self, blk, n, px):
        return (blk['col'] + 2 * n, 0)

    def advance(self, blk, adv):
        pass

    def claim(self, blk, tx, ty, code, phase, tail, half=0):
        k = (code, phase)
        s = self.tbl.get(k)
        if s is None:
            if self.next >= self.cap:
                self.overflow += 1
                s = 0
            else:
                s = self.next
                self.tbl[k] = s
                self.next += 1
        return BASE + 4 * s + (2 if tail else 0) + half

    def stats(self, sc):
        used = sorted(t for t in sc.tiles if any(sc.tiles[t]))
        return len(used), (max(used) if used else 0)


class SchemeS:
    """屏幕格定号：tile = TILE_BASE + ty*30 + tx（下半 = ty+1 行的同列）"""
    name = 'S 屏幕格定号'
    lower = LOWER_S
    spacing = 12

    def layout(self, blk, n, px):
        return (blk['tx'], px & 7)

    def advance(self, blk, adv):
        blk['tx'] += adv

    def claim(self, blk, tx, ty, code, phase, tail, half=0):
        n = (ty + half) * TILES_X + tx + (1 if tail else 0)
        # 引擎箭头固定占 TILE_BASE+0xFE/+0xFF：跳过这两个号，保持单射
        if n >= ARROW_TILE:
            n += 2
        return BASE + n

    def stats(self, sc):
        used = sorted(t for t in sc.tiles if any(sc.tiles[t]))
        return len(used), (max(used) if used else 0)


# ------------------------------------------------------------------ 绘制（复刻 print_glyph_px）
def draw_block(sc, sch, blk):
    """复刻 PrintNextChar_hook.c::print_glyph_px 的相位推进 + 落砖 + UpdateTilemap

    每个方案自己决定「本字落在哪个 tile 列、以什么相位」：
      P/S  线性推进（12px 步进 ⇒ 相邻字共享尾列，phase 交替 0/4）
      A    每字独占 2 个 tile 列（16px 步进 ⇒ 无共享，phase 恒 0）
    """
    blk['tx'] = blk['col']
    blk['offset'] = 0        # P 方案的 TILE_OFFSET（每块 InitTextPrinter 复位为 0）
    ty = blk['row']
    px = 0
    for n, (code, g128) in enumerate(blk['glyphs']):
        tx, phase = sch.layout(blk, n, px)
        w0 = min(8 - phase, INK)
        w1 = INK - w0
        adv = max(1, (phase + ADVANCE) >> 3)   # C 源码：adv = (phase + advance) >> 3

        t0 = sch.claim(blk, tx, ty, code, phase, False, 0)
        t0l = sch.claim(blk, tx, ty, code, phase, False, 1)
        up, lo = extract_cols(g128, 0, w0)
        blend_glyph_4bpp(list_view(sc.tile(t0)), up, w0, phase, COLORS)
        blend_glyph_4bpp(list_view(sc.tile(t0l)), lo, w0, phase, COLORS)

        if w1 != 0:
            t1 = sch.claim(blk, tx, ty, code, phase, True, 0)
            t1l = sch.claim(blk, tx, ty, code, phase, True, 1)
            up, lo = extract_cols(g128, w0, w1)
            blend_glyph_4bpp(list_view(sc.tile(t1)), up, w1, 0, COLORS)
            blend_glyph_4bpp(list_view(sc.tile(t1l)), lo, w1, 0, COLORS)
            zero = bytes(32)
            if w1 < 8:
                blend_glyph_4bpp(list_view(sc.tile(t1)), zero, 8 - w1, w1, COLORS)
                blend_glyph_4bpp(list_view(sc.tile(t1l)), zero, 8 - w1, w1, COLORS)

        sc.utm(tx, ty, t0, t0l)
        if w1 != 0:
            sc.utm(tx + 1, ty, t1, t1l)

        px += ADVANCE
        sch.advance(blk, adv)


# ------------------------------------------------------------------ 场景
def build_scene(idx):
    """设置页形态：10 个文本行 × 2 列 = 20 个独立块，块间大量复用同一批字。
    左边 = 标签（4 字），右边 = 取值（2 字）。"""
    pool = '\u8bbe\u7f6e\u6587\u5b57\u901f\u5ea6\u6218\u6597\u6548\u679c' \
           '\u753b\u9762\u8fb9\u6846\u7a97\u53e3\u5f00\u542f\u5173\u95ed' \
           '\u58f0\u97f3\u97f3\u91cf\u97f3\u4e50\u5b58\u50a8\u5220\u9664' \
           '\u786e\u8ba4\u53d6\u6d88\u6e29\u548c\u4e2d\u7b49\u9ad8\u4f4e' \
           '\u5feb\u6162\u901a\u77e5\u663e\u793a\u900f\u660e\u6de1\u8272'
    pool = [c for c in pool if ord(c) in idx]

    # 20 个块：标签固定 4 字，取值固定 2 字，全部从 pool 里取（⇒ 大量重复字）
    labels = ['\u8bbe\u7f6e\u6587\u5b57\u901f\u5ea6', '\u6218\u6597\u6548\u679c\u753b\u9762',
              '\u8fb9\u6846\u7a97\u53e3\u5f00\u542f', '\u5173\u95ed\u58f0\u97f3\u97f3\u91cf',
              '\u97f3\u4e50\u5b58\u50a8\u5220\u9664', '\u786e\u8ba4\u53d6\u6d88\u6e29\u548c',
              '\u4e2d\u7b49\u9ad8\u4f4e\u5feb\u6162', '\u901a\u77e5\u663e\u793a\u900f\u660e',
              '\u6de1\u8272\u6587\u5b57\u901f\u5ea6', '\u753b\u9762\u8fb9\u6846\u5173\u95ed']
    values = ['\u6162', '\u5f00', '\u5173', '\u5927', '\u5c0f', '\u4e2d',
              '\u5feb', '\u9ad8', '\u4f4e', '\u786e\u8ba4']
    labels = [s for s in labels if all(ord(c) in idx for c in s)]
    values = [s for s in values if all(ord(c) in idx for c in s)]

    blocks = []
    for i in range(min(10, len(labels))):
        ty = 1 + i * 2
        blocks.append((2, ty, labels[i]))
    for i in range(min(10, len(values))):
        ty = 1 + i * 2
        blocks.append((16, ty, values[i]))
    # 再补一批短块，逼近设置页的 22 块
    for i in range(2):
        blocks.append((22, 1 + i * 2, values[i]))
    return blocks, pool


def expected_image(idx, blocks, spacing=ADVANCE):
    """BDF 真值画面。spacing = 每字步进像素（P/S 用 12，A 用 16）"""
    exp = [[0] * SCR_W for _ in range(SCR_H)]
    for (col, row, text) in blocks:
        y0 = row * 8
        for n, ch in enumerate(text):
            rom = pack_1bpp(idx[ord(ch)])
            g = chs_cell_from_1bpp(rom, 11, 11, 2)
            x0 = col * 8 + spacing * n
            for r in range(16):
                Y = y0 + r
                if not (0 <= Y < SCR_H):
                    continue
                for j in range(INK):
                    X = x0 + j
                    if 0 <= X < SCR_W:
                        v = COLORS[cell_get(g, r, j)]
                        if v:
                            exp[Y][X] = v
    return exp


def build_full(idx, rows=10, per_row=20):
    """满屏负荷：rows 个文本行 × per_row 字 = 全屏 240×160 铺满中文。
    字形池取 BDF 里前 N 个高频字，按奇数列长循环 ⇒ 同一字会同时出现在
    相位 0 与相位 4（这是字形槽方案的最坏情况）。"""
    chars = [chr(c) for c in sorted(idx) if 0x4E00 <= c <= 0x9FFF]
    blocks = []
    for r in range(rows):
        n = per_row
        text = ''.join(chars[(r * n + k) % len(chars)] for k in range(n))
        blocks.append((0, r * 2, text))
    return blocks


def load_test(idx, caps=(128, 192, 256)):
    print()
    print('=' * 72)
    print('满屏负荷测试：10 行 × 20 字 = 200 字，铺满 240×160')
    print('-' * 72)
    blocks = build_full(idx)
    total = sum(len(t) for _, _, t in blocks)
    distinct = len(set(''.join(t for _, _, t in blocks)))
    print('总字数 %d   不同字形 G = %d' % (total, distinct))
    print()
    print('%-16s %8s %8s %8s %8s' % ('方案', '差异像素', '用号数', '最大号', '溢出'))
    print('-' * 72)
    for sch in (SchemeS(), SchemeA(cap=128), SchemeA(cap=256)):
        exp = expected_image(idx, blocks, getattr(sch, 'spacing', 12))
        sc = Screen()
        for (col, row, text) in blocks:
            glyphs = [(ord(c), chs_cell_from_1bpp(pack_1bpp(idx[ord(c)]), 11, 11, 2))
                      for c in text]
            draw_block(sc, sch, {'col': col, 'row': row, 'glyphs': glyphs})
        ren = sc.render()
        d = diff_px(exp, ren)
        ntile, tmax = sch.stats(sc)
        label = sch.name + ('' if not isinstance(sch, SchemeA) else ' cap=%d' % sch.cap)
        print('%-16s %8d %8d %8d %8d' % (label, d, ntile, tmax, getattr(sch, 'overflow', 0)))
    print('-' * 72)
    print('可用号空间：BG0 charBase 起的 32 KB = 1024 号（0..1023）')
    print('=' * 72)


def diff_px(exp, ren):
    n = 0
    for y in range(SCR_H):
        ey, ry = exp[y], ren[y]
        for x in range(SCR_W):
            if ey[x] != ry[x]:
                n += 1
    return n


def show(grid, title, x0=0, y0=0, w=180, h=48):
    print('%s  (%d,%d) %dx%d' % (title, x0, y0, w, h))
    for y in range(y0, min(y0 + h, SCR_H)):
        line = ''
        for x in range(x0, min(x0 + w, SCR_W)):
            v = grid[y][x]
            line += ('.' if v == 0 else ('#' if v == 1 else '+'))
        print('   ' + line)
    print()


def main():
    idx = parse_bdf(ROOT + r'\fonts\default\Normal.bdf')
    blocks_def, pool = build_scene(idx)
    print('BDF 可用字数: %d   场景文本块: %d   字池: %d 字'
          % (len(idx), len(blocks_def), len(pool)))
    total_chars = sum(len(t) for _, _, t in blocks_def)
    distinct = len(set(''.join(t for _, _, t in blocks_def)))
    print('总字数: %d   同屏不同字形数 G = %d' % (total_chars, distinct))
    print()

    exp12 = expected_image(idx, blocks_def, 12)
    exp16 = expected_image(idx, blocks_def, 16)

    results = []
    for sch in (SchemeP(), SchemeA(cap=192), SchemeS()):
        exp = exp16 if getattr(sch, 'spacing', 12) == 16 else exp12
        sc = Screen()
        for (col, row, text) in blocks_def:
            glyphs = [(ord(c), chs_cell_from_1bpp(pack_1bpp(idx[ord(c)]), 11, 11, 2))
                      for c in text]
            draw_block(sc, sch, {'col': col, 'row': row, 'glyphs': glyphs})
        ren = sc.render()
        d = diff_px(exp, ren)
        ntile, tmax = sch.stats(sc)
        ovf = getattr(sch, 'overflow', 0)
        results.append((sch, sc, ren, d, ntile, tmax, ovf, exp))

    print('=' * 72)
    print('%-22s %8s %8s %8s %8s' % ('方案', '差异像素', '用号数', '最大号', '溢出'))
    print('-' * 72)
    for sch, sc, ren, d, ntile, tmax, ovf, _e in results:
        print('%-22s %8d %8d %8d %8d' % (sch.name, d, ntile, tmax, ovf))
    print('=' * 72)
    print('屏幕格上限 %d 号（%d 列 × %d 行）；TILE_BASE = %d；箭头保留号 TILE_BASE+0xFE'
          % (TILES_X * TILES_Y, TILES_X, TILES_Y, BASE))
    print()

    print('目标画面（前 180×48 px，12px 步进）：')
    show(exp12, '')
    for sch, sc, ren, d, ntile, tmax, ovf, _e in results:
        print('实际渲染 — %s（差异 %d px）：' % (sch.name, d))
        show(ren, '')

    ok = [sch.name for sch, sc, ren, d, *_ in results if d == 0]
    bad = [sch.name for sch, sc, ren, d, *_ in results if d != 0]
    print('通过（逐像素 == BDF 真值）:', '、'.join(ok) if ok else '无')
    print('未通过                  :', '、'.join(bad) if bad else '无')

    load_test(idx)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
