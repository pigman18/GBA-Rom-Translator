# -*- coding: utf-8 -*-
"""修 analyze_ui_takeover.py：模板cb 不再用硬编码表（记账式），改为直接读日志字段。"""
import io, sys

P = 'scripts/analyze_ui_takeover.py'
s = io.open(P, encoding='utf-8', newline='').read()
s = s.replace('\r\n', '\n')          # 归一，避免 CRLF 不匹配
orig = s
n = 0

# --- 1) seen 里带上 tcb（正则 group(5) 本来就抓到了，只是没存） ---
old1 = '''        seen[tpl] = dict(bgnum=int(m.group(2)), bg=m.group(6), lcb=int(m.group(7)),
                         b=m.group(8), a=m.group(9), xs=xs, ln=ln)'''
new1 = '''        seen[tpl] = dict(bgnum=int(m.group(2)), bg=m.group(6), lcb=int(m.group(7)),
                         tcb=int(m.group(5)), b=m.group(8), a=m.group(9), xs=xs, ln=ln)'''
assert s.count(old1) == 1, ('old1 count=%d' % s.count(old1))
s = s.replace(old1, new1); n += 1

# --- 2) 去掉硬编码模板表，直接用日志里的模板cb ---
old2 = '''            tcb = {"0x081BB7B4": 0, "0x081BB7E4": 0, "0x081BB43C": 1,
                   "0x081BB46C": 2, "0x081BB5BC": 2}.get(f"0x{tpl:08X}", None)
            ok = ("✅cb一致" if tcb == d["lcb"] else f"⚠cb差(模板{tcb}≠层{d['lcb']})") if tcb is not None else "?"'''
new2 = '''            tcb = d["tcb"]   # 直接读日志（不再硬编码模板表 —— 记账式硬编码一律废弃）
            ok = "✅cb一致" if tcb == d["lcb"] else f"⚠cb差(模板{tcb}≠层{d['lcb']})"'''
assert s.count(old2) == 1, ('old2 count=%d' % s.count(old2))
s = s.replace(old2, new2); n += 1

io.open(P, 'w', encoding='utf-8', newline='\r\n').write(s)
print('替换成功 %d/2, 长度 %d -> %d' % (n, len(orig), len(s)))
