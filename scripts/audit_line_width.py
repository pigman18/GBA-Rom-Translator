# -*- coding: utf-8 -*-
"""audit_line_width.py — 构建期排版宽度审计（L1 静态，无 ROM / 无模拟器）

为什么存在
----------
验收标准第二条「不撞 UI」的根因不在渲染层，而在**排版层**：
日文引擎的每一个字都是 **8px 步进**（tm1 每字 `cursorTileX += 1`；tm0 每字
`TILE_OFFSET += 2`，单位 2 单位 = 1 列 = 8px —— 见 `PrintNextChar_hook.c`）。
中文用 **12px 步进**（1bpp 大库 11×11，墨 11 / 步进 12）。

⇒ 同一块版式，日文 30 字一行，中文只能排 20 字。**任何按日文 8px 排好的
固定版式，换成 12px 中文必然超宽 50%**，多出来的部分就压到 UI 上。
这是与「tile 号撞车」**完全独立的第二条根因**，过去从未被量化过。

本脚本把这条根因变成一张可核对的清单：
对每条译文，逐行算
    日文原文宽 jp_px = 8 × 可见字符数          （引擎实测步进）
    中文译文宽 cn_px = 12 × 全角数 + 8 × 半角数
并报告
    cn_px > 240   → 物理不可能（屏幕只有 240px 宽）★ 硬溢出
    cn_px > jp_px → 超出版式原设计宽度           ☆ 版式溢出

用法
----
    python scripts/audit_line_width.py            # 汇总
    python scripts/audit_line_width.py -v         # 附带明细样例
    python scripts/audit_line_width.py --limit 30
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_JSON = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"

SCREEN_PX = 240          # 30 列 × 8px
JP_ADV = 8               # 日版引擎每字步进（实证）
CN_ADV_CJK = 12          # 中文大库 11×11，步进 12
CN_ADV_HALF = 8          # 半角 / 小库 9×9，步进 10？—— 见下方 HALF_ADV_NOTE

# 半角档实测步进：DrawHalfWidth / DrawGlyph 半角路径都传 advance=8。
HALF_ADV_NOTE = 8

# 控制码：\x 单字符、{...} 花括号块（{\p} {\\n} 等）、\0A 这类十六进制
CTRL_BACKSLASH = re.compile(r"\\[0-9A-Fa-f]{2}|\\[a-zA-Z]")
CTRL_BRACE = re.compile(r"\{[^{}]*\}")


def strip_controls(s: str) -> str:
    return CTRL_BRACE.sub("", CTRL_BACKSLASH.sub("", s))


def is_cjk(ch: str) -> bool:
    o = ord(ch)
    if 0x4E00 <= o <= 0x9FFF:          # CJK 统一表意
        return True
    if 0x3000 <= o <= 0x303F:          # CJK 标点
        return True
    if 0xFF00 <= o <= 0xFFEF:          # 全角形式
        return True
    if 0x2E80 <= o <= 0x2EFF:          # 部首扩展
        return True
    if 0x3400 <= o <= 0x4DBF:          # 扩展 A
        return True
    if o in (0x2018, 0x2019, 0x201C, 0x201D, 0x2014, 0x2026, 0x3000):
        return True
    return False


def px_of(text: str, cjk: int, half: int) -> int:
    """把一行文本折算成像素宽度（控制码已剔除）。"""
    total = 0
    for ch in text:
        if ch == "\t":
            continue
        if unicodedata.combining(ch):
            continue
        total += cjk if is_cjk(ch) else half
    return total


def split_lines(s: str) -> list[str]:
    """按引擎换行控制码切行：\\n FE / \\p FB / \\l FA（含 {\\p} 花括号写法）。"""
    s = CTRL_BRACE.sub(lambda m: m.group(0).replace("{", "").replace("}", ""), s)
    return re.split(r"\\[npLl]", s)


def ratio(text: str, pred) -> float:
    vis = strip_controls(text)
    if not vis:
        return 0.0
    return sum(1 for c in vis if pred(c)) / len(vis)


def is_kana_or_kanji(ch: str) -> bool:
    o = ord(ch)
    return (0x3040 <= o <= 0x30FF) or (0x4E00 <= o <= 0x9FFF) or (0x3000 <= o <= 0x303F)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--limit", type=int, default=12)
    args = ap.parse_args()

    if not BUILD_JSON.exists():
        print(f"找不到 {BUILD_JSON}", file=sys.stderr)
        return 2

    data = json.loads(BUILD_JSON.read_text(encoding="utf-8"))
    entries = data["entries"]
    print(f"数据源 {BUILD_JSON.relative_to(ROOT)}")
    print(f"entries = {len(entries)}")

    hard = []      # cn>240
    soft = []      # cn>jp
    per_mod = defaultdict(lambda: Counter())
    widest = []    # (cn_px, jp_px, module, line)
    considered = 0
    skipped_binary = 0

    for e in entries:
        tr = e.get("translated") or ""
        orig = e.get("original") or ""
        if not tr:
            continue
        mod = e.get("module") or "?"
        # 🔴 自证闸门：日文原文本身就宽过屏幕 ⇒ 这不是「可显示的文本条」，
        # 而是「补漏剧情」等模块里被当文本收进来的二进制/乱码（实测样例：
        # `ＹギＹギ…` 宽 4088px）。它们不参与排版审计，单独计数。
        jp_lines_all = split_lines(orig)
        if max((px_of(strip_controls(x), JP_ADV, JP_ADV) for x in jp_lines_all),
               default=0) > SCREEN_PX:
            skipped_binary += 1
            continue
        # 🔴 第二道自证闸门：正文侧必须是「真日文」，译文侧必须是「真中文」。
        # 乱码条目（如 `Ｗちでｍ►ｌｍ…` → `９ゲｈ ｚＮｈ…`）两侧都过不了。
        if ratio(orig, is_kana_or_kanji) < 0.5:
            skipped_binary += 1
            continue
        if ratio(tr, is_cjk) < 0.5:
            skipped_binary += 1
            continue
        considered += 1
        jp_lines = jp_lines_all
        cn_lines = split_lines(tr)
        jp_max = max((px_of(strip_controls(x), JP_ADV, JP_ADV) for x in jp_lines),
                     default=0)
        for ln in cn_lines:
            vis = strip_controls(ln)
            w = px_of(vis, CN_ADV_CJK, CN_ADV_HALF)
            if w == 0:
                continue
            widest.append((w, jp_max, mod, vis))
            if w > SCREEN_PX:
                hard.append((w, mod, vis))
                per_mod[mod]["硬溢出"] += 1
            elif w > jp_max:
                soft.append((w, mod, vis))
                per_mod[mod]["版式溢出"] += 1
            else:
                per_mod[mod]["OK"] += 1

    print(f"参与审计的条目 = {considered}")
    print(f"剔除的非文本条（自证闸门：日文原文 >{SCREEN_PX}px / 正文非日文 / 译文非中文） = {skipped_binary}")
    print()
    print("== 结论 ==")
    print(f"  硬溢出（单行 > {SCREEN_PX}px，屏幕装不下） = {len(hard)}")
    print(f"  版式溢出（单行 > 日文原版式宽度）        = {len(soft)}")
    print(f"  合规                                      = {sum(c['OK'] for c in per_mod.values())}")
    print()
    print("== 按模块 ==")
    for mod, c in sorted(per_mod.items(), key=lambda kv: -(kv[1]["硬溢出"] + kv[1]["版式溢出"])):
        tot = sum(c.values())
        if c["硬溢出"] or c["版式溢出"]:
            print(f"  {mod:<16} 硬 {c['硬溢出']:>5} | 版式 {c['版式溢出']:>5} | OK {c['OK']:>5} | 共 {tot}")
    print()
    widest.sort(reverse=True)
    print(f"== 最宽 {args.limit} 行（像素宽 / 日文原宽 / 模块）==")
    for w, jp, mod, ln in widest[: args.limit]:
        flag = "硬" if w > SCREEN_PX else ("溢" if w > jp else "  ")
        print(f"  [{flag}] {w:>4}px (日 {jp:>4}px) {mod:<14} {ln[:34]}")

    if args.verbose and hard:
        print()
        print("== 硬溢明明细 ==")
        for w, mod, ln in sorted(hard, reverse=True)[:60]:
            print(f"  {w:>4}px {mod:<14} {ln}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
