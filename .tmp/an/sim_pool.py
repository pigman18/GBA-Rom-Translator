# -*- coding: utf-8 -*-
"""可视化「预取覆盖区间」与「我方池位置」：旧代码(写死521) vs B(pool=max(tb+512,521))。
模拟 engine.c：tile = tb + 2*g, g = gp + slot, gp = (pool-tb+1)>>1
预取 worker 覆盖砖区间 = [tb, tb+512)  （用 win[0x16] 那把 global base）
"""
from PIL import Image, ImageDraw

def first_tile(pool, tb, slot=0):
    gp = (pool - tb + 1) >> 1 if pool > tb else 0
    g = gp + slot
    return tb + 2 * g

def pool_old(tb):   return 521
def pool_new(tb):
    p = tb + 512
    if p < 521: p = 521
    if p + 2 * 224 > 1024: p = 1024 - 2 * 224
    return p

W, H = 1240, 640
im = Image.new("RGB", (W, H), (22, 22, 26))
d = ImageDraw.Draw(im)

def bar(y, x0, x1, lo, hi, color, label, scale=0.9, h=26):
    X0 = 120 + int(lo * scale); X1 = 120 + int(hi * scale)
    d.rectangle([X0, y, X1, y + h], fill=color, outline=(240, 240, 240))
    d.text((X0 + 4, y + 6), label, fill=(20, 20, 20) if color[0] > 140 else (255, 255, 255))
    return X0, X1

d.text((12, 10), "区块占用示意（砖号 0..1024）—— 引擎预取覆盖 [TILE_BASE, TILE_BASE+512)", fill=(255, 220, 120))
d.text((12, 28), "我方池起点  pool = max(TILE_BASE+512, 521)；第一个槽的砖 = TILE_BASE + 2*gp", fill=(180, 200, 255))

cases = [(1, "TILE_BASE = 1  （模拟：tile 719，安全）"),
         (12, "TILE_BASE = 12 （旧代码：池起点 521 落在预取区间内！）"),
         (40, "TILE_BASE = 40 （旧代码：512 < 40+512=552 ⇒ 必然重叠）")]
yy = 60
for tb, title in cases:
    d.text((12, yy), title, fill=(255, 180, 120)); yy += 18
    # 预取区间
    bar(yy, 0, 0, tb, tb + 512, (90, 90, 105), "engine glyph cache [tb, tb+512)", scale=0.9)
    yy += 30
    # 旧
    t_old = first_tile(pool_old(tb), tb)
    hit_old = t_old < tb + 512
    bar(yy, 0, 0, pool_old(tb), pool_old(tb) + 448,
        (200, 60, 60) if hit_old else (60, 170, 90),
        "OLD pool=521  first tile=%d  %s" % (t_old, "被预取覆盖!" if hit_old else "OK"), scale=0.9, h=22)
    yy += 26
    # 新
    pn = pool_new(tb)
    t_new = first_tile(pn, tb)
    hit_new = t_new < tb + 512
    bar(yy, 0, 0, pn, pn + 448,
        (200, 60, 60) if hit_new else (60, 170, 90),
        "B   pool=%d  first tile=%d  %s" % (pn, t_new, "被预取覆盖!" if hit_new else "OK"), scale=0.9, h=22)
    yy += 46

# 刻度
d.line([120, yy + 4, 120 + 1024, yy + 4], fill=(200, 200, 200))
for t in range(0, 1025, 128):
    d.line([120 + t, yy + 4, 120 + t, yy + 12], fill=(200, 200, 200))
    d.text((120 + t - 12, yy + 14), str(t), fill=(200, 200, 200))

out = r"C:\code\GBA-Rom-Translator\.tmp\an\sim_pool.png"
im.save(out)
print("saved", out, im.size)
print("\n%-6s %-8s %-14s %-8s %s" % ("tb", "pool_old", "old first tile", "hit?", "pool_new(B) / first tile / hit?"))
for tb in (1, 8, 9, 12, 40, 100, 500):
    to = first_tile(pool_old(tb), tb)
    pn = pool_new(tb)
    tn = first_tile(pn, tb)
    print("%-6d %-8d %-14d %-8s %d / %d / %s"
          % (tb, pool_old(tb), to, "YES" if to < tb + 512 else "no",
             pn, tn, "YES" if tn < tb + 512 else "no"))
