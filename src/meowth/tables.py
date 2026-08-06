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


def clear_table_cache() -> None:
    _TABLE_BY_GAME.clear()


def base() -> int:
    return int(_tbl().get("base", 0x08000000))


def module_cfg(module_id: str, game_id: str = "") -> dict:
    """Table row for ``module_id``（tables 键 = 模块 id，来自 texts.json）。"""
    if not module_id:
        return {}
    t = _tbl(game_id)
    c = t.get(module_id)
    if isinstance(c, dict):
        return c
    for v in t.values():
        if isinstance(v, dict) and v.get("module") == module_id:
            return v
    return {}


def iter_table_cfgs(game_id: str = ""):
    """Yield ``(key, cfg)`` for assembled name/desc tables."""
    for k, v in _tbl(game_id).items():
        if k in ("base",) or not isinstance(v, dict):
            continue
        if "offset" in v or "table" in v:
            yield k, v


def item_data_cfg() -> dict:
    """Struct name table（含 entry_size + name_stride）。"""
    for _, c in iter_table_cfgs():
        if "entry_size" in c and "name_stride" in c:
            return c
    return {}


def nature_names_cfg() -> dict:
    """Pointer name table（含 table 键、无 offset）。"""
    for _, c in iter_table_cfgs():
        if "table" in c and "offset" not in c:
            return c
    return {}


def chs_species_stride() -> int:
    for _, c in iter_table_cfgs():
        if c.get("chs_stride") and c.get("stride") and "entry_size" not in c:
            return int(c["chs_stride"])
    return 24


def chs_move_stride() -> int:
    n = 0
    for _, c in iter_table_cfgs():
        if c.get("chs_stride") and c.get("stride") and "entry_size" not in c:
            n += 1
            if n >= 2:
                return int(c["chs_stride"])
    return 24


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


def extract_module(rom: bytes, module_id: str) -> list[dict]:
    """按 ``tables[module_id]`` 形态抽取（stride / struct / ptr），无英文别名表。"""
    c = module_cfg(module_id)
    if not c:
        return []
    mid = c.get("module") or module_id
    if "entry_size" in c and "name_stride" in c and "offset" in c:
        return _extract_struct_names(rom, c, mid)
    if "table" in c and "count" in c and "offset" not in c:
        return _extract_ptr_names(rom, c, mid)
    if "offset" in c and "stride" in c and "count" in c:
        return extract_fixed_table(
            rom,
            offset=int(c["offset"]),
            stride=int(c["stride"]),
            count=int(c["count"]),
            module=mid,
            id_prefix=mid,
        )
    return []


def _extract_struct_names(rom: bytes, c: dict, mid: str) -> list[dict]:
    BASE_VAL = base()
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


def _extract_ptr_names(rom: bytes, c: dict, mid: str) -> list[dict]:
    BASE_VAL = base()
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


def extract_species_names(rom: bytes) -> list[dict]:
    """DEPRECATED — prefer ``extract_module`` with module id from texts.json."""
    import warnings

    warnings.warn("extract_species_names is deprecated; use extract_module", DeprecationWarning, stacklevel=2)
    for key, c in iter_table_cfgs():
        if c.get("stride") and "entry_size" not in c and c.get("offset") is not None:
            return extract_module(rom, c.get("module") or key)
    return []


def extract_move_names(rom: bytes) -> list[dict]:
    import warnings

    warnings.warn("extract_move_names is deprecated; use extract_module", DeprecationWarning, stacklevel=2)
    seen = 0
    for key, c in iter_table_cfgs():
        if c.get("stride") and "entry_size" not in c and c.get("offset") is not None:
            seen += 1
            if seen == 2:
                return extract_module(rom, c.get("module") or key)
    return []


def extract_ability_names(rom: bytes) -> list[dict]:
    for key, c in iter_table_cfgs():
        if c.get("stride") and "entry_size" not in c and c.get("offset") is not None:
            mid = c.get("module") or key
            # skip until we find a short stride typical of abilities (8) after species/moves
            if int(c.get("stride") or 0) == 8:
                return extract_module(rom, mid)
    return []


def extract_type_names(rom: bytes) -> list[dict]:
    for key, c in iter_table_cfgs():
        if int(c.get("stride") or 0) == 5 and c.get("offset") is not None:
            return extract_module(rom, c.get("module") or key)
    return []


def extract_item_names(rom: bytes) -> list[dict]:
    c = item_data_cfg()
    if not c:
        return []
    return extract_module(rom, c.get("module") or "")


def extract_nature_names(rom: bytes) -> list[dict]:
    c = nature_names_cfg()
    if not c:
        return []
    return extract_module(rom, c.get("module") or "")


def extract_item_descriptions(rom: bytes) -> list[dict]:
    import warnings

    warnings.warn(
        "extract_item_descriptions is deprecated; corpus comes from texts.json",
        DeprecationWarning,
        stacklevel=2,
    )
    c = item_data_cfg()
    if not c or "offset" not in c:
        return []
    BASE_VAL = base()
    mid = str(c.get("module") or "")
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



