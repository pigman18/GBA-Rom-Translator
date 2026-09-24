# -*- coding: utf-8 -*-
"""同步 gdb_patcher.py 的层 2 轨迹解析：
  16B 头 + 22×16B 条目；新增 bgNum / bg_by_sb / expect_cnt / is_en 字段与交叉验证判读。"""
import io

P = r'C:\code\GBA-Rom-Translator\src\util\gdb_patcher.py'
s = io.open(P, encoding='utf-8', newline='').read().replace('\r\n', '\n')

subs = []

# 1) 布局注释
subs.append((
r'''#  布局见 hook/include/bg_remap.h：16B 头 + 40×12B 条目 @ EWRAM 0x0203FC04
_BGMAP_TRACE_ADDR = 0x0203FC04
_BGMAP_MAGIC = 0x314D4742          # 'BGM1'
_BGMAP_HDR = 16
_BGMAP_ENT = 12
_BGMAP_MAX = 40''',
r'''#  布局见 hook/include/bg_remap.h：16B 头 + 22×16B 条目 @ EWRAM 0x0203FC04
_BGMAP_TRACE_ADDR = 0x0203FC04
_BGMAP_MAGIC = 0x314D4742          # 'BGM1'
_BGMAP_HDR = 16                    # 16B 头（magic/calls/matched/nomatch/cb_diff/n_ent/last_bg）
_BGMAP_ENT = 16
_BGMAP_MAX = 22'''
))

# 2) 期望表注释（定位依据已从 sb 改为 bgNum）
subs.append((
r'''_BGMAP_EXPECT = {                  # 设计 §2.3 实测：模板 → 它该落在哪一层
    # ⚠ 只放**本场景稳定**的期望：同一个 sb 在不同时刻可能被配到不同层
    #   （实测 sb=15 出现过 BG0/BG2/BG3、sb=30 出现过 BG0/BG3）⇒ 其余不列，
    #   否则会把「层跟着模板动态切换」误判成「定位规则错」。''',
r'''_BGMAP_EXPECT = {                  # 模板 → 它该落在哪一层（依据 = 模板自带 bgNum，非 sb）
    # 🔴 2026-09-11 口径修正：定位依据由「模板 screenBase」改为**模板第 0 字节 bgNum**
    #   （照抄美版 UpdateBGRegs）。⇒ 期望是**模板的确定函数**，不再受"同一 sb 跨时刻变层"影响。
    #   ⚠ 只放**本场景稳定**的期望（领航员两个窗口）。'''
))

# 3) 条目解析
subs.append((
r'''        ents.append({
            "i": i,
            "tpl": int.from_bytes(raw[o:o + 4], "little"),
            "sb": raw[o + 4], "tpl_cb": raw[o + 5],
            "layer_cb": raw[o + 6], "bg": raw[o + 7],
            "before": int.from_bytes(raw[o + 8:o + 10], "little"),
            "after": int.from_bytes(raw[o + 10:o + 12], "little"),
        })''',
r'''        ents.append({
            "i": i,
            "tpl": int.from_bytes(raw[o:o + 4], "little"),
            "before": int.from_bytes(raw[o + 4:o + 6], "little"),
            "after": int.from_bytes(raw[o + 6:o + 8], "little"),
            "expect": int.from_bytes(raw[o + 8:o + 10], "little"),
            "sb": raw[o + 10], "tpl_cb": raw[o + 11],
            "bg": raw[o + 12], "bg_by_sb": raw[o + 13],
            "layer_cb": raw[o + 14], "is_en": raw[o + 15],
        })'''
))

# 4) 单条渲染
subs.append((
r'''def _bgmap_ent_line(e: dict) -> str:
    """单条轨迹 → 一行判读。"""
    if e["bg"] >= 4:
        return (f"tpl=0x{e['tpl']:08X} sb={e['sb']:>2}(0x{e['sb']:02X}) 模板cb={e['tpl_cb']}"
                " ⇒ 🔴 无同 screenBase 的 BG 层（未命中）")
    okcb = ("✅cb一致" if e["layer_cb"] == e["tpl_cb"]
            else f"⚠cb差(模板{e['tpl_cb']}≠层{e['layer_cb']})")
    zr = "" if e["before"] == e["after"] else "  🔴写后变了！"
    return (f"tpl=0x{e['tpl']:08X} sb={e['sb']:>2}(0x{e['sb']:02X}) 模板cb={e['tpl_cb']}"
            f" ⇒ 命中 {_BG_NAMES[e['bg']]} (层cb={e['layer_cb']})"
            f" CNT 0x{e['before']:04X}→0x{e['after']:04X}  {okcb}{zr}")''',
r'''def _bgmap_ent_line(e: dict) -> str:
    """单条轨迹 → 一行判读（bgNum 定位 + 两条交叉验证线索）。"""
    if e["bg"] >= 4:
        return (f"tpl=0x{e['tpl']:08X} sb={e['sb']:>2}(0x{e['sb']:02X}) 模板cb={e['tpl_cb']}"
                " ⇒ 🔴 bgNum 非法(>3)：模板布局假设错？")
    # 线索①：模板 bgNum 定位 vs 按 sb 扫描
    if e["bg_by_sb"] == 0xFF:
        xsb = "sb扫描:无同sb层"
    elif e["bg_by_sb"] == e["bg"]:
        xsb = "✅bgNum=sb扫描"
    else:
        xsb = f"⚠bgNum→BG{e['bg']}≠sb扫描→BG{e['bg_by_sb']}"
    okcb = ("✅cb一致" if e["layer_cb"] == e["tpl_cb"]
            else f"⚠cb差(模板{e['tpl_cb']}≠层{e['layer_cb']})")
    zr = "" if e["before"] == e["after"] else "  🔴写后变了！"
    en = "" if e["is_en"] else "  ⚠该层未使能"
    # 线索②：照抄 UpdateBGRegs 完整公式会不会改变现值（S3 风险预判）
    exp = "" if e["expect"] == e["before"] else f"  ⚠UBR会写0x{e['expect']:04X}(≠现值)"
    return (f"tpl=0x{e['tpl']:08X} bgNum={e['bg']}({_BG_NAMES[e['bg']]}) sb={e['sb']:>2}"
            f" 模板cb={e['tpl_cb']} ⇒ {_BG_NAMES[e['bg']]}(层cb={e['layer_cb']})"
            f" CNT 0x{e['before']:04X}→0x{e['after']:04X}  {xsb} {okcb}{zr}{en}{exp}")'''
))

# 5) tick 的键与值
subs.append((
r'''    for e in ents:
        key = (e["tpl"], e["sb"], e["tpl_cb"], e["layer_cb"], e["bg"])
        val = (e["before"], e["after"])
        if seen.get(key) == val:
            continue
        seen[key] = val
        ctx.log("  [BGMAP+] " + _bgmap_ent_line(e))''',
r'''    for e in ents:
        key = (e["tpl"], e["sb"], e["tpl_cb"], e["layer_cb"], e["bg"], e["bg_by_sb"])
        val = (e["before"], e["after"], e["expect"])
        if seen.get(key) == val:
            continue
        seen[key] = val
        ctx.log("  [BGMAP+] " + _bgmap_ent_line(e))'''
))

# 6) 结算判读段
subs.append((
r'''    ctx.log("  ---- 对照设计 §2.3 的期望 ----")
    exp_fail = 0
    for tpl, (want_bg, want_name, want_sb, label) in _BGMAP_EXPECT.items():
        got = seen.get(tpl)
        if got is None:
            ctx.log(f"  · 0x{tpl:08X}（{label}）期望 {want_name}(sb{want_sb})：本次未出现")
        elif got == want_bg:
            ctx.log(f"  ✅ 0x{tpl:08X}（{label}）→ {want_name}(sb{want_sb}) 与期望一致")
        else:
            exp_fail += 1
            ctx.log(f"  🔴 0x{tpl:08X}（{label}）→ BG{got}，期望 {want_name}(sb{want_sb})"
                    " ⇒ 定位规则错，S2 不通过")

    if matched == 0:
        ctx.log("  判读：🔴 一次都没命中 ⇒ 定位没生效，别往下走 S3。")
    elif exp_fail:
        ctx.log(f"  判读：🔴 {exp_fail} 个已知模板落到了**错误的层** ⇒ 定位规则错，S2 不通过"
                "（先别改 charBase）。")
    elif cb_diff:
        ctx.log(f"  判读：✅ 定位生效；⚠ 其中 {cb_diff} 条「层cb ≠ 模板cb」"
                "—— 该窗口的层 cb 与模板声明不符，**这批窗口就是 S3 的工单**。")
    else:
        ctx.log("  判读：✅ 定位生效，且层 cb 与模板 cb 全部一致"
                "（＝官方已按模板配好 (sb,cb)，我们的写回恒等 ⇒ 零回归）。")
    ctx.log("  ⚠ 别忘了：本步 BGxCNT 写回值与现值恒等 ⇒ 截图应与 S2 前**完全一致**；"
            "截图若有变化，就是「找错了层」。")''',
r'''    # ── 交叉验证：模板 bgNum 定位的层  vs  按 sb 扫描的层 ──────────────────────
    xsb_total = 0
    xsb_same = 0
    xsb_none = 0
    xsb_bad = []
    exp_diff = 0
    for e in ents:
        if e["bg"] >= 4:
            continue
        if e["bg_by_sb"] == 0xFF:
            xsb_none += 1
        else:
            xsb_total += 1
            if e["bg_by_sb"] == e["bg"]:
                xsb_same += 1
            else:
                xsb_bad.append(e)
        if e["expect"] != e["before"]:
            exp_diff += 1
    ctx.log("  ---- 交叉验证：模板 bgNum 定位  vs  按 screenBase 扫描 ----")
    ctx.log(f"  · 可比 {xsb_total} 条 / 同层 {xsb_same} / sb 扫不到层 {xsb_none}"
            f" / 不一致 {len(xsb_bad)}")
    for e in xsb_bad[:6]:
        ctx.log(f"    ⚠ tpl=0x{e['tpl']:08X} sb={e['sb']}：bgNum→BG{e['bg']}"
                f" 但 sb 扫描→BG{e['bg_by_sb']}")
    ctx.log(f"  ---- 照抄 UpdateBGRegs 完整公式**会改变现值**的条目：{exp_diff} / {len(ents)}"
            "（= S3 的风险面；>0 说明模板 priority/cb 与层现值不完全一致）")

    ctx.log("  ---- 对照期望（依据 = 模板自带 bgNum）----")
    exp_fail = 0
    for tpl, (want_bg, want_name, want_sb, label) in _BGMAP_EXPECT.items():
        got = seen.get(tpl)
        if got is None:
            ctx.log(f"  · 0x{tpl:08X}（{label}）期望 {want_name}(sb{want_sb})：本次未出现")
        elif got == want_bg:
            ctx.log(f"  ✅ 0x{tpl:08X}（{label}）→ {want_name}(sb{want_sb}) 与期望一致")
        else:
            exp_fail += 1
            ctx.log(f"  🔴 0x{tpl:08X}（{label}）→ BG{got}，期望 {want_name}(sb{want_sb})"
                    " ⇒ 定位规则错，S2 不通过")

    if matched == 0:
        ctx.log("  判读：🔴 一次都没命中 ⇒ 定位没生效，别往下走 S3。")
    elif exp_fail:
        ctx.log(f"  判读：🔴 {exp_fail} 个已知模板落到了**错误的层** ⇒ 定位规则错，S2 不通过"
                "（先别改 charBase）。")
    elif xsb_bad:
        ctx.log(f"  判读：⚠ 定位生效，但有 {len(xsb_bad)} 条「bgNum 定位 ≠ sb 扫描」"
                "—— 说明层的 sb 不总是等于模板声明的 sb；**以 bgNum 为准**（那是官方原语）。")
    elif cb_diff:
        ctx.log(f"  判读：✅ 定位生效；⚠ 其中 {cb_diff} 条「层cb ≠ 模板cb」"
                "—— 该窗口的层 cb 与模板声明不符，**这批窗口就是 S3 的工单**。")
    else:
        ctx.log("  判读：✅ 定位生效，且层 cb 与模板 cb 全部一致"
                "（＝官方已按模板配好 (sb,cb)，我们的写回恒等 ⇒ 零回归）。")
    ctx.log("  ⚠ 别忘了：本步 BGxCNT 写回值与现值恒等 ⇒ 截图应与 S2 前**完全一致**；"
            "截图若有变化，就是「找错了层」。")'''
))

ok = 0
for i, (o, n) in enumerate(subs, 1):
    c = s.count(o)
    if c != 1:
        print('[%d] FAIL count=%d  %s' % (i, c, o.splitlines()[0][:70]))
        continue
    s = s.replace(o, n, 1)
    ok += 1
    print('[%d] OK' % i)

print('---- %d/%d applied ----' % (ok, len(subs)))
if ok == len(subs):
    io.open(P, 'w', encoding='utf-8', newline='').write(s.replace('\n', '\r\n'))
    print('WROTE')
else:
    print('NOT WRITTEN')
