# -*- coding: utf-8 -*-
"""l1cmp.py <tag> <win_hex> [d:slot | slot ...] — v26 硬 L1 判据（静态，无需模拟器交互）

对每个域（0/1）的每个占用槽：
  A. 重建整字（左半 TL/BL cols[phase,8)，右半 TR/BR cols[0,w1)）
     与 **ROM 里 1bpp 字库真值**（chs_cell_from_1bpp 同算法 + fill_colors 调色）逐 nibble 全等。
  B. v26 不变式：phase>0 时，本槽 cols[0,phase) 必须等于「上一字右半」同行 cols[0,phase)。

调色 = fill_colors()（win[0x0C]=C / [0x0D]=D / [0x0E]=E + ADDR_OPT_FG_COLOR 覆盖）
⇒ 期望值是**精确 nibble**，不是形状近似。无参数 = 全查。
"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
ROM = Path(r"C:/code/GBA-Rom-Translator/roms/outputs/_t1.gba")

LIBS = {  # lib → (addr, width, rows, row_off, bytes)
    1: (0x09500000, 11, 11, 2, 16),
    2: (0x09700000, 9, 11, 2, 13),
    3: (0x09600000, 9, 9, 5, 11),
}
OWN_BASE, OWN_N = 352, 40
FAR_BASE, FAR_N = 528, 92
KEYS0, STAMPS0 = 0x08, 0x2E8
KEYS1, STAMPS1 = 0x458, 0x738
STRIDE, SLAB = 4, 0x3E000

tag, win_addr = sys.argv[1], int(sys.argv[2], 16)
want = set()
for t in sys.argv[3:]:
    if ":" in t:
        d, s = t.split(":")
        want.add((int(d), int(s)))
    else:
        want.add((None, int(t)))

vram = (T / ("drive_%s_vram.bin" % tag)).read_bytes()
iw = (T / ("drive_%s_iwram.bin" % tag)).read_bytes()
ew = (T / ("drive_%s_ewram.bin" % tag)).read_bytes()
rom = ROM.read_bytes()


IW_BASE, EW_BASE = 0x03000000, 0x02000000


def buf_of(addr):
    if addr >= 0x08000000:
        return rom
    return iw if addr >= IW_BASE else ew


def off_of(addr):
    if addr >= 0x08000000:
        return addr - 0x08000000
    return (addr - IW_BASE) if addr >= IW_BASE else (addr - EW_BASE)


def rd8(addr):
    return buf_of(addr)[off_of(addr)]


def rd32(addr):
    return struct.unpack_from("<I", buf_of(addr), off_of(addr))[0]


# ---- 调色（= fill_colors）----
color_c, color_d, color_e = (rd8(win_addr + o) for o in (0x0C, 0x0D, 0x0E))
fg_ov = ew[0x3FFD1]                       # ADDR_OPT_FG_COLOR - 0x02000000
C = fg_ov if fg_ov else color_c
COLORS = [color_d] * 16
COLORS[14], COLORS[15] = color_e, C

TPLD = rd32(rd32(win_addr + 0x00) + 0x0C)
TB = rd8(win_addr + 0x16)
DOM = 0 if (((TPLD & 0xFFFFC000) + 0x4000) in (0x06004000, 0x06008000)) else 1

# ---- 每个域的落点必须取「**写它的那个窗口**」的 tileData / TILE_BASE -------------
# 槽表是全局的，两域可能由**不同窗口**写入（例：队伍页队名走 cb1 窗口 = 域 0，
# 而菜单 / 设置页的文字走 cb2 窗口 = 域 1）。只拿一个窗口的 tileData 去套另一个域
# 会整整偏一个 charBlock（0x4000）—— 曾据此误报「dom1 全部 A 差异」。
# 窗口表由 diag_log 维护（ADDR_TRACE + (8 + i*8)*4，24 项，首 5 字 = win/tpl/
# tileData/map/count）。
TRACE = 0x3C000                  # 0x0203C000 - 0x02000000
TR_TBL, TR_W, TR_N = 8, 8, 24
DOMT = {}
for _i in range(TR_N):
    _w, _tpl, _td, _mp, _cnt = struct.unpack_from(
        "<IIIII", ew, TRACE + (TR_TBL + _i * TR_W) * 4)
    if not _w or not _td:
        continue
    _dom = 0 if (((_td & 0xFFFFC000) + 0x4000) in (0x06004000, 0x06008000)) else 1
    DOMT[_dom] = (_td, rd8(_w + 0x16), _w, _cnt)
if DOM not in DOMT:
    DOMT[DOM] = (TPLD, TB, win_addr, -1)

print("win=%08X tpl->tileData=%08X dom=%d tb=%d  C=%d(ov=%d) D=%d E=%d -> [0]=%d [14]=%d [15]=%d"
      % (win_addr, TPLD, DOM, TB, color_c, fg_ov, color_d, color_e,
         COLORS[0], COLORS[14], COLORS[15]))
for _d in sorted(DOMT):
    _td, _tb, _w, _c = DOMT[_d]
    print("   域%d: tileData=%08X tb=%d win=%08X 落字数=%s"
          % (_d, _td, _tb, _w, "?" if _c < 0 else _c))


def vram_off(dom):
    return (DOMT[dom][0] - 0x06000000) & 0x1FFFF


def tile(n, dom):
    o = vram_off(dom) + n * 32
    return vram[o:o + 32]


def px(t, x, y):
    return (t[y * 4 + (x >> 1)] >> ((x & 1) * 4)) & 0xF


def font_mask(lib, code):
    addr, w, rows, roff, nb = LIBS[lib]
    off = (addr - 0x08000000) + code * nb
    d = rom[off:off + nb]
    return [[(d[(r * w + x) >> 3] >> (7 - ((r * w + x) & 7))) & 1
             for x in range(w)] for r in range(rows)], w, rows, roff


def expected(lib, code):
    """完全照抄 chs_cell_from_1bpp + fill_colors：cell 值 15→C、14→E、0→D。"""
    m, w, rows, roff = font_mask(lib, code)
    ink = [[0] * 16 for _ in range(16)]
    for r in range(rows):
        for x in range(w):
            ink[roff + r][x] = m[r][x]
    cell = [[0] * 16 for _ in range(16)]
    for r in range(16):
        for x in range(16):
            if ink[r][x]:
                cell[r][x] = 15
            elif r >= 1 and x >= 1 and ink[r - 1][x - 1]:
                cell[r][x] = 14
    return [[COLORS[v] for v in row] for row in cell], w


def dec(lo):
    k = lo >> 3
    return {"code": k >> 8, "lib": (k >> 4) & 3, "ink": k & 0xF, "phase": lo & 7}


def lookup(dom, lo):
    ko, n = (KEYS1, FAR_N) if dom else (KEYS0, OWN_N)
    for i in range(n):
        if struct.unpack_from("<I", ew, SLAB + ko + i * 8)[0] == lo:
            return i
    return None


def base_of(dom):
    return (FAR_BASE + DOMT[dom][1]) if dom else OWN_BASE


bad_total = 0
for dom in (0, 1):
    ko, n = (KEYS1, FAR_N) if dom else (KEYS0, OWN_N)
    base = base_of(dom)
    for i in range(n):
        if want and (dom, i) not in want and (None, i) not in want:
            continue
        lo, hi = struct.unpack_from("<II", ew, SLAB + ko + i * 8)
        if lo == 0:
            continue
        d = dec(lo)
        tl = base + i * STRIDE
        w0 = min(8 - d["phase"], d["ink"])
        w1 = d["ink"] - w0
        # cell 列空间：格列 c（0..ink-1）= 本字第 c 个像素
        got = [[None] * 16 for _ in range(16)]
        for y in range(8):
            for c in range(w0):
                got[y][c] = px(tile(tl, dom), d["phase"] + c, y)
                got[y + 8][c] = px(tile(tl + 1, dom), d["phase"] + c, y)
        for y in range(8):
            for c in range(w0, d["ink"]):
                got[y][c] = px(tile(tl + 2, dom), c - w0, y)
                got[y + 8][c] = px(tile(tl + 3, dom), c - w0, y)
        # 原始 tile 列空间（B 判据要按 tile 列比）
        rawU = [[px(tile(tl, dom), x, y) for x in range(8)] for y in range(8)]
        rawL = [[px(tile(tl + 1, dom), x, y) for x in range(8)] for y in range(8)]
        exp, _w = expected(d["lib"], d["code"])
        bad = [(c, y, got[y][c], exp[y][c]) for y in range(16)
               for c in range(d["ink"]) if got[y][c] != exp[y][c]]
        # ---- v26 B：TL/BL cols[0,phase) 必须是上一字右半 ----
        shb = []
        if d["phase"] > 0:
            pj = lookup(dom, hi) if hi else None
            if pj is None:
                srcU = [[COLORS[0]] * 8 for _ in range(8)]
                srcL = [[COLORS[0]] * 8 for _ in range(8)]
            else:
                pt = base_of(dom) + pj * STRIDE
                srcU = [[px(tile(pt + 2, dom), x, y) for x in range(8)] for y in range(8)]
                srcL = [[px(tile(pt + 3, dom), x, y) for x in range(8)] for y in range(8)]
            for y in range(8):
                for x in range(d["phase"]):
                    if rawU[y][x] != srcU[y][x]:
                        shb.append((x, y, rawU[y][x], srcU[y][x]))
                    if rawL[y][x] != srcL[y][x]:
                        shb.append((x, y + 8, rawL[y][x], srcL[y][x]))
        bad_total += len(bad) + len(shb)
        msg = "OK" if not bad else "A差异%d %s" % (len(bad), bad[:6])
        if shb:
            msg += " | B差异%d %s" % (len(shb), shb[:6])
        print("dom%d slot%-3d tile=%-4d code=%04X lib%d ink%2d phase%d | %s"
              % (dom, i, tl, d["code"], d["lib"], d["ink"], d["phase"], msg))
        if bad:
            for y in range(16):
                print("   %2d got %s" % (y, "".join("%X" % (v if v is not None else 0)
                                                     for v in got[y][:d["ink"]])))
                print("      exp %s" % ("".join("%X" % v for v in exp[y][:d["ink"]])))

print("\n==== %s (总差异 %d) ====" % ("L1 通过" if bad_total == 0 else "L1 不通过", bad_total))
