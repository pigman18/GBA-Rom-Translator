# -*- coding: utf-8 -*-
"""callers_filter：通用「消费可达」判定。

给定一个候选地址（传入地址），沿「谁把我加载进寄存器 → 我传给谁（BL）
→ 被调方闭包」这条链往上爬，直到经过 value 列表里的任一地址，即判 True。

原则：独立、通用、不叠含义。
- 不做文本识别、不猜寄存器真值、不区分注入叶/消费叶——value 只是地址列表。
- 换一种数据（如图片），只要把 value 换成对应消费点地址即可复用。

value 列表两种项：
- ``{name, address}``：address 是消费点；走上面的正向爬升。
- ``{name}``（内建 op：message / trainerbattle / …）：脚本操作数，走脚本 walk。
"""

from __future__ import annotations

import re
import struct
from typing import Any

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

from util._script_walk import get_script_roots, walk_script_ops

BASE = 0x08000000
TITLE_LZ_BAND = (0x36D000, 0x370000)

# 脚本 op 项：走 walk_script_ops，不经地址爬升
_INBUILT_OPS = frozenset(
    {"message", "messageautoscroll", "loadword_callstd", "trainerbattle"}
)

# 被调方闭包深度（正向爬升时，BL 目标向上/向下能追多远）
_DEFAULT_CALLEE_DEPTH = 8

_CALLERS_CACHE: dict[tuple[Any, ...], frozenset[int]] = {}
_ACTIVE_ROM: bytes | None = None
_MD = Cs(CS_ARCH_ARM, CS_MODE_THUMB)

_FUNC_ENTRY_MEMO: dict[tuple[int, int], int | None] = {}


def set_active_rom(rom: bytes | None) -> None:
    global _ACTIVE_ROM
    _ACTIVE_ROM = rom


def get_active_rom() -> bytes | None:
    return _ACTIVE_ROM


def clear_callers_cache() -> None:
    _CALLERS_CACHE.clear()
    _FUNC_ENTRY_MEMO.clear()
    _CALLEE_REACH_MEMO.clear()


def _parse_addr(v: object) -> int:
    if isinstance(v, int):
        return v
    s = str(v).strip().lower().replace("_", "")
    return int(s, 16)


def _fo(vma_or_fo: int) -> int:
    if vma_or_fo >= BASE:
        return vma_or_fo - BASE
    return vma_or_fo


def _is_rom_ptr(v: int, rom_len: int) -> bool:
    if not (BASE <= v < BASE + rom_len):
        return False
    fo = v - BASE
    if TITLE_LZ_BAND[0] <= fo < TITLE_LZ_BAND[1]:
        return False
    return True


def _is_rom_text_ptr(v: int, rom_len: int) -> bool:
    if not _is_rom_ptr(v, rom_len):
        return False
    fo = v - BASE
    if fo < 0x100000 or fo >= rom_len:
        return False
    return True


def _add_ptr(out: set[int], v: int, rom: bytes) -> None:
    if not _is_rom_text_ptr(v, len(rom)):
        return
    out.add(v - BASE)


# ---------------------------------------------------------------------------
# 通用原语
# ---------------------------------------------------------------------------

def _thumb_bl_target(rom: bytes, fo: int) -> int | None:
    if fo < 0 or fo + 4 > len(rom):
        return None
    hw1, hw2 = struct.unpack_from("<HH", rom, fo)
    if (hw1 & 0xF800) != 0xF000:
        return None
    if (hw2 & 0xD000) != 0xD000:
        return None
    s = (hw1 >> 10) & 1
    imm10 = hw1 & 0x3FF
    j1 = (hw2 >> 13) & 1
    j2 = (hw2 >> 11) & 1
    imm11 = hw2 & 0x7FF
    i1 = 1 ^ (j1 ^ s)
    i2 = 1 ^ (j2 ^ s)
    imm = (s << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
    if s:
        imm -= 1 << 25
    return (BASE + fo + 4 + imm) & ~1


def _build_bl_index(rom: bytes, *, scan_end: int | None = None) -> dict[int, list[int]]:
    """target_vma(~1) -> [call_fo, …]"""
    n = len(rom)
    end = min(n - 3, scan_end if scan_end is not None else n)
    idx: dict[int, list[int]] = {}
    fo = 0
    while fo < end:
        if TITLE_LZ_BAND[0] <= fo < TITLE_LZ_BAND[1]:
            fo = TITLE_LZ_BAND[1]
            continue
        tgt = _thumb_bl_target(rom, fo)
        if tgt is not None:
            idx.setdefault(tgt, []).append(fo)
            fo += 4
            continue
        fo += 2
    return idx


def _find_func_entry(rom: bytes, call_fo: int) -> int | None:
    """自调用点向前找含 LR 的 Thumb push，当作函数入口。"""
    start = call_fo & ~1
    if start < 0 or start >= len(rom):
        return None
    key = (id(rom), start)
    if key in _FUNC_ENTRY_MEMO:
        return _FUNC_ENTRY_MEMO[key]
    lo = max(0, start - 0x400)
    fo = start
    result: int | None = None
    while fo >= lo:
        hw = struct.unpack_from("<H", rom, fo)[0]
        if (hw & 0xFF00) == 0xB500 and (hw & 0x0100):
            result = fo
            break
        fo -= 2
    _FUNC_ENTRY_MEMO[key] = result
    return result


# ---------------------------------------------------------------------------
# 正向爬升：候选地址 -> ldr -> BL -> 被调方闭包 -> 是否到 sink
# ---------------------------------------------------------------------------

def _build_literal_ldrs(
    rom: bytes, *, scan_end: int | None = None
) -> dict[int, list[tuple[int, str, int]]]:
    """value_vma -> [(ldr_fo, reg, insn_size)]：全盘找「ldr Rd, [pc, #imm]」并反查字面量值。"""
    n = len(rom)
    end = min(n - 1, scan_end if scan_end is not None else 0x400000)
    out: dict[int, list[tuple[int, str, int]]] = {}
    fo = 0
    while fo < end:
        if TITLE_LZ_BAND[0] <= fo < TITLE_LZ_BAND[1]:
            fo = TITLE_LZ_BAND[1]
            continue
        hw = struct.unpack_from("<H", rom, fo)[0]
        lit_fo: int | None = None
        reg: str | None = None
        size = 2
        if (hw & 0xF800) == 0x4800:
            # Thumb-1 ldr Rd, [pc, #imm8*4]
            rd = (hw >> 8) & 0x7
            imm = (hw & 0xFF) * 4
            lit_fo = ((fo + 4) & ~3) + imm
            reg = f"r{rd}"
        elif hw in (0xF8DF, 0xF85F) and fo + 4 <= n:
            # Thumb-2 ldr.w Rd, [pc, #±imm12]
            hw2 = struct.unpack_from("<H", rom, fo + 2)[0]
            rd = (hw2 >> 12) & 0xF
            imm = hw2 & 0xFFF
            sign = 1 if hw == 0xF8DF else -1
            lit_fo = ((fo + 4) & ~3) + sign * imm
            reg = f"r{rd}"
            size = 4
        if lit_fo is not None and reg is not None:
            if 0 <= lit_fo <= n - 4:
                v = struct.unpack_from("<I", rom, lit_fo)[0]
                if _is_rom_ptr(v, n):
                    out.setdefault(v, []).append((fo, reg, size))
            fo += size
            continue
        fo += 2
    return out


def _next_bl_target(rom: bytes, insn_fo: int, reg: str, insn_size: int) -> int | None:
    """从 ldr 之后正向走到下一条 BL：返回其目标 VMA；若值被解引用/写回/分支则 None。"""
    n = len(rom)
    start = insn_fo + insn_size
    chunk = rom[start : min(n, start + 0x40)]
    live = reg
    for insn in _MD.disasm(chunk, BASE + start):
        m = insn.mnemonic
        parts = [p.strip().lower() for p in insn.op_str.split(",")]
        if m == "bl":
            return _thumb_bl_target(rom, insn.address - BASE)
        if m in ("blx", "bx", "b", "pop", "push", "ldm", "stm", "cbz", "cbnz"):
            return None
        if m.startswith("b"):
            return None
        # live 被解引用（ldr rM, [live, …]）→ 它是表基，不是直接正文
        if m == "ldr" and len(parts) >= 2 and live in parts[1]:
            return None
        # 写回 live 寄存器 → 值已不是原样传给下一条 BL
        if parts and parts[0] == live and m not in ("cmp", "cmn", "tst", "teq", "nop"):
            return None
    return None


def _expand_ptr_table(rom: bytes, base_vma: int, stride: int, max_n: int = 256) -> list[int]:
    """自表基连读 u32 正文指针，遇非法指针即停。"""
    n = len(rom)
    if stride < 2:
        stride = 4
    out: list[int] = []
    for i in range(max_n):
        fo = (base_vma - BASE) + i * stride
        if fo < 0 or fo + 4 > n:
            break
        p = struct.unpack_from("<I", rom, fo)[0]
        if not _is_rom_text_ptr(p, n):
            break
        out.append(p)
    return out


def _scan_table_consumers(
    rom: bytes, insn_fo: int, reg: str, insn_size: int, table_base_vma: int
) -> list[tuple[int, int | None]]:
    """从「ldr reg, =table」后正向走，收集 [被加载元素 vma -> bl 目标 vma]。"""
    n = len(rom)
    start = insn_fo + insn_size
    chunk = rom[start : min(n, start + 0x60)]
    base_regs = {reg}
    pending: list[int] = []
    results: list[tuple[int, int | None]] = []
    for insn in _MD.disasm(chunk, BASE + start):
        m = insn.mnemonic
        op = insn.op_str
        parts = [p.strip().lower() for p in op.split(",")]
        if m == "bl":
            tgt = _thumb_bl_target(rom, insn.address - BASE)
            for pv in pending:
                results.append((pv, tgt))
            pending = []
            continue
        if m in ("blx", "bx", "b", "pop", "push", "ldm", "stm", "cbz", "cbnz") or m.startswith("b"):
            break
        # ldr rM, [rN, #off]（静态偏移 → 表基+off）
        m1 = re.match(r"^(\w+)\s*,\s*\[(\w+)\s*,\s*#(-?0x[0-9a-f]+|-?\d+)\]$", op, re.I)
        if m1:
            base_r, off_s = m1.group(2).lower(), m1.group(3)
            if base_r in base_regs:
                off = int(off_s, 0)
                pending = [table_base_vma + off]
            continue
        # ldr rM, [rN, rIdx(, lsl #k)]（动态索引 → 整表展开）
        m2 = re.match(r"^(\w+)\s*,\s*\[(\w+)\s*,\s*(\w+)(?:\s*,\s*lsl\s*#(\d+))?\]$", op, re.I)
        if m2:
            base_r, lsl_s = m2.group(2).lower(), m2.group(4)
            if base_r in base_regs:
                stride = (1 << int(lsl_s)) if lsl_s else 4
                pending = _expand_ptr_table(rom, table_base_vma, stride)
            continue
        # 表基寄存器转发（mov rX, rN / adds rX, rN, #0）
        if m in ("mov", "movs") and len(parts) == 2 and parts[1] in base_regs:
            base_regs.add(parts[0])
            continue
        if m in ("add", "adds") and len(parts) >= 3 and parts[2] in ("#0", "0") and parts[1] in base_regs:
            base_regs.add(parts[0])
            continue
        # 写回表基寄存器 → 移出
        if parts and parts[0] in base_regs and m not in ("cmp", "cmn", "tst", "teq", "nop"):
            base_regs.discard(parts[0])
    return results


def _func_callees(rom: bytes, entry_fo: int, cap: int = 0x1000) -> set[int]:
    """扫 entry_fo 起的函数体到首个返回指令，收集 BL 目标（文件偏移）。

    以函数返回指令（bx lr / pop {...,pc}）为界，不再扫进后续无关代码；
    否则叶函数（只 str 指针到全局就 bx lr）会把下个函数里的 BL 误算成自己的 callee。
    """
    n = len(rom)
    end = min(n, entry_fo + cap)
    out: set[int] = set()
    fo = entry_fo
    while fo < end - 1:
        t = _thumb_bl_target(rom, fo)
        if t is not None:
            cfo = (t & ~1) - BASE
            if 0 <= cfo < n:
                out.add(cfo)
            fo += 4
            continue
        hw = struct.unpack_from("<H", rom, fo)[0]
        if hw == 0x4770 or (hw & 0xFF00) == 0xBD00:
            break  # bx lr / pop {..., pc}
        fo += 2
    return out


_CALLEE_REACH_MEMO: dict[tuple[int, frozenset[int]], bool] = {}


def _callee_reaches(rom: bytes, target_fo: int, sink_fos: frozenset[int], depth: int = 8) -> bool:
    """从 target_fo 沿被调方闭包（正向）爬，看是否到达任一 sink。"""
    key = (target_fo & ~1, sink_fos)
    hit = _CALLEE_REACH_MEMO.get(key)
    if hit is not None:
        return hit
    result = False
    seen: set[int] = set()
    frontier = [target_fo & ~1]
    for _ in range(depth + 1):
        nxt: list[int] = []
        for f in frontier:
            if f in seen:
                continue
            seen.add(f)
            if f in sink_fos:
                result = True
                break
            for c in _func_callees(rom, f):
                if c in sink_fos:
                    result = True
                    break
                if c not in seen:
                    nxt.append(c)
            if result:
                break
        if result:
            break
        frontier = nxt
        if not frontier:
            break
    _CALLEE_REACH_MEMO[key] = result
    return result


def _forward_reachable(rom: bytes, sink_fos: list[int]) -> frozenset[int]:
    """正向：所有「被 ldr 加载、紧接着 BL 给一个能到 sink 的函数」的地址。

    分两种：
    - 直接：ldr rN,=text; bl → text 本身可达。
    - 表基：ldr rN,=table; ldr rM,[rN,…]; bl → 表项可达。
    """
    n = len(rom)
    lit_ldrs = _build_literal_ldrs(rom)
    if not lit_ldrs:
        return frozenset()
    sink = frozenset(s & ~1 for s in sink_fos if 0 <= s < n)

    out: set[int] = set()
    for value_vma, loaders in lit_ldrs.items():
        a = value_vma - BASE
        if not (0 <= a < n):
            continue
        for fo, reg, size in loaders:
            tgt = _next_bl_target(rom, fo, reg, size)
            if tgt is not None:
                if _callee_reaches(rom, (tgt & ~1) - BASE, sink):
                    out.add(a)
                    break
            for elem_vma, btgt in _scan_table_consumers(rom, fo, reg, size, value_vma):
                if btgt is not None and _callee_reaches(rom, (btgt & ~1) - BASE, sink):
                    ea = elem_vma - BASE
                    if 0 <= ea < n:
                        out.add(ea)
    return frozenset(out)


# ---------------------------------------------------------------------------
# 配置解析
# ---------------------------------------------------------------------------

def _address_sinks_from_spec(spec: dict[str, Any]) -> list[int]:
    out: list[int] = []
    val = spec.get("value")
    if not isinstance(val, list):
        return out
    for item in val:
        if not isinstance(item, dict):
            continue
        if item.get("address") is None:
            continue
        out.append(_fo(_parse_addr(item["address"])))
    return out


def _script_ops_from_spec(spec: dict[str, Any]) -> frozenset[str]:
    val = spec.get("value")
    ops: set[str] = set()
    if isinstance(val, list):
        for item in val:
            if not isinstance(item, dict):
                continue
            if item.get("address") is not None:
                continue
            name = str(item.get("name") or "").strip().lower()
            if name in _INBUILT_OPS:
                ops.add(name)
    return frozenset(ops)


def _configs_from_filters(
    filters: list[dict[str, Any]] | None,
) -> list[tuple[list[int], frozenset[str]]]:
    out: list[tuple[list[int], frozenset[str]]] = []
    for spec in filters or []:
        if not isinstance(spec, dict):
            continue
        if str(spec.get("type") or "") != "callers_filter":
            continue
        sinks = _address_sinks_from_spec(spec)
        ops = _script_ops_from_spec(spec)
        if not sinks and not ops:
            continue
        out.append((sinks, ops))
    return out


def filters_need_callers(filters: list[dict[str, Any]] | None) -> bool:
    return bool(_configs_from_filters(filters))


# ---------------------------------------------------------------------------
# 公开入口
# ---------------------------------------------------------------------------

def ensure_callers_cache(
    rom: bytes, filters: list[dict[str, Any]] | None
) -> frozenset[int] | None:
    configs = _configs_from_filters(filters)
    if not configs:
        return None
    merged_sinks: set[int] = set()
    merged_ops: set[str] = set()
    for sinks, ops in configs:
        merged_sinks.update(sinks)
        merged_ops.update(ops)

    roots = get_script_roots()
    roots_key = tuple(sorted((str(k), str(v)) for k, v in roots.items()))
    key = (id(rom), tuple(sorted(merged_sinks)), frozenset(merged_ops), roots_key)
    hit = _CALLERS_CACHE.get(key)
    if hit is not None:
        return hit

    out: set[int] = set()
    if merged_sinks:
        out |= _forward_reachable(rom, sorted(merged_sinks))
    if merged_ops & _INBUILT_OPS:
        walk_script_ops(rom, frozenset(merged_ops), out, add_ptr=_add_ptr)

    reachable = frozenset(out)
    _CALLERS_CACHE[key] = reachable
    return reachable


def get_callers_reachable_for_filters(
    rom: bytes, filters: list[dict[str, Any]] | None
) -> frozenset[int] | None:
    return ensure_callers_cache(rom, filters)
