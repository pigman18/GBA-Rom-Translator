# -*- coding: utf-8 -*-
"""生成 tm1 指针模式（TM1_MODE_PTR）的汉字槽表。

背景
----
PTR 模式把每个汉字画进字库里"本窗口未引用的空槽"，tilemap 表项直接指向它。
  · 未选中态：kOptChsSlots  （普通色，黑）
  · 选中态  ：kOptChsSelSlots（高亮色，红）—— 本脚本生成

为什么选中态必须**按汉字**分配槽（而不是共用一小撮槽）：
  旧实现用 CHS_SEL_SLOT_BASE(309) 起的 3 个槽，按"组内第几个字"分配。
  那是**全局共用**的 —— 光标一移动，新选中的字写进同一批槽，而旧选中行的
  tilemap 表项还指着它们，于是旧行内容被顶掉（"移动光标文字替换"）。
  按汉字分配后："快"的红字永远只在"快"的槽里，别的字写不进去 → 不替换；
  未选中态仍走原槽 → 也不会把别的行染红。

约束（每个槽 4 个连续 tile，ptr_base+0..+3 全要用）
----
  1. 避开 kOptGlyphAvoid 里的引用字形（各占 2 tile：t 与 t+1）
  2. 避开 kOptChsSlots 已占用的 [s, s+4)
  3. 落在 charblock2 内：tile < 512
槽与槽之间**不需要连续**，各自 4 连续即可。

用法：
  python scripts/gen_chs_sel_slots.py            # 打印到 stdout
  python scripts/gen_chs_sel_slots.py -o FILE    # 写入文件
"""
import argparse
import os
import re
import sys

# ---- 引用字形（各占 2 tile：t 与 t+1）—— 与 text_scene.c kOptGlyphAvoid 一致
GLYPH_AVOID = [
    0x001, 0x021, 0x031, 0x06F, 0x077, 0x08B, 0x0FF,
    0x143, 0x145, 0x147, 0x149, 0x14B, 0x14D, 0x14F,
    0x151, 0x153, 0x159, 0x15D, 0x171, 0x18D, 0x199,
    0x1B7, 0x1BF, 0x1C3,
    0x1DF, 0x1E1,
]
TILE_MAX = 512          # charblock2 上限（不含）


def blocked_set():
    """被引用字形占用的 tile 集合（每个字形 2 格）。"""
    b = set()
    for t in GLYPH_AVOID:
        b.add(t)
        b.add(t + 1)
    return b


def parse_slots_inc(path):
    """解析 chs_slots.inc：返回 [(glyph, slot), ...]"""
    txt = open(path, encoding="utf-8").read()
    pat = re.compile(r"\{\s*0x([0-9A-Fa-f]{4})u,\s*0x([0-9A-Fa-f]{4})u\s*\}")
    return [(int(g, 16), int(s, 16)) for g, s in pat.findall(txt)]


def alloc_sel_slots(n_slots, used):
    """为 n_slots 个汉字分配选中槽，返回 [(base_tile), ...]"""
    blocked = blocked_set() | used
    out = []
    t = 1
    while len(out) < n_slots and t + 4 <= TILE_MAX:
        window = {t + k for k in range(4)}
        if not (window & blocked):
            out.append(t)
            blocked |= window
            t += 4
        else:
            t += 1
    if len(out) < n_slots:
        raise SystemExit("空间不足：只分配到 %d/%d 个槽" % (len(out), n_slots))
    return out


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_inc = os.path.join(
        root, "configs", "POKEMON_RUBY_AXVJ00", "hook", "src", "text", "chs_slots.inc")

    ap = argparse.ArgumentParser()
    ap.add_argument("--slots-inc", default=default_inc)
    ap.add_argument("-o", "--output")
    args = ap.parse_args()

    pairs = parse_slots_inc(args.slots_inc)
    print("; 解析到 %d 条汉字槽（来源 %s）" % (len(pairs), args.slots_inc),
          file=sys.stderr)

    # 已占用：原槽表的每个 [s, s+4)
    used = set()
    for _g, s in pairs:
        used |= {s + k for k in range(4)}

    blocked = blocked_set()

    # 自检：原槽表有没有踩到引用字形
    clash = []
    for _g, s in pairs:
        hit = {s + k for k in range(4)} & blocked
        if hit:
            clash.append((s, sorted(hit)))
    if clash:
        print("; ⚠ 原槽表与引用字形冲突：", file=sys.stderr)
        for s, hit in clash:
            print(";   槽 0x%03X(%d) 压住 %s" % (s, s, hit), file=sys.stderr)
    else:
        print("; ✓ 原槽表未踩引用字形", file=sys.stderr)

    sels = alloc_sel_slots(len(pairs), used)

    lines = []
    lines.append("/* 由 scripts/gen_chs_sel_slots.py 生成 —— 勿手改 */")
    lines.append("/*")
    lines.append(" * 选中态（红色）汉字槽：与 kOptChsSlots **一一对应**的下标。")
    lines.append(" * 为什么要按汉字分配（而不是共用一小撮槽）：")
    lines.append(" *   共用槽是全局的 —— 光标一移动，新选中的字写进同一批槽，")
    lines.append(" *   旧选中行的 tilemap 表项仍指向它们 → 旧行内容被顶掉。")
    lines.append(" *   按汉字分配后每个字的红字有专属槽，别的字写不进去。")
    lines.append(" * 约束：每槽 4 连续 tile；避开引用字形（各 2 格）与原槽表；tile < 512。")
    lines.append(" */")
    lines.append("static const struct { uint16_t glyph; uint16_t slot; } "
                 "kOptChsSelSlots[%d] = {" % len(pairs))
    for (g, _s), sel in zip(pairs, sels):
        lines.append("    { 0x%04Xu, 0x%04Xu }," % (g, sel))
    lines.append("};")

    text = "\n".join(lines) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print("; 已写入 %s（选中槽 %d 个，占用 tile %d..%d）"
              % (args.output, len(sels), min(sels), max(sels) + 3), file=sys.stderr)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
