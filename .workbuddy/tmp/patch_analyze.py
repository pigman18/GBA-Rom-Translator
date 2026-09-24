# -*- coding: utf-8 -*-
"""同步 scripts/analyze_ui_takeover.py 的 S2 段：适配新轨迹行格式（bgNum + 交叉验证）。
自动保持原文件的换行风格。"""
import re

P = r'C:\code\GBA-Rom-Translator\scripts\analyze_ui_takeover.py'
raw_b = open(P, 'rb').read()
crlf = raw_b.count(b'\r\n') > 0
s = raw_b.decode('utf-8').replace('\r\n', '\n')

OLD = '''    # ---------- S2：层 2（bg_remap） ----------
    head("S2) 层 2：模板 screenBase → BG 层 定位判读")
    fp = re.search(r"ROM 指纹：(.*)", raw)
    if not fp:
        print("  ROM 指纹 : **未见指纹行** ⇒ 工具早于 2026-09-11 的 S2 增强，请用新版重采")
    else:
        v = fp.group(1).strip()
        mark = "🔴" if "原版 ROM" in v else ("✅" if "注入版" in v else "·")
        print(f"  {mark} ROM 指纹: {v}")
    if "[BGMAP!]" in raw:
        print("  🔴 轨迹全程未写入 ⇒ bg_remap 从未被调用（或跑了原版 ROM）")
    elif "[BGMAP…]" in raw:
        print("  · 早期读到过「轨迹尚未初始化」——**正常**（进文本窗口前 magic 必为 0）")

    tick = re.findall(r"\\[BGMAP\\+\\] (.*)", raw)
    dump = re.findall(r"^ {2}· (tpl=0x[0-9A-Fa-f]+ .*)$", raw, re.M)
    rows = tick or dump
    src = "增量 [BGMAP+]" if tick else ("结算 [BGMAP]" if dump else "无")
    ent_re = re.compile(
        r"tpl=(0x[0-9A-Fa-f]+) sb=(\\d+)\\(0x([0-9A-Fa-f]{2})\\) 模板cb=(\\d+)"
        r" ⇒ 命中 (BG\\d) \\(层cb=(\\d+)\\) CNT 0x([0-9A-Fa-f]{4})→0x([0-9A-Fa-f]{4})")
    seen: dict[int, tuple] = {}
    nomatch = []
    for ln in rows:
        m = ent_re.search(ln)
        if m:
            seen[int(m.group(1), 16)] = (int(m.group(2)), m.group(5),
                                        int(m.group(6)), m.group(7), m.group(8))
        elif "未命中" in ln:
            nomatch.append(ln)
    if not rows:
        print("  ⚠ 轨迹一行都没有 ⇒ 本次日志不是新版工具采的（或 ROM 没跑到 UI）")
        print("     新版会在跑的过程中就打 [BGMAP+]（不依赖 Ctrl-C），并读实机 BGxCNT。")
    else:
        print(f"  轨迹来源 {src}：命中 {len(seen)} 个模板，未命中 {len(nomatch)} 条")
        print(f"  {'模板':<12}{'sb':<4}{'命中层':<7}{'层cb':<6}{'CNT 前→后':<16}cb 判定")
        for tpl, (sb, bg, lcb, b, a) in sorted(seen.items()):
            tcb = {"0x081BB7B4": 0, "0x081BB7E4": 0, "0x081BB43C": 1,
                   "0x081BB46C": 2, "0x081BB5BC": 2}.get(f"0x{tpl:08X}", None)
            ok = ("✅cb一致" if tcb == lcb else f"⚠cb差(模板{tcb}≠层{lcb})") if tcb is not None else "?"
            zero = "✅恒等" if b == a else "🔴写后变了"
            print(f"  0x{tpl:08X}  {sb:<4}{bg:<7}{lcb:<6}{b}→{a}    {ok} {zero}")
        print("  ⇒ 零回归硬要求：每行 CNT 前→后 **必须恒等**（S2 只重写 screenBase）。")
        for want, (wbg, wname, wsb, label) in {
                0x081BB7B4: (0, "BG0", 31, "领航员 训练家名/列表"),
                0x081BB7E4: (3, "BG3", 30, "领航员 路线名")}.items():
            got = seen.get(want)
            if got is None:
                print(f"  · 0x{want:08X}（{label}）期望 {wname}(sb{wsb})：本次未出现")
            elif got[1] == wname:
                print(f"  ✅ 0x{want:08X}（{label}）→ {wname}(sb{wsb}) 与期望一致")
            else:
                print(f"  🔴 0x{want:08X}（{label}）→ {got[1]}，期望 {wname}(sb{wsb}) ⇒ 定位规则错")
'''

NEW = '''    # ---------- S2：层 2（bg_remap = 复刻美版 UpdateBGRegs） ----------
    head("S2) 层 2：模板 bgNum → BG 层 定位判读（复刻美版 UpdateBGRegs）")
    fp = re.search(r"ROM 指纹：(.*)", raw)
    if not fp:
        print("  ROM 指纹 : **未见指纹行** ⇒ 工具早于 2026-09-11 的 S2 增强，请用新版重采")
    else:
        v = fp.group(1).strip()
        mark = "🔴" if "原版 ROM" in v else ("✅" if "注入版" in v else "·")
        print(f"  {mark} ROM 指纹: {v}")
    if "[BGMAP!]" in raw:
        print("  🔴 轨迹全程未写入 ⇒ bg_remap 从未被调用（或跑了原版 ROM）")
    elif "[BGMAP…]" in raw:
        print("  · 早期读到过「轨迹尚未初始化」——**正常**（进文本窗口前 magic 必为 0）")

    tick = re.findall(r"\\[BGMAP\\+\\] (.*)", raw)
    dump = re.findall(r"^ {2}· (tpl=0x[0-9A-Fa-f]+ .*)$", raw, re.M)
    rows = tick or dump
    src = "增量 [BGMAP+]" if tick else ("结算 [BGMAP]" if dump else "无")
    ent_re = re.compile(
        r"tpl=(0x[0-9A-Fa-f]+) bgNum=(\\d+)\\((BG\\d)\\) sb=\\s*(\\d+) 模板cb=(\\d+)"
        r" ⇒ (BG\\d)\\(层cb=(\\d+)\\) CNT 0x([0-9A-Fa-f]{4})→0x([0-9A-Fa-f]{4})")
    seen: dict[int, dict] = {}
    nomatch = []
    xsb_same = xsb_diff = xsb_none = 0
    ubr_diff = []
    for ln in rows:
        m = ent_re.search(ln)
        if not m:
            if "bgNum 非法" in ln or "未命中" in ln:
                nomatch.append(ln)
            continue
        tpl = int(m.group(1), 16)
        if "✅bgNum=sb扫描" in ln:
            xs = "same"; xsb_same += 1
        elif "⚠bgNum→" in ln:
            xs = "diff"; xsb_diff += 1
        elif "sb扫描:无同sb层" in ln:
            xs = "none"; xsb_none += 1
        else:
            xs = "?"
        if "⚠UBR会写" in ln:
            ubr_diff.append(ln)
        seen[tpl] = dict(bgnum=int(m.group(2)), bg=m.group(6), lcb=int(m.group(7)),
                         b=m.group(8), a=m.group(9), xs=xs, ln=ln)
    if not rows:
        print("  ⚠ 轨迹一行都没有 ⇒ 本次日志不是新版工具采的（或 ROM 没跑到 UI）")
        print("     新版会在跑的过程中就打 [BGMAP+]（不依赖 Ctrl-C），并读实机 BGxCNT。")
    else:
        print(f"  轨迹来源 {src}：命中 {len(seen)} 个模板，非法/未命中 {len(nomatch)} 条")
        print(f"  {'模板':<12}{'bgNum':<7}{'命中层':<7}{'层cb':<6}{'CNT 前→后':<18}零回归 / cb")
        for tpl, d in sorted(seen.items()):
            tcb = {"0x081BB7B4": 0, "0x081BB7E4": 0, "0x081BB43C": 1,
                   "0x081BB46C": 2, "0x081BB5BC": 2}.get(f"0x{tpl:08X}", None)
            ok = ("✅cb一致" if tcb == d["lcb"] else f"⚠cb差(模板{tcb}≠层{d['lcb']})") if tcb is not None else "?"
            zero = "✅恒等" if d["b"] == d["a"] else "🔴写后变了"
            print(f"  0x{tpl:08X}  {d['bgnum']:<7}{d['bg']:<7}{d['lcb']:<6}"
                  f"{d['b']}→{d['a']}  {zero} {ok}")
        print("  ⇒ 零回归硬要求：每行 CNT 前→后 **必须恒等**（S2 只重写 screenBase 位）。")
        print(f"  ---- 交叉验证（模板 bgNum 定位 vs 按 sb 扫描）：同层 {xsb_same} / "
              f"不同层 {xsb_diff} / sb 扫不到 {xsb_none} ----")
        for tpl, d in sorted(seen.items()):
            if d["xs"] == "diff":
                print(f"    ⚠ 0x{tpl:08X} bgNum={d['bgnum']} 命中 {d['bg']}，"
                      f"但按 sb 扫描落在别的层")
        if xsb_diff:
            print("    ⇒ 层的 sb ≠ 模板 sb —— **以 bgNum 为准**（官方原语就是读模板 bgNum）。")
        print(f"  ---- 照抄 UpdateBGRegs 完整公式会改变现值的条目：{len(ubr_diff)}"
              "（= S3 风险面；>0 说明模板 priority/cb 与层现值不完全一致）----")
        for want, (wbg, wname, wsb, label) in {
                0x081BB7B4: (0, "BG0", 31, "领航员 训练家名/列表"),
                0x081BB7E4: (3, "BG3", 30, "领航员 路线名")}.items():
            got = seen.get(want)
            if got is None:
                print(f"  · 0x{want:08X}（{label}）期望 {wname}(sb{wsb})：本次未出现")
            elif got["bg"] == wname:
                print(f"  ✅ 0x{want:08X}（{label}）→ {wname}(sb{wsb}) 与期望一致")
            else:
                print(f"  🔴 0x{want:08X}（{label}）→ {got['bg']}，期望 {wname}(sb{wsb}) ⇒ 定位规则错")
'''

c = s.count(OLD)
print('match =', c)
if c == 1:
    s = s.replace(OLD, NEW, 1)
    out = s.replace('\n', '\r\n') if crlf else s
    open(P, 'wb').write(out.encode('utf-8'))
    print('WROTE (crlf=%s)' % crlf)
else:
    print('NOT WRITTEN')
