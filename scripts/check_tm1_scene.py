#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""tm1 窗口布局配置表离线自检。

不改 ROM、不上机就能发现：
  · 中文区越出 charblock2（tile 0..511）
  · 中文区踩到该窗口**已实测引用的字形 tile**（表现为串字 / 纯色方块）
  · 会话足迹越过本行预留 [base, base+span)（2026-08-29 "打到底踩单声道"BUG）
  · 会话足迹越出本区窗口 [off, off+span)
  · 任意两会话足迹重叠（谁后画谁赢 → 串字/残留/乱码）
  · zone 表结构错误（末条非 0xFF / cx_hi 非递增 / 相邻 DYN 窗口重叠）
  · zone_n / glyph_avoid_n / row_tab_n 与实际数组长度不符（sizeof 脱节）

布局只有一种：PTR 区（固定槽，不吃行区，由 gen_tm1_slots.py 管账）+
DYN 区（行基址 + 行内 off/span，相邻字共享 tile = 12px）。
配置在 text_scene.c（**指定初始化器**），算法在 text_layout.c。
历史模式 PARTITION / GRID 的模拟已随其代码一起删除，要翻旧账用 git 历史。

用法:
    python scripts/check_tm1_scene.py [text_scene.c]

退出码 0 = 全部通过；1 = 有错。
"""
import os
import re
import sys

DEFAULT_SRC = r"configs/POKEMON_RUBY_AXVJ00/hook/src/text/text_scene.c"

TILE_MIN, TILE_MAX = 1, 513          # charblock2 = tile 0..511；≥512 即进入 charblock3
CHARBLOCK2_MAX = 511                 # 严格不越界的上限

# 实测会话几何：模板 -> [(curX, curY, 字数, 说明)]
# 数据来源 gdb [CFF]/[UTM]。界面改版后必须更新，否则自检会失真。
SESSIONS = {
    0x081BB874: [
        (4, 1, 4, "标题"), (4, 5, 4, "对话速度"), (15, 5, 1, "慢"), (19, 5, 2, "普通"),
        (23, 5, 1, "快"), (4, 7, 4, "战斗动画"), (15, 7, 1, "看"), (23, 7, 2, "不看"),
        (4, 9, 4, "对战规则"), (15, 9, 2, "替换"), (22, 9, 3, "打到底"),
        (4, 11, 2, "声音"), (15, 11, 3, "单声道"), (22, 11, 3, "立体声"),
        (4, 13, 4, "按键模式"), (15, 13, 2, "普通"),
        (4, 15, 2, "窗口"), (15, 15, 2, "类型"), (4, 17, 2, "关闭"),
    ],
}
# ⚠ 上面这份几何是**手抄**的，仅用于估算"实际足迹"。
#   几何与配置不符是此类 BUG 的头号来源（v18 把 cx=22 当成 19..21）——
#   改译文/改布局后必须对 gdb 日志复核。


# ---------------------------------------------------------------- 解析工具

def to_int(tok: str) -> int:
    """C 字面量 → int：容忍 0x 前缀与 u/U/l/L 后缀。"""
    t = tok.strip().rstrip("uUlL")
    return int(t, 16) if t.lower().startswith("0x") else int(t)


def strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


def collect_defines(src: str) -> dict:
    out = {}
    for m in re.finditer(r"#\s*define\s+(\w+)\s+([^\n]+)", src):
        name, val = m.group(1), m.group(2).split("/*")[0].strip()
        try:
            out[name] = to_int(val)
        except ValueError:
            out[name] = val          # 形如 TM1_ZONE_PTR 的符号常量
    return out


def grab_block(src: str, start: int) -> str:
    depth, i = 0, start
    while i < len(src):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1
    raise ValueError("unbalanced braces")


def split_items(body: str) -> list:
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


def resolve_value(tok: str, defs: dict):
    """宏递归展开 → int；sizeof 表达式原样返回（由调用方按数组实长核对）。"""
    t = tok.strip()
    for _ in range(8):
        if t not in defs:
            break
        v = defs[t]
        if isinstance(v, str):
            t = v.strip()
        else:
            return v
    if "sizeof" in t:
        return t
    try:
        return to_int(t)
    except ValueError:
        return t


def parse_named_items(body: str, defs: dict) -> dict:
    """解析指定初始化器块体：".name = value, ..." → {name: value}。"""
    out = {}
    for t in split_items(body):
        nm = re.match(r"\.(\w+)\s*=\s*(.+)", t.strip())
        if nm:
            out[nm.group(1)] = resolve_value(nm.group(2), defs)
    return out


def parse_u16_array(src: str, name: str):
    m = re.search(r"\b%s\s*\[\s*\d*\s*\]\s*=\s*\{" % re.escape(name), src)
    if not m:
        return None
    body = grab_block(src, m.end() - 1)[1:-1]
    return [to_int(it) for it in split_items(body) if it.strip()]


def parse_zone_array(src: str, name: str, defs: dict):
    """解析 struct Tm1Zone[]（指定初始化器）→ [(cx_hi, strategy, font, off, span)]。
    PTR 区可省略 off/span（C 零初始化）。名字为 0/NULL 时返回 []。"""
    if not name or name in ("0",):
        return []
    m = re.search(r"\b%s\s*\[[^\]]*\]\s*=\s*\{" % re.escape(name), src)
    if not m:
        return None
    body = grab_block(src, m.end() - 1)[1:-1]
    out = []
    for it in split_items(body):
        d = parse_named_items(it.strip().strip("{}"), defs)
        if all(k in d for k in ("cx_hi", "strategy", "font")):
            out.append((d["cx_hi"], d["strategy"],
                        d["font"], d.get("off", 0), d.get("span", 0)))
    return out


# 字段顺序即 struct Tm1WinCfg（text_scene.h）；配置必须用指定初始化器写全
FIELDS = ["name", "tpl", "row_tab", "row_span_tab", "row_tab_n",
          "row_y0", "row_shift", "zones", "zone_n",
          "glyph_avoid", "glyph_avoid_n"]

ZONE_PTR, ZONE_DYN = 0, 1      # TM1_ZONE_PTR / TM1_ZONE_DYN（text_scene.h）


def parse_cfgs(src: str, defs: dict) -> list:
    cfgs = []
    for m in re.finditer(r"struct\s+Tm1WinCfg\s+(\w+)\s*=\s*\{", src):
        d = parse_named_items(grab_block(src, m.end() - 1)[1:-1], defs)
        missing = [f for f in FIELDS if f not in d]
        if missing:
            print("  ⚠ %s 缺字段 %s，跳过（配置必须用指定初始化器写全）"
                  % (m.group(1), ",".join(missing)))
            continue
        extra = [k for k in d if k not in FIELDS]
        if extra:
            print("  ⚠ %s 有未知字段 %s（text_scene.h 改了要同步 FIELDS）"
                  % (m.group(1), ",".join(extra)))
        cfgs.append(d)
    return cfgs


# ---------------------------------------------------------------- 落址模拟

def sim_partition(c, rows, spans, zones, sessions):
    """落址模拟。返回 (occ, prints)：
      occ    tile -> note（供引用字形冲突检查）
      prints [(note, base, lo, hi, span_lim, zoff, zspan)] 每会话足迹。
    与 text_layout.c 同构：PTR 区跳过（不吃行区，gen_tm1_slots.py 管账）；
    DYN 区从 zone.off 起，按 12px 两趟推进（8px 字模 pass2_w=0 自动只走一趟）。"""
    occ = {}
    prints = []

    def zone_of(cx):
        for z in zones:
            if cx < z[0]:
                return z
        return zones[-1] if zones else None

    for cx, cy, n, note in sessions:
        z = zone_of(cx)
        if z is None or z[1] == ZONE_PTR:
            continue                      # PTR 固定槽：不占行区
        # 行号推导与 scene_tm1_row_base 同式（含 clamp）
        if cy <= c["row_y0"]:
            r = 1
        else:
            r = (cy - c["row_y0"]) >> c["row_shift"]
            r = max(1, min(c["row_tab_n"], r))
        base = rows[r - 1]
        span_lim = spans[r - 1] if r - 1 < len(spans) else 0

        wide = (z[2] == 0)                # font==0 → 12px 两趟
        lo, hi = None, None
        px, o = 0, z[3]
        for _ in range(n):
            sp = px & 7
            for t in (o, o + 1):
                occ[base + t] = note
                lo = base + t if lo is None else min(lo, base + t)
                hi = base + t if hi is None else max(hi, base + t)
            if sp + 8 > 8:
                for t in (o + 2, o + 3):
                    occ[base + t] = note
                    lo = base + t if lo is None else min(lo, base + t)
                    hi = base + t if hi is None else max(hi, base + t)
            o += 2
            px += 8
            if wide:
                for t in (o, o + 1):
                    occ[base + t] = note
                    lo = base + t if lo is None else min(lo, base + t)
                    hi = base + t if hi is None else max(hi, base + t)
                if sp + 4 > 8:
                    for t in (o + 2, o + 3):
                        occ[base + t] = note
                        lo = base + t if lo is None else min(lo, base + t)
                        hi = base + t if hi is None else max(hi, base + t)
                o += (0 if sp == 0 else 2)
                px += 4
        prints.append((note, base, lo, hi, span_lim, z[3], z[4]))
    return occ, prints


# ---------------------------------------------------------------- 检查报告

def report(tag, occ, avoid_pairs):
    tiles = sorted(occ)
    over = [t for t in tiles if t > CHARBLOCK2_MAX]
    hit = sorted(set(occ) & avoid_pairs)
    print("  %s" % tag)
    print("    写入 %d tile，范围 %d..%d" % (len(tiles), tiles[0], tiles[-1]))
    print("    越出 charblock2(>%d): %s" % (CHARBLOCK2_MAX,
          ("%d 个 → %s" % (len(over), over[:6])) if over else "无 ✓"))
    print("    与引用字形冲突: %s" % (
          ("%d 个 → %s" % (len(hit), hit[:8])) if hit else "无 ✓"))
    return len(over), len(hit)


def main() -> int:
    args = sys.argv[1:]
    src_path = next((a for a in args if not a.startswith("--")), DEFAULT_SRC)

    src = preprocess_conditionals(
            strip_comments(open(src_path, encoding="utf-8", errors="replace").read()))
    defs = collect_defines(src)
    # 同目录头文件（text_scene.h）里的宏也并入（TM1_ZONE_* 定义在那）
    hdr = os.path.join(os.path.dirname(os.path.abspath(src_path)), "text_scene.h")
    if os.path.exists(hdr):
        defs.update(collect_defines(open(hdr, encoding="utf-8", errors="replace").read()))
    cfgs = parse_cfgs(src, defs)
    if not cfgs:
        print("未在 %s 找到可解析的 Tm1WinCfg" % src_path)
        return 1

    fail = 0
    for c in cfgs:
        print("=" * 68)
        print("%s  模板=0x%08X" % (c["name"], c["tpl"]))
        sess = SESSIONS.get(c["tpl"])

        rows = parse_u16_array(src, c["row_tab"]) or []
        spans = parse_u16_array(src, c["row_span_tab"]) or []
        zones = parse_zone_array(src, c["zones"], defs)
        avoid = parse_u16_array(src, c["glyph_avoid"]) or []

        # ---- sizeof/字数与实际数组长度一致性 ----
        for key, actual, label in ((c["row_tab_n"], len(rows), "row_tab"),
                                   (c["zone_n"], len(zones), "zones"),
                                   (c["glyph_avoid_n"], len(avoid), "glyph_avoid")):
            if isinstance(key, int) and key != actual:
                print("  ✗ %s_n=%d 与 %s 实际 %d 条不符" % (label, key, label, actual))
                fail += 1

        # ---- zone 表结构 ----
        if not zones:
            print("  ✗ 区表 %s 解析失败/为空" % c["zones"])
            fail += 1
            continue
        if zones[-1][0] != 0xFF:
            print("  ✗ 区表末条 cx_hi=%d ≠ 0xFF（缺兜底）" % zones[-1][0])
            fail += 1
        for a, b in zip(zones, zones[1:]):
            if b[0] <= a[0]:
                print("  ✗ 区表 cx_hi 非递增: %s → %s" % (a[0], b[0]))
                fail += 1
            if a[1] == ZONE_DYN and b[1] == ZONE_DYN and a[3] + a[4] > b[3]:
                print("  ✗ 相邻 DYN 区窗口重叠: off%d+span%d 压过 off%d"
                      % (a[3], a[4], b[3]))
                fail += 1

        # ---- 引用字形禁区（各占 2 格）----
        avoid_pairs = set()
        for t in avoid:
            avoid_pairs.add(t)
            avoid_pairs.add(t + 1)

        if not sess:
            print("  ⚠ 无实测会话几何，跳过落址模拟")
            continue

        occ, prints = sim_partition(c, rows, spans, zones, sess)
        no, nh = report("DYN 行=%d 预留=%s 分区=%d 段" % (len(rows), spans, len(zones)),
                        occ, avoid_pairs)
        fail += bool(no) + bool(nh)

        # ---- 会话足迹检查（"打到底踩单声道"BUG 的直接教训）----
        for note, base, lo, hi, span_lim, zoff, zspan in prints:
            if lo is None:
                continue
            if span_lim and hi >= base + span_lim:
                print("  ✗ [%s] 足迹 %d..%d 越过行界 %d（base=%d 预留=%d）"
                      % (note, lo, hi, base + span_lim, base, span_lim))
                fail += 1
            if hi >= base + zoff + zspan or lo < base + zoff:
                print("  ✗ [%s] 足迹 %d..%d 越出区窗口 [%d,%d)"
                      % (note, lo, hi, base + zoff, base + zoff + zspan))
                fail += 1
        for i in range(len(prints)):
            for j in range(i + 1, len(prints)):
                n1, _b1, l1, h1, *_ = prints[i]
                n2, _b2, l2, h2, *_ = prints[j]
                if l1 is None or l2 is None:
                    continue
                if l1 <= h2 and l2 <= h1:
                    print("  ✗ 会话足迹重叠: [%s] %d..%d ↔ [%s] %d..%d"
                          % (n1, l1, h1, n2, l2, h2))
                    fail += 1

    print("=" * 68)
    print("结论：%s" % ("全部通过 ✓" if not fail else "有 %d 项不通过 ✗" % fail))
    return 1 if fail else 0


def preprocess_conditionals(src: str) -> str:
    """处理 #if/#elif/#else/#endif，只保留当前成立的分支。"""
    defs = collect_defines(src)
    out, stack = [], []

    for ln in src.splitlines():
        s = ln.strip()
        if s.startswith("#if"):
            v = eval_cond(s[3:].strip(), defs)
            stack.append([v, v])
            continue
        if s.startswith("#elif") and stack:
            taken = stack[-1][1]
            v = (not taken) and eval_cond(s[5:].strip(), defs)
            stack[-1] = [v, taken or v]
            continue
        if s.startswith("#else") and stack:
            taken = stack[-1][1]
            stack[-1] = [not taken, True]
            continue
        if s.startswith("#endif"):
            if stack:
                stack.pop()
            continue
        if s.startswith("#ifdef"):
            stack.append([s[6:].strip() in defs, True])
            continue
        if s.startswith("#ifndef"):
            stack.append([s[7:].strip() not in defs, True])
            continue
        if all(a for a, _t in stack):
            out.append(ln)
    return "\n".join(out)


def eval_cond(expr: str, defs: dict) -> bool:
    """求值 #if 表达式。只需支持宏名/数字的比较与真值判断。"""
    def resolve(tok):
        v = resolve_value(tok, defs)
        return v

    for op in ("==", "!="):
        if op in expr:
            a, b = expr.split(op, 1)
            ra, rb = resolve(a), resolve(b)
            if isinstance(ra, int) and isinstance(rb, int):
                return ra == rb if op == "==" else ra != rb
            sa, sb = str(ra), str(rb)
            return sa == sb if op == "==" else sa != sb
    r = resolve(expr)
    if isinstance(r, int):
        return r != 0
    return bool(r) and r != "0"


if __name__ == "__main__":
    sys.exit(main())
