#!/usr/bin/env python3
"""evidence_gate.py — 改码/编译前的硬门槛。

## 为什么存在

2026-11-18 的事故复盘（52 轮未修好一个 4 字菜单 BUG）：

1. 反复「猜公式 → 改 → 跑 bot → 看图 → 猜错」，从不用仓库里的硬证据通道。
2. 跑了 GDB，但只把 `textMode=0 fontNum=3` 当标签抄下来，
   没意识到 **textMode 是决定落址算法的分派键** —— 而
   `docs/POKEMON_RUBY_AXVJ00.md` §4「textMode：7 项分发表」写得清清楚楚。
3. 错误假设一旦形成，会筛掉能纠正它的信息，且自己察觉不到。
4. 没有「我修不了」的止损点，于是一直换假设试到 52 轮。

约束只能靠硬门槛。本脚本实现四条规则，缺任一条就拒绝编译/改码。

## 四条规则

**R1 三类证据齐全**（static / gdb / bot），且都晚于上次构建。

**R2 先预测后验证**（最重要）：改码前必须写下可证伪的数字预测，
    构建后自动比对 GDB 实测值。不符 → 记为 FAILED 并写进台账。

**R3 三连失败即停**：同一目标连续 3 次预测 FAILED → 拒绝继续，
    强制输出「我修不了」而不是继续换假设。

**R4 先读结构再动手**：读机制文档前必须先列出它的全部章节标题，
    标题里出现「分发表 / 矩阵 / 分派 / 表」等词，必须逐项读完。
    以「已列标题 + 已引用分发表原文」作为凭据。

## 用法

    # 读文档前：列出章节标题（R4 第一步）
    python scripts/evidence_gate.py --toc docs/POKEMON_RUBY_AXVJ00.md

    # 确认要读的分发表章节（R4 第二步，必须带原文引用）
    python scripts/evidence_gate.py --cite-doc docs/POKEMON_RUBY_AXVJ00.md \
        --section "4. textMode" --quote "按 win[0x0A] 查 FontFuncTable"

    # 记录三类证据（R1）
    python scripts/evidence_gate.py --record static --detail "..."
    python scripts/evidence_gate.py --record gdb    --detail "..."
    python scripts/evidence_gate.py --record bot    --detail "..."

    # 写预测（R2）—— 改码前
    python scripts/evidence_gate.py --predict "第3个字的tile号" \
        --probe GridTile --field u --expect 0x009a

    # 构建后验证（R2）—— 解析 gdb_probe.log 自动比对
    python scripts/evidence_gate.py --verify work/.../translated/gdb_probe.log

    # 编译前检查（build.bat 调用）
    python scripts/evidence_gate.py --check

    # 查看状态
    python scripts/evidence_gate.py --status
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK_SRC = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "hook" / "src"
HOOK_INC = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "hook" / "include"

WORK = ROOT / "work"
LOG = WORK / ".evidence_log.jsonl"
TOKEN = WORK / ".evidence_token"
PRED = WORK / ".prediction.json"
LEDGER = WORK / ".prediction_ledger.jsonl"
DOCS = WORK / ".docs_read.jsonl"

KINDS = ("static", "gdb", "bot")
KIND_LABEL = {"static": "静态反汇编", "gdb": "GDB 运行时探针", "bot": "bot 场景采集"}
KIND_HOWTO = {
    "static": 'python scripts\\evidence_gate.py --record static --detail "objdump <addr>"',
    "gdb": 'python scripts\\evidence_gate.py --record gdb --detail "bot --gdb InitTextPrinter"',
    "bot": 'python scripts\\evidence_gate.py --record bot --detail "<scene> N pairs"',
}

# R4：这些词出现在章节标题里，说明该节描述的是「分派 / 映射 / 矩阵」类结构，
# 必须逐项读完才能动手 —— 2026-11-18 就是漏了「7 项分发表」这一节。
STRUCT_WORDS = ("分发表", "分派", "矩阵", "对照表", "映射表", "表")

MAX_CONSECUTIVE_FAIL = 3   # R3


def _now() -> float:
    return time.time()


def _append_jsonl(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _last_build_time() -> float:
    """上次**成功构建**的时间。

    token 由 --check 在放行时写出，构建脚本随后才真正跑 gcc。
    若直接拿 token 的 mtime 当基线，--check 一写就把基线推高，
    刚记录的证据立刻变成「早于上次构建」而失效（实测踩到）。
    所以把基线存进 token 内容，由构建成功后的 --mark-built 更新。
    """
    try:
        data = json.loads(TOKEN.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0.0
    v = data.get("built_at")
    return float(v) if isinstance(v, (int, float)) else 0.0


def mark_built() -> int:
    """构建成功后调用：把基线推到当前时刻，下一轮需要重新取证。"""
    WORK.mkdir(parents=True, exist_ok=True)
    TOKEN.write_text(json.dumps({"t": _now(), "built_at": _now()}),
                     encoding="utf-8")
    print("[evidence] 已标记构建完成，下一轮需重新取证")
    return 0


# ---------------------------------------------------------------- R1 证据

def record(kind: str, detail: str) -> int:
    if kind not in KINDS:
        print(f"未知证据类型 {kind!r}，只接受 {KINDS}")
        return 2
    _append_jsonl(LOG, {"t": _now(), "kind": kind, "detail": detail})
    print(f"[evidence] +{kind}: {detail}")
    return 0


def _fresh_evidence() -> dict[str, dict]:
    since = _last_build_time()
    out: dict[str, dict] = {}
    for r in _read_jsonl(LOG):
        if not isinstance(r.get("t"), (int, float)):
            continue
        if r["t"] <= since:
            continue
        if r.get("kind") in KINDS:
            out[r["kind"]] = r
    return out


# ---------------------------------------------------------- R2 预测验证

def predict(claim: str, probe: str, field: str, expect: str) -> int:
    PRED.parent.mkdir(parents=True, exist_ok=True)
    PRED.write_text(
        json.dumps(
            {"t": _now(), "claim": claim, "probe": probe,
             "field": field, "expect": expect, "status": "pending"},
            ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"[predict] 待验证：{claim} = {expect}")
    print(f"          probe={probe} field={field}")
    print("          改码 → 构建 → 跑 bot → --verify 自动比对")
    return 0


def _parse_probe_values(log_path: Path, probe: str, field: str) -> list[str]:
    """从 gdb_probe.log 里抽某个探针某个字段的实测值（十六进制字符串）。"""
    try:
        raw = log_path.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return []

    vals: list[str] = []
    # 优先匹配 handler 自定义格式 "[GT] ... u=0x0094"
    for m in re.finditer(rf"\b{re.escape(field)}=(0x[0-9a-fA-F]+|\d+)", raw):
        vals.append(m.group(1).lower())
    if vals:
        return vals

    # 退回到通用寄存器行：PC=0x... r0=0x... r1=0x...
    for line in raw.splitlines():
        if probe and probe not in line and "PC=" not in line:
            continue
        m = re.search(rf"\b{re.escape(field)}=(0x[0-9a-fA-F]+)", line)
        if m:
            vals.append(m.group(1).lower())
    return vals


def verify(log_path: Path) -> int:
    if not PRED.is_file():
        print("[verify] 没有待验证的预测（--predict 先写一条）")
        return 2
    try:
        pred = json.loads(PRED.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("[verify] 预测文件损坏")
        return 2

    expect = str(pred.get("expect", "")).lower()
    field = str(pred.get("field", ""))
    probe = str(pred.get("probe", ""))

    vals = _parse_probe_values(log_path, probe, field)
    if not vals:
        print(f"[verify] 在 {log_path.name} 里找不到 field={field!r} 的实测值")
        print("         → 探针可能没命中，或地址/字段名写错")
        rec = {**pred, "t": _now(), "status": "NO_DATA", "actual": None}
        _append_jsonl(LEDGER, rec)
        pred["status"] = "NO_DATA"
        PRED.write_text(json.dumps(pred, ensure_ascii=False, indent=1),
                        encoding="utf-8")
        return 1

    hit = expect in vals
    actual = vals[0] if not hit else expect
    status = "PASS" if hit else "FAILED"

    print(f"[verify] {pred.get('claim')}")
    print(f"         预期 {expect} / 实测 {actual}  → {status}")
    if not hit:
        uniq = sorted(set(vals))[:8]
        print(f"         实测值集合（前 8）：{uniq}")

    rec = {**pred, "t": _now(), "status": status, "actual": actual}
    _append_jsonl(LEDGER, rec)
    pred["status"] = status
    pred["actual"] = actual
    PRED.write_text(json.dumps(pred, ensure_ascii=False, indent=1),
                    encoding="utf-8")

    consec = _consecutive_failures()
    if consec >= MAX_CONSECUTIVE_FAIL:
        print()
        print("=" * 68)
        print(f"  [STOP] 连续 {consec} 次预测失败 —— 按 R3 必须停止")
        print("=" * 68)
        print()
        print("  你已经在同一个点上连续猜错，继续换假设只会烧轮次。")
        print("  正确做法：明确写出「我修不了」，并把已经确认的事实交给用户，")
        print("  而不是再改一版代码去试。")
        print()
    return 0 if hit else 1


def _consecutive_failures() -> int:
    n = 0
    for r in reversed(_read_jsonl(LEDGER)):
        if r.get("status") == "FAILED":
            n += 1
        else:
            break
    return n


# -------------------------------------------------- R4 先读结构再动手

def toc(doc: str) -> int:
    p = Path(doc)
    if not p.is_absolute():
        p = ROOT / doc
    if not p.is_file():
        print(f"[toc] 文件不存在：{p}")
        return 2
    heads = []
    for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace")
                               .splitlines(), 1):
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            heads.append((len(m.group(1)), i, m.group(2).strip()))
    if not heads:
        print("[toc] 没找到 markdown 标题")
        return 1

    print(f"[toc] {doc} 共 {len(heads)} 个章节")
    print()
    risky = []
    for level, lineno, title in heads:
        mark = ""
        if level <= 3 and any(w in title for w in STRUCT_WORDS):
            mark = "   <<< 结构/分派类，必须逐项读完"
            risky.append((lineno, title))
        print(f"  {'#' * level} L{lineno}: {title}{mark}")

    _append_jsonl(DOCS, {"t": _now(), "doc": str(doc),
                         "headings": len(heads),
                         "risky": [t for _, t in risky]})

    if risky:
        print()
        print(f"[toc] 发现 {len(risky)} 个结构类章节：")
        for lineno, title in risky:
            print(f"        L{lineno}: {title}")
        print()
        print("  这些章节描述的是「按某个字段分派到不同实现」的机制。")
        print("  2026-11-18 就是漏读了「textMode：7 项分发表」这一节，")
        print("  导致 52 轮都在用错误假设猜落址公式。")
        print()
        print("  读完请用 --cite-doc 记录原文引用再动手：")
        print(f'    python scripts\\evidence_gate.py --cite-doc {doc} '
              f'--section "{risky[0][1]}" --quote "<原文一句>"')
    return 0


def cite_doc(doc: str, section: str, quote: str) -> int:
    if not quote or len(quote.strip()) < 4:
        print("[cite] --quote 太短，必须是真的原文引用")
        return 2
    _append_jsonl(DOCS, {"t": _now(), "doc": doc, "section": section,
                         "quote": quote.strip()})
    print(f"[cite] {doc} §{section}")
    print(f'       "{quote.strip()}"')
    return 0


# ------------------------------------- R5 覆盖度清单（机器可核对）

def scan_windows(log: str) -> int:
    """从 gdb_probe.log 扫出所有出现过的窗口模板 + textMode + fontNum。

    2026-11-18 事故：ruby 有 53 个窗口模板，我只验证了其中 4 个
    （且 4 个恰好同 textMode），却当成「全部验证过」继续往下做。
    覆盖度必须由机器从日志统计，不能自报。
    """
    p = Path(log)
    if not p.is_absolute():
        p = ROOT / log
    if not p.is_file():
        print(f"[scan] 日志不存在：{p}")
        return 2

    raw = p.read_bytes().decode("utf-8", errors="replace")
    seen: dict[str, dict] = {}
    for line in raw.splitlines():
        m = re.search(r"模板@(0x[0-9a-fA-F]+)", line)
        if not m:
            continue
        tpl = m.group(1).lower()
        tm = re.search(r"textMode=(\d+)", line)
        fn = re.search(r"font=(\d+)", line)
        rec = seen.setdefault(tpl, {"tpl": tpl, "textModes": set(), "fonts": set()})
        if tm:
            rec["textModes"].add(int(tm.group(1)))
        if fn:
            rec["fonts"].add(int(fn.group(1)))

    if not seen:
        print("[scan] 日志里没有窗口模板记录（探针没命中 InitTextPrinter？）")
        return 1

    out = WORK / ".window_coverage.json"
    data = {
        "t": _now(),
        "log": str(log),
        "templates": [
            {"tpl": v["tpl"],
             "textModes": sorted(v["textModes"]),
             "fonts": sorted(v["fonts"])}
            for v in sorted(seen.values(), key=lambda x: x["tpl"])
        ],
    }
    WORK.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    tms = sorted({tm for v in seen.values() for tm in v["textModes"]})
    print(f"[scan] 共发现 {len(seen)} 个窗口模板，textMode 覆盖 {tms}")
    print()
    for v in sorted(seen.values(), key=lambda x: x["tpl"]):
        print(f"  {v['tpl']}  textMode={sorted(v['textModes'])}  "
              f"font={sorted(v['fonts'])}")
    print()
    print("  ★ 只有你**实际验证过**的模板/ textMode 才能声称支持。")
    print("    用 --claim 声明本次要覆盖哪些，--check 会核对清单。")
    return 0


def claim(what: str, value: str) -> int:
    """声明本次改动覆盖范围（必须与 .window_coverage.json 对得上）。"""
    p = WORK / ".scope_claim.json"
    data = {}
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
    data.setdefault("t", _now())
    if what == "textmode":
        data["textModes"] = [int(x) for x in value.split(",") if x.strip()]
    elif what == "template":
        data["templates"] = [x.strip().lower() for x in value.split(",") if x.strip()]
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[claim] {what} = {value}")
    return 0


# ------------------------------------- R6 假设作废（冲突数据必须显式处理）

def falsify(reason: str, evidence: str) -> int:
    """显式作废当前假设。写入台账后，R2 的 PASS 预测不再作数。"""
    if not reason.strip():
        print("[falsify] 必须写明哪条假设被推翻")
        return 2
    _append_jsonl(WORK / ".falsified.jsonl",
                  {"t": _now(), "reason": reason, "evidence": evidence})
    # 当前预测作废
    if PRED.is_file():
        try:
            pred = json.loads(PRED.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pred = {}
        pred["status"] = "FALSIFIED"
        PRED.write_text(json.dumps(pred, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(f"[falsify] 假设作废：{reason}")
    if evidence:
        print(f"          依据：{evidence}")
    print("          → 必须换假设，不能修补旧假设继续走")
    return 0


# ------------------------------------- R7 文档冻结（禁止改旧文档自证）

def guard_doc(rel_path: str) -> int:
    """检查某个 docs/ 文件是否被标记为「已冻结」。

    2026-11-18 事故：只验证了 4 个 textMode 就把旧文档改成「53 个模板全部
    验证通过」，后续 GDB 拿到新数据反而被这份「权威文档」压住。
    结论类文档只许追加，不许改既有结论；改既有结论必须先 --falsify。
    """
    p = Path(rel_path)
    if not p.is_absolute():
        p = ROOT / rel_path
    frozen = WORK / ".frozen_docs.json"
    data = {}
    if frozen.is_file():
        try:
            data = json.loads(frozen.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
    key = str(rel_path).replace("\\", "/")
    if key in data:
        print(f"[guard] {rel_path} 已冻结（{data[key].get('why', '')}）")
        print("        结论类文档只许追加，不许改既有结论。")
        print("        要改结论：先 --falsify 作废旧结论。")
        return 1
    return 0


def freeze_doc(rel_path: str, why: str) -> int:
    frozen = WORK / ".frozen_docs.json"
    data = {}
    if frozen.is_file():
        try:
            data = json.loads(frozen.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
    key = str(rel_path).replace("\\", "/")
    data[key] = {"t": _now(), "why": why}
    WORK.mkdir(parents=True, exist_ok=True)
    frozen.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    print(f"[freeze] {rel_path} 已冻结：{why}")
    return 0


# ------------------------------------------------------------- R1/R2/R3/R4 汇总

def check() -> int:
    problems: list[str] = []

    # R1：三类证据
    ev = _fresh_evidence()
    missing = [k for k in KINDS if k not in ev]
    if missing:
        problems.append("R1 缺少证据：" + "、".join(KIND_LABEL[k] for k in missing))

    # R2：必须有已 PASS 的预测
    if not PRED.is_file():
        problems.append("R2 没有预测：改码前必须 --predict 写下可证伪的数字")
    else:
        try:
            pred = json.loads(PRED.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pred = {}
        st = pred.get("status")
        if st != "PASS":
            problems.append(
                f"R2 预测未通过（status={st}）："
                f"「{pred.get('claim', '?')}」预期 {pred.get('expect', '?')}，"
                f"实测 {pred.get('actual', '未验证')}")

    # R3：三连失败
    consec = _consecutive_failures()
    if consec >= MAX_CONSECUTIVE_FAIL:
        problems.append(
            f"R3 连续 {consec} 次预测失败 —— 必须停止换假设，"
            f"明确写出「我修不了」并交出已确认事实")

    # R4：读过结构文档
    docs = _read_jsonl(DOCS)
    cited = [d for d in docs if d.get("quote")]
    if not cited:
        problems.append(
            "R4 没有引用任何机制文档原文：先 --toc 列出章节标题，"
            "再 --cite-doc 记录分发表等结构类章节的原文")

    # R5：覆盖度必须由机器统计，且声明范围不能超出实测清单
    cov_path = WORK / ".window_coverage.json"
    claim_path = WORK / ".scope_claim.json"
    cov = None
    if cov_path.is_file():
        try:
            cov = json.loads(cov_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cov = None
    if not cov:
        problems.append(
            "R5 没有窗口覆盖度清单：先 --scan <gdb_probe.log> 让机器统计"
            "实际出现过哪些模板/textMode（2026-11-18 只验 4 个就说全部验过）")
    else:
        known_tm = {tm for t in cov.get("templates", []) for tm in t.get("textModes", [])}
        cl = None
        if claim_path.is_file():
            try:
                cl = json.loads(claim_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                cl = None
        if not cl:
            problems.append(
                "R5 没有声明覆盖范围：用 --claim textmode <列表> 明确本次改动"
                "覆盖哪些 textMode（不得声称全部）")
        else:
            claimed = set(cl.get("textModes", []))
            bogus = claimed - known_tm
            if bogus:
                problems.append(
                    f"R5 声明的 textMode {sorted(bogus)} 不在实测清单里 "
                    f"{sorted(known_tm)} —— 不能凭记忆声称支持")

    # R6：若存在未处理的证伪记录，禁止继续用旧预测
    falsified = _read_jsonl(WORK / ".falsified.jsonl")
    if falsified:
        last = falsified[-1]
        if last.get("t", 0) > (_last_build_time() or 0):
            problems.append(
                f"R6 假设已被证伪（{last.get('reason')}）—— "
                "必须换假设重写 --predict，不能在旧假设上修补")

    if problems:
        print("=" * 70)
        print("  [X] 被拒绝：以下门槛未满足")
        print("=" * 70)
        print()
        for p in problems:
            print(f"  - {p}")
        print()
        print("  这四条不是形式主义，每一条都对应 2026-11-18 那次失败的具体环节：")
        print("    R1 证据      → 我反复靠猜而不跑数据")
        print("    R2 预测      → 我把错误猜想当成正确结果，没有可证伪的数字")
        print("    R3 三连止损  → 我换假设试到 52 轮，没有「我修不了」的止损点")
        print("    R4 读结构    → 我跳读文档，漏掉「textMode 7 项分发表」，")
        print("                   于是不知道 textMode 是决定落址算法的分派键")
        print()
        print("  补齐方式：")
        if missing:
            for k in missing:
                print(f"    {KIND_HOWTO[k]}")
        if not PRED.is_file() or problems:
            print('    python scripts\\evidence_gate.py --predict "第3个字的tile号" '
                  '--probe GridTile --field u --expect 0x009a')
            print('    python scripts\\evidence_gate.py --verify <gdb_probe.log>')
        print('    python scripts\\evidence_gate.py --toc docs/POKEMON_RUBY_AXVJ00.md')
        print('    python scripts\\evidence_gate.py --cite-doc docs/POKEMON_RUBY_AXVJ00.md '
              '--section "4. textMode" --quote "..."')
        print()
        print("=" * 70)
        return 1

    WORK.mkdir(parents=True, exist_ok=True)
    prev_built = _last_build_time()
    TOKEN.write_text(
        json.dumps({"t": _now(), "built_at": prev_built,
                    "kinds": {k: ev[k]["detail"] for k in KINDS},
                    "prediction": json.loads(PRED.read_text(encoding="utf-8"))},
                   ensure_ascii=False),
        encoding="utf-8")
    print("[evidence] OK: R1-R4 全部满足，允许编译")
    for k in KINDS:
        print(f"    {KIND_LABEL[k]:14s} {ev[k]['detail']}")
    pred = json.loads(PRED.read_text(encoding="utf-8"))
    print(f"    预测已验证        {pred.get('claim')} = {pred.get('actual')}")
    print(f"    文档引用          {len(cited)} 条")
    return 0


def status() -> int:
    since = _last_build_time()
    print(f"上次构建: "
          f"{time.strftime('%H:%M:%S', time.localtime(since)) if since else '(无)'}")
    ev = _fresh_evidence()
    print(f"证据（本轮有效 {len(ev)}/3）:")
    for k in KINDS:
        print(f"  {'[OK]' if k in ev else '[--]'} {KIND_LABEL[k]:14s} "
              f"{ev[k]['detail'] if k in ev else '缺'}")

    if PRED.is_file():
        try:
            pred = json.loads(PRED.read_text(encoding="utf-8"))
            print(f"预测: {pred.get('claim')} 预期 {pred.get('expect')} "
                  f"→ {pred.get('status')} (实测 {pred.get('actual', '—')})")
        except (OSError, json.JSONDecodeError):
            print("预测: 文件损坏")
    else:
        print("预测: 无")

    consec = _consecutive_failures()
    print(f"连续失败: {consec}/{MAX_CONSECUTIVE_FAIL}"
          + ("  [STOP]" if consec >= MAX_CONSECUTIVE_FAIL else ""))

    cited = [d for d in _read_jsonl(DOCS) if d.get("quote")]
    print(f"文档引用: {len(cited)} 条")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="改码/编译前硬门槛")
    ap.add_argument("--record", choices=KINDS)
    ap.add_argument("--detail", default="")
    ap.add_argument("--predict", metavar="CLAIM")
    ap.add_argument("--probe", default="")
    ap.add_argument("--field", default="")
    ap.add_argument("--expect", default="")
    ap.add_argument("--verify", metavar="LOG")
    ap.add_argument("--toc", metavar="DOC")
    ap.add_argument("--cite-doc", metavar="DOC")
    ap.add_argument("--section", default="")
    ap.add_argument("--quote", default="")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--mark-built", action="store_true")
    ap.add_argument("--scan", metavar="LOG")
    ap.add_argument("--claim", nargs=2, metavar=("WHAT", "VALUE"))
    ap.add_argument("--falsify", metavar="REASON")
    ap.add_argument("--evidence", default="")
    ap.add_argument("--freeze-doc", nargs=2, metavar=("DOC", "WHY"))
    ap.add_argument("--guard-doc", metavar="DOC")
    args = ap.parse_args()

    if args.record:
        return record(args.record, args.detail or "(未说明)")
    if args.predict:
        return predict(args.predict, args.probe, args.field, args.expect)
    if args.verify:
        p = Path(args.verify)
        if not p.is_absolute():
            p = ROOT / args.verify
        return verify(p)
    if args.toc:
        return toc(args.toc)
    if args.cite_doc:
        return cite_doc(args.cite_doc, args.section, args.quote)
    if args.mark_built:
        return mark_built()
    if args.scan:
        return scan_windows(args.scan)
    if args.claim:
        return claim(args.claim[0], args.claim[1])
    if args.falsify:
        return falsify(args.falsify, args.evidence)
    if args.freeze_doc:
        return freeze_doc(args.freeze_doc[0], args.freeze_doc[1])
    if args.guard_doc:
        return guard_doc(args.guard_doc)
    if args.status:
        return status()
    return check()


if __name__ == "__main__":
    sys.exit(main())
