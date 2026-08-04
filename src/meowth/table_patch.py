"""Rebuild AXVJ name tables for Chinese and patch refs. Config-driven."""

from __future__ import annotations

import struct

from .tables import (
    base,
    build_chs_table,
    find_literal_refs,
    rom_table_entries,
)
from .charmap import Charmap
from .jp_pcs import decode_pcs


def _merge_table_entries(
    rom: bytes,
    overlays: list[dict],
    *,
    offset: int,
    stride: int,
    count: int,
    module: str,
) -> list[dict]:
    """Start from full JP ROM table, then overlay any translated rows."""
    merged = {
        int(e["table_index"]): dict(e)
        for e in rom_table_entries(
            rom, offset=offset, stride=stride, count=count, module=module
        )
    }
    for e in overlays:
        if "table_index" not in e:
            continue
        idx = int(e["table_index"])
        if idx not in merged:
            continue
        slot = merged[idx]
        if e.get("translated"):
            slot["translated"] = e["translated"]
        if e.get("original"):
            slot["original"] = e["original"]
        if e.get("original_hex"):
            slot["original_hex"] = e["original_hex"]
    return [merged[i] for i in range(count)]


def _is_lsl_imm(h: int, imm: int) -> tuple[bool, int, int]:
    """Return (ok, rd, rm) if h is `lsls rd, rm, #imm`."""
    if (h >> 11) != 0:
        return False, 0, 0
    if ((h >> 6) & 0x1F) != imm:
        return False, 0, 0
    rd = h & 0x7
    rm = (h >> 3) & 0x7
    return True, rd, rm


def _is_adds_reg(h: int, rd: int, rn: int, rm: int) -> bool:
    """`adds rd, rn, rm` (register)."""
    if (h >> 9) != 0b0001100:
        return False
    return (h & 0x7) == rd and ((h >> 3) & 0x7) == rn and ((h >> 6) & 0x7) == rm


def _ldr_pc_target(insn_off: int, h: int) -> int | None:
    """If h is ldr rd, [pc, #imm], return absolute target offset."""
    if (h & 0xF800) != 0x4800:
        return None
    imm = h & 0xFF
    pc = insn_off + 4
    base = pc & ~2
    return base + imm * 4


def _patch_mul6_to_mul24(rom: bytearray, literal_off: int) -> int:
    """Near a gSpeciesNames literal, widen species*6 index to *24.

    Patterns:
      lsls rA, rB, #1 ; adds rC, rA, rB ; lsls rC, rC, #1   (*6)
      (also classic where A==C)
    """
    start = max(0, literal_off - 0x80)
    for abs_i in range(start, literal_off - 4, 2):
        h0 = struct.unpack_from("<H", rom, abs_i)[0]
        h1 = struct.unpack_from("<H", rom, abs_i + 2)[0]
        h2 = struct.unpack_from("<H", rom, abs_i + 4)[0]
        ok0, ra, rb = _is_lsl_imm(h0, 1)
        if not ok0:
            continue
        # adds rC, rA, rB
        if (h1 >> 9) != 0b0001100:
            continue
        rc = h1 & 0x7
        rn = (h1 >> 3) & 0x7
        rm = (h1 >> 6) & 0x7
        if not ((rn == ra and rm == rb) or (rn == rb and rm == ra)):
            continue
        ok2, rd2, rm2 = _is_lsl_imm(h2, 1)
        if not ok2 or rd2 != rc or rm2 != rc:
            continue
        # lsls rc, rc, #1 -> #3  => *6 becomes *24
        new_h2 = (h2 & ~0x07C0) | (3 << 6)
        struct.pack_into("<H", rom, abs_i + 4, new_h2)
        return 1
    return 0


def _is_lsr_imm(h: int, imm: int) -> tuple[bool, int, int]:
    """Return (ok, rd, rm) if h is `lsrs rd, rm, #imm`."""
    if (h >> 11) != 0b00001:
        return False, 0, 0
    if ((h >> 6) & 0x1F) != imm:
        return False, 0, 0
    rd = h & 0x7
    rm = (h >> 3) & 0x7
    return True, rd, rm


def _patch_mul8_to_mul16(rom: bytearray, literal_off: int) -> int:
    """Near a gMoveNames/gAbilityNames literal, change *8 to *16.

    Patterns:
      - ``lsls rd, rm, #3`` 鈫?``#4``
      - ``lsls rd, rd, #16`` / ``lsrs rd, rd, #13`` 鈫?lsr ``#12``  (*8鈫?16)
    """
    start = max(0, literal_off - 0x100)
    # Find ldr that targets this literal, then a widenable *8 shortly before it
    for abs_i in range(start, literal_off, 2):
        h = struct.unpack_from("<H", rom, abs_i)[0]
        tgt = _ldr_pc_target(abs_i, h)
        if tgt != literal_off:
            continue
        # lsl #16 + lsr #13 == *8  (summary-screen style)
        if abs_i >= 4:
            h0 = struct.unpack_from("<H", rom, abs_i - 4)[0]
            h1 = struct.unpack_from("<H", rom, abs_i - 2)[0]
            ok0, rd0, rm0 = _is_lsl_imm(h0, 16)
            ok1, rd1, rm1 = _is_lsr_imm(h1, 13)
            if ok0 and ok1 and rd0 == rd1 == rm1 and rm0 == rd0:
                new_h1 = (h1 & ~0x07C0) | (12 << 6)
                struct.pack_into("<H", rom, abs_i - 2, new_h1)
                return 1
        for back in range(abs_i - 2, max(start, abs_i - 0x40), -2):
            hb = struct.unpack_from("<H", rom, back)[0]
            ok, rd, rm = _is_lsl_imm(hb, 3)
            if not ok:
                continue
            new_h = (hb & ~0x07C0) | (4 << 6)
            struct.pack_into("<H", rom, back, new_h)
            return 1
    # Fallback: first lsl #3 in window
    for abs_i in range(start, literal_off, 2):
        h = struct.unpack_from("<H", rom, abs_i)[0]
        ok, _, _ = _is_lsl_imm(h, 3)
        if ok:
            new_h = (h & ~0x07C0) | (4 << 6)
            struct.pack_into("<H", rom, abs_i, new_h)
            return 1
    return 0


def _item_rom_name_entries(rom: bytes, item_cfg: dict) -> list[dict]:
    """Every item name slot from gItems (for merge / CHS table build)."""
    offset = item_cfg["offset"]
    entry_size = item_cfg["entry_size"]
    name_stride = item_cfg["name_stride"]
    count = item_cfg["count"]
    out: list[dict] = []
    for i in range(count):
        off = offset + i * entry_size
        raw = bytes(rom[off : off + name_stride])
        text = ""
        if 0xFF in raw:
            text = decode_pcs(raw[: raw.index(0xFF) + 1])
        out.append(
            {
                "table_index": i,
                "original_hex": raw.hex(" "),
                "original": text,
                "translated": "",
                "module": item_cfg.get("module") or "道具名",
            }
        )
    return out


def _find_item_getname_ldr(rom: bytes, lit: int) -> int | None:
    """Return ldr offset of ItemId_GetName if lit is its gItems literal.

    Fingerprint (AXVJ): itemId*40 via lsl#2 / adds / lsl#3 immediately before
    ``ldr rd, =gItems``, then ``adds`` 鈥?returns name pointer (struct start).
    Field getters load gItems earlier into another reg and ldrh/ldrb after.
    """
    for abs_i in range(max(0, lit - 0x28), lit, 2):
        h = struct.unpack_from("<H", rom, abs_i)[0]
        if _ldr_pc_target(abs_i, h) != lit:
            continue
        if abs_i < 6:
            continue
        h0 = struct.unpack_from("<H", rom, abs_i - 6)[0]
        h1 = struct.unpack_from("<H", rom, abs_i - 4)[0]
        h2 = struct.unpack_from("<H", rom, abs_i - 2)[0]
        ok0, rd0, rm0 = _is_lsl_imm(h0, 2)
        ok2, rd2, rm2 = _is_lsl_imm(h2, 3)
        if not (ok0 and ok2 and rd0 == rd2 and rm2 == rd0):
            continue
        if (h1 >> 9) != 0b0001100:
            continue
        rd = h1 & 0x7
        rn = (h1 >> 3) & 0x7
        rm = (h1 >> 6) & 0x7
        if rd != rd0:
            continue
        if not ((rn == rd0 and rm == rm0) or (rn == rm0 and rm == rd0)):
            continue
        return abs_i
    return None


def _patch_item_getname_to_stride16(rom: bytearray, ldr_off: int) -> int:
    """Rewrite ItemId_GetName index math from *40 to *16 (lsl #4 + nops)."""
    h0 = struct.unpack_from("<H", rom, ldr_off - 6)[0]
    ok, rd, rm = _is_lsl_imm(h0, 2)
    if not ok:
        return 0
    new_lsl = (4 << 6) | (rm << 3) | rd
    struct.pack_into("<H", rom, ldr_off - 6, new_lsl)
    struct.pack_into("<H", rom, ldr_off - 4, 0x46C0)  # nop
    struct.pack_into("<H", rom, ldr_off - 2, 0x46C0)  # nop
    return 1


def _load_table_patches(tables_cfg: dict) -> list[dict]:
    """Return list of table patch configs that have chs_stride set."""
    patches: list[dict] = []
    for key, cfg in tables_cfg.items():
        if not isinstance(cfg, dict):
            continue
        if "chs_stride" not in cfg:
            continue
        patch = dict(cfg)
        patch["tables_key"] = key
        patch.setdefault("module", cfg.get("module") or key)
        patches.append(patch)
    return patches


def _entry_module(e: dict) -> str:
    return str(e.get("module") or e.get("_axvj_module") or e.get("category") or "")


def _process_literal_ref_table(
    rom: bytearray,
    entries: list[dict],
    encode,
    tables_cfg: dict,
    patch: dict,
    write_offset: int,
) -> tuple[int, dict]:
    """Process a table referenced by literal pool pointers with multiply widen."""
    key = patch["tables_key"]
    module = patch.get("module") or key
    offset = patch["offset"]
    stride = patch["stride"]
    count = patch["count"]
    chs_stride = patch["chs_stride"]
    widen_fn_name = patch.get("widen_fn", "")
    base_addr = base()

    label = module or key

    matched = [e for e in entries if _entry_module(e) == module]
    if not matched:
        return write_offset, {}

    full = _merge_table_entries(
        bytes(rom), matched,
        offset=offset, stride=stride, count=count, module=module,
    )
    table = build_chs_table(
        full, encode,
        stride=chs_stride, count=count, table_label=label,
    )

    lits = [
        lit for lit in find_literal_refs(bytes(rom), offset)
        if struct.unpack_from("<I", rom, lit)[0] == base_addr + offset
    ]

    safe: list[int] = []
    for lit in lits:
        probe = bytearray(rom)
        patched = False
        if widen_fn_name == "mul6_to_mul24":
            patched = bool(_patch_mul6_to_mul24(probe, lit))
        elif widen_fn_name == "mul8_to_mul16":
            patched = bool(_patch_mul8_to_mul16(probe, lit))
        if patched:
            safe.append(lit)
        else:
            print(f"  {label}: lit 0x{lit:X} cannot be widened (keeping JP ref)")

    result: dict[str, int] = {}
    if safe:
        new_base = base_addr + write_offset
        need = write_offset + len(table)
        if need > len(rom):
            rom.extend(b"\x00" * (need - len(rom) + 0x1000))
        rom[write_offset:write_offset + len(table)] = table
        write_offset += len(table)
        result["written"] = 1
        for lit in safe:
            struct.pack_into("<I", rom, lit, new_base)
            result["ptr_patched"] = result.get("ptr_patched", 0) + 1
            if widen_fn_name == "mul6_to_mul24":
                result["mul_patched"] = result.get("mul_patched", 0) + _patch_mul6_to_mul24(rom, lit)
            elif widen_fn_name == "mul8_to_mul16":
                result["mul_patched"] = result.get("mul_patched", 0) + _patch_mul8_to_mul16(rom, lit)
        print(f"  {label}: {len(safe)}/{len(lits)} sites widened")
    else:
        print(f"  {label}: no widen sites among {len(lits)} lits")
    result["lits_total"] = len(lits)
    result["lits_safe"] = len(safe)
    return write_offset, result


def _process_item_table(
    rom: bytearray,
    entries: list[dict],
    encode,
    tables_cfg: dict,
    patch: dict,
    write_offset: int,
) -> tuple[int, dict]:
    """Process item name table via gItems struct + ItemId_GetName patching."""
    key = patch["tables_key"]
    module = patch.get("module") or "道具名"
    chs_stride = patch["chs_stride"]
    count = patch["count"]
    base_addr = base()

    item_cfg = tables_cfg.get("item_data", {})
    if not item_cfg:
        raise ValueError("table_patch: item_data config missing for item patch")

    merged = {int(e["table_index"]): dict(e) for e in _item_rom_name_entries(bytes(rom), item_cfg)}
    for e in entries:
        em = _entry_module(e)
        if em != module and em != "道具名":
            continue
        if "table_index" not in e:
            continue
        idx = int(e["table_index"])
        if idx not in merged:
            continue
        if e.get("translated"):
            merged[idx]["translated"] = e["translated"]
        if e.get("original"):
            merged[idx]["original"] = e["original"]
        if e.get("original_hex"):
            merged[idx]["original_hex"] = e["original_hex"]
    full_items = [merged[i] for i in range(count)]
    table = build_chs_table(
        full_items, encode,
        stride=chs_stride, count=count, table_label=module or key,
    )

    offset = item_cfg["offset"]
    lits = [
        lit for lit in find_literal_refs(bytes(rom), offset)
        if struct.unpack_from("<I", rom, lit)[0] == base_addr + offset
    ]
    getname: list[tuple[int, int]] = []
    for lit in lits:
        ldr = _find_item_getname_ldr(bytes(rom), lit)
        if ldr is not None:
            getname.append((lit, ldr))
        else:
            print(f"  {key}: lit 0x{lit:X} not ItemId_GetName (keeping JP ref)")

    result: dict[str, int] = {}
    if getname:
        new_base = base_addr + write_offset
        need = write_offset + len(table)
        if need > len(rom):
            rom.extend(b"\x00" * (need - len(rom) + 0x1000))
        rom[write_offset:write_offset + len(table)] = table
        write_offset += len(table)
        result["written"] = 1
        for lit, ldr in getname:
            struct.pack_into("<I", rom, lit, new_base)
            result["ptr_patched"] = result.get("ptr_patched", 0) + 1
            result["mul_patched"] = result.get("mul_patched", 0) + _patch_item_getname_to_stride16(rom, ldr)
        print(f"  {key}: {len(getname)} GetName site(s)")
    else:
        print(f"  {key}: no ItemId_GetName among {len(lits)} lits")
    result["lits_total"] = len(lits)
    result["lits_safe"] = len(getname)
    return write_offset, result


def inject_name_tables(
    rom: bytearray,
    entries: list[dict],
    *,
    charmap: Charmap,
    write_offset: int,
    tables_cfg: dict | None = None,
) -> tuple[int, dict]:
    """Write expanded Chinese name tables and retarget ROM references.

    Reads patch config from ``tables_cfg`` (or auto-loads from game config).
    Only tables with ``chs_stride`` set are processed;
    ``patch_type: "item"`` uses item-specific logic (gItems struct).
    """
    if tables_cfg is None:
        from .tables import _tbl
        tables_cfg = _tbl()

    patches = _load_table_patches(tables_cfg)
    if not patches:
        return write_offset, {}

    def encode(text: str) -> bytes:
        from .config_loader import F9_PHRASE_DEFAULT, get_active_game_id, module_write_op

        raw = charmap.encode(text)
        if len(raw) < 4 or raw[0] != 0xF9 or raw[1] != F9_PHRASE_DEFAULT:
            return raw
        gid = get_active_game_id() or ""
        mid = getattr(encode, "_module", None)
        code = module_write_op(gid, mid) if gid else None
        if code is None:
            return raw
        # F9 <op> hi lo … — op replaces default phrase channel (80)
        return bytes([0xF9, code & 0xFF]) + raw[2:]

    while write_offset % 4:
        write_offset += 1

    stats: dict[str, dict] = {}
    for patch in patches:
        while write_offset % 4:
            write_offset += 1
        encode._module = patch.get("module")  # type: ignore[attr-defined]
        patch_type = patch.get("patch_type", "literal_ref_widen")
        if patch_type == "item":
            write_offset, tbl_stats = _process_item_table(
                rom, entries, encode, tables_cfg, patch, write_offset,
            )
        else:
            write_offset, tbl_stats = _process_literal_ref_table(
                rom, entries, encode, tables_cfg, patch, write_offset,
            )
        if tbl_stats:
            stats[patch["tables_key"]] = tbl_stats

    return write_offset, stats
