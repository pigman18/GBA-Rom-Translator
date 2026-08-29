# -*- coding: utf-8 -*-
"""生成 tm1 混合模式（TM1_MODE_MIX）的汉字固定槽表。

产出两个文件（都在 configs/POKEMON_RUBY_AXVJ00/hook/src/text/）：
  chs_slots.inc      —— PTR 段（固定槽）用的汉字 → tile 映射
  chs_slots_sel.inc  —— 选中态（红字）镜像槽；当前 PTR 段=标签列不吃高亮，表为空

关键：**动态区优先，槽表去填剩下的缝**。
  MIX 模式下标签列走 PTR 固定槽、候选列走 DYN 动态分配，两者共享同一个
  charblock2([1,512))。行基址表（kOptRows）必须整段留给 DYN，槽表只能挤在
  剩余碎片里 —— 所以本脚本会先从 text_scene.c 读出 kOptRows 和分区占用，
  把它们标记为"禁区"，再给汉字分配槽。

约束（每个槽 4 个连续 tile：ptr_base+0..+3）
----
  1. 避开引用字形（kOptGlyphAvoid，各占 2 tile：t 与 t+1）
  2. 避开 DYN 行区（kOptRows[i] .. +行占用）
  3. tile < 512（charblock2）
槽与槽之间不需要连续，各自 4 连续即可。

用法（仓库根）：
  python scripts/gen_tm1_slots.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT_DIR = os.path.join(ROOT, "configs", "POKEMON_RUBY_AXVJ00", "hook", "src", "text")
SLOTS_INC = os.path.join(TEXT_DIR, "chs_slots.inc")
SEL_INC = os.path.join(TEXT_DIR, "chs_slots_sel.inc")
SCENE_C = os.path.join(TEXT_DIR, "text_scene.c")

TILE_MAX = 512

# 与 text_scene.c kOptGlyphAvoid 一致（各占 2 tile：t 与 t+1）
GLYPH_AVOID = [
    0x001, 0x021, 0x031, 0x06F, 0x077, 0x08B, 0x0FF,
    0x143, 0x145, 0x147, 0x149, 0x14B, 0x14D, 0x14F,
    0x151, 0x153, 0x159, 0x15D, 0x171, 0x18D, 0x199,
    0x1B7, 0x1BF, 0x1C3, 0x1DF, 0x1E1,
]


def parse_glyphs(path):
    """从现有 chs_slots.inc 读出汉字集合（只取 glyph，slot 会被重算）。"""
    txt = open(path, encoding="utf-8").read()
    pat = re.compile(r"\{\s*0x([0-9A-Fa-f]{4})u,\s*0x([0-9A-Fa-f]{4})u\s*\}")
    return [int(g, 16) for g, _s in pat.findall(txt)]


def parse_scene(path):
    """从 text_scene.c 读出：行基址表 kOptRows + DYN 分区的行内最大占用。"""
    txt = open(path, encoding="utf-8").read()

    m = re.search(r"kOptRows\s*\[\s*\d+\s*\]\s*=\s*\{(.*?)\}", txt, re.S)
    if not m:
        raise SystemExit("未找到 kOptRows，检查 text_scene.c")
    # 槽值有 3 位也有 4 位（0x033u / 0x08Du），不能写死位数
    rows = [int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{3,4})u", m.group(1))]
    if not rows:
        raise SystemExit("kOptRows 解析出 0 行，检查 text_scene.c 的写法")

    # kOptZones：{ cx_hi, STRATEGY, font, off, span }
    span = 0
    for zm in re.finditer(
            r"\{\s*(\d+|0x[0-9A-Fa-f]+)u,\s*TM1_ZONE_(\w+),\s*(\d+)u,"
            r"\s*(\d+)u,\s*(\d+)u\s*\}", txt):
        strat, _font, off, sp = zm.group(2), zm.group(3), int(zm.group(4)), int(zm.group(5))
        if strat == "DYN":
            span = max(span, off + sp)
    if span == 0:
        raise SystemExit("未解析到任何 DYN 分区，检查 kOptZones")
    return rows, span


def blocked_set(rows, row_span):
    b = set()
    for t in GLYPH_AVOID:
        b.add(t)
        b.add(t + 1)
    for r in rows:                      # DYN 行区整段保留
        b |= set(range(r, r + row_span))
    return b


def alloc(n, blocked):
    blocked = set(blocked)          # 副本：不要污染调用方的集合，否则自检必然误报
    out = []
    t = 1
    while len(out) < n and t + 4 <= TILE_MAX:
        w = {t + k for k in range(4)}
        if not (w & blocked):
            out.append(t)
            blocked |= w
            t += 4
        else:
            t += 1
    if len(out) < n:
        raise SystemExit("空间不足：只分配到 %d/%d 个槽（需 %d tile）"
                         % (len(out), n, n * 4))
    return out


def main():
    glyphs = parse_glyphs(SLOTS_INC)
    rows, row_span = parse_scene(SCENE_C)
    blocked = blocked_set(rows, row_span)

    print("汉字数        : %d" % len(glyphs))
    print("DYN 行基址    : %s，每行 %d tile" % (rows, row_span))
    print("DYN 占用      : %s" % ["[%d,%d)" % (r, r + row_span) for r in rows])

    slots = alloc(len(glyphs), blocked)

    # ---- 自检 ----
    for s in slots:
        w = {s + k for k in range(4)}
        assert not (w & blocked), "槽 %d 与禁区冲突" % s
        assert s + 4 <= TILE_MAX, "槽 %d 越界" % s
    print("PTR 槽        : %d 个，tile %d..%d（共 %d tile）"
          % (len(slots), min(slots), max(slots) + 3, len(slots) * 4))
    print("自检          : 无冲突、无越界")

    out = []
    out.append("/* 由 scripts/gen_tm1_slots.py 生成 —— 勿手改 */")
    out.append("/*")
    out.append(" * PTR 段（固定槽）的汉字 → tile 映射。每个汉字 4 个连续 tile：")
    out.append(" *   +0 左上 / +1 左下 / +2 右上 / +3 右下")
    out.append(" *")
    out.append(" * 分配约束（脚本自动保证，改配置后重跑即可）：")
    out.append(" *   1. 避开引用字形（各占 2 格）")
    out.append(" *   2. 避开 DYN 动态区（kOptRows 整段留给候选列，本表只能填缝）")
    out.append(" *   3. tile < 512")
    out.append(" * ⚠ 汉字集合来自 gdb 实测；改翻译（增删汉字）后必须重新采集并生成本表。")
    out.append(" */")
    out.append("static const struct { uint16_t glyph; uint16_t slot; } "
               "kOptChsSlots[%d] = {" % len(glyphs))
    for g, s in zip(glyphs, slots):
        out.append("    { 0x%04Xu, 0x%04Xu }," % (g, s))
    out.append("};")
    with open(SLOTS_INC, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("已写入 %s" % os.path.basename(SLOTS_INC))

    # 选中态表：当前 PTR 段（标签列）不吃高亮，清空以省 tile。
    # 若将来 PTR 段包含会高亮的文本，把 need_sel 改成 True 重新分配。
    need_sel = False
    if need_sel:
        sel = alloc(len(glyphs), blocked | {s + k for s in slots for k in range(4)})
    else:
        sel = []
    body = "".join("    { 0x%04Xu, 0x%04Xu },\n" % (g, s)
                   for g, s in zip(glyphs, sel))
    n_sel = max(len(sel), 1)
    if not sel:
        # 零长数组会有"空初始化列表"+ sizeof 除零问题，放一条永不命中的哨兵
        body = "    { 0xFFFFu, 0x0000u },   /* 哨兵：glyph 0xFFFF 永不命中 */\n"
    sel_txt = []
    sel_txt.append("/* 由 scripts/gen_tm1_slots.py 生成 —— 勿手改 */")
    sel_txt.append("/*")
    sel_txt.append(" * 选中态（红色）汉字槽。当前为**空表**，原因：")
    sel_txt.append(" *   PTR 段只用于标签列，而标签不吃高亮（DrawOptionMenuChoice_hook")
    sel_txt.append(" *   只包装候选字符串，标签不走它 ⇒ ADDR_OPT_FG_COLOR 恒为 0）；")
    sel_txt.append(" *   候选列走 DYN，选中色只是换个前景色重画一遍，**不占额外 tile**。")
    sel_txt.append(" * 若将来 PTR 段要放会高亮的文本：把脚本里 need_sel 改成 True")
    sel_txt.append(" * 重新生成（会再吃掉 41*4 个 tile，需确认空间够）。")
    sel_txt.append(" *")
    sel_txt.append(" * ⚠ 若非空，本表必须与 kOptChsSlots **下标一一对应**。")
    sel_txt.append(" *   选中槽若按“组内第几个字”共用一小撮槽（旧实现），光标一移动")
    sel_txt.append(" *   就会顶掉旧选中行仍在引用的那批槽 → 文字替换。必须 per-glyph。")
    sel_txt.append(" */")
    sel_txt.append("static const struct { uint16_t glyph; uint16_t slot; } "
                   "kOptChsSelSlots[%d] = {" % n_sel)
    sel_txt.append(body.rstrip("\n"))
    sel_txt.append("};")
    with open(SEL_INC, "w", encoding="utf-8") as f:
        f.write("\n".join(sel_txt) + "\n")
    print("已写入 %s（%d 条，标签列不吃高亮故为空）"
          % (os.path.basename(SEL_INC), len(sel)))


if __name__ == "__main__":
    sys.exit(main())
