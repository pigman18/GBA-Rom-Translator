# -*- coding: utf-8 -*-
"""callers_filter：预计算「经 callers(sinks) / 脚本操作数」可达的正文文件偏移。

与 addr_patcher callers 同向：
1. 全盘 Thumb 反汇编，找 bl/blx 到配置 sink，按 text_arg（r0/r1）回溯 ROM 指针；
2. 按 value.script_ops 收脚本操作数（message / msgbox / trainerbattle）。

训练家开场经 ShowFieldMessage(GetTrainerIntroSpeech())，指针在 RAM，
BL 回溯看不到 → 必须扫脚本 trainerbattle(0x5C) 操作数。
"""

from __future__ import annotations

import struct
from typing import Any

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

BASE = 0x08000000
SCRIPT_BANK_MIN = 0x100000
TITLE_LZ_BAND = (0x36D000, 0x370000)

# pokeruby data/script_cmd_table.inc
_SCRIPT_OP_LOADWORD = 0x0F
_SCRIPT_OP_CALLSTD = 0x09
_SCRIPT_OP_MESSAGE = 0x67
_SCRIPT_OP_MESSAGE_AUTOSCROLL = 0x9B
_SCRIPT_OP_TRAINERBATTLE = 0x5C

_FIELD_MESSAGE_SINK_NAMES = frozenset(
    {
        "ShowFieldMessage",
        "ShowFieldAutoScrollMessage",
    }
)

# include/constants/battle_setup.h → 各 type 的文本指针个数（其后可能还有 event script）
_TRAINERBATTLE_TEXT_PTRS: dict[int, int] = {
    0: 2,  # SINGLE
    1: 2,  # CONTINUE_SCRIPT_NO_MUSIC
    2: 2,  # CONTINUE_SCRIPT
    3: 1,  # SINGLE_NO_INTRO_TEXT
    4: 3,  # DOUBLE
    5: 2,  # REMATCH
    6: 3,  # CONTINUE_SCRIPT_DOUBLE
    7: 3,  # REMATCH_DOUBLE
    8: 3,  # CONTINUE_SCRIPT_DOUBLE_NO_MUSIC
}

_DEFAULT_FIELD_SCRIPT_OPS = frozenset(
    {"message", "messageautoscroll", "loadword_callstd"}
)

# (name, file_off, text_arg)  text_arg in {"r0","r1"}
SinkSpec = tuple[str, int, str]

_CALLERS_CACHE: dict[tuple[Any, ...], frozenset[int]] = {}
_ACTIVE_ROM: bytes | None = None


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


def _is_rom_text_ptr(v: int, rom_len: int) -> bool:
    if not (BASE <= v < BASE + rom_len):
        return False
    fo = v - BASE
    if fo < SCRIPT_BANK_MIN or fo >= rom_len:
        return False
    if TITLE_LZ_BAND[0] <= fo < TITLE_LZ_BAND[1]:
        return False
    return True


def _sinks_from_spec(spec: dict[str, Any]) -> list[SinkSpec]:
    out: list[SinkSpec] = []
    seen: set[tuple[int, str]] = set()
    val = spec.get("value")
    if not isinstance(val, dict):
        return out
    sinks = val.get("sinks")
    if not isinstance(sinks, list):
        return out
    for item in sinks:
        if not isinstance(item, dict):
            continue
        addr = item.get("address")
        if addr is None:
            continue
        name = str(item.get("name") or "").strip()
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
) -> list[tuple[list[SinkSpec], frozenset[str]]]:
    out: list[tuple[list[SinkSpec], frozenset[str]]] = []
    for spec in filters or []:
        if not isinstance(spec, dict):
            continue
        if str(spec.get("type") or "") != "callers_filter":
            continue
        sinks = _sinks_from_spec(spec)
        ops = _script_ops_from_spec(spec, sinks)
        if not sinks and not ops:
            continue
        out.append((sinks, ops))
    return out


def filters_need_callers(filters: list[dict[str, Any]] | None) -> bool:
    return bool(_configs_from_filters(filters))


def _add_ptr(out: set[int], v: int, rom: bytes) -> None:
    """调用链已解析出的 ROM 指针直接收录；形态二次过滤交给其它 filter。"""
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


def _resolve_reg_rom_ptrs(
    rom: bytes, call_fo: int, md: Cs, reg: str
) -> list[int]:
    """从 bl 调用点向前回溯，解析传入 reg（r0/r1）的 ROM 指针字面量。"""
    n = len(rom)
    target_reg = reg.lower()
    win_lo = max(0, (call_fo - 0x80) & ~1)
    chunk = rom[win_lo:call_fo]
    if len(chunk) < 2:
        return []
    insns = list(md.disasm(chunk, BASE + win_lo))
    found: int | None = None
    known: dict[str, int] = {}

    def set_reg(dest: str, vma: int | None) -> None:
        if vma is None:
            known.pop(dest, None)
        else:
            known[dest] = vma

    for insn in reversed(insns):
        mnem = insn.mnemonic
        op = insn.op_str
        if found is not None and mnem in ("bl", "blx"):
            break
        if mnem == "ldr" and "[pc," in op:
            imm = _parse_ldr_pc_imm(op)
            if imm is None:
                continue
            lit_addr = _pc_literal_addr(insn.address, insn.size, imm)
            lit_fo = lit_addr - BASE
            if not (0 <= lit_fo <= n - 4):
                continue
            v = struct.unpack_from("<I", rom, lit_fo)[0]
            dest = op.split(",")[0].strip()
            set_reg(dest, v if _is_rom_text_ptr(v, n) else None)
            if dest == target_reg and found is None and _is_rom_text_ptr(v, n):
                found = v
            continue
        if mnem in ("mov", "movs", "adds"):
            parts = [p.strip() for p in op.split(",")]
            if len(parts) >= 2 and parts[0] == target_reg:
                src = parts[1]
                if src in known and found is None:
                    found = known[src]
            continue
        if mnem in ("bl", "blx"):
            if found is None:
                break
            break
        if mnem == "push":
            break

    if found is not None:
        return [found]
    return []


def _resolve_arg0_rom_ptrs(rom: bytes, call_fo: int, md: Cs) -> list[int]:
    """兼容旧名：回溯 r0。"""
    return _resolve_reg_rom_ptrs(rom, call_fo, md, "r0")


def _thumb_bl_target(rom: bytes, fo: int) -> int | None:
    """解码 fo 处 Thumb BL/BLX(imm) 目标 VMA；非该编码则 None。"""
    if fo < 0 or fo + 4 > len(rom):
        return None
    hw1, hw2 = struct.unpack_from("<HH", rom, fo)
    if (hw1 & 0xF800) != 0xF000:
        return None
    # BL: second 11j1 1 j2 1 imm11；BLX imm 亦落在 0xD000 掩码族
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


def _iter_bl_sites_to(rom: bytes, target_vma: int, *, scan_end: int | None = None) -> list[int]:
    """全盘（跳过标题 LZ）找 Thumb bl/blx imm → target 的调用点文件偏移。"""
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
            fo += 4  # BL 为 4 字节
            continue
        fo += 2
    return out


def _collect_from_bl_call_sites(
    rom: bytes,
    sinks: list[SinkSpec],
    out: set[int],
) -> None:
    """按原始 BL 编码找调用点（避免 Capstone 线性失步），再按 text_arg 回溯字面量。"""
    n = len(rom)
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    # fo -> set of text_args
    by_fo: dict[int, set[str]] = {}
    for _name, fo, text_arg in sinks:
        if 0 <= fo < n:
            by_fo.setdefault(fo, set()).add(text_arg)
    if not by_fo:
        return
    scan_end = min(n, 0x400000)
    for sink_fo, regs in by_fo.items():
        for call_fo in _iter_bl_sites_to(rom, BASE + sink_fo, scan_end=scan_end):
            for reg in regs:
                for v in _resolve_reg_rom_ptrs(rom, call_fo, md, reg):
                    _add_ptr(out, v, rom)


def _collect_script_message_ptrs(rom: bytes, out: set[int], ops: frozenset[str]) -> None:
    n = len(rom)
    if "message" in ops:
        start = 0
        while True:
            i = rom.find(bytes([_SCRIPT_OP_MESSAGE]), start, n - 5)
            if i < 0:
                break
            start = i + 1
            v = struct.unpack_from("<I", rom, i + 1)[0]
            _add_ptr(out, v, rom)
    if "messageautoscroll" in ops:
        start = 0
        while True:
            i = rom.find(bytes([_SCRIPT_OP_MESSAGE_AUTOSCROLL]), start, n - 5)
            if i < 0:
                break
            start = i + 1
            v = struct.unpack_from("<I", rom, i + 1)[0]
            _add_ptr(out, v, rom)
    if "loadword_callstd" in ops:
        start = 0
        while True:
            i = rom.find(bytes([_SCRIPT_OP_LOADWORD]), start, n - 8)
            if i < 0:
                break
            start = i + 1
            v = struct.unpack_from("<I", rom, i + 2)[0]
            if not _is_rom_text_ptr(v, n):
                continue
            window = rom[i + 6 : i + 18]
            if _SCRIPT_OP_CALLSTD not in window:
                continue
            _add_ptr(out, v, rom)


def _collect_trainerbattle_ptrs(rom: bytes, out: set[int]) -> None:
    """脚本 trainerbattle(0x5C)：按 type 取 intro/defeat/… 文本指针。"""
    n = len(rom)
    start = SCRIPT_BANK_MIN
    end = min(n, 0x3C0000)
    while True:
        i = rom.find(bytes([_SCRIPT_OP_TRAINERBATTLE]), start, end)
        if i < 0:
            break
        start = i + 1
        if i + 6 >= n:
            continue
        tb_type = rom[i + 1]
        n_ptr = _TRAINERBATTLE_TEXT_PTRS.get(tb_type)
        if n_ptr is None:
            continue
        base = i + 6
        need = base + 4 * n_ptr
        if need > n:
            continue
        for k in range(n_ptr):
            v = struct.unpack_from("<I", rom, base + 4 * k)[0]
            _add_ptr(out, v, rom)


def build_callers_reachable(
    rom: bytes,
    sinks: list[tuple[str, int]] | list[SinkSpec],
    script_ops: frozenset[str] | None = None,
) -> frozenset[int]:
    """sinks: (name, fo) 视为 text_arg=r0；或 (name, fo, text_arg)。"""
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
    if norm:
        _collect_from_bl_call_sites(rom, norm, out)
    if ops & {"message", "messageautoscroll", "loadword_callstd"}:
        _collect_script_message_ptrs(rom, out, ops)
    if "trainerbattle" in ops:
        _collect_trainerbattle_ptrs(rom, out)
    return frozenset(out)


def ensure_callers_cache(
    rom: bytes, filters: list[dict[str, Any]] | None
) -> frozenset[int] | None:
    configs = _configs_from_filters(filters)
    if not configs:
        return None
    merged: dict[tuple[int, str], str] = {}  # (fo, text_arg) -> name
    merged_ops: set[str] = set()
    for sinks, ops in configs:
        for name, fo, text_arg in sinks:
            merged.setdefault((fo, text_arg), name)
        merged_ops |= set(ops)
    sinks_list: list[SinkSpec] = [
        (name, fo, ta) for (fo, ta), name in sorted(merged.items(), key=lambda x: (x[0][0], x[0][1]))
    ]
    ops_fs = frozenset(merged_ops)
    key = (
        id(rom),
        tuple((n, fo, ta) for n, fo, ta in sinks_list),
        tuple(sorted(ops_fs)),
    )
    hit = _CALLERS_CACHE.get(key)
    if hit is not None:
        return hit
    reachable = build_callers_reachable(rom, sinks_list, ops_fs)
    _CALLERS_CACHE[key] = reachable
    return reachable


def get_callers_reachable_for_filters(
    rom: bytes, filters: list[dict[str, Any]] | None
) -> frozenset[int] | None:
    return ensure_callers_cache(rom, filters)


def clear_callers_cache() -> None:
    _CALLERS_CACHE.clear()
