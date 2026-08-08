"""Rebuild AXVJ name tables for Chinese and patch refs. Config-driven."""

from __future__ import annotations

import struct

from .tables import (
    base,
    build_chs_table,
    find_literal_refs,
    item_data_cfg,
    rom_table_entries,
)
from .charmap import Charmap
from .jp_pcs import decode_pcs


def _parse_rom_offset(addr) -> int | None:
    """``0x08XXXXXX`` / int → file offset; invalid → None."""
    if addr is None or addr == "":
        return None
    try:
        a = int(addr) if isinstance(addr, int) else int(str(addr).strip(), 0)
    except (TypeError, ValueError):
        return None
    if a >= 0x08000000:
        a -= 0x08000000
    return a if a >= 0 else None


def _slot_index_from_entry(
    e: dict,
    *,
    offset: int,
    stride: int,
    count: int,
    index_bias: int = 0,
) -> int | None:
    """Map an inject entry to a table slot — prefer ``address``, then ``table_index``."""
    if stride <= 0 or count <= 0:
        return None
    rom_off = _parse_rom_offset(e.get("address"))
    if rom_off is not None and rom_off >= offset:
        delta = rom_off - offset
        if delta % stride == 0:
            idx = delta // stride
            if 0 <= idx < count:
                return idx
    ti = e.get("table_index")
    if ti is None or ti == "":
        return None
    try:
        idx = int(ti) + int(index_bias)
    except (TypeError, ValueError):
        return None
    if 0 <= idx < count:
        return idx
    return None


def _exact_literal_refs(rom: bytes, table_offset: int) -> list[int]:
    base_addr = base()
    return [
        lit
        for lit in find_literal_refs(rom, table_offset)
        if struct.unpack_from("<I", rom, lit)[0] == base_addr + table_offset
    ]


def _resolve_literal_table_base(
    rom: bytes, offset: int, stride: int
) -> tuple[int, int]:
    """Literal pool may point at a NONE pad one slot before extract ``offset``.

    Returns ``(lit_offset, prefix_slots)`` where ``prefix_slots`` is usually 0 or 1.
    """
    if _exact_literal_refs(rom, offset):
        return offset, 0
    if stride > 0 and offset >= stride:
        prev = offset - stride
        if _exact_literal_refs(rom, prev):
            return prev, 1
    return offset, 0


def _merge_table_entries(
    rom: bytes,
    overlays: list[dict],
    *,
    offset: int,
    stride: int,
    count: int,
    module: str,
    index_bias: int = 0,
) -> list[dict]:
    """Start from full JP ROM table, then overlay translated rows by address."""
    merged = {
        int(e["table_index"]): dict(e)
        for e in rom_table_entries(
            rom, offset=offset, stride=stride, count=count, module=module
        )
    }
    for e in overlays:
        idx = _slot_index_from_entry(
            e, offset=offset, stride=stride, count=count, index_bias=index_bias
        )
        if idx is None or idx not in merged:
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


def _try_widen_mul6_at(rom: bytearray, abs_i: int) -> bool:
    """If ``rom[abs_i..]`` is classic species*6, widen final lsl to #3 (*24)."""
    if abs_i < 0 or abs_i + 6 > len(rom):
        return False
    h0 = struct.unpack_from("<H", rom, abs_i)[0]
    h1 = struct.unpack_from("<H", rom, abs_i + 2)[0]
    h2 = struct.unpack_from("<H", rom, abs_i + 4)[0]
    ok0, ra, rb = _is_lsl_imm(h0, 1)
    if not ok0:
        return False
    if (h1 >> 9) != 0b0001100:
        return False
    rc = h1 & 0x7
    rn = (h1 >> 3) & 0x7
    rm = (h1 >> 6) & 0x7
    if not ((rn == ra and rm == rb) or (rn == rb and rm == ra)):
        return False
    ok2, rd2, rm2 = _is_lsl_imm(h2, 1)
    if not ok2 or rd2 != rc or rm2 != rc:
        return False
    # Already widened?
    ok24, rd24, rm24 = _is_lsl_imm(h2, 3)
    if ok24 and rd24 == rc and rm24 == rc:
        return False
    new_h2 = (h2 & ~0x07C0) | (3 << 6)
    struct.pack_into("<H", rom, abs_i + 4, new_h2)
    return True


def _patch_mul6_to_mul24(rom: bytearray, literal_off: int) -> int:
    """Near a gSpeciesNames literal, widen every species*6 index to *24.

    Must patch **all** matches in the window — a single early false hit (or a
    helper that shares the pool) used to leave the real dex *6 intact while the
    literal was already retargeted at the ×24 table (e.g. species 284 → slot 71).

    Patterns:
      lsls rA, rB, #1 ; adds rC, rA, rB ; lsls rC, rC, #1   (*6)
    """
    n = 0
    # Before and after the pool entry: *6 often sits on either side of the ldr.
    start = max(0, literal_off - 0x100)
    end = min(len(rom) - 4, literal_off + 0x100)
    for abs_i in range(start, end, 2):
        if _try_widen_mul6_at(rom, abs_i):
            n += 1
    # Also widen near every ldr that loads this literal (wider call-site cover).
    ldr_lo = max(0, literal_off - 0x400)
    ldr_hi = min(len(rom) - 2, literal_off + 0x40)
    for i in range(ldr_lo, ldr_hi, 2):
        h = struct.unpack_from("<H", rom, i)[0]
        if _ldr_pc_target(i, h) != literal_off:
            continue
        for abs_i in range(max(0, i - 0x80), min(len(rom) - 4, i + 0x40), 2):
            if _try_widen_mul6_at(rom, abs_i):
                n += 1
    return n


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
    name_win = int(
        item_cfg.get("name_stride")
        or item_cfg.get("name_max")
        or item_cfg.get("desc_ptr_offset")
        or entry_size
    )
    count = item_cfg["count"]
    out: list[dict] = []
    for i in range(count):
        off = offset + i * entry_size
        window = bytes(rom[off : off + name_win])
        text = ""
        raw = window
        if 0xFF in window:
            raw = window[: window.index(0xFF) + 1]
            text = decode_pcs(raw)
        out.append(
            {
                "table_index": i,
                "original_hex": raw.hex(" "),
                "original": text,
                "translated": "",
                "byte_length": len(raw) if text else 0,
                "module": item_cfg.get("module") or "",
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

    # Game literals often point at a NONE pad one slot before extract start
    # (招式名/特性名). Expand from that physical base; overlay by address.
    lit_offset, prefix = _resolve_literal_table_base(bytes(rom), offset, stride)
    total = count + prefix
    if prefix:
        print(
            f"  {label}: literal base 0x{lit_offset:X} "
            f"(extract 0x{offset:X}, +{prefix} pad slot)"
        )

    full = _merge_table_entries(
        bytes(rom), matched,
        offset=lit_offset, stride=stride, count=total, module=module,
        index_bias=prefix,
    )
    table = build_chs_table(
        full, encode,
        stride=chs_stride, count=total, table_label=label,
    )

    lits = _exact_literal_refs(bytes(rom), lit_offset)

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
    result["lit_offset"] = lit_offset
    result["prefix_slots"] = prefix
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
    module = patch.get("module") or item_data_cfg().get("module") or ""
    if not module:
        raise ValueError("table_patch item: module id missing on patch/config")
    chs_stride = patch["chs_stride"]
    count = patch["count"]
    base_addr = base()

    item_cfg = item_data_cfg()
    if not item_cfg:
        # tables 键已改为模块 id；按形态回退
        for _k, v in (tables_cfg or {}).items():
            if isinstance(v, dict) and "entry_size" in v and v.get("offset") is not None:
                item_cfg = v
                break
    if not item_cfg:
        raise ValueError("table_patch: item struct table config missing")

    merged = {int(e["table_index"]): dict(e) for e in _item_rom_name_entries(bytes(rom), item_cfg)}
    item_offset = int(item_cfg["offset"])
    entry_size = int(item_cfg["entry_size"])
    for e in entries:
        em = _entry_module(e)
        if module and em and em != module:
            continue
        idx = _slot_index_from_entry(
            e, offset=item_offset, stride=entry_size, count=count
        )
        if idx is None or idx not in merged:
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

    Modules with ``relocate`` not explicitly true are skipped (no write widen);
    those entries inject via plan type/target_hex instead.
    """
    if tables_cfg is None:
        from .tables import _tbl
        tables_cfg = _tbl()

    patches = _load_table_patches(tables_cfg)
    if not patches:
        return write_offset, {}

    from .config_loader import apply_module_phrase_channel, get_active_game_id
    from .translate_plan import module_allows_table_widen

    game_id = get_active_game_id() or ""

    def encode(text: str) -> bytes:
        raw = charmap.encode(text)
        mid = getattr(encode, "_module", None)
        return apply_module_phrase_channel(raw, get_active_game_id() or "", mid)

    while write_offset % 4:
        write_offset += 1

    stats: dict[str, dict] = {}
    for patch in patches:
        mid = patch.get("module") or patch["tables_key"]
        if not module_allows_table_widen(game_id, mid):
            print(f"  {mid}: skip write widen (relocate!=true; use type/target_hex)")
            continue
        while write_offset % 4:
            write_offset += 1
        encode._module = mid  # type: ignore[attr-defined]
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
