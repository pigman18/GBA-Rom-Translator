#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
addr_patcher.py
===============
ROM 地址交叉引用（Thumb）。

  callers  — 谁 bl/blx 到该地址；--depth>1 时向上展开调用链
  refs     — 谁以 LE 指针引用该地址（指针站）

用法：
  python src/util/addr_patcher.py callers 0x08061CF4
  python src/util/addr_patcher.py callers 0x08061CF4 --depth 3
  python src/util/addr_patcher.py refs 0x0814BA38
  python src/util/addr_patcher.py callers 0x08061CF4 -o out.json
"""

from __future__ import annotations

import argparse
import bisect
import json
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

BASE = 0x08000000
TITLE_LZ_BAND = (0x36D000, 0x370000)
# 调用点向上归属函数入口的最大跨度
FUNC_SPAN_MAX = 0x2000
# 无已知 bl 目标时，向前找 push {…, lr} 的上限
PROLOGUE_BACK_MAX = 0x400

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_ROM = REPO_ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"


def parse_addr(text: str) -> int:
    s = text.strip().lower().replace("_", "")
    if s.startswith("0x"):
        return int(s, 16)
    return int(s, 16)


def to_file_off(addr: int, rom_len: int) -> int:
    """VMA 或文件偏移 → 文件偏移。"""
    if addr >= BASE:
        fo = addr - BASE
    else:
        fo = addr
    if fo < 0 or fo >= rom_len:
        raise SystemExit(f"地址越界: 0x{addr:X} (rom_len=0x{rom_len:X})")
    return fo


def to_vma(fo_or_vma: int) -> int:
    if fo_or_vma >= BASE:
        return fo_or_vma
    return BASE + fo_or_vma


@dataclass
class CallSite:
    address: int  # VMA of bl/blx
    file_off: int
    mnemonic: str
    op_str: str
    target: int  # aligned VMA

    def as_dict(self) -> dict[str, Any]:
        return {
            "address": f"0x{self.address:08X}",
            "file_off": self.file_off,
            "mnemonic": self.mnemonic,
            "op_str": self.op_str,
            "target": f"0x{self.target:08X}",
        }


@dataclass
class CallIndex:
    """全盘 bl/blx 反向索引：target -> call sites；entries = 所有被调用目标。"""

    by_target: dict[int, list[CallSite]] = field(default_factory=dict)
    entries_sorted: list[int] = field(default_factory=list)  # 对齐 VMA，升序

    def callers_of(self, target_vma: int) -> list[CallSite]:
        return list(self.by_target.get(target_vma & ~1, ()))


def build_call_index(rom: bytes) -> CallIndex:
    """一次全盘反汇编，建反向调用索引（后续 depth 查询 O(1)）。"""
    n = len(rom)
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    by_target: dict[int, list[CallSite]] = {}
    seen_site: set[tuple[int, int]] = set()  # (call_fo, target)
    chunk = 0x1000
    fo = 0
    while fo < n:
        if TITLE_LZ_BAND[0] <= fo < TITLE_LZ_BAND[1]:
            fo = TITLE_LZ_BAND[1]
            continue
        size = min(chunk, n - fo)
        data = rom[fo : min(n, fo + size + 4)]
        for insn in md.disasm(data, BASE + fo):
            call_fo = insn.address - BASE
            if call_fo >= fo + size:
                continue
            if insn.mnemonic not in ("bl", "blx"):
                continue
            if not insn.op_str.startswith("#"):
                continue
            try:
                tgt = int(insn.op_str[1:], 16) & ~1
            except ValueError:
                continue
            if tgt < BASE or tgt >= BASE + n:
                continue
            key = (call_fo, tgt)
            if key in seen_site:
                continue
            seen_site.add(key)
            site = CallSite(
                address=insn.address,
                file_off=call_fo,
                mnemonic=insn.mnemonic,
                op_str=insn.op_str,
                target=tgt,
            )
            by_target.setdefault(tgt, []).append(site)
        fo += size

    for sites in by_target.values():
        sites.sort(key=lambda s: s.file_off)

    entries = sorted(by_target.keys())
    return CallIndex(by_target=by_target, entries_sorted=entries)


def _find_push_lr_prologue(rom: bytes, site_fo: int) -> int | None:
    """从调用点向前找最近的 push {…, lr}（Thumb B5xx）。"""
    fo = site_fo & ~1
    limit = max(0, fo - PROLOGUE_BACK_MAX)
    while fo > limit:
        fo -= 2
        if TITLE_LZ_BAND[0] <= fo < TITLE_LZ_BAND[1]:
            break
        hw = struct.unpack_from("<H", rom, fo)[0]
        if (hw & 0xFF00) == 0xB500:  # push with LR
            return BASE + fo
    return None


def resolve_func_entry(rom: bytes, index: CallIndex, site_fo: int) -> int:
    """
    调用点所属函数入口（启发式）：
    1) 不大于 site、且落在 FUNC_SPAN_MAX 内的最近 bl 目标；
    2) 否则向前找 push {lr}；
    3) 再不行则用调用点自身对齐地址（弱归属，仅防断链）。
    """
    site_vma = BASE + site_fo
    entries = index.entries_sorted
    i = bisect.bisect_right(entries, site_vma) - 1
    if i >= 0:
        cand = entries[i]
        if site_vma - cand <= FUNC_SPAN_MAX:
            return cand
    pro = _find_push_lr_prologue(rom, site_fo)
    if pro is not None:
        return pro & ~1
    return site_vma & ~1


def find_callers(rom: bytes, target_vma: int, index: CallIndex | None = None) -> list[dict[str, Any]]:
    """直接调用点（depth=1）。可传入已建索引避免重复扫盘。"""
    idx = index or build_call_index(rom)
    return [s.as_dict() for s in idx.callers_of(target_vma)]


@dataclass
class ChainNode:
    depth: int
    site: CallSite
    func: int  # 调用点所属函数入口 VMA
    parent_target: int  # 本层 bl 的目标（即下一层/种子函数）

    def as_dict(self) -> dict[str, Any]:
        d = self.site.as_dict()
        d["depth"] = self.depth
        d["func"] = f"0x{self.func:08X}"
        d["parent_target"] = f"0x{self.parent_target:08X}"
        return d


def find_caller_chains(
    rom: bytes,
    target_vma: int,
    *,
    depth: int = 1,
    index: CallIndex | None = None,
) -> list[ChainNode]:
    """
    向上展开调用链。
    depth=1：仅直接 bl→target。
    depth=N：对每层调用点归属函数 F，再查 bl→F，直到 N 或无更多 callers。
    """
    if depth < 1:
        raise ValueError("depth must be >= 1")
    idx = index or build_call_index(rom)
    seed = target_vma & ~1
    out: list[ChainNode] = []
    # BFS：队列元素 (func_to_query, depth_level)
    queue: list[tuple[int, int]] = [(seed, 1)]
    visited_fn: set[int] = {seed}

    while queue:
        fn, level = queue.pop(0)
        if level > depth:
            continue
        for site in idx.callers_of(fn):
            container = resolve_func_entry(rom, idx, site.file_off)
            node = ChainNode(
                depth=level,
                site=site,
                func=container,
                parent_target=fn,
            )
            out.append(node)
            if level < depth and container not in visited_fn:
                visited_fn.add(container)
                queue.append((container, level + 1))

    out.sort(key=lambda n: (n.depth, n.site.file_off))
    return out


def find_refs(rom: bytes, target_vma: int, *, unaligned: bool = True) -> list[dict[str, Any]]:
    """扫 ROM 内指向 target_vma 的 LE 指针站（默认同查非对齐）。"""
    n = len(rom)
    needle = struct.pack("<I", target_vma & 0xFFFFFFFF)
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    start = 0
    while True:
        i = rom.find(needle, start)
        if i < 0:
            break
        start = i + 1
        if TITLE_LZ_BAND[0] <= i < TITLE_LZ_BAND[1]:
            continue
        if not unaligned and (i & 3) != 0:
            continue
        if i in seen:
            continue
        seen.add(i)
        out.append(
            {
                "address": f"0x{BASE + i:08X}",
                "file_off": i,
                "aligned": (i & 3) == 0,
                "target": f"0x{target_vma & 0xFFFFFFFF:08X}",
            }
        )
    out.sort(key=lambda x: x["file_off"])
    return out


def _print_chains(nodes: list[ChainNode], seed: int) -> None:
    """按 parent_target 嵌套打印：同一函数的多层调用点归在一支下。"""
    by_parent: dict[int, list[ChainNode]] = {}
    for n in nodes:
        by_parent.setdefault(n.parent_target, []).append(n)
    for lst in by_parent.values():
        lst.sort(key=lambda x: x.site.file_off)

    print(f"0x{seed:08X}")
    expanded: set[int] = set()

    def walk(target: int, depth: int) -> None:
        sites = by_parent.get(target, ())
        if not sites:
            return
        indent = "  " * depth
        funcs_order: list[int] = []
        seen_fn: set[int] = set()
        for n in sites:
            print(
                f"{indent}<- 0x{n.site.address:08X}  "
                f"{n.site.mnemonic:4} {n.site.op_str}  "
                f"[fn 0x{n.func:08X}]"
            )
            if n.func not in seen_fn:
                seen_fn.add(n.func)
                funcs_order.append(n.func)
        for fn in funcs_order:
            if fn in expanded:
                continue
            expanded.add(fn)
            walk(fn, depth + 1)

    walk(seed, 1)


def _print_refs(rows: list[dict[str, Any]]) -> None:
    for r in rows:
        al = "aligned" if r.get("aligned") else "unaligned"
        print(f"{r['address']}  ({al})")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"[ok] wrote {path}", file=sys.stderr)


def cmd_callers(args: argparse.Namespace) -> int:
    rom_path: Path = args.rom
    rom = rom_path.read_bytes()
    target = to_vma(parse_addr(args.address)) & ~1
    _ = to_file_off(target, len(rom))
    depth = int(args.depth)
    print(
        f"[i] callers of 0x{target:08X}  depth={depth}  "
        f"rom={rom_path}  size=0x{len(rom):X}"
    )
    print("[i] building call index (full-ROM disasm)...", flush=True)
    index = build_call_index(rom)
    print(
        f"[i] index: {len(index.by_target)} targets, "
        f"{sum(len(v) for v in index.by_target.values())} call sites",
        flush=True,
    )
    nodes = find_caller_chains(rom, target, depth=depth, index=index)
    _print_chains(nodes, target)
    by_d: dict[int, int] = {}
    for n in nodes:
        by_d[n.depth] = by_d.get(n.depth, 0) + 1
    summary = ", ".join(f"L{d}={by_d[d]}" for d in sorted(by_d)) or "none"
    print(f"[ok] callers x{len(nodes)} ({summary}) -> 0x{target:08X}")
    if args.output:
        _write_json(
            Path(args.output),
            {
                "cmd": "callers",
                "rom": str(rom_path),
                "target": f"0x{target:08X}",
                "depth": depth,
                "count": len(nodes),
                "by_depth": {str(k): v for k, v in sorted(by_d.items())},
                "sites": [n.as_dict() for n in nodes],
            },
        )
    return 0


def cmd_refs(args: argparse.Namespace) -> int:
    rom_path: Path = args.rom
    rom = rom_path.read_bytes()
    target = to_vma(parse_addr(args.address))
    print(
        f"[i] refs to 0x{target:08X}  rom={rom_path}  "
        f"unaligned={not args.aligned_only}"
    )
    rows = find_refs(rom, target, unaligned=not args.aligned_only)
    _print_refs(rows)
    print(f"[ok] refs x{len(rows)} -> 0x{target:08X}")
    if args.output:
        _write_json(
            Path(args.output),
            {
                "cmd": "refs",
                "rom": str(rom_path),
                "target": f"0x{target:08X}",
                "count": len(rows),
                "sites": rows,
            },
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="addr_patcher: callers / refs（Thumb 交叉引用）"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument(
            "address",
            help="目标地址（0x08…… VMA 或文件偏移）",
        )
        sp.add_argument(
            "--rom",
            type=Path,
            default=DEFAULT_ROM,
            help=f"ROM（默认 {DEFAULT_ROM}）",
        )
        sp.add_argument(
            "-o",
            "--output",
            type=Path,
            default=None,
            help="可选：写出 JSON",
        )

    p_c = sub.add_parser(
        "callers",
        help="列出 bl/blx 到该地址的调用点；--depth 展开上层调用链",
    )
    add_common(p_c)
    p_c.add_argument(
        "--depth",
        type=int,
        default=1,
        metavar="N",
        help="调用链层数（默认 1=仅直接调用；3=向上两层父函数）",
    )
    p_c.set_defaults(func=cmd_callers)

    p_r = sub.add_parser("refs", help="列出指向该地址的 LE 指针站")
    add_common(p_r)
    p_r.add_argument(
        "--aligned-only",
        action="store_true",
        help="仅 4 字节对齐指针站",
    )
    p_r.set_defaults(func=cmd_refs)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
