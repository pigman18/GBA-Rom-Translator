"""逐条导出 unresolved（无指针 / 无锚点）条目，供人工核对「是不是真文本」。

用法::

    PYTHONPATH=src python scripts/dump_unresolved.py POKEMON_RUBY_AXVJ00 > work/axvj/unresolved.txt

与 ``diag_unresolved.py`` 的分工：那个脚本只按闸门计数，回答「卡在哪」；
这个脚本回答「这些东西到底是什么」，所以要给出足够人工判断的原始证据：

1. 地址 / 模块 / 原文 / 译文
2. 该串前后各 32 字节的原始 hex（看是不是结构体字段、是否被 FF 包围）
3. 串长度的字节分解（前 3 字节是什么命令头？）
4. ``_find_anchor`` 的逐步回溯过程 —— 每一步的串内容、是否有站点、
   若被判「不像文本」则给出实际内容。用来验证「往前找指针够不够」。
5. 全 ROM 里是否存在**低 16 位**等于该 offset 的 u16（base+offset 的
   最朴素形态，只作参考，不能当结论）。
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from meowth.jp_pcs import decode_pcs, looks_like_jp_text
from meowth.write_plan import MAX_CHAIN_BYTES, _text_ptr_index

GBA_BASE = 0x08000000


def trace_anchor(rom: bytes, idx: dict, addr: int, max_back: int = 96) -> str:
    """复刻 ``_find_anchor`` 并记录逐步过程，返回一句话结论。"""
    cur = addr
    steps: list[str] = []
    for i in range(max_back):
        if addr - cur > MAX_CHAIN_BYTES:
            return f"FAIL dist>{MAX_CHAIN_BYTES} after {i}step | " + " <- ".join(steps[-3:])
        p = rom.rfind(b"\xff", max(0, cur - 400), cur - 1)
        if p < 0:
            return f"FAIL no_ff within 400B after {i}step"
        s = p + 1
        e = rom.find(b"\xff", s, min(s + 400, len(rom)))
        if e < 0:
            return f"FAIL no_end after {i}step"
        body = rom[s:e + 1]
        try:
            txt = decode_pcs(body)
        except Exception:
            txt = "?"
        ok = looks_like_jp_text(body)
        sites = idx.get(s) or []
        steps.append(f"{s:#x}({len(body)}B,{'jp' if ok else 'NO'},"
                     f"{len(sites)}site,{txt[:14]!r})")
        if not ok:
            return f"STOP not_jp @{s:#x} after {i}step | " + " <- ".join(steps[-4:])
        if sites:
            return f"OK @{s:#x} sites={len(sites)} after {i}step"
        cur = s
    return f"FAIL max_back {max_back} | " + " <- ".join(steps[-3:])


def u16_offset_hits(rom: bytes, off: int, limit: int = 6) -> list[int]:
    """全 ROM 找 u16 值 == off & 0xFFFF 的位置（base+offset 最朴素形态）。"""
    lo = off & 0xFFFF
    needle = lo.to_bytes(2, "little")
    hits: list[int] = []
    i = rom.find(needle)
    while i >= 0 and len(hits) < limit:
        hits.append(i)
        i = rom.find(needle, i + 1)
    return hits


def main() -> int:
    gid = sys.argv[1] if len(sys.argv) > 1 else "POKEMON_RUBY_AXVJ00"
    rom = Path(f"roms/origin/{gid}.gba").read_bytes()
    plan = json.load(open(Path("work") / gid / "write.plan.json", encoding="utf-8"))
    build = json.load(open(Path("work") / gid / "translate.build.json", encoding="utf-8"))
    by_id = {e["id"]: e for e in build["entries"] if e.get("id")}

    idx = _text_ptr_index(rom)
    rows = []
    for s in plan["skip"]:
        if s.get("reason") != "unresolved_redirect":
            continue
        e = by_id.get(s["id"])
        if not e or not e.get("address"):
            continue
        off = (int(e["address"], 16) if isinstance(e["address"], str)
               else e["address"]) - GBA_BASE
        if not (0 <= off < len(rom)):
            continue
        end = rom.find(b"\xff", off, off + 513)
        raw = rom[off:end + 1] if end > off else rom[off:off + 16]
        try:
            jp = decode_pcs(raw)
        except Exception:
            jp = "?"
        rows.append({
            "off": off,
            "id": s["id"],
            "module": e.get("module") or "?",
            "jp": jp,
            "zh": e.get("translated") or "",
            "nbytes": len(raw),
            "head": raw[:4].hex(" "),
            "before": rom[max(0, off - 32):off].hex(" "),
            "after": rom[off + len(raw):off + len(raw) + 32].hex(" "),
            "anchor": trace_anchor(rom, idx, off),
            "u16": u16_offset_hits(rom, off),
        })

    print(f"# unresolved {len(rows)} 条（共 {len(plan['skip'])} 条 skip）")
    print("# 字段：off | module | nbytes | head | jp | zh")
    print("#   before: 前 32B 原始 hex；after: 后 32B 原始 hex")
    print("#   anchor: _find_anchor 复刻的回溯过程")
    mod = Counter(r["module"] for r in rows)
    print("# 模块分布: " + ", ".join(f"{k}={v}" for k, v in mod.most_common()))
    print()
    for r in rows:
        print(f"=== {r['off']:#08x} [{r['module']}] {r['nbytes']}B head={r['head']}")
        print(f"  jp : {r['jp']!r}")
        print(f"  zh : {r['zh']!r}")
        print(f"  ctx: {r['before']} | {r['after']}")
        print(f"  anc: {r['anchor']}")
        if r["u16"]:
            print(f"  u16: {[hex(h) for h in r['u16']]}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
