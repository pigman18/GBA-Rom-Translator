# -*- coding: utf-8 -*-
"""完整离线模拟器：忠实复刻 engine_emit_glyph（gid→slot→pool→tile→64B→tilemap），
把「VRAM + tilemap」渲染成屏幕 PNG，用于视觉验收。

模拟对象（逐行对照 configs/POKEMON_RUBY_AXVJ00/hook/src/text/engine.c）：
  chs8_hash(gid)   = floor(gid*19173961 / 2^32) 修正 => gid % 224
  chs8_slot(gid)   粘性直接映射 + 线性探测(8 步)，表满 => 拒发
  pool             = max(TILE_BASE + 512, 521)，并受 1024 上限夹
  gp               = (pool - TILE_BASE + 1) >> 1
  g                = gp + slot
  tile             = TILE_BASE + 2*g
  dst               = tdata + tile*32，拷 64B：dst[i] = (hi?fg:bg)<<4 | (lo?fg:bg)
  UpdateTilemap    tilemap[cell] = tile | pal<<12；tilemap[cell+32] = tile+1 | pal<<12
"""
import re
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(r"C:\code\GBA-Rom-Translator")
BDF = ROOT / "fonts/default/Middle.bdf"

SLOT_N = 224
GUARD = 521
ENGINE_CACHE = 512
COPY = 64
MEDIA = 128

# ---------------- BDF → 4bpp 8x16 字节（与 bin 布局一致：前 64B = 上砖+下砖） ----------
text = BDF.read_text("utf-8", errors="replace")
GB = {}
for m in re.finditer(r"^STARTCHAR.*?^ENCODING\s+(\d+).*?^BITMAP\s*$(.*?)^ENDCHAR",
                     text, re.M | re.S):
    GB[int(m.group(1))] = [int(l.strip(), 16) for l in
                           m.group(2).strip().splitlines() if l.strip()]

def glyph_bytes(ch):
    """返回 64 字节 4bpp（上砖 32B + 下砖 32B），nibble ∈ {0,0xF}"""
    r = GB.get(ord(ch))
    out = bytearray()
    if r is None:
        return bytes(64)
    for y in range(16):
        H = (r[y] >> 8) & 0xFF if y < len(r) else 0
        for i in range(4):
            lo = 0xF if (H >> (7 - 2 * i)) & 1 else 0
            hi = 0xF if (H >> (7 - 2 * i - 1)) & 1 else 0
            out.append((hi << 4) | lo)
    return bytes(out)

# ---------------- charmap：PCS → 汉字；再由 PCS 算 gid（= pack_glyph_index） ----------
PCS = {}
for line in (ROOT / "configs/POKEMON_RUBY_AXVJ00/charmap.txt").read_text(
        encoding="utf-8", errors="replace").splitlines():
    if "=" in line:
        k, v = line.split("=", 1)
        try:
            PCS[int(k, 16)] = v
        except ValueError:
            pass

def pack_glyph_index(lead, trail):
    idx = lead
    if idx >= 6:
        if idx >= 0x1B:
            idx -= 1
        idx -= 1
    idx -= 1
    return ((idx & 0xFF) << 8) | (trail & 0xFF)

def gid_of(ch):
    for code, s in PCS.items():
        if s == ch:
            return pack_glyph_index(code >> 8, code & 0xFF)
    return None

# ---------------- engine_emit_glyph 复刻 ----------------
def chs8_hash(gid):
    q = (gid * 19173961) >> 32
    k = gid - q * SLOT_N
    if k >= SLOT_N:
        k -= SLOT_N
    return k

class Engine:
    def __init__(self, tile_base=1, fg=15, bg=0, pal=0, tpl_id=0):
        self.tb = tile_base
        self.fg = fg
        self.bg = bg
        self.pal = pal
        self.tag = [0] * SLOT_N
        self.cnt = 0
        self.sig = tpl_id
        self.cur_tile_x = 0
        self.cur_y = 0
        self.vram = bytearray(1024 * 32)      # charBase 0：1024 个 4bpp tile
        self.tilemap = []                     # (row, col) = tile
        self.log = []

    def slot_of(self, gid):
        want = gid + 1
        k = chs8_hash(gid)
        for _ in range(8):
            t = self.tag[k]
            if t == want:
                return k
            if t == 0:
                if self.cnt >= SLOT_N:
                    return None
                self.tag[k] = want
                self.cnt += 1
                return k
            k += 1
            if k >= SLOT_N:
                k = 0
        return None

    def emit(self, gid, ch="?"):
        if gid >= 7168:
            return 0
        slot = self.slot_of(gid)
        if slot is None:
            self.log.append((ch, "表满拒发"))
            return 0
        tb = self.tb
        pool = tb + ENGINE_CACHE
        if pool < GUARD:
            pool = GUARD
        if pool + 2 * SLOT_N > 1024:
            pool = 1024 - 2 * SLOT_N
        gp = (pool - tb + 1) >> 1 if pool > tb else 0
        g = gp + slot
        tile = tb + 2 * g
        if tile + 1 > 1023:
            self.log.append((ch, "越界"))
            return 0
        src = glyph_bytes(ch)
        off = tile * 32
        for i in range(COPY):
            b = src[i]
            lo = b & 0x0F
            hi = b >> 4
            self.vram[off + i] = ((self.fg if hi else self.bg) << 4) | \
                                 (self.fg if lo else self.bg)
        row, col = self.cur_y, self.cur_tile_x
        self.tilemap.append((row, col, tile, self.pal))
        self.tilemap.append((row + 1, col, tile + 1, self.pal))
        self.cur_tile_x += 1
        self.log.append((ch, "tile=%d(pool=%d slot=%d)" % (tile, pool, slot)))
        return 1

# ---------------- 渲染 ----------------
def render(eng, cols, rows, zoom=8, bgcol=(255, 255, 255), inkcol=(33, 132, 255)):
    W, H = cols * 8, rows * 8
    img = np.full((H, W, 3), 255, np.uint8)
    m = {}
    for row, col, tile, pal in eng.tilemap:
        m[(row, col)] = tile
    for (row, col), tile in m.items():
        for ty in range(8):
            for tx in range(8):
                byte = eng.vram[tile * 32 + ty * 4 + tx // 2]
                v = (byte >> 4) if (tx % 2) else (byte & 0x0F)
                x, y = col * 8 + tx, row * 8 + ty
                if 0 <= x < W and 0 <= y < H:
                    img[y, x] = inkcol if v == 15 else bgcol
    im = Image.fromarray(img).resize((W * zoom, H * zoom), Image.NEAREST)
    return im

def demo(text, tile_base, fg, bg, rows=4, cols=32, zoom=8, title=""):
    e = Engine(tile_base=tile_base, fg=fg, bg=bg)
    for ch in text:
        g = gid_of(ch)
        if g is None:
            e.log.append((ch, "charmap 无此字")); continue
        e.emit(g, ch)
    im = render(e, cols, rows, zoom)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, im.width - 1, 22], fill=(24, 24, 28))
    d.text((6, 6), "%s  TILE_BASE=%d fg=%d bg=%d  %s"
           % (title, tile_base, fg, bg, " ".join("%s:%s" % (c, s) for c, s in e.log)), \
           fill=(255, 220, 120))
    return im, e

CASES = [
    ("时间", 1, 15, 0, "A tb=1"),
    ("宝可航员梦领", 1, 15, 0, "B tb=1"),
    ("领航员时间返回继续", 1, 15, 0, "C tb=1 8字"),
    ("领航员时间返回继续", 10, 15, 0, "D tb=10"),
    ("领航员时间返回继续", 21, 15, 0, "E tb=21"),
    ("领航员时间返回继续", 1, 1, 15, "F 反色 fg=1 bg=15"),
]
ims = []
for t, tb, fg, bg, tag in CASES:
    im, e = demo(t, tb, fg, bg, title=tag)
    ims.append(im)
    print("[%s] %s" % (tag, e.log))

W = max(i.width for i in ims)
H = sum(i.height for i in ims)
out = Image.new("RGB", (W, H), (16, 16, 20))
y = 0
for i in ims:
    out.paste(i, (0, y)); y += i.height
p = r"C:\code\GBA-Rom-Translator\.tmp\an\sim_engine.png"
out.save(p)
print("saved", p, out.size)
