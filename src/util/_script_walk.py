# -*- coding: utf-8 -*-
"""从地图脚本入口 BFS walk 字节码，抽取 script_ops 点名的文本指针。

入口：gMapGroups → MapHeader → mapScripts / events；外加 gStdScripts。
操作数长度表摘自 pokeemerald ``scrcmd.c`` / ``event.inc``（与 AXVJ 字段本
``gScriptCmdTable@0x08145190`` 的 opcode 编号一致：end=0x02、call=0x04…）。
"""

from __future__ import annotations

import struct
from collections import deque
from typing import Any, Callable, Iterable

BASE = 0x08000000
SCRIPT_BANK_MIN = 0x100000

# Emerald 编号；含 opcode 字节。0x5C trainerbattle 长度随 type 变，表中为 None。
_OP_SIZE: list[int | None] = [
    1, 1, 1, 1, 5, 5, 6, 6, 2, 2, 3, 3, 1, 1, 2, 6,  # 00-0F
    3, 6, 6, 6, 3, 9, 5, 5, 5, 5, 5, 3, 3, 6, 6, 6,  # 10-1F
    9, 5, 5, 5, 5, 3, 5, 1, 3, 3, 3, 3, 5, 1, 1, 3,  # 20-2F
    1, 3, 1, 4, 3, 1, 3, 2, 2, 8, 8, 8, 3, 8, 8, 8,  # 30-3F
    8, 8, 5, 1, 5, 5, 5, 5, 3, 5, 5, 3, 3, 3, 3, 7,  # 40-4F
    9, 3, 5, 3, 5, 3, 5, 7, 5, 5, 1, 4, None, 1, 1, 1,  # 50-5F (5C=trainerbattle)
    3, 3, 3, 7, 3, 4, 1, 5, 1, 1, 1, 1, 1, 1, 3, 5,  # 60-6F
    6, 6, 5, 5, 5, 5, 1, 2, 5, 1, 3, 5, 3, 4, 2, 4,  # 70-7F (7C=3)
    4, 4, 4, 4, 4, 6, 5, 5, 5, 3, 4, 1, 1, 1, 1, 3,  # 80-8F
    6, 6, 6, 4, 3, 4, 3, 2, 3, 3, 2, 5, 3, 4, 3, 3,  # 90-9F
    1, 5, 9, 1, 3, 1, 2, 3, 6, 5, 9, 3, 5, 5, 1, 5,  # A0-AF
    5, 8, 1, 3, 3, 3, 6, 1, 5, 5, 5, 6, 6, 5, 5, 6,  # B0-BF
    3, 3, 3, 2, 8, 1,  # C0-C5（AXVJ 表止于此）
]

_OP_END = 0x02
_OP_RETURN = 0x03
_OP_CALL = 0x04
_OP_GOTO = 0x05
_OP_GOTO_IF = 0x06
_OP_CALL_IF = 0x07
_OP_GOTOSTD = 0x08
_OP_CALLSTD = 0x09
_OP_GOTOSTD_IF = 0x0A
_OP_CALLSTD_IF = 0x0B
_OP_LOADWORD = 0x0F
_OP_TRAINERBATTLE = 0x5C
_OP_MESSAGE = 0x67
_OP_MESSAGE_AUTOSCROLL = 0x9B

# include/constants/battle_setup.h → 文本指针个数（@ op+6）
_TRAINERBATTLE_TEXT_PTRS: dict[int, int] = {
    0: 2,
    1: 2,
    2: 2,
    3: 1,
    4: 3,
    5: 2,
    6: 3,
    7: 3,
    8: 3,
}
# 其后另有续跑脚本指针的 type
_TRAINERBATTLE_HAS_SCRIPT = frozenset({1, 2, 6, 8})

# MapScripts tag（pokeemerald map_scripts）
_MAP_SCRIPT_FRAME_TABLE = 2
_MAP_SCRIPT_WARP_TABLE = 4

_OBJECT_EVENT_SIZE = 0x18
_OBJECT_SCRIPT_OFF = 0x10
_COORD_EVENT_SIZE = 0x10
_COORD_SCRIPT_OFF = 0x0C
_BG_EVENT_SIZE = 0x0C
_BG_UNION_OFF = 0x08

_MAX_QUEUE = 200_000
_MAX_STEPS = 2_000_000

AddPtr = Callable[[set[int], int, bytes], None]

_SCRIPT_ROOTS: dict[str, Any] = {}


def set_script_roots(roots: dict[str, Any] | None) -> None:
    global _SCRIPT_ROOTS
    _SCRIPT_ROOTS = dict(roots or {})


def get_script_roots() -> dict[str, Any]:
    return dict(_SCRIPT_ROOTS)


def _parse_addr(v: object) -> int:
    if isinstance(v, int):
        return int(v)
    s = str(v).strip().lower().replace("_", "")
    if s.startswith("0x"):
        return int(s, 16)
    return int(s, 16)


def _fo(vma_or_fo: int) -> int:
    if vma_or_fo >= BASE:
        return vma_or_fo - BASE
    return vma_or_fo


def _is_script_ptr(v: int, rom_len: int) -> bool:
    if not (BASE <= v < BASE + rom_len):
        return False
    fo = v - BASE
    return SCRIPT_BANK_MIN <= fo < rom_len


def _trainerbattle_meta(rom: bytes, fo: int) -> tuple[int, int, bool] | None:
    """返回 (instr_size_incl_opcode, text_ptr_count, has_script_ptr)。"""
    n = len(rom)
    if fo + 6 > n:
        return None
    tb_type = rom[fo + 1]
    n_ptr = _TRAINERBATTLE_TEXT_PTRS.get(tb_type)
    if n_ptr is None:
        return None
    has_script = tb_type in _TRAINERBATTLE_HAS_SCRIPT
    # op + type + trainer_u16 + local_u16 + texts + optional script
    size = 1 + 1 + 2 + 2 + 4 * n_ptr + (4 if has_script else 0)
    if fo + size > n:
        return None
    return size, n_ptr, has_script


def _collect_map_script_entries(rom: bytes, scripts_vma: int, out: set[int]) -> None:
    if not _is_script_ptr(scripts_vma, len(rom)):
        # 允许空表指针落在脚本带外？仍试读 tag=0
        if not (BASE <= scripts_vma < BASE + len(rom)):
            return
    fo = scripts_vma - BASE
    n = len(rom)
    guard = 0
    while fo < n and guard < 64:
        guard += 1
        tag = rom[fo]
        if tag == 0:
            return
        if fo + 5 > n:
            return
        ptr = struct.unpack_from("<I", rom, fo + 1)[0]
        fo += 5
        if tag in (_MAP_SCRIPT_FRAME_TABLE, _MAP_SCRIPT_WARP_TABLE):
            _collect_frame_table(rom, ptr, out)
        elif _is_script_ptr(ptr, n):
            out.add(ptr - BASE)


def _collect_frame_table(rom: bytes, table_vma: int, out: set[int]) -> None:
    if not (BASE <= table_vma < BASE + len(rom)):
        return
    fo = table_vma - BASE
    n = len(rom)
    for _ in range(128):
        if fo + 8 > n:
            return
        var_id = struct.unpack_from("<H", rom, fo)[0]
        if var_id == 0:
            return
        script = struct.unpack_from("<I", rom, fo + 4)[0]
        if _is_script_ptr(script, n):
            out.add(script - BASE)
        fo += 8


def _collect_event_scripts(rom: bytes, events_vma: int, out: set[int]) -> None:
    if not (BASE <= events_vma < BASE + len(rom) - 16):
        return
    efo = events_vma - BASE
    nobj, _nwarp, ncoord, nbg = rom[efo : efo + 4]
    obj_p, _warp_p, coord_p, bg_p = struct.unpack_from("<IIII", rom, efo + 4)
    n = len(rom)

    if nobj and BASE <= obj_p < BASE + n:
        base = obj_p - BASE
        for i in range(min(int(nobj), 64)):
            off = base + i * _OBJECT_EVENT_SIZE
            if off + _OBJECT_EVENT_SIZE > n:
                break
            script = struct.unpack_from("<I", rom, off + _OBJECT_SCRIPT_OFF)[0]
            if _is_script_ptr(script, n):
                out.add(script - BASE)

    if ncoord and BASE <= coord_p < BASE + n:
        base = coord_p - BASE
        for i in range(min(int(ncoord), 64)):
            off = base + i * _COORD_EVENT_SIZE
            if off + _COORD_EVENT_SIZE > n:
                break
            script = struct.unpack_from("<I", rom, off + _COORD_SCRIPT_OFF)[0]
            if _is_script_ptr(script, n):
                out.add(script - BASE)

    if nbg and BASE <= bg_p < BASE + n:
        base = bg_p - BASE
        for i in range(min(int(nbg), 64)):
            off = base + i * _BG_EVENT_SIZE
            if off + _BG_EVENT_SIZE > n:
                break
            union = struct.unpack_from("<I", rom, off + _BG_UNION_OFF)[0]
            if _is_script_ptr(union, n):
                out.add(union - BASE)


def _iter_map_headers(rom: bytes, roots: dict[str, Any]) -> Iterable[int]:
    """Yield MapHeader file offsets."""
    ptrs_vma = roots.get("map_header_ptrs")
    count = roots.get("map_header_count")
    if ptrs_vma is not None and count is not None:
        base = _fo(_parse_addr(ptrs_vma))
        n = int(count)
        for i in range(n):
            off = base + i * 4
            if off + 4 > len(rom):
                break
            hdr = struct.unpack_from("<I", rom, off)[0]
            if BASE <= hdr < BASE + len(rom) - 0x1C:
                yield hdr - BASE
        return

    # fallback: gMapGroups（组表指向 MapHeader* 数组）
    groups_vma = roots.get("gMapGroups")
    groups_count = roots.get("gMapGroups_count")
    if groups_vma is None or groups_count is None:
        return
    gfo = _fo(_parse_addr(groups_vma))
    gc = int(groups_count)
    # 若配置了 map_header_ptrs 作为 group0，优先已在上面处理
    group_starts: list[int] = []
    for i in range(gc):
        off = gfo + i * 4
        if off + 4 > len(rom):
            break
        p = struct.unpack_from("<I", rom, off)[0]
        if BASE <= p < BASE + len(rom):
            group_starts.append(p)
    # 无明确每组长度时：读到非 MapHeader 指针为止（保守：每组最多 128）
    for gs in group_starts:
        fo = gs - BASE
        for _ in range(128):
            if fo + 4 > len(rom):
                break
            hdr = struct.unpack_from("<I", rom, fo)[0]
            fo += 4
            if not (BASE <= hdr < BASE + len(rom) - 0x1C):
                break
            # 粗验：layout/events/scripts 像指针
            hfo = hdr - BASE
            layout, events, scripts = struct.unpack_from("<III", rom, hfo)
            if not (
                BASE <= layout < BASE + len(rom)
                and BASE <= events < BASE + len(rom)
                and BASE <= scripts < BASE + len(rom)
            ):
                break
            yield hfo


def collect_script_entries(rom: bytes, roots: dict[str, Any] | None = None) -> set[int]:
    """收集脚本入口文件偏移（去重）。"""
    r = roots if roots is not None else _SCRIPT_ROOTS
    out: set[int] = set()
    for hfo in _iter_map_headers(rom, r):
        _layout, events, scripts, _conn = struct.unpack_from("<IIII", rom, hfo)
        _collect_map_script_entries(rom, scripts, out)
        _collect_event_scripts(rom, events, out)

    std_vma = r.get("gStdScripts")
    std_count = r.get("gStdScripts_count", 8)
    if std_vma is not None:
        sfo = _fo(_parse_addr(std_vma))
        for i in range(int(std_count)):
            off = sfo + i * 4
            if off + 4 > len(rom):
                break
            p = struct.unpack_from("<I", rom, off)[0]
            if _is_script_ptr(p, len(rom)):
                out.add(p - BASE)
    return out


def _enqueue_script(queue: deque[int], seen: set[int], vma: int, rom_len: int) -> None:
    if not _is_script_ptr(vma, rom_len):
        return
    fo = vma - BASE
    if fo in seen:
        return
    if len(seen) >= _MAX_QUEUE:
        return
    seen.add(fo)
    queue.append(fo)


def walk_script_ops(
    rom: bytes,
    ops: frozenset[str],
    out: set[int],
    *,
    add_ptr: AddPtr,
    roots: dict[str, Any] | None = None,
    entries: set[int] | None = None,
) -> None:
    """自入口 BFS；命中 script_ops 时经 add_ptr 收录正文指针。"""
    if not ops:
        return
    r = roots if roots is not None else _SCRIPT_ROOTS
    if not r and entries is None:
        return

    want_msg = "message" in ops
    want_auto = "messageautoscroll" in ops
    want_lw = "loadword_callstd" in ops
    want_tb = "trainerbattle" in ops

    std_scripts: list[int] = []
    std_vma = r.get("gStdScripts")
    std_count = int(r.get("gStdScripts_count", 8) or 8)
    if std_vma is not None:
        sfo = _fo(_parse_addr(std_vma))
        for i in range(std_count):
            off = sfo + i * 4
            if off + 4 > len(rom):
                break
            std_scripts.append(struct.unpack_from("<I", rom, off)[0])

    entry_set = entries if entries is not None else collect_script_entries(rom, r)
    seen: set[int] = set()
    queue: deque[int] = deque()
    for fo in sorted(entry_set):
        if fo not in seen:
            seen.add(fo)
            queue.append(fo)

    n = len(rom)
    steps = 0
    while queue and steps < _MAX_STEPS:
        fo = queue.popleft()
        pc = fo
        local_guard = 0
        while 0 <= pc < n and local_guard < 10000:
            local_guard += 1
            steps += 1
            if steps > _MAX_STEPS:
                return
            op = rom[pc]
            if op == _OP_END or op == _OP_RETURN:
                break

            if op == _OP_TRAINERBATTLE:
                meta = _trainerbattle_meta(rom, pc)
                if meta is None:
                    break
                size, n_ptr, has_script = meta
                if want_tb:
                    base = pc + 6
                    for k in range(n_ptr):
                        v = struct.unpack_from("<I", rom, base + 4 * k)[0]
                        add_ptr(out, v, rom)
                if has_script:
                    script = struct.unpack_from("<I", rom, pc + 6 + 4 * n_ptr)[0]
                    _enqueue_script(queue, seen, script, n)
                pc += size
                continue

            if op >= len(_OP_SIZE) or _OP_SIZE[op] is None:
                break
            size = _OP_SIZE[op]
            assert size is not None
            if pc + size > n:
                break

            if op == _OP_CALL or op == _OP_GOTO:
                dest = struct.unpack_from("<I", rom, pc + 1)[0]
                _enqueue_script(queue, seen, dest, n)
                if op == _OP_GOTO:
                    break
                pc += size
                continue

            if op == _OP_GOTO_IF or op == _OP_CALL_IF:
                dest = struct.unpack_from("<I", rom, pc + 2)[0]
                _enqueue_script(queue, seen, dest, n)
                if op == _OP_GOTO_IF:
                    # 条件未知：两端都走——fallthrough + dest
                    pc += size
                    continue
                pc += size
                continue

            if op in (_OP_GOTOSTD, _OP_CALLSTD):
                idx = rom[pc + 1]
                if 0 <= idx < len(std_scripts):
                    _enqueue_script(queue, seen, std_scripts[idx], n)
                if op == _OP_GOTOSTD:
                    break
                pc += size
                continue

            if op in (_OP_GOTOSTD_IF, _OP_CALLSTD_IF):
                idx = rom[pc + 2]
                if 0 <= idx < len(std_scripts):
                    _enqueue_script(queue, seen, std_scripts[idx], n)
                pc += size
                continue

            if want_msg and op == _OP_MESSAGE and size >= 5:
                v = struct.unpack_from("<I", rom, pc + 1)[0]
                if v:
                    add_ptr(out, v, rom)
            elif want_auto and op == _OP_MESSAGE_AUTOSCROLL and size >= 5:
                v = struct.unpack_from("<I", rom, pc + 1)[0]
                if v:
                    add_ptr(out, v, rom)
            elif want_lw and op == _OP_LOADWORD and size >= 6:
                v = struct.unpack_from("<I", rom, pc + 2)[0]
                window = rom[pc + 6 : pc + 18]
                if _OP_CALLSTD in window:
                    add_ptr(out, v, rom)

            pc += size
