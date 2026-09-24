# -*- coding: utf-8 -*-
"""单块调试：定位 verify_planA 的差异来源"""
import importlib.util, sys
ROOT = r'C:\code\GBA-Rom-Translator'
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

spec = importlib.util.spec_from_file_location('pa', ROOT + r'\scripts\verify_planA.py')
pa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pa)

idx = pa.parse_bdf(ROOT + r'\fonts\default\Normal.bdf')
text = '\u8bbe\u7f6e\u6587\u5b57'   # 设置文字

blocks = [(2, 1, text)]
exp = pa.expected_image(idx, blocks)

for name, sch in (('P', pa.SchemeP()), ('S', pa.SchemeS()), ('A', pa.SchemeA(cap=192))):
    sc = pa.Screen()
    glyphs = [(ord(c), pa.chs_cell_from_1bpp(pa.pack_1bpp(idx[ord(c)]), 11, 11, 2))
              for c in text]
    pa.draw_block(sc, sch, {'col': 2, 'row': 1, 'glyphs': glyphs})
    ren = sc.render()
    d = [(x, y) for y in range(pa.SCR_H) for x in range(pa.SCR_W) if exp[y][x] != ren[y][x]]
    print('=== %s  差异 %d px' % (name, len(d)))
    if d:
        xs = [p[0] for p in d]; ys = [p[1] for p in d]
        print('   x 范围 %d..%d   y 范围 %d..%d' % (min(xs), max(xs), min(ys), max(ys)))
        # 按行统计
        from collections import Counter
        rc = Counter(p[1] for p in d)
        print('   按行:', sorted(rc.items())[:20])
        # 只看第 8..24 行（本块所在）
        inblock = [p for p in d if 8 <= p[1] < 24]
        print('   块内差异 %d px，前 24 个:' % len(inblock), inblock[:24])
        print('   tilemap:', sorted(sc.tmap.items())[:14])
        print('   tiles 有数据的号:', sorted(t for t in sc.tiles if any(sc.tiles[t])))
    print()
