#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""execute_filter 后端：「候选地址是否被指定函数消费」判定。

核心 API::

    is_execute(rom, address, addressList) -> bool
        单地址判定：address 是否被 addressList 中任一函数的 BL 闭包消费。

    get_consumed_set(rom, specs) -> frozenset[int]
        批量预计算：返回被消费地址集合（用于 extract_scan 快速路径）。

消费语义：``C(t) ⇒ B(t) ⇒ sink(t)``——
- t 作为 BL 参数（r0–r3）进入调用链（参数逆推）；
- 或 t 被脚本 op（message/trainerbattle 等）的参数位引用（脚本 op 扫描）。

依赖 capstone（``pip install capstone``）。不 import texts_patcher（避免环）。
"""

from __future__ import annotations

import bisect
import struct
from typing import Any

BASE = 0x08000000
DEFAULT_DEPTH = 8
_FALLBACK_FUNC_SPAN = 0x800
_MAX_FUNC_SPAN = 0x4000
_PARAM_WINDOW = 96

_ACTIVE_ROM: bytes | None = None

_CODE_INDEX_CACHE: dict[int, tuple[dict[int, list[int]], list[int]]] = {}
_EXECUTE_SET_CACHE: dict[tuple[Any, ...], frozenset[int]] = {}
_FUNC_INSNS_CACHE: dict[tuple[int, int], list[Any]] = {}
# (id(rom), frozenset(sinks), depth) -> frozenset[int]
_IS_EXECUTE_CACHE: dict[tuple[int, frozenset[int], int], frozenset[int]] = {}
# (id(rom), ops_tuple) -> frozenset[int]：脚本 op 消费集合缓存
_SCRIPT_SET_CACHE: dict[tuple, frozenset[int]] = {}


def set_active_rom(rom: bytes | None) -> None:
    global _ACTIVE_ROM
    _ACTIVE_ROM = rom


def get_active_rom() -> bytes | None:
    return _ACTIVE_ROM


def _cs_mod():
    try:
        import capstone  # type: ignore
    except ImportError as e:
        raise SystemExit(
            "execute_filter 需要第三方包 capstone： pip install capstone"
        ) from e
    return capstone


def _parse_addr(v: Any) -> int:
    if isinstance(v, int):
        return v
    s = str(v).strip().lower().replace("_", "")
    if not s:
        return 0
    if s.startswith("0x"):
        return int(s, 16)
    if any(c in "abcdef" for c in s):
        return int(s, 16)
    return int(s, 10)


def _to_file_off(addr: int, rom_len: int) -> int | None:
    a = addr - BASE if addr >= BASE else addr
    if 0 <= a < rom_len:
        return a
    return None


# ---------------------------------------------------------------------------
# 内建脚本 op 表（AXVJ 实测验证）
# ---------------------------------------------------------------------------
_SCRIPT_OPS: dict[str, tuple[tuple[int, tuple[int, ...]], ...]] = {
    "message": ((0x67, (1,)),),
    "messageautoscroll": ((0x9B, (1,)),),
    "loadword": ((0x0F, (2,)),),
    "trainerbattle": ((0x5C, (6, 10, 14, 18)),),
}


def _scan_script_op_refs(
    rom: bytes, op_byte: int, ptr_offsets: tuple[int, ...]
) -> set[int]:
    n = len(rom)
    top = BASE + n
    out: set[int] = set()
    need = 1 + max(ptr_offsets) + 3
    o = 0
    last = n - need
    while o < last:
        if rom[o] == op_byte:
            for poff in ptr_offsets:
                v = struct.unpack_from("<I", rom, o + poff)[0]
                if BASE <= v < top:
                    out.add(v - BASE)
        o += 1
    return out


def parse_sink_items(
    value: Any, *, rom_len: int = 1 << 26
) -> tuple[list[tuple[str, int, int]], list[str]]:
    if isinstance(value, dict):
        value = [value]
    funcs: list[tuple[str, int, int]] = []
    ops: list[str] = []
    if not isinstance(value, (list, tuple)):
        return funcs, ops
    for item in value:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        addr = item.get("address")
        if addr is None or addr == "":
            if name in _SCRIPT_OPS:
                ops.append(name)
            continue
        try:
            raw = _parse_addr(addr)
        except (TypeError, ValueError):
            continue
        fo = _to_file_off(raw, rom_len)
        if fo is None:
            continue
        try:
            depth = int(item.get("depth") or DEFAULT_DEPTH)
        except (TypeError, ValueError):
            depth = DEFAULT_DEPTH
        if depth < 1:
            depth = 1
        funcs.append((name, fo, depth))
    return funcs, ops


def filters_need_execute(filters: list[dict[str, Any]] | None) -> bool:
    for spec in filters or []:
        if not isinstance(spec, dict):
            continue
        if str(spec.get("type") or "") != "execute_filter":
            continue
        funcs, ops = parse_sink_items(spec.get("value"))
        if funcs or ops:
            return True
    return False


# ---------------------------------------------------------------------------
# 代码索引（BL / func_starts）
# ---------------------------------------------------------------------------

def _build_code_index(rom: bytes) -> tuple[dict[int, list[int]], list[int]]:
    key = id(rom)
    hit = _CODE_INDEX_CACHE.get(key)
    if hit is not None:
        return hit

    n = len(rom)
    bl_index: dict[int, list[int]] = {}
    func_starts: list[int] = []
    unpack_h = struct.unpack_from

    o = 0
    last = n - 3
    while o < last:
        h1 = unpack_h("<H", rom, o)[0]
        if (h1 & 0xFF00) == 0xB500:
            func_starts.append(o)
        if (h1 & 0xF800) == 0xF000:
            h2 = unpack_h("<H", rom, o + 2)[0]
            if (h2 & 0xF800) == 0xF800:
                s = (h1 >> 10) & 1
                off = (s << 21) | ((h1 & 0x3FF) << 12) | ((h2 & 0x7FF) << 1)
                if s:
                    off -= 1 << 22
                t = o + 4 + off
                if 0 <= t < n:
                    bl_index.setdefault(t, []).append(o)
        o += 2

    o = 0
    while o < last:
        w = unpack_h("<I", rom, o)[0]
        if (w & 0x0F000000) == 0x0B000000:
            imm24 = w & 0x00FFFFFF
            off = imm24 << 2
            if imm24 & 0x00800000:
                off -= 1 << 26
            t = o + 8 + off
            if 0 <= t < n:
                bl_index.setdefault(t, []).append(o)
        o += 4

    func_starts.sort()
    out = (bl_index, func_starts)
    _CODE_INDEX_CACHE[key] = out
    return out


def _owner_func(func_starts: list[int], site: int) -> int | None:
    i = bisect.bisect_right(func_starts, site) - 1
    if i < 0:
        return None
    return func_starts[i]


def _func_span(func_starts: list[int], owner: int, rom_len: int) -> tuple[int, int]:
    j = bisect.bisect_right(func_starts, owner)
    if j < len(func_starts):
        end = func_starts[j]
    else:
        end = min(owner + _FALLBACK_FUNC_SPAN, rom_len)
    if end - owner > _MAX_FUNC_SPAN:
        end = owner + _MAX_FUNC_SPAN
    return owner, end


_BRANCH_MNEMS = frozenset(
    {
        "b", "beq", "bne", "bhs", "blo", "bcs", "bcc", "bmi", "bpl",
        "bvs", "bvc", "bhi", "bls", "bge", "blt", "bgt", "ble",
        "bx", "blx", "bl", "swi", "svc", "cbz", "cbnz",
    }
)
_UNCOND_BRANCH_MNEMS = frozenset({"b", "bx", "blx", "bl", "swi", "svc"})
_NO_WRITE_MNEMS = frozenset(
    {
        "cmp", "cmn", "tst", "teq", "str", "strh", "strb",
        "stm", "stmia", "stmdb", "push", "nop", "msr", "mrs",
    }
)


def _func_insns(rom: bytes, func_start: int, span_end: int) -> list[Any]:
    key = (id(rom), func_start)
    hit = _FUNC_INSNS_CACHE.get(key)
    if hit is not None:
        return hit
    cs = _cs_mod()
    md = _MD_CACHE.get(id(rom))
    if md is None:
        md = cs.Cs(cs.CS_ARCH_ARM, cs.CS_MODE_THUMB)
        md.detail = True
        md.skipdata = True
        _MD_CACHE[id(rom)] = md
    code = rom[func_start:span_end]
    insns = list(md.disasm(code, BASE + func_start))
    _FUNC_INSNS_CACHE[key] = insns
    return insns


_MD_CACHE: dict[int, Any] = {}


def _call_param_refs(
    rom: bytes,
    site: int,
    func_start: int,
    func_end: int,
    mask: int,
) -> tuple[dict[int, int], int]:
    cs = _cs_mod()
    from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_OP_REG  # type: ignore

    n = len(rom)
    top = BASE + n
    insns = _func_insns(rom, func_start, func_end)
    site_vma = BASE + site
    idx = bisect.bisect_left([i.address for i in insns], site_vma)
    if idx >= len(insns) or insns[idx].address != site_vma:
        return {}, 0

    need = {r for r in range(4) if (mask >> r) & 1}
    src: dict[int, int] = {}
    dead: set[int] = set()
    alias: dict[int, int] = {}

    def _reg_no(insn: Any, op: Any) -> int:
        name = insn.reg_name(op.reg) or ""
        if name.startswith("r") and name[1:].isdigit():
            return int(name[1:])
        return {"sp": 13, "lr": 14, "pc": 15}.get(name, -1)

    invalid_id = cs.arm.ARM_INS_INVALID
    steps = 0
    for insn in reversed(insns[:idx]):
        if steps >= _PARAM_WINDOW or not need:
            break
        if insn.id == invalid_id:
            continue
        steps += 1
        mn = insn.mnemonic
        ops = insn.operands
        if mn in _UNCOND_BRANCH_MNEMS:
            break
        if mn in _NO_WRITE_MNEMS or not ops:
            continue
        if ops[0].type != ARM_OP_REG:
            continue
        rD = _reg_no(insn, ops[0])

        if mn == "ldr" and len(ops) >= 2 and ops[1].type == ARM_OP_MEM:
            mem = ops[1].mem
            if insn.reg_name(mem.base) == "pc":
                if rD in need:
                    lit = ((insn.address + 4) & ~3) + mem.disp
                    fo = lit - BASE
                    v = (
                        struct.unpack_from("<I", rom, fo)[0]
                        if 0 <= fo and fo + 4 <= n
                        else 0
                    )
                    if BASE <= v < top:
                        src[rD] = v - BASE
                    else:
                        dead.add(rD)
                    need.discard(rD)
                continue
            if rD in need:
                dead.add(rD)
                need.discard(rD)
            continue
        if mn == "adr" and len(ops) >= 2 and ops[1].type == ARM_OP_IMM:
            if rD in need:
                v = int(ops[1].imm)
                if BASE <= v < top:
                    src[rD] = v - BASE
                else:
                    dead.add(rD)
                need.discard(rD)
            continue
        if mn in ("mov", "movs") and len(ops) >= 2:
            if rD in need:
                if ops[1].type == ARM_OP_REG:
                    rS = _reg_no(insn, ops[1])
                    if 0 <= rS < 12:
                        alias[rD] = rS
                        need.discard(rD)
                        if rS not in src and rS not in dead:
                            need.add(rS)
                    else:
                        dead.add(rD)
                        need.discard(rD)
                else:
                    dead.add(rD)
                    need.discard(rD)
            continue
        if (
            mn in ("add", "adds", "sub", "subs")
            and len(ops) >= 3
            and ops[2].type == ARM_OP_IMM
            and int(ops[2].imm) == 0
            and ops[1].type == ARM_OP_REG
        ):
            if rD in need:
                rS = _reg_no(insn, ops[1])
                if 0 <= rS < 12:
                    alias[rD] = rS
                    need.discard(rD)
                    if rS not in src and rS not in dead:
                        need.add(rS)
                else:
                    dead.add(rD)
                    need.discard(rD)
            continue
        if mn == "pop" or mn.startswith("ldm"):
            for op in ops:
                if op.type != ARM_OP_REG:
                    continue
                r = _reg_no(insn, op)
                if r in need:
                    dead.add(r)
                    need.discard(r)
            continue
        if rD in need:
            dead.add(rD)
            need.discard(rD)

    for rD, rS in alias.items():
        seen_r = {rD}
        r = rS
        while r in alias and r not in seen_r:
            seen_r.add(r)
            r = alias[r]
        if r in src:
            src[rD] = src[r]
        elif r in dead:
            dead.add(rD)
        else:
            need.add(rD)

    unresolved = 0
    for r in need:
        if 0 <= r < 4 and r not in src and r not in dead:
            unresolved |= 1 << r
    return src, unresolved


def _is_thumb_bl_at(rom: bytes, site: int) -> bool:
    if site < 0 or site + 4 > len(rom):
        return False
    h1, h2 = struct.unpack_from("<HH", rom, site)
    return (h1 & 0xF800) == 0xF000 and (h2 & 0xF800) == 0xF800


# ---------------------------------------------------------------------------
# 内部：可达函数 BFS + 代码指针排除
# ---------------------------------------------------------------------------

def _visited_funcs(
    rom: bytes, sinks: list[int], depth: int
) -> tuple[set[int], dict[int, list[int]], list[int]]:
    bl_index, func_starts = _build_code_index(rom)
    visited: set[int] = set(sinks)
    frontier = list(sinks)
    for _ in range(max(1, depth)):
        nxt: list[int] = []
        for f in frontier:
            for site in bl_index.get(f, ()):
                owner = _owner_func(func_starts, site)
                if owner is None or owner in visited:
                    continue
                visited.add(owner)
                nxt.append(owner)
        if not nxt:
            break
        frontier = nxt
    return visited, bl_index, func_starts


def _code_filter(
    func_starts: list[int],
    bl_index: dict[int, list[int]],
    visited: set[int],
    n: int,
) -> tuple[set[int], set[int], set[int], list[tuple[int, int]]]:
    spans = sorted(_func_span(func_starts, f, n) for f in visited)
    merged: list[list[int]] = []
    for a, b in spans:
        if merged and a <= merged[-1][1]:
            if b > merged[-1][1]:
                merged[-1][1] = b
        else:
            merged.append([a, b])
    code_spans = [(a, b) for a, b in merged]
    starts_set = set(func_starts)
    callee_set = set(bl_index.keys())
    return starts_set, callee_set, set(), code_spans


def _is_code_ptr(
    t: int,
    starts_set: set[int],
    callee_set: set[int],
    code_spans: list[tuple[int, int]],
    span_starts: list[int],
) -> bool:
    tc = t & ~1
    if t in starts_set or tc in starts_set:
        return True
    if t in callee_set or tc in callee_set:
        return True
    i = bisect.bisect_right(span_starts, t) - 1
    if i >= 0 and (
        code_spans[i][0] <= t < code_spans[i][1]
        or code_spans[i][0] <= tc < code_spans[i][1]
    ):
        return True
    return False


def _expand_pointer_table(rom: bytes, base: int) -> list[int]:
    """指针表展开：base 起连续 ROM 指针（≥3 才算表）的目标列表；至多 512 项。"""
    n = len(rom)
    top = BASE + n
    out: list[int] = []
    o = base
    while o + 4 <= n and len(out) < 512:
        v = struct.unpack_from("<I", rom, o)[0]
        if not (BASE <= v < top):
            break
        out.append(v - BASE)
        o += 4
    if len(out) < 3:
        return []
    return out


def _ldr_literal_value(rom: bytes, insn: Any) -> int | None:
    """capstone 指令 → ``ldr rN, [pc, #imm]`` 字面量的值（ROM 文件偏移），否则 None。"""
    cs = _cs_mod()
    if insn.id == cs.arm.ARM_INS_INVALID:
        return None
    if insn.mnemonic != "ldr" or len(insn.operands) < 2:
        return None
    op1 = insn.operands[1]
    if op1.type != cs.arm.ARM_OP_MEM:
        return None
    if insn.reg_name(op1.mem.base) != "pc":
        return None
    lit = ((insn.address + 4) & ~3) + op1.mem.disp
    fo = lit - BASE
    if not (0 <= fo and fo + 4 <= len(rom)):
        return None
    v = struct.unpack_from("<I", rom, fo)[0]
    if BASE <= v < BASE + len(rom):
        return v - BASE
    return None


def _collect_consumed_set(
    rom: bytes,
    sinks: list[int],
    depth: int,
) -> frozenset[int]:
    """两阶段消费判定：调用关系 BFS + 参数逆推 + 指针表展开。

    内部实现（外部通过 is_execute / get_consumed_set 调用）。
    """
    visited, bl_index, func_starts = _visited_funcs(rom, sinks, depth)
    n = len(rom)
    starts_set = set(func_starts)
    callee_set = set(bl_index.keys())
    spans = sorted(_func_span(func_starts, f, n) for f in visited)
    merged: list[list[int]] = []
    for a, b in spans:
        if merged and a <= merged[-1][1]:
            if b > merged[-1][1]:
                merged[-1][1] = b
        else:
            merged.append([a, b])
    code_spans = [(a, b) for a, b in merged]
    span_starts = [a for a, _ in code_spans]

    # 第一阶段：参数逆推
    raw_refs: list[int] = []
    for f in visited:
        for site in bl_index.get(f, ()):
            if not _is_thumb_bl_at(rom, site):
                continue
            owner = _owner_func(func_starts, site)
            if owner is None:
                continue
            _lo2, hi2 = _func_span(func_starts, owner, n)
            src, _unresolved = _call_param_refs(rom, site, owner, hi2, 0xF)
            raw_refs.extend(src.values())

    # 第二阶段：指针表展开
    # 收集 visited 函数 ldr 的字面量值（表基址 / 单个数据指针）
    table_bases: set[int] = set()
    for f in visited:
        lo, hi = _func_span(func_starts, f, n)
        for insn in _func_insns(rom, f, hi):
            v = _ldr_literal_value(rom, insn)
            if v is not None:
                table_bases.add(v)
    for tb in table_bases:
        raw_refs.append(tb)
        raw_refs.extend(_expand_pointer_table(rom, tb))

    # 第三阶段：代码指针排除
    consumed: set[int] = set()
    for t in raw_refs:
        if _is_code_ptr(t, starts_set, callee_set, code_spans, span_starts):
            continue
        consumed.add(t)
    return frozenset(consumed)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_execute(
    rom: bytes,
    address: int,
    addressList: list[int],
    *,
    script_ops: list[str] | None = None,
    depth: int = DEFAULT_DEPTH,
    exclude_set: frozenset[int] | None = None,
) -> bool:
    """单地址判定：address（文件偏移）是否被消费。

    消费 = 命中以下任一：
    - address 作为 BL 参数（r0–r3）进入 addressList 中某函数的调用链；
    - address 被 script_ops 指定的脚本 op 参数位引用。

    exclude_set: 预计算的排除集合（如其它 filter 已消费的地址），命中排除集时视为未消费。

    内部预计算被消费集合（缓存），O(1) 查成员。
    """
    if rom is None or address < 0 or address >= len(rom):
        return False
    if not addressList and not script_ops:
        return False

    # 函数参数逆推
    if addressList:
        key = (id(rom), frozenset(addressList), depth)
        consumed = _IS_EXECUTE_CACHE.get(key)
        if consumed is None:
            consumed = _collect_consumed_set(rom, addressList, depth)
            _IS_EXECUTE_CACHE[key] = consumed
        if address in consumed:
            if exclude_set is None or address not in exclude_set:
                return True

    # 脚本 op 引用（预计算并缓存）
    if script_ops:
        ops_key = (id(rom), tuple(sorted(script_ops)))
        script_set = _SCRIPT_SET_CACHE.get(ops_key)
        if script_set is None:
            script_set = frozenset()
            for op_name in set(script_ops):
                for op_byte, ptr_offsets in _SCRIPT_OPS.get(op_name, ()):
                    script_set |= _scan_script_op_refs(rom, op_byte, ptr_offsets)
            _SCRIPT_SET_CACHE[ops_key] = script_set
        if address in script_set:
            if exclude_set is None or address not in exclude_set:
                return True

    return False


def get_consumed_set(
    rom: bytes, specs: list[dict[str, Any]] | None, *, exclude_set: frozenset[int] | None = None
) -> frozenset[int] | None:
    """批量预计算：返回 specs 内所有 execute_filter 的被消费地址并集（缓存）。

    exclude_set: 预计算的排除集合，命中排除集的地址从结果中剔除。
    用于 extract_scan 快速路径 / export_texts 迭代。
    """
    funcs: list[tuple[str, int, int]] = []
    ops: list[str] = []
    for spec in specs or []:
        if not isinstance(spec, dict):
            continue
        if str(spec.get("type") or "") != "execute_filter":
            continue
        f, o = parse_sink_items(spec.get("value"), rom_len=len(rom))
        funcs.extend(f)
        ops.extend(o)
    if not funcs and not ops:
        return None
    key = (id(rom), tuple(sorted(funcs)), tuple(sorted(set(ops))))
    hit = _EXECUTE_SET_CACHE.get(key)
    if hit is not None:
        return hit
    consumed: set[int] = set()
    for _name, fo, depth in funcs:
        # 复用 is_execute 的缓存（单 sink）
        ie_key = (id(rom), frozenset([fo]), depth)
        ie_hit = _IS_EXECUTE_CACHE.get(ie_key)
        if ie_hit is not None:
            consumed |= set(ie_hit)
        else:
            consumed |= set(_collect_consumed_set(rom, [fo], depth))
    for op_name in set(ops):
        for op_byte, ptr_offsets in _SCRIPT_OPS[op_name]:
            consumed |= _scan_script_op_refs(rom, op_byte, ptr_offsets)
    out = frozenset(consumed)
    _EXECUTE_SET_CACHE[key] = out
    if exclude_set is not None:
        out = out - exclude_set
    return out
