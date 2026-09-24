#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sim_render.py —— engine.c 落字逻辑的离线渲染模拟器（视觉验收工具）

忠实复刻 configs/POKEMON_RUBY_AXVJ00/hook/src/text/engine.c 的 engine_emit_glyph：

    chs8_hash(gid)  = (gid * 19173961) >> 32，修正后 == gid % 224   （定点倒数，避 __aeabi_uidivmod）
    chs8_slot(gid)  粘性「gid→槽」直接映射 + 线性探测（上限 8 步）；表满 224 ⇒ 拒发
    pool            = max(TILE_BASE + 512, 521)，并受 (1024 - 2*224) 夹逼
    gp              = (pool - TILE_BASE + 1) >> 1
    tile            = TILE_BASE + 2*(gp + slot)
    写砖            dst[i] = ((hi ? fg : bg) << 4) | (lo ? fg : bg)   i ∈ [0,64)  ← 上砖+下砖
    写 map          tilemap[cell] = tile | pal<<12；tilemap[cell+32] = tile+1 | pal<<12
    游标            win[0x1B] += 1

用途：
  1) **验证落字数学**：渲染出来的汉字应当清晰、8px 步进、墨在 cell 行 2..12（11 行）。
     若这里就不正常 ⇒ 是 engine.c / charmap / 字库的 bug（纯数学）。
     若这里正常但实机不正常 ⇒ 是运行时环境问题（最典型：引擎 GlyphPrefetchWorker
     每帧回灌日文字模，覆盖砖区间 [TILE_BASE, TILE_BASE+512)）。
  2) **规划池位**：--tilebase 扫一遍，看首砖是否落进预取区间（--check-pool）。

用法：
  python scripts/sim_render.py "领航员时间返回继续"                 # 渲染 + 打印每个字的 tile
  python scripts/sim_render.py "宝可梦" --tilebase 20 --zoom 16
  python scripts/sim_render.py --check-pool                        # 只打印 tb 0..128 的池位表
  python scripts/sim_render.py "测试文本" --out out/sim.png
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BDF = ROOT / "fonts/default/Middle.bdf"
CHARMAP = ROOT / "configs/POKEMON_RUBY_AXVJ00/charmap.txt"

SLOT_N = 224
GUARD = 521
ENGINE_CACHE = 512          # GlyphPrefetchWorker 覆盖 [TILE_BASE, TILE_BASE + 512)
COPY_BYTES = 64
GLYPH_MAX = 7168
TILE_MAX = 1024             # charBase 的 10 bit 砖号上限


# ---------------- 字库 ----------------
def load_bdf(path: Path) -> dict[int, list[int]]:
    text = path.read_text("utf-8", errors="replace")
    g: dict[int, list[int]] = {}
    for m in re.finditer(r"^STARTCHAR.*?^ENCODING\s+(\d+).*?^BITMAP\s*$(.*?)^ENDCHAR",
                         text, re.M | re.S):
        g[int(m.group(1))] = [int(l.strip(), 16)
                              for l in m.group(2).strip().splitlines() if l.strip()]
    return g


def glyph_4bpp(gb: dict[int, list[int]], ch: str) -> bytes:
    """BDF 字形 → 64 字节 4bpp（上砖 32B + 下砖 32B），与 Middle 库 bin 布局一致。"""
    r = gb.get(ord(ch))
    out = bytearray()
    if r is None:
        return bytes(COPY_BYTES)
    for y in range(16):
        H = (r[y] >> 8) & 0xFF if y < len(r) else 0
        for i in range(4):
            lo = 0xF if (H >> (7 - 2 * i)) & 1 else 0
            hi = 0xF if (H >> (7 - 2 * i - 1)) & 1 else 0
            out.append((hi << 4) | lo)
    return bytes(out)


# ---------------- charmap → gid ----------------
def load_pcs(path: Path) -> dict[int, str]:
    d: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            try:
                d[int(k, 16)] = v
            except ValueError:
                pass
    return d


def pack_glyph_index(lead: int, trail: int) -> int:
    """engine.c:pack_glyph_index —— PCS 双字节 → gid（跳过无效 lead 0/6/0x1B/0x1F…）。"""
    idx = lead
    if idx >= 6:
        if idx >= 0x1B:
            idx -= 1
        idx -= 1
    idx -= 1
    return ((idx & 0xFF) << 8) | (trail & 0xFF)


def gid_of(pcs: dict[int, str], ch: str) -> int | None:
    for code, s in pcs.items():
        if s == ch:
            return pack_glyph_index(code >> 8, code & 0xFF)
    return None


# ---------------- 引擎 ----------------
def chs8_hash(gid: int) -> int:
    q = (gid * 19173961) >> 32
    k = gid - q * SLOT_N
    return k - SLOT_N if k >= SLOT_N else k


class Engine:
    def __init__(self, tile_base: int = 1, fg: int = 15, bg: int = 0, pal: int = 0):
        self.tb, self.fg, self.bg, self.pal = tile_base, fg, bg, pal
        self.tag = [0] * SLOT_N
        self.cnt = 0
        self.cur_col = self.cur_row = 0
        self.vram = bytearray(TILE_MAX * 32)
        self.tilemap: list[tuple[int, int, int, int]] = []
        self.log: list[str] = []
        # 池位（与 engine.c 同式）
        p = tile_base + ENGINE_CACHE
        if p < GUARD:
            p = GUARD
        if p + 2 * SLOT_N > TILE_MAX:
            p = TILE_MAX - 2 * SLOT_N
        self.pool = p
        self.gp = ((p - tile_base + 1) >> 1) if p > tile_base else 0

    def slot_of(self, gid: int):
        k = chs8_hash(gid)
        want = gid + 1
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
            k = (k + 1) % SLOT_N
        return None

    def emit(self, gid: int, gb, ch: str = "?") -> int:
        if gid >= GLYPH_MAX:
            self.log.append("%s: gid 越界" % ch)
            return 0
        slot = self.slot_of(gid)
        if slot is None:
            self.log.append("%s: 表满拒发" % ch)
            return 0
        tile = self.tb + 2 * (self.gp + slot)
        if tile + 1 > TILE_MAX - 1:
            self.log.append("%s: 砖号越界" % ch)
            return 0
        src = glyph_4bpp(gb, ch)
        off = tile * 32
        for i in range(COPY_BYTES):
            b = src[i]
            self.vram[off + i] = (((self.fg if (b >> 4) else self.bg) << 4)
                                  | (self.fg if (b & 0x0F) else self.bg))
        self.tilemap.append((self.cur_row, self.cur_col, tile, self.pal))
        self.tilemap.append((self.cur_row + 1, self.cur_col, tile + 1, self.pal))
        self.cur_col += 1
        self.log.append("%s -> gid=%d slot=%d tile=%d" % (ch, gid, slot, tile))
        return 1


def render(eng: Engine, cols: int, rows: int, zoom: int = 8):
    W, H = cols * 8, rows * 8
    img = np.full((H, W, 3), 255, np.uint8)
    for row, col, tile, _pal in set(eng.tilemap):
        for ty in range(8):
            for tx in range(8):
                byte = eng.vram[tile * 32 + ty * 4 + tx // 2]
                v = (byte >> 4) if (tx % 2) else (byte & 0x0F)
                x, y = col * 8 + tx, row * 8 + ty
                if 0 <= x < W and 0 <= y < H:
                    img[y, x] = (33, 132, 255) if v == 15 else (255, 255, 255)
    return Image.fromarray(img).resize((W * zoom, H * zoom), Image.NEAREST)


def check_pool(tb_max: int = 128):
    print("%-6s %-8s %-12s %-10s" % ("tb", "pool", "首个槽的砖", "落在预取区间?"))
    for tb in range(0, tb_max + 1):
        e = Engine(tile_base=tb)
        t0 = e.tb + 2 * e.gp
        hit = t0 < tb + ENGINE_CACHE
        print("%-6d %-8d %-12d %-10s" % (tb, e.pool, t0, "★被覆盖" if hit else "ok"))


def main() -> int:
    ap = argparse.ArgumentParser(description="engine.c 落字离线渲染模拟器")
    ap.add_argument("text", nargs="?", default="领航员时间返回继续")
    ap.add_argument("--tilebase", type=int, default=1, help="win[0x16] TILE_BASE")
    ap.add_argument("--fg", type=int, default=15, help="win[0x0C] 墨色调色板号")
    ap.add_argument("--bg", type=int, default=0, help="win[0x0D] 底色调色板号")
    ap.add_argument("--pal", type=int, default=0, help="tilemap 高 4 位调色板")
    ap.add_argument("--zoom", type=int, default=8)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--check-pool", action="store_true", help="只打印池位表")
    args = ap.parse_args()

    if args.check_pool:
        check_pool()
        return 0

    gb = load_bdf(BDF)
    pcs = load_pcs(CHARMAP)
    eng = Engine(args.tilebase, args.fg, args.bg, args.pal)
    for ch in args.text:
        g = gid_of(pcs, ch)
        if g is None:
            print("  %s: charmap 里没有" % ch)
            continue
        eng.emit(g, gb, ch)

    print("TILE_BASE=%d  pool=%d  gp=%d" % (eng.tb, eng.pool, eng.gp))
    for line in eng.log:
        print("  " + line)

    cols = max(8, ((len(args.text) + 7) // 8 + 1) * 8)
    rows = 2 * ((len(args.text) + cols - 1) // cols + 1)
    im = render(eng, cols, rows, args.zoom)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, im.width, 18], fill=(24, 24, 28))
    d.text((4, 4), "tb=%d pool=%d fg=%d bg=%d  %s"
           % (eng.tb, eng.pool, args.fg, args.bg, args.text), fill=(255, 220, 120))
    out = args.out or (ROOT / "out" / "sim_render.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    print("saved %s  (%dx%d)" % (out, im.width, im.height))
    return 0


if __name__ == "__main__":
    sys.exit(main())
