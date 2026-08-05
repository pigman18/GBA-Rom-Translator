"""Fixed name tables — layouts from ``translate/modules.inject.json``.

Used at extract (read JP rows) and again at build (widen/reloc Chinese tables).
Assembled into a legacy tables dict by ``tables_from_modules_inject``.
"""

from __future__ import annotations

import struct
from pathlib import Path

from .config_loader import get_active_game_id, list_available_games, load_game_config
from .jp_pcs import decode_pcs, make_entry_id

_TABLE_BY_GAME: dict[str, dict] = {}


def _resolve_any_game_id() -> str:
    games = list_available_games()
    if not games:
        raise RuntimeError("No game configs found in configs/ directory")
    return games[0]


def _tbl(game_id: str = "") -> dict:
    gid = (game_id or get_active_game_id() or _resolve_any_game_id()).strip()
    if gid not in _TABLE_BY_GAME:
        _TABLE_BY_GAME[gid] = load_game_config(gid).get("tables", {})
    return _TABLE_BY_GAME[gid]


def base() -> int:
    return int(_tbl().get("base", 0x08000000))


def species_names_cfg():
    return _tbl().get("species_names", {})


def move_names_cfg():
    return _tbl().get("move_names", {})


def ability_names_cfg():
    return _tbl().get("ability_names", {})


def type_names_cfg():
    return _tbl().get("type_names", {})


def item_data_cfg():
    return _tbl().get("item_data", {})


def nature_names_cfg():
    return _tbl().get("nature_names", {})


def chs_species_stride() -> int:
    return _tbl().get("chs_species_stride", 24)


def chs_move_stride() -> int:
    return _tbl().get("chs_move_stride", 24)


# ---------------------------------------------------------------------------
# Public extraction functions (unchanged API, config-driven underneath)
# ---------------------------------------------------------------------------


def _slot_text(rom: bytes, off: int, stride: int) -> tuple[str, bytes]:
    slot = rom[off: off + stride]
    if 0xFF not in slot:
        return "", slot
    end = slot.index(0xFF)
    raw = slot[: end + 1]
    return decode_pcs(raw), raw


def extract_fixed_table(
    rom: bytes,
    *,
    offset: int,
    stride: int,
    count: int,
    module: str,
    id_prefix: str,
) -> list[dict]:
    entries: list[dict] = []
    BASE = base()
    table_ptr = BASE + offset
    for i in range(count):
        off = offset + i * stride
        text, raw = _slot_text(rom, off, stride)
        if not text:
            continue
        entries.append({
            "id": make_entry_id(f"0x{BASE + off:08X}", raw.hex(" ")),
            "address": f"0x{BASE + off:08X}",
            "table_index": i,
            "table_base": f"0x{table_ptr:08X}",
            "byte_length": stride,
            "original_hex": raw.hex(" "),
            "original": text,
            "translated": "",
            "module": module,
            "is_pointer_based": False,
            "is_fixed_table": True,
            "pointer_sources": [],
            "pointer_addresses": [],
        })
    return entries


def extract_species_names(rom: bytes) -> list[dict]:
    c = species_names_cfg()
    if not c or "offset" not in c:
        return []
    return extract_fixed_table(
        rom, offset=c["offset"], stride=c["stride"], count=c["count"],
        module=c.get("module") or "物种名", id_prefix="pkmn",
    )


def extract_move_names(rom: bytes) -> list[dict]:
    c = move_names_cfg()
    if not c or "offset" not in c:
        return []
    return extract_fixed_table(
        rom, offset=c["offset"], stride=c["stride"], count=c["count"],
        module=c.get("module") or "招式名", id_prefix="move",
    )


def extract_ability_names(rom: bytes) -> list[dict]:
    c = ability_names_cfg()
    if not c or "offset" not in c:
        return []
    return extract_fixed_table(
        rom, offset=c["offset"], stride=c["stride"], count=c["count"],
        module=c.get("module") or "特性名", id_prefix="ability",
    )


def extract_type_names(rom: bytes) -> list[dict]:
    c = type_names_cfg()
    if not c or "offset" not in c:
        return []
    return extract_fixed_table(
        rom, offset=c["offset"], stride=c["stride"], count=c["count"],
        module=c.get("module") or "属性名", id_prefix="type",
    )


def extract_item_names(rom: bytes) -> list[dict]:
    c = item_data_cfg()
    if not c or "offset" not in c:
        return []
    BASE_VAL = base()
    mid = c.get("module") or "道具名"
    entries: list[dict] = []
    table_ptr = BASE_VAL + c["offset"]
    for i in range(c["count"]):
        off = c["offset"] + i * c["entry_size"]
        text, raw = _slot_text(rom, off, c["name_stride"])
        if not text or set(text) <= {"？", "ー", "-", " "}:
            continue
        entries.append({
            "id": make_entry_id(f"0x{BASE_VAL + off:08X}", raw.hex(" ")),
            "address": f"0x{BASE_VAL + off:08X}",
            "table_index": i,
            "table_base": f"0x{table_ptr:08X}",
            "byte_length": c["name_stride"],
            "original_hex": raw.hex(" "),
            "original": text,
            "translated": "",
            "module": mid,
            "is_pointer_based": False,
            "is_fixed_table": True,
            "pointer_sources": [],
            "pointer_addresses": [],
        })
    return entries


def extract_item_descriptions(rom: bytes) -> list[dict]:
    c = item_data_cfg()
    if not c or "offset" not in c:
        return []
    BASE_VAL = base()
    mid = "道具说明"
    entries: list[dict] = []
    seen: set[int] = set()
    for i in range(c["count"]):
        ent = c["offset"] + i * c["entry_size"]
        ptr_off = ent + c["desc_ptr_offset"]
        if ptr_off + 4 > len(rom):
            break
        ptr = struct.unpack_from("<I", rom, ptr_off)[0]
        if not (BASE_VAL <= ptr < BASE_VAL + 0x800000):
            continue
        so = ptr - BASE_VAL
        if so in seen or so + 2 >= len(rom):
            continue
        eos = rom.find(b"\xFF", so, so + 160)
        if eos < 0:
            continue
        raw = rom[so: eos + 1]
        if not (4 <= len(raw) <= 160):
            continue
        text = decode_pcs(raw)
        if not text or "<" in text:
            continue
        if not any("\u3040" <= ch <= "\u30ff" for ch in text):
            continue
        seen.add(so)
        entries.append({
            "id": make_entry_id(f"0x{BASE_VAL + so:08X}", raw.hex(" ")),
            "address": f"0x{BASE_VAL + so:08X}",
            "table_index": i,
            "byte_length": len(raw),
            "original_hex": raw.hex(" "),
            "original": text,
            "translated": "",
            "module": mid,
            "is_pointer_based": True,
            "is_fixed_table": False,
            "pointer_sources": [f"0x{BASE_VAL + ptr_off:08X}"],
            "pointer_addresses": [f"0x{BASE_VAL + ptr_off:08X}"],
        })
    return entries


def extract_nature_names(rom: bytes) -> list[dict]:
    c = nature_names_cfg()
    if not c or "table" not in c:
        return []
    BASE_VAL = base()
    mid = c.get("module") or "性格名"
    entries: list[dict] = []
    for i in range(c["count"]):
        lit = c["table"] + i * 4
        if lit + 4 > len(rom):
            break
        ptr = struct.unpack_from("<I", rom, lit)[0]
        if not (BASE_VAL <= ptr < BASE_VAL + 0x800000):
            continue
        so = ptr - BASE_VAL
        eos = rom.find(b"\xFF", so, so + 24)
        if eos < 0:
            continue
        raw = rom[so: eos + 1]
        text = decode_pcs(raw)
        if not text:
            continue
        entries.append({
            "id": make_entry_id(f"0x{BASE_VAL + so:08X}", raw.hex(" ")),
            "address": f"0x{BASE_VAL + so:08X}",
            "table_index": i,
            "table_base": f"0x{BASE_VAL + c['table']:08X}",
            "byte_length": len(raw),
            "original_hex": raw.hex(" "),
            "original": text,
            "translated": "",
            "module": mid,
            "is_pointer_based": True,
            "is_fixed_table": False,
            "pointer_sources": [f"0x{BASE_VAL + lit:08X}"],
            "pointer_addresses": [f"0x{BASE_VAL + lit:08X}"],
        })
    return entries


def find_literal_refs(rom: bytes, target_offset: int) -> list[int]:
    BASE_VAL = base()
    needle = struct.pack("<I", BASE_VAL + target_offset)
    hits: list[int] = []
    pos = 0
    size = min(len(rom), 0x800000)
    while True:
        i = rom.find(needle, pos, size)
        if i < 0:
            break
        if i % 4 == 0:
            hits.append(i)
        pos = i + 1
    return hits


def build_chs_table(
    entries: list[dict],
    encode,
    *,
    stride: int,
    count: int,
    eos: int = 0xFF,
    table_label: str = "",
) -> bytes:
    by_index = {int(e["table_index"]): e for e in entries if "table_index" in e}
    out = bytearray()
    eos_b = bytes([eos & 0xFF])
    for i in range(count):
        slot = bytearray([0x00] * stride)
        e = by_index.get(i)
        if not e:
            slot[0] = eos & 0xFF
            out.extend(slot)
            continue
        translated = (e.get("translated") or "").strip('"')
        original = (e.get("original") or "").strip('"')
        if translated and translated != original:
            try:
                encoded = bytearray(encode(translated))
            except Exception as exc:
                raise ValueError(
                    f"{table_label}[{i}]: encode failed for '{translated}': {exc}"
                ) from exc
            while encoded and encoded[-1] in (0xFA, 0xFF):
                encoded.pop()
            encoded.extend(eos_b)
            if len(encoded) > stride:
                truncated = encoded[: stride - 1] + eos_b
                addr_hex = f" @ 0x{int(e.get('address', '0'), 16):X}" if e and e.get("address") else ""
                print(
                    f"  WARN {table_label}[{i}]{addr_hex}: '{translated}' "
                    f"encoded {len(encoded)}B > stride {stride}B, truncating"
                )
                print(f"    -> after truncation: {truncated.hex()}")
                encoded = truncated
            slot[: len(encoded)] = encoded
        else:
            raw = bytes.fromhex(e.get("original_hex", "ff").replace(" ", ""))
            if len(raw) > stride:
                print(
                    f"  WARN {table_label}[{i}]: original hex {len(raw)}B "
                    f"> stride {stride}B, truncating"
                )
                raw = raw[: stride - 1] + eos_b
            slot[: len(raw)] = raw
        out.extend(slot)
    return bytes(out)


def rom_table_entries(
    rom: bytes,
    *,
    offset: int,
    stride: int,
    count: int,
    module: str = "",
) -> list[dict]:
    entries: list[dict] = []
    for i in range(count):
        off = offset + i * stride
        raw = bytes(rom[off: off + stride])
        text, _ = _slot_text(rom, off, stride)
        e = {
            "table_index": i,
            "original_hex": raw.hex(" "),
            "original": text,
            "translated": "",
        }
        if module:
            e["module"] = module
        entries.append(e)
    return entries



