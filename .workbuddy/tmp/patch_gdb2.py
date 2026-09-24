# -*- coding: utf-8 -*-
"""修 gdb_patcher 收尾文案的统计口径：n_bg 应数「落到的 BG 层」，不是数 cnt_before 取值。"""
import io

P = 'src/util/gdb_patcher.py'
s = io.open(P, encoding='utf-8', newline='').read().replace('\r\n', '\n')

old = '''        n_bg = len({v[0] for v in seen})
        ctx.log(f"\\n[BGMAP] 全程记录到 {len(seen)} 个不同的 (模板,sb,模板cb,层cb,层) 组合"
                f"（覆盖 {n_bg} 个层）⇒ **层 2 定位确实执行过**。")'''
new = '''        bgs = sorted({int(k[4]) for k in seen if int(k[4]) < 4})
        bg_txt = ", ".join(_BG_NAMES[b] for b in bgs) if bgs else "—"
        ctx.log(f"\\n[BGMAP] 全程记录到 {len(seen)} 个不同的 (模板,sb,模板cb,层cb,层) 组合，"
                f"实际落到 {len(bgs)} 个 BG 层（{bg_txt}）⇒ **层 2 定位确实执行过**。")'''
assert s.count(old) == 1, 'count=%d' % s.count(old)
s = s.replace(old, new)

io.open(P, 'w', encoding='utf-8', newline='\r\n').write(s)
print('OK')
