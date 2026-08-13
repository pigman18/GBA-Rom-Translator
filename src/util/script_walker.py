#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""script_walker.py
===================
Gen3 脚本字节流步进器：从脚本入口按 ``gScriptCmdTable`` op 协议解码，收集
所有"文本指针 op"后随 4 字节文件偏移集合。

op 表采自 pokeruby ``include/macros/event.inc``（AXVJ 同引擎，op 码与参数
布局完全一致）。仅静态步进，不调用 capstone。

公开 API::

    walk_scripts(rom, script_entries, *, include_buffer=False) -> frozenset[int]
    walk_script(rom, entry_fo, *, include_buffer=False) -> frozenset[int]

文本 op：
  - ``0x67 message`` / ``0x9B messageautoscroll`` / ``0xBD vmessage``：
    op + 4byte ptr
  - ``0x78 braillemessage``：op + 4byte ptr（盲文文本，仍属可译文本）
  - ``0xBE vloadptr``：op + 4byte ptr
  - ``0xC8 loadhelp``：op + 4byte ptr
  - ``0x85 bufferstring`` / ``0xBF vbufferstring``：op + 1byte out + 4byte
    ptr（缓冲串）
  - ``0x0F loadword`` + 紧随 ``0x09 callstd``：loadword 的 4byte 值作为
    文本指针（仅当 callstd std ∈ {0,1,2,3,7,8} 的 StdMsg 索引时才视作文本；
    当前实现宽松策略：只要后随 callstd 即收，调用方再过滤）
  - ``0x5C trainerbattle``：op + 1byte type + 2byte trainer + 2byte local_id
    + N×4byte 文本/event 指针（N 按 type 取）

终止 op：``0x02 end`` / ``0x03 return`` / ``0x0D killscript``。
跳转 op：``0x05 goto`` / ``0x06 goto_if`` / ``0x07 call_if`` / ``0x04 call``
/``0xB9 vgoto`` / ``0xBA vcall`` / ``0xBB vgoto_if`` / ``0xBC vcall_if``，
跳转目标 4 字节作为新入口递归步进。
"""

from __future__ import annotations

import struct
from typing import Iterable

BASE = 0x08000000

# op 码 -> 参数字节数（含 op 码本身用于步进的字节数；不含 op 后变长 trainerbattle）
# 值取自 pokeruby include/macros/event.inc 宏的 .byte / .2byte / .4byte 总和。
_OP_ARG_BYTES: dict[int, int] = {
    0x00: 1, 0x01: 1, 0x02: 1, 0x03: 1, 0x04: 5, 0x05: 5, 0x06: 6, 0x07: 6,
    0x08: 2, 0x09: 2, 0x0A: 3, 0x0B: 3, 0x0C: 1, 0x0D: 1, 0x0E: 2, 0x0F: 6,
    0x10: 3, 0x11: 6, 0x12: 6, 0x13: 6, 0x14: 3, 0x15: 9, 0x16: 5, 0x17: 5,
    0x18: 5, 0x19: 5, 0x1A: 5, 0x1B: 3, 0x1C: 3, 0x1D: 6, 0x1E: 6, 0x1F: 6,
    0x20: 9, 0x21: 5, 0x22: 5, 0x23: 5, 0x24: 5, 0x25: 3, 0x26: 5, 0x27: 1,
    0x28: 3, 0x29: 3, 0x2A: 3, 0x2B: 3, 0x2C: 5, 0x2D: 1, 0x2E: 1, 0x2F: 3,
    0x30: 1, 0x31: 3, 0x32: 1, 0x33: 4, 0x34: 3, 0x35: 1, 0x36: 3, 0x37: 2,
    0x38: 2, 0x39: 8, 0x3A: 8, 0x3B: 8, 0x3C: 3, 0x3D: 8, 0x3E: 8, 0x3F: 8,
    0x40: 8, 0x41: 8, 0x42: 5, 0x43: 1, 0x44: 5, 0x45: 5, 0x46: 5, 0x47: 5,
    0x48: 3, 0x49: 5, 0x4A: 5, 0x4B: 3, 0x4C: 3, 0x4D: 3, 0x4E: 3, 0x4F: 7,
    0x50: 9, 0x51: 3, 0x52: 5, 0x53: 3, 0x54: 5, 0x55: 3, 0x56: 5, 0x57: 7,
    0x58: 5, 0x59: 5, 0x5A: 1, 0x5B: 4, 0x5C: -1, 0x5D: 1, 0x5E: 1, 0x5F: 1,
    0x60: 3, 0x61: 3, 0x62: 3, 0x63: 7, 0x64: 3, 0x65: 4, 0x66: 1, 0x67: 5,
    0x68: 1, 0x69: 1, 0x6A: 1, 0x6B: 1, 0x6C: 1, 0x6D: 1, 0x6E: 3, 0x6F: 5,
    0x70: 6, 0x71: 6, 0x72: 5, 0x73: 5, 0x74: 5, 0x75: 5, 0x76: 1, 0x77: 2,
    0x78: 5, 0x79: 15, 0x7A: 3, 0x7B: 5, 0x7C: 3, 0x7D: 4, 0x7E: 2,
    0x7F: 4, 0x80: 4, 0x81: 4, 0x82: 4, 0x83: 4, 0x84: 4, 0x85: 6, 0x86: 5,
    0x87: 5, 0x88: 5, 0x89: 3, 0x8A: 4, 0x8B: 1, 0x8C: 1, 0x8D: 1, 0x8E: 1,
    0x8F: 3, 0x90: 6, 0x91: 6, 0x92: 6, 0x93: 3, 0x94: 3, 0x95: 3, 0x96: 3,
    0x97: 2, 0x98: 3, 0x99: 3, 0x9A: 2, 0x9B: 5, 0x9C: 3, 0x9D: 4, 0x9E: 3,
    0x9F: 3, 0xA0: 1, 0xA1: 5, 0xA2: 9, 0xA3: 1, 0xA4: 3, 0xA5: 1, 0xA6: 2,
    0xA7: 3, 0xA8: 6, 0xA9: 5, 0xAA: 9, 0xAB: 3, 0xAC: 5, 0xAD: 5, 0xAE: 1,
    0xAF: 5, 0xB0: 5, 0xB1: 1, 0xB2: 1, 0xB3: 3, 0xB4: 3, 0xB5: 3, 0xB6: 6,
    0xB7: 1, 0xB8: 5, 0xB9: 5, 0xBA: 5, 0xBB: 6, 0xBC: 6, 0xBD: 5, 0xBE: 5,
    0xBF: 6, 0xC0: 3, 0xC1: 3, 0xC2: 3, 0xC3: 2, 0xC4: 8, 0xC5: 1, 0xC6: 4,
    0xC7: 2, 0xC8: 5, 0xC9: 1, 0xCA: 1, 0xCB: 1, 0xCC: 6,
}

# 终止 op（跳出当前脚本块）
_TERMINATORS = frozenset({0x02, 0x03, 0x0D})

# 跳转 op -> 文本指针在 op 内的偏移
_JUMP_PTR_OFFS: dict[int, int] = {
    0x04: 1, 0x05: 1, 0x06: 2, 0x07: 2,
    0xB9: 1, 0xBA: 1, 0xBB: 2, 0xBC: 2,
}

# 文本 op -> 文本指针在 op 内的偏移列表（一般 1 个）
_TEXT_PTR_OFFS: dict[int, tuple[int, ...]] = {
    0x67: (1,),     # message
    0x9B: (1,),     # messageautoscroll
    0xBD: (1,),     # vmessage
    0x78: (1,),     # braillemessage
    0xBE: (1,),     # vloadptr
    0xC8: (1,),     # loadhelp
    0x85: (2,),     # bufferstring (op + 1byte out + 4byte ptr)
    0xBF: (2,),     # vbufferstring (op + 1byte out + 4byte ptr)
}

# trainerbattle(0x5C) 各 type 的"文本指针个数"（其余为 event script 指针，
# 不算文本）。表取自 pokeruby include/constants/battle_setup.h。
# 顺序：[文本指针数, event_script 指针数]
_TRAINERBATTLE_LAYOUT: dict[int, tuple[int, int]] = {
    0: (2, 0),  # SINGLE：intro, lose
    1: (2, 1),  # CONTINUE_SCRIPT_NO_MUSIC：intro, lose, event
    2: (2, 1),  # CONTINUE_SCRIPT：intro, lose, event
    3: (1, 0),  # SINGLE_NO_INTRO_TEXT：lose
    4: (3, 0),  # DOUBLE：intro, lose, not_enough
    5: (2, 0),  # REMATCH：intro, lose
    6: (3, 1),  # CONTINUE_SCRIPT_DOUBLE：intro, lose, not_enough, event
    7: (3, 0),  # REMATCH_DOUBLE：intro, lose, not_enough
    8: (3, 1),  # CONTINUE_SCRIPT_DOUBLE_NO_MUSIC：intro, lose, not_enough, event
}

# callstd(0x09) 的 std 索引：当 loadword(0x0F) 后随 callstd，且 std ∈
# 这组"消息类 StdMsg"时，loadword 的 4byte 值视作文本指针。
# 参见 pokeruby include/macros/event.inc::callstd function names。
_CALLSTD_TEXT_INDICES = frozenset({0, 1, 7, 8})

DEFAULT_OP_TABLE = _OP_ARG_BYTES


def _read_ptr(rom: bytes, fo: int) -> int | None:
    if fo < 0 or fo + 4 > len(rom):
        return None
    v = struct.unpack_from("<I", rom, fo)[0]
    if not (BASE <= v < BASE + len(rom)):
        return None
    return v - BASE


def _is_rom_ptr(v: int, rom_len: int) -> bool:
    return BASE <= v < BASE + rom_len


def walk_script(
    rom: bytes,
    entry_fo: int,
    *,
    include_buffer: bool = False,
    _visited: set[int] | None = None,
    out_text: set[int] | None = None,
    out_entries: set[int] | None = None,
) -> set[int]:
    """从单个脚本入口 step through op，收集文本指针文件偏移。

    递归处理 goto/call 跳转。``_visited`` 防无限递归。返回 ``out_text`` 集合。
    """
    if _visited is None:
        _visited = set()
    if out_text is None:
        out_text = set()
    if out_entries is None:
        out_entries = set()
    n = len(rom)
    fo = entry_fo
    if not (0 <= fo < n):
        return out_text
    if fo in _visited:
        return out_text
    _visited.add(fo)

    while 0 <= fo < n:
        op = rom[fo]
        if op in _TERMINATORS:
            break
        if op == 0x5C:  # trainerbattle 变长
            if fo + 6 > n:
                break
            tb_type = rom[fo + 1]
            layout = _TRAINERBATTLE_LAYOUT.get(tb_type)
            if layout is None:
                # 未知 type：当作 1 个 ptr 跳过到下一个对齐 4 字节处作罢
                fo += 6
                continue
            n_text, n_event = layout
            n_total = n_text + n_event
            base_off = fo + 6
            if base_off + 4 * n_total > n:
                break
            for i in range(n_text):
                p = _read_ptr(rom, base_off + 4 * i)
                if p is not None:
                    out_text.add(p)
            fo = base_off + 4 * n_total
            continue
        size = _OP_ARG_BYTES.get(op)
        if size is None:
            # 未知 op：当作 1 字节步进，避免断链；最多前推 64 字节试探
            fo += 1
            continue
        # 文本 op
        text_offs = _TEXT_PTR_OFFS.get(op)
        if text_offs is not None and (include_buffer or op not in (0x85, 0xBF)):
            for off in text_offs:
                if fo + off + 4 <= n:
                    p = _read_ptr(rom, fo + off)
                    if p is not None:
                        out_text.add(p)
        # loadword(0x0F) + 后随 callstd：loadword 的 value 在 op 偏移 +2
        if op == 0x0F:
            next_fo = fo + size
            if next_fo < n and rom[next_fo] == 0x09:  # callstd
                if next_fo + 2 <= n:
                    std_idx = rom[next_fo + 1]
                    if std_idx in _CALLSTD_TEXT_INDICES:
                        p = _read_ptr(rom, fo + 2)
                        if p is not None:
                            out_text.add(p)
        # 跳转 op：递归步进目标
        jmp_off = _JUMP_PTR_OFFS.get(op)
        if jmp_off is not None:
            tgt = _read_ptr(rom, fo + jmp_off)
            if tgt is not None and tgt not in out_entries:
                out_entries.add(tgt)
                walk_script(
                    rom,
                    tgt,
                    include_buffer=include_buffer,
                    _visited=_visited,
                    out_text=out_text,
                    out_entries=out_entries,
                )
        fo += size

    return out_text


def walk_scripts(
    rom: bytes,
    script_entries: Iterable[int],
    *,
    include_buffer: bool = False,
) -> frozenset[int]:
    """对一批脚本入口收集所有文本指针文件偏移。"""
    out: set[int] = set()
    entries: set[int] = set()
    for entry_fo in script_entries:
        if entry_fo is None:
            continue
        if not (0 <= entry_fo < len(rom)):
            continue
        if entry_fo in entries:
            continue
        entries.add(entry_fo)
        walk_script(
            rom,
            entry_fo,
            include_buffer=include_buffer,
            out_text=out,
            out_entries=entries,
        )
    return frozenset(out)


# 结构体偏移：MapHeader / MapScript 头表（pokeruby src/fieldmap.h / map.h）
# MapHeader 布局（Gen3 RS/FRLG 通用，24 字节）：
#   u8 mapWidth;       offset 0
#   u8 mapHeight;      offset 1
#   u8 mapLayoutId;    offset 2
#   u8 mapView(2byte); offset 3? — 实际布局在 RS 是 24 字节固定
# 此处只用 ``scripts`` 字段（offset 8 在 RW，offset 12 在 FRLG，需要识别）
# pokeruby 美版 MapHeader 布局（src/map.h::gMapHeader）:
#   u8 mapWidth; u8 mapHeight; u8 mapLayoutId;
#   const struct MapHeader *mapLayout;  ← 不对，layout 是单独结构
# 实际：MapScripts 在 MapHeader 内偏移 8（pokeruby 0606_xx）
# 这里采用 EXPERIMENTAL 8 / 12 双试，verify_map_headers 时交叉验证择优。
MAPHEADER_SCRIPTS_OFFSETS_RS = (8,)
MAPHEADER_SCRIPTS_OFFSETS_FRLG = (12,)


def _read_u32(rom: bytes, fo: int) -> int | None:
    if fo < 0 or fo + 4 > len(rom):
        return None
    return struct.unpack_from("<I", rom, fo)[0]


def iter_map_script_entries(
    rom: bytes,
    map_headers_fo: int,
    *,
    max_maps: int = 512,
    scripts_offs: tuple[int, ...] = MAPHEADER_SCRIPTS_OFFSETS_RS,
) -> set[int]:
    """遍历 gMapHeaders 表，对每项 MapHeader 解 scripts 字段。

    MapScripts 实际格式（pokeruby src/script.c::MapHeaderGetScriptTable）：
      [u8 type; u32 script_ptr] [u8 type; u32 script_ptr] ... [u8 0]
    每项 **5 字节**（无对齐填充），终止符是单字节 0。
    """
    n = len(rom)
    entries: set[int] = set()

    for i in range(max_maps):
        hdr_fo = map_headers_fo + i * 4
        if hdr_fo + 4 > n:
            break
        map_hdr_vma = _read_u32(rom, hdr_fo)
        if map_hdr_vma is None or not (BASE <= map_hdr_vma < BASE + n):
            break  # 表终止
        map_hdr_fo = map_hdr_vma - BASE

        scripts_vma = None
        for off in scripts_offs:
            v = _read_u32(rom, map_hdr_fo + off)
            if v is not None and BASE <= v < BASE + n:
                scripts_vma = v
                break
        if scripts_vma is None:
            continue
        scripts_tbl_fo = scripts_vma - BASE
        # 遍历 5 字节 stride
        cur = scripts_tbl_fo
        while True:
            if cur + 5 > n:
                break
            ent_type = rom[cur]
            if ent_type == 0:  # 终止符
                break
            if ent_type > 0x3F:
                break  # 越界：非合法 type
            script_ptr = _read_u32(rom, cur + 1)
            if script_ptr is None or not (BASE <= script_ptr < BASE + n):
                break
            entries.add(script_ptr - BASE)
            cur += 5
            # 防失控：单表 256 项上限
            if cur - scripts_tbl_fo > 5 * 256:
                break
    return entries


def verify_map_headers(
    rom: bytes, map_headers_fo: int, *, max_maps: int = 512
) -> tuple[bool, tuple[int, ...], int]:
    """交叉验证候选 ``map_headers_fo`` 真的是 ``gMapHeaders``。

    试 RS 偏移 8 与 FRLG 偏移 12；统计每张地图的 scripts 表能解出多少
    ``script_ptr``。命中率 ≥ 0.7 即视作确认。
    返回 ``(ok, scripts_offs, valid_map_count)``。
    """
    best_offs: tuple[int, ...] = ()
    best_count = 0
    for offs in (MAPHEADER_SCRIPTS_OFFSETS_RS, MAPHEADER_SCRIPTS_OFFSETS_FRLG):
        ents = iter_map_script_entries(rom, map_headers_fo, max_maps=max_maps, scripts_offs=offs)
        if len(ents) > best_count:
            best_count = len(ents)
            best_offs = offs
    if best_count < 1:
        return False, (), 0
    ok = best_count >= 16
    return ok, best_offs, best_count