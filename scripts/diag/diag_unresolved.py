"""诊断 ``write.plan.json`` 里 unresolved 条目到底卡在哪一道闸门。

用法::

    PYTHONPATH=src python scripts/diag_unresolved.py POKEMON_RUBY_AXVJ00

输出两张表：

1. **按闸门分布**（每个模块各有多少条卡在哪一步）
2. **样本**（每个闸门列 3 条，带原文与站点上下文）

为什么要这个工具：``unresolved_redirect`` 只是「最后没生成写入计划」的
统称，实际可能卡在 6 个完全不同的地方（没指针 / 非对齐 / 落在正文 span /
标题图形 deny / 可信 LZ 段但 source 判定失败 / 脚本 source 判定失败）。
以前只能临时写一段探测代码去猜，容易得出互相矛盾的结论 —— 比如
「加一条指针数组判据应该能救 107 条」实测输出一个字节都没变，
因为那些站点在更前面就被 in_body / LZ 段拦掉了。

闸门顺序必须与 ``policy.filter_pointer_sources`` 严格一致，改那边时同步这里。
"""

from __future__ import annotations

import json
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

from meowth.charmap import Charmap
from meowth.config_loader import game_config_dir, texts_json_path
from meowth.extract import ptr_in_trusted_lz, trusted_lz_spans
from meowth.jp_pcs import decode_pcs
from meowth.modules import entry_is_script_like
from meowth.policy import (
    BIRCH_PTR_ALLOW,
    TITLE_LZ_BAND,
    _ptr_array_element_ok,
    _script_cmd_ptr_ok,
    _script_inline_hdr_ok,
    is_class_text_ptr,
    is_local_pool_ptr,
    is_script_inline_ptr,
    ptr_source_ok,
    ptr_site_in_text_body,
    title_gfx_ptr_deny,
)
from meowth.write_plan import (
    _find_anchor,
    _ptr_sources_for_entry,
    _text_ptr_index,
)

GBA_BASE = 0x08000000


def classify(rom: bytes, idx: dict, off: int, category: str, spans,
             text_spans) -> tuple[str, list[int]]:
    """返回 (第一道拒绝闸门, 该串的全部候选站点)。"""
    sites = idx.get(off) or []
    if not sites:
        return "no_pointer", []

    target = GBA_BASE + off
    entry = {"category": category, "module": category}
    script_like = entry_is_script_like(entry)
    first = "unknown"
    for p in sites:
        if p + 4 > len(rom):
            first = "out_of_range"
            continue
        inline = is_script_inline_ptr(rom, p, target)
        in_body = ptr_site_in_text_body(p, text_spans)
        inline_hdr = (
            inline
            or _script_inline_hdr_ok(rom, p)
            or _ptr_array_element_ok(rom, p)
        )
        # 脚本命令指针：u16 命令字 + 参数 + u32 文本指针（非对齐的另一种合法形态）
        cmd_ptr = bool(p & 3) and _script_cmd_ptr_ok(rom, p) and not in_body
        inline_hdr = inline_hdr or cmd_ptr
        if p & 3:
            if not inline_hdr:
                first = "misaligned"
                continue
        elif in_body and not inline_hdr:
            first = "in_text_body"
            continue
        if p in title_gfx_ptr_deny():
            first = "title_gfx_deny"
            continue
        tlz = TITLE_LZ_BAND()
        if tlz[0] <= p < tlz[1]:
            first = "title_lz_band"
            continue
        if p in BIRCH_PTR_ALLOW or is_class_text_ptr(rom, p, target) \
                or is_local_pool_ptr(p, target):
            return "accepted", sites
        if ptr_in_trusted_lz(p, spans):
            if not ptr_source_ok(rom, p, target, lz_spans=spans, strict=False):
                first = "trusted_lz+src_reject"
                continue
            return "accepted", sites
        if script_like and not ptr_source_ok(
            rom, p, target, lz_spans=spans, strict=False
        ):
            if not inline_hdr:
                first = "script+src_reject"
                continue
        return "accepted", sites
    return first, sites


def main() -> int:
    gid = sys.argv[1] if len(sys.argv) > 1 else "POKEMON_RUBY_AXVJ00"
    plan_path = Path("work") / gid / "write.plan.json"
    build_path = Path("work") / gid / "translate.build.json"
    rom = Path(f"roms/origin/{gid}.gba").read_bytes()
    plan = json.load(open(plan_path, encoding="utf-8"))
    build = json.load(open(build_path, encoding="utf-8"))
    by_id = {e["id"]: e for e in build["entries"] if e.get("id")}

    unresolved = [
        s for s in plan["skip"] if s.get("reason") == "unresolved_redirect"
    ]
    print(f"unresolved_redirect: {len(unresolved)}")

    # text_spans 与实际 plan 同样的口径：用条目地址 + FF 终止位置
    spans = []
    for e in build["entries"]:
        a = e.get("address")
        if not a:
            continue
        off = (int(a, 16) if isinstance(a, str) else a) - GBA_BASE
        if off < 0 or off >= len(rom):
            continue
        end = rom.find(bytes([0xFF]), off, off + 513)
        if end > off:
            spans.append((off, end + 1))
    spans.sort()

    idx = _text_ptr_index(rom)
    lz = trusted_lz_spans(rom)

    gates: Counter = Counter()
    per_module: defaultdict[str, Counter] = defaultdict(Counter)
    samples: defaultdict[str, list] = defaultdict(list)
    for s in unresolved:
        e = by_id.get(s["id"])
        if not e:
            gates["no_entry"] += 1
            continue
        module = e.get("module") or "?"
        a = e.get("address")
        if not a:
            gates["no_address"] += 1
            continue
        off = (int(a, 16) if isinstance(a, str) else a) - GBA_BASE
        gate, sites = classify(rom, idx, off, module, lz, spans)
        if gate == "no_pointer":
            if _find_anchor(rom, idx, off):
                gate = "no_ptr_but_anchor"  # 锚点有，卡在 cluster 生成
            else:
                gate = "no_ptr_no_anchor"
        if gate == "accepted":
            # 用 plan 同一个函数复核：它返回非空却仍 unresolved，说明卡在
            # 更后一步（span 差异 / 槽太短 / 表区间跳过）
            if _ptr_sources_for_entry(
                rom, e, text_spans=spans, lz_spans=lz
            ):
                gate = "src_found_but_unresolved"
        gates[gate] += 1
        per_module[module][gate] += 1
        if len(samples[gate]) < 3:
            end = rom.find(bytes([0xFF]), off, off + 513)
            raw = bytes(rom[off:end + 1]) if end > off else b""
            try:
                text = decode_pcs(raw)
            except Exception:
                text = "?"
            ctx = ""
            if sites:
                p = sites[0]
                ctx = f" site@{p:#x} ctx={rom[p - 4:p + 4].hex(' ')}"
            samples[gate].append(
                f"    {a} {module} {text[:26]!r}{ctx}"
            )

    print("\n== 按闸门 ==")
    for gate, n in gates.most_common():
        print(f"  {gate:24s} {n}")

    print("\n== 按模块 × 闸门 ==")
    for module, cc in sorted(per_module.items(), key=lambda kv: -sum(kv[1].values())):
        total = sum(cc.values())
        detail = ", ".join(f"{g}={v}" for g, v in cc.most_common())
        print(f"  {module:16s} {total:5d}  {detail}")

    print("\n== 样本 ==")
    for gate, rows in samples.items():
        print(f"  [{gate}]")
        for r in rows:
            print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
