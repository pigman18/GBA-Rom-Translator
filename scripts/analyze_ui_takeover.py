#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ui_takeover.log 判读器（S1.7 配套，2026-09-11）

用法：
    python scripts/analyze_ui_takeover.py [日志路径]
    # 默认：src/util/work/POKEMON_RUBY_AXVJ00/ui_takeover.log

为什么需要它：`[UISUMMARY]` 只在**按 Ctrl-C** 时才打；实际采集常因直接关 mGBA 而缺失。
本脚本改为从逐条 `[UIH]` 行重算，**没有 summary 也能出判读**。

输出四张表（对应 GDB_UI_TAKEOVER.md §4.4 的 A~D）：
  A. ①/② 返回值分布（帧基址：tm3 = tileOffset+602 / tm1 = 512·256 / tm0·2 = 0）
  B. 链核对：⑤ base → ⑥ base 是否 = +9；tileOffset 是否恒 1
  C. cb 来源：⑦⑧ 的 win→tpl→charBase / tileData 分布
  D. 官方用量：tm3 声明 602 实际 2；tm1 font0,3 → 512、余 → 256；框 9 / 14
另附：自检结论（静态/`[UIH-PC!!]`/`[UISUMMARY]`）+ 收尾方式。
"""
from __future__ import annotations

import collections
import pathlib
import re
import sys

DEFAULT_LOG = "src/util/work/POKEMON_RUBY_AXVJ00/ui_takeover.log"
VRAM = 0x06000000

POINTS = ["TextLoadWindowTemplate", "ChsAllocTplMenu", "JpTm1Alloc",
          "MultistepInitWindowTileData", "InitWindowTileData",
          "ChsAllocFrame9", "ChsAllocDlg14", "ChsAllocFrameGfx",
          "ChsAllocDlgGfx", "BgLz77VramSvc"]


def parse(path: pathlib.Path) -> dict[str, list[dict]]:
    """把 [UIH] 块解析成 {点名字: [{'n':序号,'body':[行,…]}, …]}。"""
    by: dict[str, list[dict]] = collections.defaultdict(list)
    cur = None
    for ln in path.read_text(encoding="utf-8", errors="replace").split("\n"):
        m = re.match(r"\[UIH\] (\S+) #(\d+)/(\d+) (.*)$", ln)
        if m:
            cur = {"n": int(m.group(2)), "body": []}
            by[m.group(1)].append(cur)
            continue
        if cur is not None:
            if ln.startswith("[") or ln.startswith("="):
                cur = None
            elif ln.strip():
                cur["body"].append(ln.strip())
    return by


def field(body: list[str], pat: str, default: str = "?") -> str:
    m = re.search(pat, "\n".join(body))
    return m.group(1) if m else default


def regs(body: list[str]) -> dict[str, int]:
    line = next((x for x in body if x.startswith("pc=0x")), "")
    return {k: int(v, 16)
            for k, v in re.findall(r"(r\d+)=0x([0-9A-Fa-f]{8})", line)}


def cb_of(addr: int) -> str:
    if not (VRAM <= addr < VRAM + 0x10000):
        return "—"
    off = addr - VRAM
    return f"cb{off // 0x4000}+0x{off % 0x4000:04X}"


def head(txt: str) -> None:
    print("\n" + "=" * 74)
    print(txt)
    print("=" * 74)


def main(argv: list[str]) -> int:
    repo = pathlib.Path(__file__).resolve().parent.parent
    path = pathlib.Path(argv[1]) if len(argv) > 1 else repo / DEFAULT_LOG
    if not path.is_absolute():
        path = (repo / path)
    if not path.is_file():
        print(f"找不到日志：{path}", file=sys.stderr)
        return 2
    raw = path.read_text(encoding="utf-8", errors="replace")
    by = parse(path)

    # ---------- 自检 ----------
    head("0) 自检")
    static = re.search(r"接管点自检(通过|失败)[^\n]*", raw)
    print("  静态首字节校验 :", static.group(0).strip() if static else "**未见自检行**")
    n_pc = raw.count("[UIH-PC!!]")
    n_hot = raw.count("[UIH-HOT]")
    n_sum = raw.count("[UISUMMARY]")
    print(f"  运行期 pc 自检 : [UIH-PC!!] × {n_pc}   ({'✅ 无挂错' if n_pc == 0 else '🔴 有挂错！'})")
    print(f"  热函数守卫     : [UIH-HOT]  × {n_hot}"
          + ("   ⚠ 被标记的点见下：③④⑩ 触顶属**正常**（每帧/每字/每块图形的高频装载点），"
             "不等于挂错；真正要担心的是 ①/②/⑤⑥ 这类「一窗一次」的点触顶。"
             if n_hot else "   （无点触顶）"))
    print(f"  结算           : {'✅ 有 [UISUMMARY]' if n_sum else '⚠ 无（多半是直接关了 mGBA，未按 Ctrl-C）—— 不影响本脚本判读'}")
    print(f"  命中统计       : " + "  ".join(f"{k}={len(by.get(k, []))}" for k in POINTS))
    for k in POINTS:
        if not by.get(k):
            print(f"    · {k} 0 次（本次未触发）")
    tail = re.search(r"\[停止\][^\n]*|追踪结束[^\n]*", raw)
    print("  收尾           :", tail.group(0).strip() if tail else "?")
    vram_warn = sum(1 for ln in raw.split("\n") if "接管点自检失败" in ln)
    if n_pc == 0 and static and "通过" in static.group(0) and vram_warn == 0:
        print("  ⇒ ✅ 本次采集**无挂错**，参数可判读。")

    # ---------- A ----------
    head("A) ①/② 返回值（＝帧基址，不是 cap）")
    agg = collections.Counter()
    for b in by.get("JpTm1Alloc", []):
        tm = field(b["body"], r"textMode=(\d+)")
        fp = field(b["body"], r"fontNum=(\d+)")
        cap = field(b["body"], r"返回 cap = (\d+)")
        tpl = field(b["body"], r"tpl=(0x[0-9A-Fa-f]+)")
        agg[(tm, fp, cap, tpl)] += 1
    if agg:
        print(f"  {'tm':<3}{'font':<5}{'返回号':<8}{'模板':<14}次数")
        for (tm, fp, cap, tpl), c in sorted(agg.items(), key=lambda x: -x[1]):
            print(f"  {tm:<3}{fp:<5}{cap:<8}{tpl:<14}{c}")
    else:
        print("  （无 JpTm1Alloc 命中）")
    print("  参考：tm3→tileOffset+602=603；tm1/font0,3→512；tm1/余→256；tm0/2→0")

    # ---------- B ----------
    head("B) 链核对：①②返回 →(槽 0202E6F0)→ ⑤ base →(⑤返+9，槽 0202E6F2)→ ⑥")
    f9 = collections.Counter()
    for b in by.get("ChsAllocFrame9", []):
        f9[int(field(b["body"], r"入参 base/tileOffset = (\d+)", "0"))] += 1
    d14 = collections.Counter()
    for b in by.get("ChsAllocDlg14", []):
        d14[int(field(b["body"], r"入参 base/tileOffset = (\d+)", "0"))] += 1
    print(f"  ⑤ base 取值 : {dict(sorted(f9.items()))}")
    print(f"  ⑥ base 取值 : {dict(sorted(d14.items()))}")
    ok = all((v + 9) in d14 for v in f9)
    print(f"  ⇒ ⑥ = ⑤+9 ？{'✅ 成立' if ok else '🔴 不成立（链假设要改）'}")
    offs = set()
    for name in ("TextLoadWindowTemplate", "ChsAllocTplMenu"):
        for b in by.get(name, []):
            offs.add(field(b["body"], r"入参 base/tileOffset = (\d+)"))
    print(f"  ①/② 入参 tileOffset 取值 : {sorted(offs)}   ⇒ {'✅ 恒 1' if offs == {'1'} else '⚠ 非恒 1，S3 要按实际值处理'}")

    # ---------- C ----------
    head("C) cb 来源：⑦⑧ 的 win→tpl（⑤⑥ 的入参里没有 cb）")
    agg = collections.Counter()
    for name in ("ChsAllocFrameGfx", "ChsAllocDlgGfx"):
        for b in by.get(name, []):
            agg[(name,
                 field(b["body"], r"tpl=(0x[0-9A-Fa-f]+)"),
                 field(b["body"], r"charBase=(\d+)"),
                 field(b["body"], r"screenBase=(\d+)"),
                 field(b["body"], r"textMode=(\d+)"),
                 field(b["body"], r"tileData=(0x[0-9A-Fa-f]+)"))] += 1
    if agg:
        print(f"  {'点':<20}{'模板':<14}{'cb':<4}{'sb':<4}{'tm':<4}{'tileData':<13}次数")
        for k, c in sorted(agg.items(), key=lambda x: -x[1]):
            print(f"  {k[0]:<20}{k[1]:<14}{k[2]:<4}{k[3]:<4}{k[4]:<4}{k[5]:<13}{c}")
    else:
        print("  （无 ⑦⑧ 命中）")
    print("  ⇒ cb 的**唯一权威来源 = 模板 tileData（@0xC 绝对 VRAM 指针）**；⑤⑥ 拿不到。")

    # ---------- D ----------
    head("D) 官方用量（＝v10 要换成 vram_alloc 的量）")
    tpl_atlas = collections.Counter()
    for name in ("TextLoadWindowTemplate", "ChsAllocTplMenu"):
        for b in by.get(name, []):
            tpl_atlas[(name, field(b["body"], r"tpl=(0x[0-9A-Fa-f]+)"),
                       field(b["body"], r"charBase=(\d+)"),
                       field(b["body"], r"textMode=(\d+)"),
                       field(b["body"], r"fontNum=(\d+)"),
                       field(b["body"], r"tileData=(0x[0-9A-Fa-f]+)"))] += 1
    print(f"  {'点':<22}{'模板':<14}{'cb':<4}{'tm':<4}{'font':<5}{'tileData':<13}次数")
    for k, c in sorted(tpl_atlas.items(), key=lambda x: -x[1]):
        print(f"  {k[0]:<24}{k[1]:<14}{k[2]:<4}{k[3]:<4}{k[4]:<5}{k[5]:<13}{c}")
    print("  用量表：tm3 → 声明 602 / 实际 2（+框 23）；tm1/font0,3 → 512（256 字×2 tile）；")
    print("          tm1/余 → 256（256 字×1 tile）；⑦ 框 9；⑧ 框 14。全部落 tileData + 号*32。")

    # ---------- S2：层 2（bg_remap = 复刻美版 UpdateBGRegs） ----------
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

    tick = re.findall(r"\[BGMAP\+\] (.*)", raw)
    dump = re.findall(r"^ {2}· (tpl=0x[0-9A-Fa-f]+ .*)$", raw, re.M)
    rows = tick or dump
    src = "增量 [BGMAP+]" if tick else ("结算 [BGMAP]" if dump else "无")
    ent_re = re.compile(
        r"tpl=(0x[0-9A-Fa-f]+) bgNum=(\d+)\((BG\d)\) sb=\s*(\d+) 模板cb=(\d+)"
        r" ⇒ (BG\d)\(层cb=(\d+)\) CNT 0x([0-9A-Fa-f]{4})→0x([0-9A-Fa-f]{4})")
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
                         tcb=int(m.group(5)), b=m.group(8), a=m.group(9), xs=xs, ln=ln)
    if not rows:
        print("  ⚠ 轨迹一行都没有 ⇒ 本次日志不是新版工具采的（或 ROM 没跑到 UI）")
        print("     新版会在跑的过程中就打 [BGMAP+]（不依赖 Ctrl-C），并读实机 BGxCNT。")
    else:
        print(f"  轨迹来源 {src}：命中 {len(seen)} 个模板，非法/未命中 {len(nomatch)} 条")
        print(f"  {'模板':<12}{'bgNum':<7}{'命中层':<7}{'层cb':<6}{'CNT 前→后':<18}零回归 / cb")
        for tpl, d in sorted(seen.items()):
            tcb = d["tcb"]   # 直接读日志（不再硬编码模板表 —— 记账式硬编码一律废弃）
            ok = "✅cb一致" if tcb == d["lcb"] else f"⚠cb差(模板{tcb}≠层{d['lcb']})"
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

    cnts = []
    for m in re.finditer(r"实机 (BG0=0x[0-9A-Fa-f]{4}.*)", raw):
        if m.group(1) not in cnts:
            cnts.append(m.group(1))
    if cnts:
        print("\n  实机 BGxCNT 快照（去重）:")
        for c in cnts:
            print("   ", c)
    calc = []
    for m in re.finditer(r"层2复算: (tpl=0x[0-9A-Fa-f]+ sb=\d+ ⇒ .*)", raw):
        if m.group(1) not in calc:
            calc.append(m.group(1))
    if calc:
        print("\n  Python 侧独立复算（与 hook 轨迹互为交叉验证）:")
        for c in calc:
            print("   ", c)

    # ---------- 交叉：窗口对象 / 模板集合 ----------
    head("E) 附加：window 对象 与 模板全集")
    wins = collections.Counter()
    for name in by:
        for b in by[name]:
            w = field(b["body"], r"win=(0x[0-9A-Fa-f]+)")
            if w != "?":
                wins[w] += 1
    print("  win 对象:", dict(wins) or "（无 win 字段）")
    alltpl = sorted({field(b["body"], r"tpl=(0x[0-9A-Fa-f]+)")
                     for name in by for b in by[name]
                     if field(b["body"], r"tpl=(0x[0-9A-Fa-f]+)") != "?"})
    print(f"  出现的模板 {len(alltpl)} 个: {', '.join(alltpl)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
