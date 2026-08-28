#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""tm1 窗口布局配置表离线自检。

不改 ROM、不上机就能发现：
  · 中文区越出 charblock2（tile 0..511）
  · 中文区踩到该窗口**已实测引用的字形 tile**（表现为串字 / 纯色方块）
  · 行与行（或槽与槽）tile 重叠
  · 候选槽容量小于它需要的推进量
  · col_label_max == 0 之类的"分支死掉"配置错误

支持的两种布局模式（见 text_scene.h）：
  PARTITION —— 行基址表 + 列子区。省、不越界，但依赖文本结构。
  GRID      —— tile = base + (y-y0)*stride + (x-x0)，lower = +stride。
               不依赖文本结构、可全 12px，但格位需求大。

用法:
    python scripts/check_tm1_scene.py [text_scene.c]
    python scripts/check_tm1_scene.py --search-base          # 搜安全的 grid_base
    python scripts/check_tm1_scene.py --assume-grid          # 按 GRID 模式校验（无视 C 里的 mode）
    python scripts/check_tm1_scene.py --all-12px             # GRID 下候选列也按 12px 试算

退出码 0 = 全部通过；1 = 有错。
"""
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
        (4, 13, 4, "按键模式"), (23, 13, 2, "类型"),
        (4, 15, 2, "窗口"), (18, 15, 1, "慢"), (4, 17, 2, "关闭"),
    ],
}


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
            out[name] = val          # 形如 TM1_MODE_GRID 的符号常量
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


def parse_u16_array(src: str, name: str):
    m = re.search(r"\b%s\s*\[\s*\d*\s*\]\s*=\s*\{" % re.escape(name), src)
    if not m:
        return None
    body = grab_block(src, m.end() - 1)[1:-1]
    return [to_int(it) for it in split_items(body) if it.strip()]


def parse_slot_array(src: str, name: str):
    m = re.search(r"\b%s\s*\[\s*\d*\s*\]\s*=\s*\{" % re.escape(name), src)
    if not m:
        return None
    body = grab_block(src, m.end() - 1)[1:-1]
    out = []
    for it in split_items(body):
        nums = re.findall(r"0x[0-9A-Fa-f]+|\d+", it)
        if len(nums) == 3:
            out.append(tuple(to_int(v) for v in nums))
    return out


def parse_mirror_array(src: str, name: str):
    """解析 struct Tm1Mirror[] = { {src, dst}, ... }；返回 [(src, dst), ...]"""
    if not name or name in ("0", "((const struct Tm1Mirror *)0)"):
        return []
    m = re.search(r"\b%s\s*\[\s*\d*\s*\]\s*=\s*\{" % re.escape(name), src)
    if not m:
        return None
    body = grab_block(src, m.end() - 1)[1:-1]
    out = []
    for it in split_items(body):
        nums = re.findall(r"0x[0-9A-Fa-f]+|\d+", it)
        if len(nums) == 2:
            out.append((to_int(nums[0]), to_int(nums[1])))
    return out


# 字段顺序必须与 text_scene.h 的 struct Tm1WinCfg 一致
FIELDS = ["name", "tpl", "mode", "row_tab", "row_span_tab", "row_tab_n",
          "row_y0", "row_shift", "title_base", "col_label_max",
          "lbl_off", "lbl_span", "slots", "slot_n", "cand_font",
          "grid_base", "grid_stride", "grid_x0", "grid_y0",
          "mirrors", "mirror_n", "glyph_avoid", "glyph_avoid_n"]
N_FIELDS = len(FIELDS)

MODE_NAMES = {"TM1_MODE_PARTITION": 0, "TM1_MODE_GRID": 1}


def eval_cond(expr: str, defs: dict) -> bool:
    """求值 #if 表达式。只需支持宏名/数字的比较与真值判断。"""
    def resolve(tok):
        tok = tok.strip()
        for _ in range(8):
            if tok in defs:
                v = defs[tok]
                if not isinstance(v, str):
                    return v
                tok = v.strip()
            else:
                break
        if tok in MODE_NAMES:
            return MODE_NAMES[tok]
        try:
            return to_int(tok)
        except ValueError:
            return tok

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


def preprocess_conditionals(src: str) -> str:
    """处理 #if/#elif/#else/#endif，只保留当前成立的分支。

    必要性：text_scene.c 用条件编译让 PARTITION / GRID 互斥生效
    （镜像表、cand_font 都在 #if 里）。若不做这步，collect_defines 会把
    #else 分支的值也收进来，导致 mode=GRID 时却按 PARTITION 的参数校验。
    """
    defs = collect_defines(src)          # 先收全集用于求值（含不活跃分支）
    out, stack = [], []

    for ln in src.splitlines():
        s = ln.strip()
        if s.startswith("#if"):
            v = eval_cond(s[3:].strip(), defs)
            stack.append([v, v])         # [当前是否输出, 本组是否已取过分支]
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


def parse_cfgs(src: str, defs: dict) -> list:
    cfgs = []
    for m in re.finditer(r"struct\s+Tm1WinCfg\s+(\w+)\s*=\s*\{", src):
        toks = split_items(grab_block(src, m.end() - 1)[1:-1])
        if len(toks) != N_FIELDS:
            print("  ⚠ %s 字段数 %d != %d，跳过（结构体改了要同步 FIELDS）"
                  % (m.group(1), len(toks), N_FIELDS))
            continue

        def val(i):
            # 宏可能指向另一个宏（如 OPTION_MODE → TM1_MODE_GRID），需递归展开
            t = toks[i].strip()
            for _ in range(8):
                if t in defs:
                    v = defs[t]
                    if not isinstance(v, str):
                        return v
                    t = v.strip()
                else:
                    break
            if t in MODE_NAMES:
                return MODE_NAMES[t]
            try:
                return to_int(t)
            except ValueError:
                return t
        cfgs.append(dict(zip(FIELDS, [val(i) for i in range(N_FIELDS)])))
    return cfgs


# ---------------------------------------------------------------- 落址模拟

def sim_partition(c, rows, spans, slots, sessions, cand_wide):
    occ = {}
    for cx, cy, n, note in sessions:
        if cy <= c["row_y0"]:
            base = c["title_base"]
        else:
            r = (cy - c["row_y0"]) >> c["row_shift"]
            r = max(1, min(c["row_tab_n"], r))
            base = rows[r - 1]
        # 标签列恒 12px；候选列字宽由 cand_wide 决定
        wide = cand_wide if (cx >= c["col_label_max"]) else True
        if cx < c["col_label_max"]:
            off = c["lbl_off"]
        else:
            off = None
            for cx_hi, o, _sp in slots:
                if cx < cx_hi:
                    off = o
                    break
            if off is None:
                off = slots[-1][1]
        px, o = 0, off
        for _ in range(n):
            sp = px & 7
            for t in (o, o + 1):
                occ[base + t] = note
            if sp + 8 > 8:
                for t in (o + 2, o + 3):
                    occ[base + t] = note
            o += 2
            px += 8
            if wide:
                for t in (o, o + 1):
                    occ[base + t] = note
                if sp + 4 > 8:
                    for t in (o + 2, o + 3):
                        occ[base + t] = note
                o += (0 if sp == 0 else 2)
                px += 4
    return occ


def sim_grid(c, sessions, cand_wide, base_override=None, stride=None):
    stride = stride or c["grid_stride"]
    base = c["grid_base"] if base_override is None else base_override
    occ = {}
    for cx, cy, n, note in sessions:
        wide = cand_wide if (cx >= c["col_label_max"]) else True
        px = 0
        for _ in range(n):
            sp = px & 7
            tx = px >> 3
            for cd in ((0,) if sp + 8 <= 8 else (0, 1)):
                col = min(max(cx + tx + cd - c["grid_x0"], 0), stride - 1)
                row = max(cy - c["grid_y0"], 0)
                u = base + row * stride + col
                occ[u] = note
                occ[u + stride] = note
            px += 8
            if wide:
                tx = px >> 3
                for cd in ((0,) if sp + 4 <= 8 else (0, 1)):
                    col = min(max(cx + tx + cd - c["grid_x0"], 0), stride - 1)
                    row = max(cy - c["grid_y0"], 0)
                    u = base + row * stride + col
                    occ[u] = note
                    occ[u + stride] = note
                px += 4
    return occ


# ---------------------------------------------------------------- 主流程

def report(tag, occ, avoid_pairs, mirrors=None):
    """mirrors: [(src, dst), ...] —— 被镜像兜住的 tile 不算真踩踏。
    返回 (越界数, 未兜住的踩踏数, 需镜像数)"""
    mirrors = mirrors or []
    tiles = sorted(occ)
    over = [t for t in tiles if t > CHARBLOCK2_MAX]
    hit = [t for t in tiles if t in avoid_pairs]

    def mirrored(t):
        for s, _d in mirrors:
            if t == s or t == s + 1:
                return True
        return False

    covered = [t for t in hit if mirrored(t)]
    real = [t for t in hit if not mirrored(t)]

    print("  %s" % tag)
    print("    写入 %d tile，范围 %d..%d" % (len(tiles), tiles[0], tiles[-1]))
    print("    越出 charblock2(>%d): %s" % (CHARBLOCK2_MAX,
          ("%d 个 → %s" % (len(over), over[:6])) if over else "无 ✓"))
    if hit:
        print("    与引用字形冲突: %d 个 → %s" % (len(hit), hit[:8]))
        print("      其中由镜像兜住: %d 个%s" % (len(covered), " ✓" if covered else ""))
    print("    实际踩踏(未兜住): %s" % (
          ("%d 个 → %s" % (len(real), real[:8])) if real else "无 ✓"))
    return len(over), len(real), len(hit)


def check_mirrors(c, mirrors, occ, avoid_pairs):
    """镜像表自身的合法性。返回错误数。"""
    bad = 0
    if len(mirrors) != c["mirror_n"]:
        print("  ✗ mirror_n=%d 但实际表有 %d 条" % (c["mirror_n"], len(mirrors)))
        bad += 1
    if not mirrors:
        return bad

    print("  镜像表 %d 条：" % len(mirrors))
    used_dst = set()
    for s, d in mirrors:
        notes = []
        if s % 2 == 0:
            notes.append("src 应为奇数(字形起点 = startOffset+glyph*2)")
            bad += 1
        if d % 2 == 0:
            notes.append("dst 应为奇数（须与 src 同奇偶，lower 才对得上）")
            bad += 1
        for t in (s, s + 1):
            if t not in avoid_pairs:
                notes.append("src %d 并非引用字形（冗余镜像）" % t)
        for t in (d, d + 1):
            if t > CHARBLOCK2_MAX:
                notes.append("dst %d 越出 charblock2" % t)
                bad += 1
            if t in avoid_pairs:
                notes.append("dst %d 压在引用字形上" % t)
                bad += 1
            if t in occ:
                notes.append("dst %d 落在中文足迹内（会被中文覆盖）" % t)
                bad += 1
            if t in used_dst:
                notes.append("dst %d 与前面的镜像槽重叠" % t)
                bad += 1
            used_dst.add(t)
        print("      %3d,%3d → %3d,%3d   %s" % (s, s + 1, d, d + 1,
              ("✗ " + "; ".join(notes)) if notes else "✓"))
        if notes and all("冗余" not in n for n in notes):
            bad += 1

    # 反向：还有没有被镜像漏掉的冲突
    covered = set()
    for s, _d in mirrors:
        covered.add(s)
        covered.add(s + 1)
    miss = sorted(t for t in occ if t in avoid_pairs and t not in covered)
    if miss:
        print("      ✗ 有 %d 个冲突未被镜像覆盖: %s" % (len(miss), miss[:8]))
        bad += 1
    else:
        print("      冲突覆盖: 全部 ✓")
    return bad


def main() -> int:
    args = sys.argv[1:]
    src_path = next((a for a in args if not a.startswith("--")), DEFAULT_SRC)
    do_search = "--search-base" in args
    assume_grid = "--assume-grid" in args or do_search
    all_12 = "--all-12px" in args or do_search

    src = preprocess_conditionals(
            strip_comments(open(src_path, encoding="utf-8", errors="replace").read()))
    defs = collect_defines(src)
    cfgs = parse_cfgs(src, defs)
    if not cfgs:
        print("未在 %s 找到可解析的 Tm1WinCfg" % src_path)
        return 1

    fail = 0
    for c in cfgs:
        sess = SESSIONS.get(c["tpl"])
        avoid = parse_u16_array(src, c["glyph_avoid"]) or []
        avoid_pairs = set()
        for t in avoid:
            avoid_pairs.add(t)
            avoid_pairs.add(t + 1)

        print("=" * 68)
        print("%s  模板=0x%08X  mode=%s  引用字形=%d 个"
              % (c["name"], c["tpl"],
                 "GRID" if (assume_grid or c["mode"] == 1) else "PARTITION",
                 len(avoid)))

        # 通用健全性
        if c["col_label_max"] == 0 and c["mode"] == 0:
            print("  ✗ col_label_max == 0 → 标签列分支永远不成立，"
                  "所有列都会走候选槽（曾因漏写这个字段踩过）")
            fail += 1
        if not sess:
            print("  ⚠ 无实测会话几何，跳过落址模拟")
            continue

        cand_wide = bool(all_12) or (c["cand_font"] == 0)  # 候选列是否 12px

        mirrors = parse_mirror_array(src, c["mirrors"])
        if mirrors is None:
            print("  ⚠ 镜像表 %s 解析失败" % c["mirrors"])
            mirrors = []
            fail += 1

        if assume_grid or c["mode"] == 1:
            # ⚠ 必须传 cand_wide（= 配置 cand_font 或 --all-12px 的结果），
            #   不能传 all_12——后者只是命令行开关，默认 False。
            occ_g = sim_grid(c, sess, cand_wide)
            no, nh, _nc = report("GRID  base=%d stride=%d x0=%d y0=%d 候选%s"
                                 % (c["grid_base"], c["grid_stride"], c["grid_x0"],
                                    c["grid_y0"], "12px" if cand_wide else "8px"),
                                 occ_g, avoid_pairs, mirrors)
            fail += bool(no) + bool(nh)
            fail += check_mirrors(c, mirrors, occ_g, avoid_pairs)
        else:
            rows = parse_u16_array(src, c["row_tab"]) or []
            spans = parse_u16_array(src, c["row_span_tab"]) or []
            slots = parse_slot_array(src, c["slots"]) or []
            if not (rows and spans and slots):
                print("  ⚠ PARTITION 数据不完整")
                fail += 1
                continue
            occ_p = sim_partition(c, rows, spans, slots, sess, cand_wide)
            no, nh, _nc = report("PARTITION 行=%d 预留=%s" % (len(rows), spans),
                                 occ_p, avoid_pairs, mirrors)
            fail += bool(no) + bool(nh)
            if mirrors:
                fail += check_mirrors(c, mirrors, occ_p, avoid_pairs)

        # 搜 grid_base。GRID 是位置式，足迹必然压到部分引用字形
        # （已穷举证明无"零冲突"解），所以搜索时**自带镜像槽分配**：
        # 冲突的字形拷到空闲处，表项改指过去 → 冲突不再是硬约束。
        if do_search:
            print("\n  --search-base：在 [%d, %d] 内搜索 base（自动分配镜像槽）"
                  % (TILE_MIN, TILE_MAX - 1))
            good = []
            for b in range(TILE_MIN, TILE_MAX):
                occ = sim_grid(c, sess, all_12, base_override=b)
                if not occ or max(occ) > CHARBLOCK2_MAX:
                    continue
                # 冲突格 → 字形起点（必为奇数：tile = 1 + glyph*2）
                starts = sorted({t if (t & 1) else t - 1
                                 for t in occ if t in avoid_pairs})
                used = set(occ) | avoid_pairs
                free = [t for t in range(1, CHARBLOCK2_MAX, 2)
                        if t not in used and (t + 1) not in used]
                if len(free) < len(starts):
                    continue
                good.append((len(starts), max(occ), b,
                             list(zip(starts, free[:len(starts)]))))
            if good:
                good.sort(key=lambda x: (x[0], x[1]))
                print("    可行 base 共 %d 个" % len(good))
                n, hi, b, mapping = good[0]
                print("    最优: base=0x%03X(%d)  需镜像 %d 个字形  足迹 max=%d"
                      % (b, b, n, hi))
                print("    → 写入 text_scene.c 的镜像表：")
                print("      static const struct Tm1Mirror kOptMirrors[%d] = {" % n)
                for s, d in mapping:
                    print("          { 0x%03Xu, 0x%03Xu },   /* %d,%d → %d,%d */"
                          % (s, d, s, s + 1, d, d + 1))
                print("      };")
                print("    其余候选（冲突数, max tile, base）：%s"
                      % [(g[0], g[1], g[2]) for g in good[1:9]])
            else:
                print("    ✗ 无可行 base：越界，或引用字形密集到镜像槽都放不下")
                print("      可试：减小 stride（列跨度）、或改 x0/y0、或改用 PARTITION")
                fail += 1

    print("=" * 68)
    print("结论：%s" % ("全部通过 ✓" if not fail else "有 %d 项不通过 ✗" % fail))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
