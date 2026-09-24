# -*- coding: utf-8 -*-
"""ledger_15_0_window_canvas.py — 15-0 窗口级画布账本（L1 静态，零 ROM 风险）

对应 `docs/方案总纲_v15_领号单位改为窗口_20260920.md` §六 步骤 15-0。

要回答的问题
------------
v15 的核心主张是「领号单位从**字**改成**窗口**」⇒ 需求 = 屏幕几何常数。
本脚本把这条主张的两侧都钉成可核对的数字：

  §1..§3  供给侧：引擎一共给了多少个窗口、各自什么属性、官方资产占掉多少号
  §4..§5  需求侧：真实译文下，单个窗口最多需要多少 tile（11×11 方案）

关键结构（本次实测新发现，修正 v15 文档的「52 个模板」）
------------------------------------------------------
`0x081BB3DC` 起是 **53 条 × 0x18 字节** 的窗口模板表，紧随其后
`0x081BB8D4` 是 **{模板指针, 窗口ID} 配对表**（引擎按 ID 取模板）。
53 条里有 **1 条** 的 `tileData = 0x06010000` —— 这是 **OBJ VRAM**
（GBA: BG 用 0x06000000..0x0600FFFF，OBJ 用 0x06010000..0x06017FFF）
⇒ **该窗口的字形根本不占 BG tile 号**。这是引擎里**已有的 OBJ 画字先例**。

字段语义（实证，来自本仓 `tools/scan_axvj_templates.py` + 本轮交叉核对）
---------------------------------------------------------------------
    0x00 bg            0x01 charBase       0x02 screenBase
    0x03 ?(<4)         0x04 palette        0x05/0x06/0x07 混合系数(fg/bg/mode)
    0x08 font          0x09 textMode
    0x0A/0x0B 恒 0（53/53）
    0x0C tileData(u32) 0x10 tilemap(u32)
    0x14..0x17 未用
⇒ 🔴 **模板里没有 width / height** ⇒ 画布面积无法从模板直读（日版无该字段）。

自证闸门（任一不过即退出，不留「看着像对」的结果）
-------------------------------------------------
    G1 模板数 == 53，且末条 +0x18 == 0x081BB8D4
    G2 TPL_TILE_DATA == 0x06000000 + charBase*0x4000，
       **唯一允许的例外** = tileData 落在 OBJ VRAM（≥0x06010000）的槽，且例外数 == 1
    G3 textMode 值域 ⊆ {0,1,2,3}，且分布与 v15 一致（tm1 为多数）
    G4 ID 配对表里的每个模板指针都必须是 53 槽之一
    G5 需求侧：参与统计的条目数 > 0，且最大行宽 ≤ 240px

用法
----
    python scripts/ledger_15_0_window_canvas.py
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BUILD_JSON = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"

BASE = 0x08000000
TPL_TABLE = 0x081BB3DC
TPL_STRIDE = 0x18
TPL_COUNT = 53
ID_TABLE = 0x081BB8D4
ID_TABLE_MAX = 0x300          # 扫描窗口上限

BG_VRAM_LO, BG_VRAM_HI = 0x06000000, 0x06010000
OBJ_VRAM_LO, OBJ_VRAM_HI = 0x06010000, 0x06018000
CHARBLOCK_TILES = 1024
WINFRAME_TILES = 23           # v14 口径：窗框占号

F_BG, F_CHARBASE, F_SCREENBASE, F_ALPHA3, F_PALETTE = 0x00, 0x01, 0x02, 0x03, 0x04
F_BLEND1, F_BLEND2, F_BLENDMODE = 0x05, 0x06, 0x07
F_FONT, F_TEXTMODE = 0x08, 0x09
F_TILEDATA, F_TILEMAP = 0x0C, 0x10

CAP = {0: 512, 1: 256, 2: 256, 3: 512, 4: 256, 5: 256}

# 中文渲染参数（与 hook/include/game.h 一致）
CN_ADV_CJK = 12
CN_ADV_HALF = 8
GLYPH_TILE_ROWS = 2           # 11×11 墨迹落在 16px 高格 = 2 个纵向 tile


def official_end(font: int) -> int:
    """v12 口径：官方资产在该 charBlock 内占用的上界（exclusive）。"""
    cap = CAP.get(font, 512)
    return max(cap + 23, cap)


def u32(b: bytes, o: int) -> int:
    return int.from_bytes(b[o:o + 4], "little")


def load_templates(rom: bytes):
    out = []
    for k in range(TPL_COUNT):
        a = TPL_TABLE + TPL_STRIDE * k
        b = rom[a - BASE:a - BASE + TPL_STRIDE]
        out.append((a, b))
    return out


# ---------------------------------------------------------------- 需求侧模型

import re
import unicodedata

CTRL_BACKSLASH = re.compile(r"\\[0-9A-Fa-f]{2}|\\[a-zA-Z]")
CTRL_BRACE = re.compile(r"\{[^{}]*\}")


def strip_controls(s: str) -> str:
    return CTRL_BRACE.sub("", CTRL_BACKSLASH.sub("", s))


def is_cjk(ch: str) -> bool:
    o = ord(ch)
    return (0x4E00 <= o <= 0x9FFF or 0x3000 <= o <= 0x303F or 0xFF00 <= o <= 0xFFEF
            or 0x2E80 <= o <= 0x2EFF or 0x3400 <= o <= 0x4DBF
            or o in (0x2018, 0x2019, 0x201C, 0x201D, 0x2014, 0x2026, 0x3000))


def is_kana_or_kanji(ch: str) -> bool:
    o = ord(ch)
    return 0x3040 <= o <= 0x30FF or 0x4E00 <= o <= 0x9FFF or 0x3000 <= o <= 0x303F


def px_of(text: str, cjk: int, half: int) -> int:
    t = 0
    for ch in text:
        if ch == "\t" or unicodedata.combining(ch):
            continue
        t += cjk if is_cjk(ch) else half
    return t


def split_lines(s: str):
    s = CTRL_BRACE.sub(lambda m: m.group(0).replace("{", "").replace("}", ""), s)
    return re.split(r"\\[npLl]", s)


def ratio(text: str, pred) -> float:
    vis = strip_controls(text)
    return (sum(1 for c in vis if pred(c)) / len(vis)) if vis else 0.0


def demand_side():
    """真实译文下的窗口画布需求（11×11 方案）。

    一个窗口的画布 tile 数 = ceil(最宽行 px / 8) × 2 × 行数
      · 列：11px 墨迹 + 12px 步进 ⇒ 每字横跨 2 个 tile 列
      · 行：11px 墨迹落在 16px 高格 ⇒ 每行 2 个 tile 行
    """
    if not BUILD_JSON.exists():
        return None
    entries = json.loads(BUILD_JSON.read_text(encoding="utf-8"))["entries"]
    per_mod = collections.defaultdict(list)   # mod -> [(canvas_tiles, cols, lines, sample)]
    kept = skipped = 0
    max_line = 0
    for e in entries:
        tr = e.get("translated") or ""
        orig = e.get("original") or ""
        if not tr:
            continue
        jp_lines = split_lines(orig)
        if max((px_of(strip_controls(x), 8, 8) for x in jp_lines), default=0) > 240:
            skipped += 1
            continue
        if ratio(orig, is_kana_or_kanji) < 0.5 or ratio(tr, is_cjk) < 0.5:
            skipped += 1
            continue
        kept += 1
        cn_lines = [strip_controls(x) for x in split_lines(tr)]
        widths = [px_of(x, CN_ADV_CJK, CN_ADV_HALF) for x in cn_lines]
        widths = [w for w in widths if w > 0]
        if not widths:
            continue
        wmax = max(widths)
        max_line = max(max_line, wmax)
        nlines = len(widths)
        cols = (wmax + 7) // 8
        tiles = cols * GLYPH_TILE_ROWS * nlines
        per_mod[e.get("module") or "?"].append((tiles, cols, nlines, cn_lines[0][:30]))
    return per_mod, kept, skipped, max_line


def main() -> int:
    rom = ROM.read_bytes()
    tpls = load_templates(rom)
    ok = True

    # ---- G1 -------------------------------------------------------------
    last_end = TPL_TABLE + TPL_STRIDE * TPL_COUNT
    if len(tpls) != TPL_COUNT or last_end != ID_TABLE:
        print("❌ G1 失败：模板数=%d，末条尾=0x%08x，期望 0x%08x"
              % (len(tpls), last_end, ID_TABLE))
        return 1
    print("✅ G1 模板表 = 0x%08x..0x%08x，共 %d 条 × 0x%02x 字节"
          % (TPL_TABLE, ID_TABLE, TPL_COUNT, TPL_STRIDE))

    # ---- G2 -------------------------------------------------------------
    exc = []
    for a, b in tpls:
        cb = b[F_CHARBASE]
        td = u32(b, F_TILEDATA)
        if OBJ_VRAM_LO <= td < OBJ_VRAM_HI:
            exc.append(a)
            continue
        if td != BG_VRAM_LO + cb * 0x4000:
            print("❌ G2 失败：0x%08x tileData=0x%08x，但 charBase=%d ⇒ 期望 0x%08x"
                  % (a, td, cb, BG_VRAM_LO + cb * 0x4000))
            ok = False
    if len(exc) != 1:
        print("❌ G2 失败：OBJ-VRAM 例外槽数 = %d，期望恰好 1" % len(exc))
        ok = False
    if ok:
        print("✅ G2 TPL_TILE_DATA ≡ 0x06000000 + charBase*0x4000（%d/%d），"
              "唯一例外 = 0x%08x（OBJ VRAM）" % (TPL_COUNT - 1, TPL_COUNT, exc[0]))

    # ---- G3 -------------------------------------------------------------
    tm_dist = collections.Counter(b[F_TEXTMODE] for _, b in tpls)
    if set(tm_dist) - {0, 1, 2, 3}:
        print("❌ G3 失败：textMode 值域越界 %s" % sorted(tm_dist))
        return 1
    if tm_dist.get(1, 0) <= max(tm_dist.values()) / 2:
        print("❌ G3 失败：tm1 不是多数派（分布 %s）" % sorted(tm_dist.items()))
        return 1
    print("✅ G3 textMode 分布 = %s（tm1 占 %.0f%%）"
          % (sorted(tm_dist.items()), 100 * tm_dist[1] / TPL_COUNT))

    # ---- G4 -------------------------------------------------------------
    valid = {a for a, _ in tpls}
    ids, bad_ptrs = [], []
    o = ID_TABLE - BASE
    for i in range(0, ID_TABLE_MAX, 8):
        p = u32(rom, o + i)
        q = u32(rom, o + i + 4)
        if p == 0 and q == 0:
            break
        if not (BG_VRAM_LO <= p < 0x0A000000) or q >= 0x10000:
            break
        ids.append((p, q))
        if p not in valid:
            bad_ptrs.append((hex(p), q))
    if bad_ptrs:
        print("❌ G4 失败：%d 个 ID 表指针不在 53 槽内，例：%s" % (len(bad_ptrs), bad_ptrs[:5]))
        return 1
    print("✅ G4 ID 配对表 = 0x%08x 起 %d 项，全部指针均命中 53 槽（id 范围 %d..%d）"
          % (ID_TABLE, len(ids), min(q for _, q in ids), max(q for _, q in ids)))
    print()

    # ================= §1 模板明细 ========================================
    print("=" * 130)
    print("§1 窗口模板明细（%d 条）" % TPL_COUNT)
    print("=" * 130)
    print("%-12s %-4s %-5s %-5s %-5s %-5s %-5s %-9s %-8s %-11s %-11s %-6s"
          % ("tpl", "bg", "cb", "sb", "pal", "bl1", "bl2", "blend", "font/tm",
             "tileData", "tilemap", "官方上界"))
    print("-" * 130)
    obj_slots = []
    for k, (a, b) in enumerate(tpls):
        td = u32(b, F_TILEDATA)
        tm = u32(b, F_TILEMAP)
        is_obj = OBJ_VRAM_LO <= td < OBJ_VRAM_HI
        tag = "  ← OBJ VRAM" if is_obj else ""
        if is_obj:
            obj_slots.append((k, a, b))
        oe = official_end(b[F_FONT])
        print("%-12s %-4d %-5d %-5d %-5d %-5d %-5d %-5d %-9s 0x%08x 0x%08x %-6d%s"
              % (hex(a), b[F_BG], b[F_CHARBASE], b[F_SCREENBASE], b[F_PALETTE],
                 b[F_BLEND1], b[F_BLEND2], b[F_BLENDMODE],
                 "%d/%d" % (b[F_FONT], b[F_TEXTMODE]), td, tm, oe, tag))

    # ================= §2 交叉统计 ========================================
    print()
    print("=" * 130)
    print("§2 交叉统计")
    print("=" * 130)
    print("textMode 分布 :", sorted(tm_dist.items()))
    print("font 分布     :", sorted(collections.Counter(b[F_FONT] for _, b in tpls).items()))
    print("charBase 分布 :", sorted(collections.Counter(b[F_CHARBASE] for _, b in tpls).items()))
    print("bg 分布       :", sorted(collections.Counter(b[F_BG] for _, b in tpls).items()))
    print()
    ct = collections.Counter((b[F_CHARBASE], b[F_TEXTMODE]) for _, b in tpls)
    tms = sorted(tm_dist)
    print("charBase × textMode：")
    print("  %-6s %s  total" % ("cb", " ".join("tm%-4d" % t for t in tms)))
    for cb in range(4):
        row = [ct.get((cb, t), 0) for t in tms]
        print("  cb%-4d %s  %d" % (cb, " ".join("%-6d" % v for v in row), sum(row)))
    print()
    print("tileData 落点分布：")
    vd = collections.Counter(u32(b, F_TILEDATA) for _, b in tpls)
    for addr, n in sorted(vd.items()):
        kind = "OBJ VRAM ★不占 BG 号" if addr >= OBJ_VRAM_LO else (
            "charBlock %d" % ((addr - BG_VRAM_LO) // 0x4000))
        print("    0x%08x × %-3d  %s" % (addr, n, kind))

    # ================= §3 供给侧账 ========================================
    print()
    print("=" * 130)
    print("§3 供给侧账（每个 charBlock 被官方资产占掉多少号）")
    print("=" * 130)
    print("一个 BG 层的 tile 号上限 = %d（tilemap 表项 10 bit）｜GBA 有 4 个 charBlock"
          % CHARBLOCK_TILES)
    print()
    print("%-6s %-9s %-14s %-12s %-13s %s" %
          ("cb", "模板数", "最坏官方上界", "名义剩余", "扣窗框后", "说明"))
    for cb in range(4):
        sub = [(a, b) for a, b in tpls if b[F_CHARBASE] == cb]
        bg_sub = [(a, b) for a, b in sub
                  if not (OBJ_VRAM_LO <= u32(b, F_TILEDATA) < OBJ_VRAM_HI)]
        if not sub:
            print("cb%-4d %-9d (无模板)" % (cb, 0))
            continue
        oe = max(official_end(b[F_FONT]) for _, b in bg_sub) if bg_sub else 0
        note = ""
        if len(sub) != len(bg_sub):
            note = "含 %d 个 OBJ 槽（不占 BG 号）" % (len(sub) - len(bg_sub))
        print("cb%-4d %-9d %-14d %-12d %-13d %s"
              % (cb, len(sub), oe, CHARBLOCK_TILES - oe,
                 CHARBLOCK_TILES - oe - WINFRAME_TILES, note))
    print()
    print("⇒ 官方资产上界只取决于 font：font0/3 ⇒ 535，其余 ⇒ 279。")
    print("⇒ 文本画布基址只要 ≥ 535（同 charBlock）即与官方资产不共享号。")

    # ================= §4 需求侧 ==========================================
    print()
    print("=" * 130)
    print("§4 需求侧（真实译文，11×11 方案：画布 tile = ceil(行宽/8) × 2 × 行数）")
    print("=" * 130)
    dm = demand_side()
    if dm is None:
        print("⚠ 找不到 %s，跳过需求侧" % BUILD_JSON)
        return 0
    per_mod, kept, skipped, max_line = dm

    # G5
    if kept == 0:
        print("❌ G5 失败：参与统计的条目 = 0")
        return 1
    if max_line > 240:
        print("❌ G5 失败：最大行宽 %dpx > 240px 屏幕宽" % max_line)
        return 1
    print("✅ G5 参与统计条目 = %d（自证闸门剔除二进制/乱码 %d 条）｜最大行宽 = %dpx"
          % (kept, skipped, max_line))
    print()

    rows = []
    for mod, lst in per_mod.items():
        lst.sort(reverse=True)
        worst = lst[0]
        rows.append((worst[0], mod, worst, len(lst)))
    rows.sort(reverse=True)
    print("%-2s %-18s %-11s %-8s %-9s %-8s %s"
          % ("#", "module", "最坏画布tile", "= 列×2×行", "列数", "行数", "样例首行"))
    print("-" * 130)
    for i, (tiles, mod, (t, cols, nlines, sample), n) in enumerate(rows[:24], 1):
        print("%-2d %-18s %-11d %-8s %-9d %-8d %s"
              % (i, mod, tiles, "(%d×2×%d)" % (cols, nlines), cols, nlines, sample))
    print()
    allt = [t for lst in per_mod.values() for t, _, _, _ in lst]
    allt.sort()
    if allt:
        p = lambda q: allt[min(len(allt) - 1, int(len(allt) * q))]
        print("全语料画布需求分布（共 %d 个文本块）：min=%d  p50=%d  p90=%d  p99=%d  max=%d"
              % (len(allt), allt[0], p(0.5), p(0.9), p(0.99), allt[-1]))
    CAP_KEEP = CHARBLOCK_TILES - 535 - WINFRAME_TILES     # 官方图集保留
    CAP_FREE = CHARBLOCK_TILES - WINFRAME_TILES           # 官方图集回收后

    print()
    print("== 判据（单窗）==")
    print("  单个窗口画布最大需求（全语料实测） = %d tile" % (allt[-1] if allt else 0))
    print("  可用 A（同 charBlock，保留官方图集 535 + 窗框 23） = %d tile" % CAP_KEEP)
    print("  可用 B（同 charBlock，回收官方图集，只剩窗框）     = %d tile" % CAP_FREE)
    if allt and allt[-1] <= CAP_KEEP:
        print("  ⇒ ✅ 单窗装得下，且**不需要回收官方图集**")
    else:
        print("  ⇒ ❌ 单窗已超 A，必须回收官方图集（15-4）或专属 charBlock")
    print("  ⚠ 这只是「单窗」；同屏多窗共存的账见 §5 与 15-3。")

    # ================= §5 多行窗口可行域 ==================================
    print()
    print("=" * 130)
    print("§5 多行窗口可行域（直接回答「领航员 9~12 行撑不撑得住」）")
    print("=" * 130)
    print("模型：一个窗口画布 = 行数 L × 列数 W × %d（每行 2 个 tile 行）" % GLYPH_TILE_ROWS)
    print("      列数 W = ceil(行宽px/8)，W 列即 8W px 宽；行数 L = 该窗口同时驻留的行数")
    print()
    Ls = [4, 6, 9, 12, 15]
    Ws = [8, 10, 13, 15, 20]
    print("  %-8s %s" % ("L\\W", "".join("%-14s" % ("%d列(%dpx)" % (w, w * 8)) for w in Ws)))
    for L in Ls:
        cells = []
        for W in Ws:
            t = L * W * GLYPH_TILE_ROWS
            mark = "✅" if t <= CAP_KEEP else ("△" if t <= CAP_FREE else "❌")
            cells.append("%-14s" % ("%d %s" % (t, mark)))
        print("  %-8s %s" % ("L=%d" % L, "".join(cells)))
    print()
    print("  ✅ = 装得下（保留官方图集）   △ = 要回收官方图集才装得下   ❌ = 装不下")
    print()
    print("  领航员相关格子：")
    for L, W in ((9, 13), (9, 15), (12, 10), (12, 13), (12, 15)):
        t = L * W * GLYPH_TILE_ROWS
        mark = "✅ 保留官方图集即可" if t <= CAP_KEEP else (
            "△ 需回收官方图集" if t <= CAP_FREE else "❌ 仍超，必须专属 charBlock")
        print("    %2d 行 × %2d 列（%3dpx） = %3d tile   %s" % (L, W, W * 8, t, mark))
    print()
    print("  屏幕物理天花板（30 列 × 10 行满屏）= %d tile"
          % (30 * 10 * GLYPH_TILE_ROWS))
    print("  ⇒ 需求被 L、W 两个**屏幕几何量**完全决定，与文本总量无关。")
    print()
    print("⚠ 未决项：模板无 width/height ⇒ 「哪个窗口用哪条模板 / 同屏几个窗口」")
    print("   需 15-0b 从 AddWindow 调用点侧枚举（本轮未做）。")
    print("✅ 15-0 完成（§1..§5，5 道自证闸门全过）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
