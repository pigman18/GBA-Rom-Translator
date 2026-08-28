#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""tm1 窗口布局配置表离线自检。

用途：改翻译 / 改布局后，不用上机就能发现
  · 中文区越出 charblock（tile [1,513)）
  · 中文区踩到该窗口**已实测引用的字形 tile**（表现为串字 / 纯色方块）
  · 行与行之间 tile 重叠
  · 候选槽容量小于它需要的推进量

用法:
    python scripts/check_tm1_scene.py [path/to/text_scene.c]

退出码 0 = 全部通过；1 = 有错。
"""
import re
import sys

DEFAULT = (r"configs/POKEMON_RUBY_AXVJ00/hook/src/text/text_scene.c")

# charblock 上限：tm1 预渲染字库铺满 [1,513)，BG tile 索引 10bit 上限 1024
TILE_MIN, TILE_MAX = 1, 513


def to_int(tok: str) -> int:
    """C 字面量 → int：容忍 0x 前缀与 u/U/l/L 后缀。"""
    t = tok.strip().rstrip("uUlL")
    return int(t, 16) if t.lower().startswith("0x") else int(t)


def strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


def grab_block(src: str, start: int) -> tuple:
    """从 src[start] 处的 '{' 起，取到配对的 '}'（忽略字符串）。"""
    depth, i, n = 0, start, len(src)
    while i < n:
        c = src[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1], i + 1
        i += 1
    raise ValueError("unbalanced braces")


def split_items(body: str) -> list:
    """顶层逗号切分（忽略嵌套 {} 内的逗号）。"""
    out, depth, cur = [], 0, ""
    for c in body:
        if c in "{[(":
            depth += 1
        elif c in "}])":
            depth -= 1
        if c == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += c
    if cur.strip():
        out.append(cur.strip())
    return out


def parse_u16_array(src: str, name: str):
    m = re.search(r"\b%s\s*\[\s*\d*\s*\]\s*=\s*\{" % re.escape(name), src)
    if not m:
        return None
    body, _ = grab_block(src, m.end() - 1)
    vals = []
    for it in split_items(body[1:-1]):
        it = it.strip()
        if it:
            vals.append(to_int(it))
    return vals


def parse_slot_array(src: str, name: str):
    m = re.search(r"\b%s\s*\[\s*\d*\s*\]\s*=\s*\{" % re.escape(name), src)
    if not m:
        return None
    body, _ = grab_block(src, m.end() - 1)
    out = []
    for it in split_items(body[1:-1]):
        inner = re.findall(r"0x[0-9A-Fa-f]+|\d+", it)
        if len(inner) == 3:
            out.append(tuple(to_int(v) for v in inner))
    return out


def parse_cfgs(src: str) -> list:
    """解析所有 `static const struct Tm1WinCfg NAME = { ... };`，按结构体字段顺序。"""
    cfgs = []
    for m in re.finditer(r"struct\s+Tm1WinCfg\s+(\w+)\s*=\s*\{", src):
        name = m.group(1)
        body, _ = grab_block(src, m.end() - 1)
        toks = split_items(body[1:-1])
        # 字段顺序（务必与 text_scene.h 的 struct Tm1WinCfg 保持一致）：
        #   0 name, 1 tpl, 2 row_tab, 3 row_span_tab, 4 row_tab_n,
        #   5 row_y0, 6 row_shift, 7 title_base, 8 col_label_max,
        #   9 lbl_off, 10 lbl_span, 11 slots, 12 slot_n,
        #   13 glyph_avoid, 14 glyph_avoid_n
        idx = list(range(15))
        assert len(toks) == len(idx), \
            "%s 字段数 %d != 15（结构体改了要同步本脚本）" % (name, len(toks))
        cfgs.append(dict(
            var=name,
            win_name=toks[0].strip().strip('"'),
            tpl=to_int(toks[1]),
            row_tab_name=toks[2].strip(),
            row_span_name=toks[3].strip(),
            row_tab_n=to_int(toks[4]),
            row_y0=to_int(toks[5]), row_shift=to_int(toks[6]),
            title_base=to_int(toks[7]),
            col_label_max=to_int(toks[8]),
            lbl_off=to_int(toks[9]), lbl_span=to_int(toks[10]),
            slots_name=toks[11].strip(), slot_n=to_int(toks[12]),
            avoid_name=toks[13].strip(), avoid_n=to_int(toks[14]),
        ))
    return cfgs


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    src = strip_comments(open(path, encoding="utf-8", errors="replace").read())

    cfgs = parse_cfgs(src)
    if not cfgs:
        print("未在 %s 找到任何 Tm1WinCfg" % path)
        return 1

    fail = 0
    for c in cfgs:
        rows = parse_u16_array(src, c["row_tab_name"])
        spans = parse_u16_array(src, c["row_span_name"])
        slots = parse_slot_array(src, c["slots_name"])
        avoid = parse_u16_array(src, c["avoid_name"])
        if rows is None or slots is None or avoid is None or spans is None:
            print("[%s] 解析失败（rows/spans/slots/avoid 之一找不到）" % c["win_name"])
            fail += 1
            continue
        if len(spans) != len(rows):
            print("[%s] row_span_tab 长度 %d != row_tab 长度 %d"
                  % (c["win_name"], len(spans), len(rows)))
            fail += 1
            continue

        # 满跨度（标签 + 所有候选槽都吃满）仅用于对照提示；
        # 实际校验一律用每行显式声明的 row_span_tab。
        want_span = max([c["lbl_off"] + c["lbl_span"]] + [s[1] + s[2] for s in slots])
        avoid_pairs = set()
        for t in avoid:
            avoid_pairs.add(t)
            avoid_pairs.add(t + 1)

        print("=" * 66)
        print("%s  模板=0x%08X  行=%d  预留=%s  满跨度=%d  引用字形=%d 个"
              % (c["win_name"], c["tpl"], len(rows), spans, want_span, len(avoid)))

        # 1) 越界
        bad = []
        if c["title_base"] + c["lbl_span"] > TILE_MAX or c["title_base"] < TILE_MIN:
            bad.append(("标题基址", c["title_base"]))
        for i, b in enumerate(rows):
            if b < TILE_MIN or b + spans[i] > TILE_MAX:
                bad.append(("行%d" % (i + 1), b))
        print("  1) 越出 tile [%d,%d): %s" % (TILE_MIN, TILE_MAX, bad or "无 ✓"))
        fail += bool(bad)

        # 2) 踩引用字形
        hit = []
        for i, b in enumerate(rows):
            for t in range(b, b + spans[i]):
                if t in avoid_pairs:
                    hit.append(("行%d" % (i + 1), t))
        for t in range(c["title_base"], c["title_base"] + c["lbl_span"]):
            if t in avoid_pairs:
                hit.append(("标题", t))
        print("  2) 踩到已实测引用字形: %s" % (hit[:8] if hit else "无 ✓"))
        fail += bool(hit)

        # 3) 行间重叠
        ov = [(i + 1, i + 2) for i in range(len(rows) - 1)
              if rows[i] + spans[i] > rows[i + 1]]
        print("  3) 行间 tile 重叠: %s" % (ov or "无 ✓"))
        fail += bool(ov)

        # 4) 槽容量 vs 每行预留。
        #    只对"预留足以容纳候选列"的行做强制检查；预留偏小的行按"标签专用行"
        #    处理（其候选列应为空，这一点脚本无法静态验证，需实测确认）。
        host_rows = [i for i in range(len(rows)) if spans[i] >= want_span]
        label_only = [i + 1 for i in range(len(rows)) if spans[i] < want_span]
        print("  4) 候选槽 (curX上界, off, span)：")
        for cx_hi, off, span in slots:
            short = [i + 1 for i in host_rows if off + span > spans[i]]
            note = ""
            if short:
                note = "  ⚠ 超出这些行的预留：%s" % short
                fail += 1
            print("       curX<%3d  off=%2d span=%2d  可容 %d 个 8px 字%s"
                  % (cx_hi, off, span, span // 2, note))
        if label_only:
            print("       标签专用行（预留 < 满跨度 %d）：%s"
                  " —— 这些行不应出现候选列，需实测确认" % (want_span, label_only))

        # 5) 槽两两重叠（设计上允许，仅提示）
        for a in range(len(slots)):
            for b in range(a + 1, len(slots)):
                o1, s1 = slots[a][1], slots[a][2]
                o2, s2 = slots[b][1], slots[b][2]
                if o1 < o2 + s2 and o2 < o1 + s1:
                    print("       提示：槽%d 与 槽%d 有意重叠（%d..%d / %d..%d）"
                          % (a, b, o1, o1 + s1, o2, o2 + s2))

    print("=" * 66)
    print("结论：%s" % ("全部通过 ✓" if not fail else "有 %d 项不通过 ✗" % fail))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
