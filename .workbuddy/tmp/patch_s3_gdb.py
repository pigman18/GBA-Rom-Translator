# -*- coding: utf-8 -*-
"""gdb_patcher 同步 v10/S3：
   ① ⑤ 已被劫持成 12B 桩 ⇒ 静态首字节校验 0004 → 10B5；
   ② frame 埋点输出补一行「v10 发号器状态」（框实际落点 / 文字起点 / 上限）。
"""
import io

P = 'src/util/gdb_patcher.py'
s = io.open(P, encoding='utf-8', newline='').read().replace('\r\n', '\n')
n = 0

# ---- 1) 插入 _v10_frame_state 定义（放在 _UI_PROBE_SPEC 之前）----
anchor = '_UI_PROBE_SPEC: dict[str, dict[str, Any]] = {'
fn = '''# ---- v10 / S3（2026-09-11）：框号发号器状态（win_alloc.c）------------------
# ⑤ `TextWindow_SetBaseTileNum` 被接管后，它的 r0（官方入参）**不再是生效的号**；
# 真正生效的是它写进 `sTextWindowBaseTileNum`(0x03000514) 的值 = 发号器给的 C。
# 本函数把发号器自身的账读出来，与槽值互为交叉验证。
_V10_FRAME_MAGIC     = 0x0203FF66
_V10_FRAME_CALLS     = 0x0203FF6A
_V10_FRAME_HI        = 0x0203FF6C
_V10_FRAME_TEXT      = 0x0203FF6E
_V10_FRAME_MAGIC_VAL = 0x5A10C0DE


def _v10_frame_state(gdb, span: int) -> str:
    """发号器状态一行。magic 不对 ⇒ 说明 ROM 还是 S3 之前的版本。"""
    raw = _read_mem(gdb, _V10_FRAME_MAGIC, 10)
    if len(raw) < 10:
        return ""
    mg = int.from_bytes(raw[0:4], "little")
    if mg != _V10_FRAME_MAGIC_VAL:
        return (f"  · v10 发号器未初始化（magic=0x{mg:08X} ≠ "
                f"0x{_V10_FRAME_MAGIC_VAL:08X}）⇒ 跑的不是 S3 之后的 ROM")
    calls = int.from_bytes(raw[4:6], "little")
    hi    = int.from_bytes(raw[6:8], "little")
    text  = int.from_bytes(raw[8:10], "little")
    box_i = (text - span) if text else 0
    return (f"  · v10 发号器：本场景第 {calls} 次发框 ⇒ 框 [{box_i}, {text}) = {span} tile，"
            f"文字起点 {text}，本窗上限 {hi}")


'''
assert s.count(anchor) == 1, 'anchor=%d' % s.count(anchor)
s = s.replace(anchor, fn + anchor, 1)
n += 1

# ---- 2) ⑤ 静态校验改桩首字节 + role 说明 ----
old2 = '''    "ChsAllocFrame9": dict(
        pc=0x08062080, verify="0004", kind="frame", base="r0", span=9,
        cursor=0x03000514, role="⑤ 标准框基址 → [base,base+9)"),'''
new2 = '''    # v10/S3（2026-09-11）：此函数已被 12B 桩劫持（push{r4,lr}+ldr/bx+pool）
    # ⇒ 首字节由 00 04 变为 10 B5（b510）。断点仍在原地址；r0 = 官方入参（**已弃用**），
    # 生效的号是它写进 0x03000514 的值（见下方「v10 发号器」行）。
    "ChsAllocFrame9": dict(
        pc=0x08062080, verify="10B5", kind="frame", base="r0", span=9,
        cursor=0x03000514, role="⑤ 标准框基址（v10 已接管，号来自 win_alloc 发号器）"),'''
assert s.count(old2) == 1, 'old2=%d' % s.count(old2)
s = s.replace(old2, new2, 1)
n += 1

# ---- 3) frame 输出补发号器状态 ----
old3 = '''        lines.append(f"  ⇒ 官方占用 = [{base}, {base + span}) = {span} tile"
                     f"（槽 {_UI_CURSOR_NAMES.get(cslot, hex(cslot))} 当前={cur}，本调用后应≈{base}）")'''
new3 = '''        lines.append(f"  ⇒ 官方入参 base={base}（v10 下已弃用），"
                     f"槽 {_UI_CURSOR_NAMES.get(cslot, hex(cslot))} 当前={cur}"
                     f"，本调用后应 = 发号器给的号")
        _v10 = _v10_frame_state(gdb, span)
        if _v10:
            lines.append(_v10)'''
assert s.count(old3) == 1, 'old3=%d' % s.count(old3)
s = s.replace(old3, new3, 1)
n += 1

io.open(P, 'w', encoding='utf-8', newline='\r\n').write(s)
print('替换成功 %d/3' % n)
