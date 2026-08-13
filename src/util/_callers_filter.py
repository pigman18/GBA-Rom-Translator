# -*- coding: utf-8 -*-
"""callers_filter：判断「类文本」会否被 PrintNextChar 消费。

PrintNextChar 读的是 win[+0x10]；绑串叶是 InitTextPrinter（str r1 → +0x10）。
本模块只做：从 bind_leaf 全盘逆推 BL → 解析文本参数（含包装层与表形 ldr）。
剧情 / UI 归属由其它 filter（地址带等）决定，不在这里分类。

脚本 message / trainerbattle 仍可走 script_ops（入口 walk，指针常经 RAM）。
"""

from __future__ import annotations

import re
import struct
from typing import Any

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

from util._script_walk import get_script_roots, walk_script_ops

BASE = 0x08000000
SCRIPT_BANK_MIN = 0x100000
TITLE_LZ_BAND = (0x36D000, 0x370000)

_FIELD_MESSAGE_SINK_NAMES = frozenset(
    {
        "ShowFieldMessage",
        "ShowFieldAutoScrollMessage",
    }
)

_DEFAULT_FIELD_SCRIPT_OPS = frozenset(
    {"message", "messageautoscroll", "loadword_callstd"}
)

# (name, file_off, text_arg)  text_arg in {"r0","r1"}
SinkSpec = tuple[str, int, str]

_CALLERS_CACHE: dict[tuple[Any, ...], frozenset[int]] = {}
_ACTIVE_ROM: bytes | None = None

_LDR_REG_IDX = re.compile(
    r"^(\w+)\s*,\s*\[(\w+)\s*,\s*(\w+)(?:\s*,\s*lsl\s*#(\d+))?\]\s*$",
    re.I,
)
_LDR_REG_IMM = re.compile(
    r"^(\w+)\s*,\s*\[(\w+)\s*,\s*#(-?0x[0-9a-fA-F]+|-?\d+)\]\s*$",
    re.I,
)


def set_active_rom(rom: bytes | None) -> None:
    global _ACTIVE_ROM
    _ACTIVE_ROM = rom


def get_active_rom() -> bytes | None:
    return _ACTIVE_ROM


def _parse_addr(v: object) -> int:
    if isinstance(v, int):
        return v
    s = str(v).strip().lower().replace("_", "")
    if s.startswith("0x"):
        return int(s, 16)
    return int(s, 16)


def _fo(vma_or_fo: int) -> int:
    if vma_or_fo >= BASE:
        return vma_or_fo - BASE
    return vma_or_fo


def _parse_text_arg(v: object) -> str:
    s = str(v or "r0").strip().lower()
    if s in ("r0", "0"):
        return "r0"
    if s in ("r1", "1"):
        return "r1"
    raise SystemExit(f"callers_filter text_arg must be r0 or r1, got {v!r}")


def _in_title_lz(fo: int) -> bool:
    return TITLE_LZ_BAND[0] <= fo < TITLE_LZ_BAND[1]


def _is_rom_ptr(v: int, rom_len: int) -> bool:
    """任意 ROM 指针（表基 / 正文）。"""
    if not (BASE <= v < BASE + rom_len):
        return False
    fo = v - BASE
    if _in_title_lz(fo):
        return False
    return True


def _is_rom_text_ptr(v: int, rom_len: int) -> bool:
    if not _is_rom_ptr(v, rom_len):
        return False
    fo = v - BASE
    if fo < SCRIPT_BANK_MIN or fo >= rom_len:
        return False
    return True


def _bind_leaf_from_value(val: dict[str, Any]) -> SinkSpec | None:
    raw = val.get("bind_leaf")
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name") or "bind_leaf").strip() or "bind_leaf"
    if "address" not in raw or raw.get("address") is None:
        raise SystemExit(f"callers_filter bind_leaf {name!r} missing 'address'")
    fo = _fo(_parse_addr(raw["address"]))
    text_arg = _parse_text_arg(raw.get("text_arg", "r1"))
    return (name, fo, text_arg)


def _wrapper_depth_from_value(val: dict[str, Any]) -> int:
    d = val.get("wrapper_depth", 4)
    try:
        n = int(d)
    except (TypeError, ValueError):
        n = 4
    return max(0, min(n, 8))


def _sinks_from_spec(spec: dict[str, Any]) -> list[SinkSpec]:
    out: list[SinkSpec] = []
    seen: set[tuple[int, str]] = set()
    val = spec.get("value")
    if not isinstance(val, dict):
        return out

    leaf = _bind_leaf_from_value(val)
    if leaf is not None:
        key = (leaf[1], leaf[2])
        seen.add(key)
        out.append(leaf)

    sinks = val.get("sinks")
    if isinstance(sinks, list):
        for item in sinks:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip() or "<unnamed>"
            if "address" not in item:
                extras = sorted(k for k in item if k not in ("name", "text_arg"))
                hint = ""
                if any(k for k in extras if "addr" in str(k).lower()):
                    hint = f" (did you mean address=? got keys {extras})"
                raise SystemExit(
                    f"callers_filter sink {name!r} missing required key 'address'{hint}"
                )
            addr = item.get("address")
            if addr is None:
                raise SystemExit(f"callers_filter sink {name!r} address is null")
            fo = _fo(_parse_addr(addr))
            text_arg = _parse_text_arg(item.get("text_arg", "r0"))
            key = (fo, text_arg)
            if key in seen:
                continue
            seen.add(key)
            out.append((name, fo, text_arg))
    return out


def _script_ops_from_spec(
    spec: dict[str, Any], sinks: list[SinkSpec]
) -> frozenset[str]:
    val = spec.get("value")
    if not isinstance(val, dict):
        val = {}
    raw = val.get("script_ops")
    if raw is None:
        if any(name in _FIELD_MESSAGE_SINK_NAMES for name, _fo, _ta in sinks):
            return _DEFAULT_FIELD_SCRIPT_OPS
        return frozenset()
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return frozenset()
    return frozenset(str(x).strip().lower() for x in raw if str(x).strip())


def _configs_from_filters(
    filters: list[dict[str, Any]] | None,
) -> list[tuple[list[SinkSpec], frozenset[str], int]]:
    """(sinks, script_ops, wrapper_depth)."""
    out: list[tuple[list[SinkSpec], frozenset[str], int]] = []
    for spec in filters or []:
        if not isinstance(spec, dict):
            continue
        if str(spec.get("type") or "") != "callers_filter":
            continue
        val = spec.get("value") if isinstance(spec.get("value"), dict) else {}
        sinks = _sinks_from_spec(spec)
        ops = _script_ops_from_spec(spec, sinks)
        depth = _wrapper_depth_from_value(val) if val.get("bind_leaf") else 0
        if not sinks and not ops:
            continue
        out.append((sinks, ops, depth))
    return out


def filters_need_callers(filters: list[dict[str, Any]] | None) -> bool:
    return bool(_configs_from_filters(filters))


def _add_ptr(out: set[int], v: int, rom: bytes) -> None:
    if not _is_rom_text_ptr(v, len(rom)):
        return
    out.add(v - BASE)


def _pc_literal_addr(insn_addr: int, insn_size: int, imm: int) -> int:
    pc = insn_addr + 4
    return (pc & ~3) + imm


def _parse_ldr_pc_imm(op_str: str) -> int | None:
    if "[pc," not in op_str:
        return None
    try:
        hash_i = op_str.index("#")
        end = op_str.find("]", hash_i)
        imm_s = op_str[hash_i + 1 : end if end > 0 else None].strip()
        return int(imm_s, 0)
    except (ValueError, IndexError):
        return None


def _expand_ptr_table(
    rom: bytes, base_vma: int, stride: int, *, text_off: int = 0, max_n: int = 256
) -> list[int]:
    """从 ROM 表基扫 u32 正文指针，遇非法指针即停。"""
    n = len(rom)
    if stride < 4:
        return []
    out: list[int] = []
    for i in range(max_n):
        fo = (base_vma - BASE) + i * stride + text_off
        if fo < 0 or fo + 4 > n:
            break
        p = struct.unpack_from("<I", rom, fo)[0]
        if not _is_rom_text_ptr(p, n):
            break
        out.append(p)
    return out


def _resolve_reg_rom_ptrs(
    rom: bytes, call_fo: int, md: Cs, reg: str
) -> list[int]:
    """窗口正扫：PC 字面量、表基+变址、lsl/add 后 ldr [Rn] → 整表展开。"""
    n = len(rom)
    target_reg = reg.lower()
    win_lo = max(0, (call_fo - 0x120) & ~1)
    chunk = rom[win_lo:call_fo]
    if len(chunk) < 2:
        return []

    # ptr[reg] = ROM vma（表基或正文）
    # scaled[reg] = lsl 位移（stride=1<<shift）
    # elem[reg] = (base_vma, stride)  — 寄存器里是 &table[i]
    ptr: dict[str, int] = {}
    scaled: dict[str, int] = {}
    elem: dict[str, tuple[int, int]] = {}
    found: list[int] = []

    def clear_reg(r: str) -> None:
        ptr.pop(r, None)
        scaled.pop(r, None)
        elem.pop(r, None)

    def copy_reg(dst: str, src: str) -> None:
        clear_reg(dst)
        if src in ptr:
            ptr[dst] = ptr[src]
        if src in scaled:
            scaled[dst] = scaled[src]
        if src in elem:
            elem[dst] = elem[src]

    def try_expand(base: int, stride: int) -> list[int]:
        if stride < 4:
            stride = 4
        return _expand_ptr_table(rom, base, stride)

    def note_load_to(dest: str, values: list[int]) -> None:
        nonlocal found
        clear_reg(dest)
        if not values:
            return
        if len(values) == 1:
            ptr[dest] = values[0]
        if dest == target_reg:
            found = values

    for insn in md.disasm(chunk, BASE + win_lo):
        mnem = insn.mnemonic
        op = insn.op_str
        parts = [p.strip().lower() for p in op.split(",")]

        if mnem == "ldr" and "[pc," in op:
            imm = _parse_ldr_pc_imm(op)
            if imm is None:
                continue
            lit_addr = _pc_literal_addr(insn.address, insn.size, imm)
            lit_fo = lit_addr - BASE
            if not (0 <= lit_fo <= n - 4):
                continue
            v = struct.unpack_from("<I", rom, lit_fo)[0]
            dest = parts[0]
            clear_reg(dest)
            if _is_rom_ptr(v, n):
                ptr[dest] = v
                # 字面量本身已是正文指针（非表基）
                if dest == target_reg and _is_rom_text_ptr(v, n):
                    # 可能是表基误判为正文；若可扩成多条则当表，否则单条
                    expanded = try_expand(v, 4)
                    if len(expanded) >= 2:
                        found = expanded
                    else:
                        found = [v]
            continue

        if mnem == "ldr":
            m = _LDR_REG_IDX.match(op.strip())
            if m:
                dest, base_r, _idx_r, lsl_s = (
                    m.group(1).lower(),
                    m.group(2).lower(),
                    m.group(3).lower(),
                    m.group(4),
                )
                if base_r in ptr:
                    lsl = int(lsl_s) if lsl_s is not None else 0
                    stride = 1 << lsl if lsl_s is not None else 4
                    note_load_to(dest, try_expand(ptr[base_r], stride))
                else:
                    clear_reg(dest)
                continue
            m2 = _LDR_REG_IMM.match(op.strip())
            if m2:
                dest, base_r, imm_s = (
                    m2.group(1).lower(),
                    m2.group(2).lower(),
                    m2.group(3),
                )
                if base_r in ptr:
                    imm = int(imm_s, 0)
                    fo = (ptr[base_r] - BASE) + imm
                    if 0 <= fo <= n - 4:
                        p = struct.unpack_from("<I", rom, fo)[0]
                        if _is_rom_text_ptr(p, n):
                            note_load_to(dest, [p])
                        else:
                            clear_reg(dest)
                    else:
                        clear_reg(dest)
                elif base_r in elem:
                    base, stride = elem[base_r]
                    note_load_to(dest, try_expand(base, stride))
                else:
                    clear_reg(dest)
                continue
            # ldr Rt, [Rn] — Start Menu / 口袋：算址后间接取指针
            m3 = re.match(r"^(\w+)\s*,\s*\[(\w+)\]\s*$", op.strip(), re.I)
            if m3:
                dest, addr_r = m3.group(1).lower(), m3.group(2).lower()
                if addr_r in elem:
                    base, stride = elem[addr_r]
                    note_load_to(dest, try_expand(base, stride))
                elif addr_r in ptr:
                    # 绝对址上的 u32：可能是单指针，也可能误把表基当绝对
                    fo = ptr[addr_r] - BASE
                    if 0 <= fo <= n - 4:
                        p = struct.unpack_from("<I", rom, fo)[0]
                        if _is_rom_text_ptr(p, n):
                            note_load_to(dest, [p])
                        else:
                            clear_reg(dest)
                    else:
                        clear_reg(dest)
                else:
                    clear_reg(dest)
                continue
            continue

        if mnem in ("lsl", "lsls") and len(parts) >= 3 and parts[2].startswith("#"):
            dest, src = parts[0], parts[1]
            try:
                sh = int(parts[2][1:], 0)
            except ValueError:
                clear_reg(dest)
                continue
            clear_reg(dest)
            if 1 <= sh <= 4:
                scaled[dest] = sh
            continue

        if mnem in ("mov", "movs") and len(parts) >= 2:
            dest, src = parts[0], parts[1]
            if src.startswith("#"):
                clear_reg(dest)
            else:
                copy_reg(dest, src)
            continue

        if mnem in ("add", "adds"):
            # adds Rd, Rs, #0 / adds Rd, Rs, Rt / add Rd, Rs
            if len(parts) == 2:
                # Thumb: add Rd, Rs  => Rd += Rs
                dest, src = parts[0], parts[1]
                if dest in scaled and src in ptr:
                    elem[dest] = (ptr[src], 1 << scaled[dest])
                    ptr.pop(dest, None)
                    scaled.pop(dest, None)
                elif src in scaled and dest in ptr:
                    elem[dest] = (ptr[dest], 1 << scaled[src])
                    ptr.pop(dest, None)
                    scaled.pop(dest, None)
                elif dest in ptr and src in ptr:
                    # 少见：两指针相加 — 清
                    clear_reg(dest)
                elif src in ptr and dest not in ptr:
                    # Rd was index-ish, Rs base without tracked scale — stride 4
                    elem[dest] = (ptr[src], 4)
                    scaled.pop(dest, None)
                elif dest in ptr:
                    # Rd = base + unknown → 仍作表基候选
                    elem[dest] = (ptr[dest], 4)
                    ptr.pop(dest, None)
                else:
                    clear_reg(dest)
                continue
            if len(parts) >= 3:
                dest = parts[0]
                a, b = parts[1], parts[2]
                if b in ("#0", "0"):
                    copy_reg(dest, a)
                    continue
                if b.startswith("#"):
                    clear_reg(dest)
                    if a in ptr:
                        # base+imm 暂当新 ptr（少见）
                        try:
                            imm = int(b[1:], 0)
                        except ValueError:
                            continue
                        ptr[dest] = ptr[a] + imm
                    continue
                # adds Rd, Ra, Rb
                base_vma = None
                sh = None
                if a in ptr and b in scaled:
                    base_vma, sh = ptr[a], scaled[b]
                elif b in ptr and a in scaled:
                    base_vma, sh = ptr[b], scaled[a]
                elif a in ptr:
                    base_vma, sh = ptr[a], 2
                elif b in ptr:
                    base_vma, sh = ptr[b], 2
                clear_reg(dest)
                if base_vma is not None:
                    stride = 1 << (sh if sh is not None else 2)
                    if stride < 4:
                        stride = 4
                    elem[dest] = (base_vma, stride)
                continue
            continue

        if mnem in ("bl", "blx"):
            # 调用会破坏调用约定寄存器；保留高位寄存器表基（r4+）粗略处理：全清
            ptr.clear()
            scaled.clear()
            elem.clear()
            continue

    return found


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


def _iter_bl_sites_to(
    rom: bytes, target_vma: int, *, scan_end: int | None = None
) -> list[int]:
    n = len(rom)
    end = min(n - 3, scan_end if scan_end is not None else n)
    tgt = target_vma & ~1
    out: list[int] = []
    fo = 0
    while fo < end:
        if TITLE_LZ_BAND[0] <= fo < TITLE_LZ_BAND[1]:
            fo = TITLE_LZ_BAND[1]
            continue
        if _thumb_bl_target(rom, fo) == tgt:
            out.append(fo)
            fo += 4
            continue
        fo += 2
    return out


def _build_bl_index(rom: bytes, *, scan_end: int | None = None) -> dict[int, list[int]]:
    """一次扫描：target_vma(~1) → [call_fo, …]。"""
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
    lo = max(0, start - 0x400)
    fo = start
    while fo >= lo:
        hw = struct.unpack_from("<H", rom, fo)[0]
        # PUSH T1: 1011 010 M Rlist — M=1 includes LR → 0xB5xx
        if (hw & 0xFF00) == 0xB500 and (hw & 0x0100):
            return fo
        fo -= 2
    return None


def _infer_outer_text_arg(
    rom: bytes, entry_fo: int, call_fo: int, callee_text_arg: str, md: Cs
) -> str:
    """看包装函数里如何把外参送进 callee_text_arg（常见 r0→r5→r1）。"""
    if entry_fo < 0 or call_fo <= entry_fo:
        return callee_text_arg
    chunk = rom[entry_fo:call_fo]
    if len(chunk) < 2:
        return callee_text_arg
    callee = callee_text_arg.lower()
    # reg -> 最初来源（追到 r0..r3 或自身）
    root: dict[str, str] = {}

    def set_root(dst: str, src: str) -> None:
        src = src.lower()
        dst = dst.lower()
        if src.startswith("#"):
            root.pop(dst, None)
            return
        root[dst] = root.get(src, src)

    for insn in md.disasm(chunk, BASE + entry_fo):
        if insn.mnemonic not in ("mov", "movs", "adds", "add"):
            continue
        parts = [p.strip().lower() for p in insn.op_str.split(",")]
        if len(parts) < 2:
            continue
        if len(parts) == 2:
            # add Rd, Rs => Rd+=Rs，不作纯转发
            if insn.mnemonic in ("mov", "movs"):
                set_root(parts[0], parts[1])
            continue
        # adds Rd, Rs, #0 / mov Rd, Rs
        if parts[2] in ("#0", "0") or (
            insn.mnemonic in ("mov", "movs") and not parts[1].startswith("#")
        ):
            set_root(parts[0], parts[1])
            continue
    cur = callee
    seen: set[str] = set()
    while cur in root and cur not in seen:
        seen.add(cur)
        cur = root[cur]
    if cur in ("r0", "r1", "r2", "r3"):
        return cur
    return callee


# AXVJ：ROM→RAM 后再绑 PrintNextChar 的常见拷贝叶（StringCopy src=r1）
_STRING_COPY_FO = 0x42E8
_STRING_COPY_TEXT_ARG = "r1"


def _collect_bind_leaf_closure(
    rom: bytes,
    leaf: SinkSpec,
    wrapper_depth: int,
    out: set[int],
) -> None:
    """从 bind_leaf 起：BL 全集 + 包装闭包 + 表展开；并扫 StringCopy 表形源。"""
    n = len(rom)
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    scan_end = min(n, 0x400000)
    bl_index = _build_bl_index(rom, scan_end=scan_end)
    _name, leaf_fo, leaf_arg = leaf
    # frontier: fo -> text_arg at call sites targeting this fo
    frontier: dict[int, str] = {leaf_fo: leaf_arg}
    seen_funcs: set[int] = {leaf_fo}

    for _depth in range(wrapper_depth + 1):
        next_frontier: dict[int, str] = {}
        for sink_fo, text_arg in frontier.items():
            for call_fo in bl_index.get((BASE + sink_fo) & ~1, ()):
                for v in _resolve_reg_rom_ptrs(rom, call_fo, md, text_arg):
                    _add_ptr(out, v, rom)
                entry = _find_func_entry(rom, call_fo)
                if entry is None or entry in seen_funcs:
                    continue
                seen_funcs.add(entry)
                outer_arg = _infer_outer_text_arg(rom, entry, call_fo, text_arg, md)
                next_frontier[entry] = outer_arg
        if not next_frontier:
            break
        frontier = next_frontier

    # 口袋名等：表项先 StringCopy 进 RAM，再被 PrintNextChar 消费
    for call_fo in bl_index.get((BASE + _STRING_COPY_FO) & ~1, ()):
        for v in _resolve_reg_rom_ptrs(rom, call_fo, md, _STRING_COPY_TEXT_ARG):
            _add_ptr(out, v, rom)


def _collect_from_bl_call_sites(
    rom: bytes,
    sinks: list[SinkSpec],
    out: set[int],
) -> None:
    """无 bind_leaf 时的旧路径：按 sinks 逐个 BL + 回溯。"""
    n = len(rom)
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    by_fo: dict[int, set[str]] = {}
    for _name, fo, text_arg in sinks:
        if 0 <= fo < n:
            by_fo.setdefault(fo, set()).add(text_arg)
    if not by_fo:
        return
    scan_end = min(n, 0x400000)
    bl_index = _build_bl_index(rom, scan_end=scan_end)
    for sink_fo, regs in by_fo.items():
        for call_fo in bl_index.get((BASE + sink_fo) & ~1, ()):
            for reg in regs:
                for v in _resolve_reg_rom_ptrs(rom, call_fo, md, reg):
                    _add_ptr(out, v, rom)


def build_callers_reachable(
    rom: bytes,
    sinks: list[tuple[str, int]] | list[SinkSpec],
    script_ops: frozenset[str] | None = None,
    *,
    wrapper_depth: int = 0,
    bind_leaf_fo: int | None = None,
) -> frozenset[int]:
    ops = script_ops if script_ops is not None else frozenset()
    norm: list[SinkSpec] = []
    for item in sinks:
        if len(item) == 2:
            name, fo = item  # type: ignore[misc]
            norm.append((name, fo, "r0"))
        else:
            name, fo, text_arg = item  # type: ignore[misc]
            norm.append((name, fo, _parse_text_arg(text_arg)))
    if not norm and not ops:
        return frozenset()
    out: set[int] = set()
    if bind_leaf_fo is not None and wrapper_depth >= 0:
        leaf = next((s for s in norm if s[1] == bind_leaf_fo), None)
        if leaf is not None:
            _collect_bind_leaf_closure(rom, leaf, wrapper_depth, out)
            # 其余非 leaf sinks 仍走直连 BL
            rest = [s for s in norm if s[1] != bind_leaf_fo]
            if rest:
                _collect_from_bl_call_sites(rom, rest, out)
        else:
            _collect_from_bl_call_sites(rom, norm, out)
    elif norm:
        _collect_from_bl_call_sites(rom, norm, out)
    if ops & {
        "message",
        "messageautoscroll",
        "loadword_callstd",
        "trainerbattle",
    }:
        walk_script_ops(rom, ops, out, add_ptr=_add_ptr)
    return frozenset(out)


def ensure_callers_cache(
    rom: bytes, filters: list[dict[str, Any]] | None
) -> frozenset[int] | None:
    configs = _configs_from_filters(filters)
    if not configs:
        return None
    merged: dict[tuple[int, str], str] = {}
    merged_ops: set[str] = set()
    max_depth = 0
    bind_fos: set[int] = set()
    for sinks, ops, depth in configs:
        for name, fo, text_arg in sinks:
            merged.setdefault((fo, text_arg), name)
        merged_ops |= set(ops)
        max_depth = max(max_depth, depth)
    for spec in filters or []:
        if not isinstance(spec, dict) or spec.get("type") != "callers_filter":
            continue
        v = spec.get("value")
        if isinstance(v, dict) and isinstance(v.get("bind_leaf"), dict):
            bind_fos.add(_fo(_parse_addr(v["bind_leaf"]["address"])))
    sinks_list: list[SinkSpec] = [
        (name, fo, ta)
        for (fo, ta), name in sorted(merged.items(), key=lambda x: (x[0][0], x[0][1]))
    ]
    ops_fs = frozenset(merged_ops)
    roots = get_script_roots()
    roots_key = tuple(sorted((str(k), str(v)) for k, v in roots.items()))
    bind_key = tuple(sorted(bind_fos))
    key = (
        id(rom),
        tuple((n, fo, ta) for n, fo, ta in sinks_list),
        tuple(sorted(ops_fs)),
        roots_key,
        max_depth,
        bind_key,
    )
    hit = _CALLERS_CACHE.get(key)
    if hit is not None:
        return hit
    bind_leaf_fo = sorted(bind_fos)[0] if bind_fos else None
    reachable = build_callers_reachable(
        rom,
        sinks_list,
        ops_fs,
        wrapper_depth=max_depth if bind_fos else 0,
        bind_leaf_fo=bind_leaf_fo,
    )
    _CALLERS_CACHE[key] = reachable
    return reachable


def get_callers_reachable_for_filters(
    rom: bytes, filters: list[dict[str, Any]] | None
) -> frozenset[int] | None:
    return ensure_callers_cache(rom, filters)


def clear_callers_cache() -> None:
    _CALLERS_CACHE.clear()
