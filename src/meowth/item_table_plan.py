"""道具名结构体表：40→48 + 字段重排（已验证布局）。

见 docs/STRUCT_TABLE_TRANSLATION_FINDINGS.md 与
scripts/research/ruby/gen_item_stride.py。

- 名字区 9→17B
- +0x1C 的 u16 **留在 0x1C**（ldrb 立即数上限 31）
- 乘法：(i*4+i)*8 → (i*2+i)*16（改两处 lsl 立即数）
"""
from __future__ import annotations

import struct
from typing import Callable

from .patch_table import GBA_BASE, TABLE_AREA_END, _fit

OLD_BASE = 0x39A648
OLD_STRIDE = 40
NEW_STRIDE = 48
NAME_CAP = 17
OLD_NAME_CAP = 9

# (旧偏移, 新偏移, 宽度)
FIELD_MAP = [
    (0x0A, 0x12, 2),
    (0x0C, 0x14, 2),
    (0x0E, 0x16, 1),
    (0x0F, 0x17, 1),
    (0x10, 0x24, 4),
    (0x14, 0x18, 1),
    (0x15, 0x19, 1),
    (0x16, 0x1A, 1),
    (0x17, 0x1B, 1),
    (0x18, 0x20, 4),
    (0x1C, 0x1C, 2),
    (0x20, 0x28, 4),
]

FIELD_LDR_SITES = [
    (0x0A53B4, "ldrh", 0x12),
    (0x0A53D8, "ldrh", 0x14),
    (0x0A53FC, "ldrb", 0x16),
    (0x0A5420, "ldrb", 0x17),
    (0x0A546C, "ldrb", 0x18),
    (0x0A5490, "ldrb", 0x19),
    (0x0A54B4, "ldrb", 0x1A),
    (0x0A54D8, "ldrb", 0x1B),
]

ADDS_SITES = [
    (0x0A5442, 0x24),
    (0x0A54FA, 0x20),
    (0x0A5546, 0x28),
]


def _enc_ldr(mn: str, imm: int) -> bytes:
    if mn == "ldrb":
        v = 0x7800 | (imm << 6) | (1 << 3) | 0
    elif mn == "ldrh":
        v = 0x8800 | ((imm // 2) << 6) | (1 << 3) | 0
    else:
        raise ValueError(mn)
    return struct.pack("<H", v)


def _enc_adds_imm(rd: int, imm: int) -> bytes:
    return struct.pack("<H", 0x3000 | (rd << 8) | imm)


def _mul_patches(rom: bytes) -> list[dict]:
    """×40 → ×48：lsls #2→#1（异寄存器）、lsls #3→#4（同寄存器）。"""
    pat = struct.pack("<I", GBA_BASE + OLD_BASE)
    sites: list[int] = []
    i = rom.find(pat)
    while i != -1:
        sites.append(i)
        i = rom.find(pat, i + 1)
    out: list[dict] = []
    for s in sites:
        st = max(0, s - 0x14)
        chunk = rom[st:s]
        # 扫 Thumb 半字
        for off in range(0, len(chunk) - 1, 2):
            abs_off = st + off
            hw = struct.unpack_from("<H", rom, abs_off)[0]
            # lsls rd, rm, #imm5 : 00000 iiiii mmm ddd
            if (hw >> 11) != 0:
                continue
            imm5 = (hw >> 6) & 0x1F
            rm = (hw >> 3) & 7
            rd = hw & 7
            new_imm = None
            note = ""
            if imm5 == 2 and rm != rd:
                new_imm = 1
                note = f"lsls r{rd},r{rm},#2→#1"
            elif imm5 == 3 and rm == rd:
                new_imm = 4
                note = f"lsls r{rd},r{rm},#3→#4"
            if new_imm is None:
                continue
            new_hw = (new_imm << 6) | (rm << 3) | rd
            out.append({
                "off": f"0x{abs_off:X}",
                "bytes": struct.pack("<H", new_hw).hex(" "),
                "label": note,
            })
    return out


def _field_patches() -> list[dict]:
    out: list[dict] = []
    for off, mn, new in FIELD_LDR_SITES:
        b = _enc_ldr(mn, new)
        out.append({
            "off": f"0x{off:X}",
            "bytes": b.hex(" "),
            "label": f"{mn} [r1,#0x{new:X}]",
        })
    for off, imm in ADDS_SITES:
        # 原指令是 adds r4,#old；保持 r4
        b = _enc_adds_imm(4, imm)
        out.append({
            "off": f"0x{off:X}",
            "bytes": b.hex(" "),
            "label": f"adds r4,#0x{imm:X}",
        })
    return out


def build_item_entry(rom: bytes, index: int, name: bytes) -> bytes:
    src = OLD_BASE + index * OLD_STRIDE
    entry = bytearray(NEW_STRIDE)
    fitted = _fit(name, NAME_CAP)
    if fitted is None:
        body = name[:-1] if name.endswith(b"\xFF") else name
        while len(body) + 1 > NAME_CAP and body:
            if body[:1] == b"\xf7":      # F7 00 hi lo = 4 字节一组
                body = body[:-4]
            else:
                body = body[:-1]
        fitted = _fit(body + b"\xFF", NAME_CAP)
    if fitted is None:
        fitted = bytes(rom[src:src + OLD_NAME_CAP])
        if len(fitted) < NAME_CAP:
            fitted = fitted + bytes(NAME_CAP - len(fitted))
    entry[0:NAME_CAP] = fitted[:NAME_CAP]
    for old_off, new_off, width in FIELD_MAP:
        entry[new_off:new_off + width] = rom[src + old_off:src + old_off + width]
    return bytes(entry)


def plan_item_table(
    rom: bytes,
    entries: list[dict],
    encoder: Callable[[str], bytes] | None,
    cursor: int,
) -> tuple[dict | None, int, str | None]:
    from .write_plan import _encode, _entry_file_off

    count = (0x39DCA7 - OLD_BASE + 1) // OLD_STRIDE  # 348
    rows: dict[int, bytes] = {}
    for e in entries:
        addr = _entry_file_off(e)
        if addr is None:
            continue
        if (addr - OLD_BASE) % OLD_STRIDE:
            continue
        idx = (addr - OLD_BASE) // OLD_STRIDE
        if not (0 <= idx < count):
            continue
        text = e.get("translated") or ""
        if not text or text == (e.get("original") or ""):
            continue
        raw = _encode(text, encoder)
        if raw:
            rows[idx] = raw
    if not rows:
        return None, cursor, "没有译文"

    blob = bytearray()
    for i in range(count):
        if i in rows:
            name = rows[i]
        else:
            src = OLD_BASE + i * OLD_STRIDE
            name = bytes(rom[src:src + OLD_NAME_CAP])
            if 0xFF in name:
                name = name[: name.index(0xFF) + 1]
        blob += build_item_entry(rom, i, name)

    if cursor + len(blob) > TABLE_AREA_END:
        return None, cursor, "补丁表区域满了"
    new_base = cursor
    cursor = (cursor + len(blob) + 3) & ~3

    insns = _mul_patches(rom) + _field_patches()
    literals: list[dict] = []
    needle = struct.pack("<I", GBA_BASE + OLD_BASE)
    start = 0
    while True:
        i = rom.find(needle, start)
        if i < 0:
            break
        if i % 4 == 0:
            literals.append({"off": f"0x{i:X}"})
        start = i + 1

    safe = "道具名"
    table = {
        "module": "道具名",
        "old_base": f"0x{OLD_BASE:X}",
        "old_stride": OLD_STRIDE,
        "new_base": f"0x{new_base:X}",
        "new_stride": NEW_STRIDE,
        "count": count,
        "name_offset": 0,
        "old_name_cap": OLD_NAME_CAP,
        "new_name_cap": NAME_CAP,
        "blob": f"gen/plan_table_{safe}.bin",
        "blob_name": f"plan_table_{safe}.bin",
        "blob_hex": bytes(blob).hex(),
        "insns": insns,
        "literals": literals,
        "field_map": {f"0x{a:X}": f"0x{b:X}" for a, b, _ in FIELD_MAP},
        "note": f"item 40→48 mul={sum(1 for x in insns if 'lsls' in (x.get('label') or ''))} field={len(FIELD_LDR_SITES)+len(ADDS_SITES)}",
    }
    return table, cursor, None
