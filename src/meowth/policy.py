"""Inject/extract policy — stage packs ``extract/`` + ``translate/`` + ``inject/``.

AUTHORITATIVE PROCESS (do not violate; see docs/FUNNEL.md and
.cursor/rules/axvj-funnel-no-hardcode.mdc):

  Domain → S0 Geography → S1 PointerClass → S2 TargetClass
        → S3 ContentPolicy → S4 Translation → S5 RewriteGate
        → S6 PostRestore → Version record

Config mapping:
- extract/config.json → S0 geography belts (SCRIPT_BANK_MIN, GFX deny ranges, …);
  ``enrich.<name>.addr_bands`` = optional Build/extract bypass scan belts
- translate/config.json skip → S3/S4 skip_zh_inject (keep JP text)
- inject/config.json → S5 site deny (title gfx ptrs, brand literals)
- translate/config.json modules → GUI addr-band scope (not this funnel file)

Domains (story / ui / pokemon / move / place / item / ime / …) MUST use
separate policies. Prefer dynamic class rules over per-address or
per-line story whitelists.

TEMPORARY debt: STABLE_SCRIPT_PREFIXES / keep_for_stable_inject exist only
as a brake; they are NOT the localization strategy — replace with domain
rules, do not extend the prefix list.

Hardcoded site lists for S1 registries live here or in ``intro_addrs``.
Do not add parallel deny/allow logic in ``rom_writer`` / ``extract``.
"""
from __future__ import annotations

import re
import struct
from enum import Enum, auto
from typing import Any, Iterable

from .config_loader import get_active_game_id, list_available_games, load_policy
from .intro_addrs import birch_ptr_allowlist, trainer_ui_ptr_allowlist
from .jp_pcs import looks_like_jp_text

_EXTRACTION_BY_GAME: dict[str, dict[str, Any]] = {}

# Defaults when policy.json is absent (other games / incomplete packs).
_DEFAULT_TITLE_GFX_PTR_DENY: frozenset[int] = frozenset()
_DEFAULT_BRAND_COMPACT_SKIP: frozenset[str] = frozenset()
_DEFAULT_SKIP_ZH_ORIGINALS = frozenset()
_DEFAULT_SKIP_ZH_PREFIXES: tuple[str, ...] = ()
# Per-game skip lives in translate/config.json (see translate/README.md).
# Empty defaults: do not re-hardcode toxic strings here.


def _resolve_any_game_id() -> str:
    games = list_available_games()
    if not games:
        raise RuntimeError("No game configs found in configs/ directory")
    return games[0]


def _resolve_game_id(game_id: str = "") -> str:
    return (game_id or get_active_game_id() or _resolve_any_game_id()).strip()


def _parse_addr(val: Any) -> int:
    if isinstance(val, int):
        return val
    s = str(val).strip().lower().replace("0x", "")
    return int(s, 16)


def _cfg(game_id: str = "") -> dict:
    gid = _resolve_game_id(game_id)
    if gid not in _EXTRACTION_BY_GAME:
        from .config_loader import load_game_config
        _EXTRACTION_BY_GAME[gid] = load_game_config(gid).get("extraction", {})
    return _EXTRACTION_BY_GAME[gid]


def _get(key: str, default):
    return _cfg().get(key, default)


def _policy(game_id: str = "") -> dict[str, Any]:
    return load_policy(_resolve_game_id(game_id))


def title_gfx_ptr_deny(game_id: str = "") -> frozenset[int]:
    raw = _policy(game_id).get("reject", {}).get("title_gfx_sites", {}).get("sites")
    if not raw:
        return _DEFAULT_TITLE_GFX_PTR_DENY
    return frozenset(_parse_addr(x) for x in raw)


def brand_compact_skip(game_id: str = "") -> frozenset[str]:
    raw = _policy(game_id).get("brand_compact_skip")
    if not raw:
        return _DEFAULT_BRAND_COMPACT_SKIP
    return frozenset(str(x) for x in raw)


def allows_ids(game_id: str = "") -> frozenset[str]:
    """config.json 顶层 ``allows``：条目 id 白名单。

    id 在 ``rejects`` 中但同时在 ``allows`` 内的条目照常翻译/注入（放行）。
    """
    raw = _policy(game_id).get("allows")
    if not raw:
        return frozenset()
    return frozenset(str(x) for x in raw)


def rejects_ids(game_id: str = "") -> frozenset[str]:
    """config.json 顶层 ``rejects``：条目 id 黑名单。

    直接拒绝（不翻译、不注入），除非同 id 也在 ``allows`` 中。
    """
    raw = _policy(game_id).get("rejects")
    if not raw:
        return frozenset()
    return frozenset(str(x) for x in raw)


def skip_zh_inject_originals(game_id: str = "") -> frozenset[str]:
    block = _policy(game_id).get("skip_zh_inject") or {}
    raw = block.get("originals")
    if not raw:
        return _DEFAULT_SKIP_ZH_ORIGINALS
    return frozenset(str(x) for x in raw)


def skip_zh_inject_prefixes(game_id: str = "") -> tuple[str, ...]:
    block = _policy(game_id).get("skip_zh_inject") or {}
    raw = block.get("prefixes")
    if not raw:
        return _DEFAULT_SKIP_ZH_PREFIXES
    return tuple(str(x) for x in raw)


# Backward-compatible names resolved via ``__getattr__`` (per active game).


def __getattr__(name: str):
    if name == "TITLE_GFX_PTR_DENY":
        return title_gfx_ptr_deny()
    if name == "BRAND_COMPACT_SKIP":
        return brand_compact_skip()
    if name == "SKIP_ZH_INJECT_ORIGINALS":
        return skip_zh_inject_originals()
    if name == "SKIP_ZH_INJECT_PREFIXES":
        return skip_zh_inject_prefixes()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def BASE() -> int:
    return 0x08000000


def SCRIPT_BANK_MIN() -> int:
    return _parse_addr(_get("script_bank_min", 0x100000))


def UI_RANGE() -> tuple:
    """Narrow UI walk for ``extract_ui_block`` (``allow.UI窄扫``)."""
    b = _bands_from_cfg(
        "allow", "UI窄扫", fallback=[[0x3E9440, 0x3E9900]]
    )
    return b[0] if b else (0x3E9440, 0x3E9900)


def _bands_from_cfg(*keys: str, fallback: list | None = None, game_id: str = "") -> tuple:
    """Read addr_bands from a nested _cfg() path, e.g. _bands_from_cfg('allow', 'UI文本')."""
    val: Any = _cfg(game_id)
    for k in keys:
        val = val.get(k, {}) if isinstance(val, dict) else {}
    raw = val.get("addr_bands") if isinstance(val, dict) else None
    if not raw:
        raw = fallback or []
    return tuple(tuple(_parse_addr(v) for v in r) for r in raw)


def UI_BANKS() -> tuple:
    return _bands_from_cfg("allow", "UI文本", fallback=[[0x3E8FC0, 0x3EA800], [0x3CFD00, 0x3DFF00], [0x3E8A80, 0x3EA800]])


def IME_RANGE() -> tuple:
    b = _bands_from_cfg(
        "allow", "IME五十音", fallback=[[0x3E98D6, 0x3E9910]]
    )
    return b[0] if b else (0x3E98D6, 0x3E9910)


def OPTION_MENU_BAND() -> tuple:
    b = _bands_from_cfg("allow", "设置菜单", fallback=[[0x37B44C, 0x37B500]])
    return b[0]


def enrich_scan_bands(name: str, game_id: str = "") -> tuple[tuple[int, int], ...]:
    """``enrich.<name>.addr_bands`` — from modules.json hidden 模块 (单源).

    v3 起 hidden 采集模块通过 ``enrich`` 字段声明其对应的 game.json enrich 名，
    并在 ``read.scan_addr_bands`` 承载扫描带；game.json ``extraction.enrich`` 已弃用。
    """
    from .config_loader import load_modules
    from .modules import _module_geo_bands

    gid = _resolve_game_id(game_id)
    for mid, meta in (load_modules(gid) or {}).items():
        if meta.get("enrich") == name and meta.get("hidden"):
            bands = _module_geo_bands(meta)
            if bands:
                return tuple(bands)
    return _bands_from_cfg("enrich", name, fallback=[], game_id=game_id)


def _enrich_hidden_block(name: str, game_id: str = "") -> dict[str, Any]:
    """Hidden module's ``read`` dict for enrich ``name`` (v3 source)."""
    from .config_loader import load_modules

    gid = _resolve_game_id(game_id)
    for mid, meta in (load_modules(gid) or {}).items():
        if meta.get("enrich") == name and meta.get("hidden"):
            return dict((meta.get("read") or {}))
    return {}


def _iter_hidden_modules(game_id: str = ""):
    """Yield hidden module metas for ``game_id`` (empty if none)."""
    from .config_loader import load_modules

    gid = _resolve_game_id(game_id)
    mods = load_modules(gid) or {}
    return [m for m in mods.values() if m.get("hidden")]


def enrich_seed_from_lexicon(name: str, game_id: str = "") -> bool:
    return bool(enrich_block(name, game_id).get("seed_from_lexicon", False))


def enrich_seed_originals(name: str, game_id: str = "") -> tuple[str, ...]:
    """JP needle list — 优先 hidden 模块 ``read.seed_originals``, 回退 game.json."""
    raw = _enrich_hidden_block(name, game_id).get("seed_originals")
    if raw:
        return tuple(str(x) for x in raw)
    block = (_cfg(game_id).get("enrich") or {}).get(name) or {}
    raw2 = block.get("seed_originals") or []
    return tuple(str(x) for x in raw2)


def enrich_block(name: str, game_id: str = "") -> dict[str, Any]:
    """Enrich ``name`` config — hidden module ``read`` (v3 单源), else game.json.

    Post-migration the rich decision keys (classify_rules / module_by_original /
    default_module / seed_from_lexicon / content_class) live on the matching
    hidden module's ``read``; game.json ``extraction.enrich`` is deprecated but
    still honored as belt-and-braces until fully purged.
    """
    hidden = _enrich_hidden_block(name, game_id)
    merged = dict(hidden)
    legacy = (_cfg(game_id).get("enrich") or {}).get(name) or {}
    # read keys are authoritative; game.json fills anything not moved yet.
    for k, v in legacy.items():
        if k not in merged and k not in ("description",):
            merged[k] = v
    return merged


def enrich_module_by_original(name: str, game_id: str = "") -> dict[str, str]:
    raw = enrich_block(name, game_id).get("module_by_original") or {}
    return {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}


def enrich_default_module(name: str, game_id: str = "") -> str:
    return str(enrich_block(name, game_id).get("default_module") or "")


def enrich_classify_rules(name: str, game_id: str = "") -> list[dict[str, Any]]:
    raw = enrich_block(name, game_id).get("classify_rules") or []
    return [dict(r) for r in raw if isinstance(r, dict)]


def enrich_keep_any_contains(name: str, game_id: str = "") -> tuple[str, ...]:
    raw = enrich_block(name, game_id).get("keep_any_contains") or []
    return tuple(str(x) for x in raw)


def content_class_spec(name: str, game_id: str = "") -> dict[str, Any]:
    """``any_of`` rule spec for a content class — hidden module ``read`` (单源).

    A hidden module whose ``read.content_class == name`` may carry the clause
    list on ``read.content_class_rules`` (v3 move). Falls back to game.json
    ``content_classes[name]`` until purged.
    """
    for meta in _iter_hidden_modules(game_id):
        r = meta.get("read") or {}
        rules = r.get("content_class_rules")
        if r.get("content_class") == name and rules:
            return {"any_of": [dict(x) for x in rules if isinstance(x, dict)]}
    return dict((_cfg(game_id).get("content_classes") or {}).get(name) or {})


def _text_compact(text: str) -> str:
    return (
        (text or "")
        .replace(" ", "")
        .replace("\u3000", "")
        .replace("\n", "")
        .replace("\r", "")
    )


def match_text_clause(text: str, clause: dict[str, Any]) -> bool:
    """Generic contains matcher for classify_rules / content_classes clauses."""
    if not clause:
        return True
    compact = _text_compact(text)
    max_len = clause.get("max_len")
    if max_len is not None and len(text or "") >= int(max_len):
        return False
    all_c = [str(x) for x in (clause.get("all_contains") or [])]
    if all_c and not all(x in compact for x in all_c):
        return False
    any_c = [str(x) for x in (clause.get("any_contains") or [])]
    if any_c and not any(x in compact for x in any_c):
        return False
    any_raw = [str(x) for x in (clause.get("any_contains_raw") or [])]
    if any_raw:
        raw_u = text or ""
        raw_up = raw_u.upper()
        if not any(x in raw_u or x.upper() in raw_up for x in any_raw):
            return False
    also = [str(x) for x in (clause.get("also_any_contains") or [])]
    if also and not any(x in compact for x in also):
        return False
    meaningful = bool(all_c or any_c or any_raw or also or max_len is not None)
    return True if meaningful or clause.get("module") else False


def classify_by_rules(
    text: str,
    rules: list[dict[str, Any]] | None,
    *,
    default_module: str = "",
) -> str:
    """First matching classify_rule wins; else ``default_module``."""
    for rule in rules or []:
        probe = {
            k: v
            for k, v in rule.items()
            if k not in ("module", "description")
        }
        if not probe or match_text_clause(text, rule):
            mid = str(rule.get("module") or "").strip()
            if mid:
                return mid
    return (default_module or "").strip()


def module_for_original(
    original: str,
    *,
    enrich_name: str,
    game_id: str = "",
) -> str:
    """``module_by_original`` map, else classify_rules, else ``default_module``."""
    by = enrich_module_by_original(enrich_name, game_id)
    if original in by:
        return by[original]
    rules = enrich_classify_rules(enrich_name, game_id)
    default = enrich_default_module(enrich_name, game_id)
    if rules:
        return classify_by_rules(original, rules, default_module=default)
    return default


def is_enrich_seed_label(
    text: str,
    *enrich_names: str,
    game_id: str = "",
) -> bool:
    """True if ``text`` (or compact form) matches any ``seed_originals`` list."""
    compact = _text_compact(text)
    for name in enrich_names:
        for seed in enrich_seed_originals(name, game_id):
            if text == seed or compact == _text_compact(seed):
                return True
    return False


def matches_content_class(text: str, class_name: str, game_id: str = "") -> bool:
    spec = content_class_spec(class_name, game_id)
    clauses = spec.get("any_of") or []
    if not clauses:
        return False
    return any(match_text_clause(text, c) for c in clauses if isinstance(c, dict))


def TITLE_LZ_BAND() -> tuple:
    b = _bands_from_cfg("reject", "标题LZ", fallback=[[0x36D000, 0x370000]])
    return b[0]


def GFX_PTR_SOURCE_DENY() -> tuple:
    return _bands_from_cfg("reject", "gfx_ptr_source", fallback=[[0x350000, 0x3E8FC0], [0x3EA800, 0x3FFF00]])


def GFX_STRING_TARGET_DENY() -> tuple:
    return _bands_from_cfg("reject", "gfx_string_target", fallback=[[0x370000, 0x3E8FC0], [0x3EA800, 0x3F0000]])


def SCRIPT_TEXT_PTR_OPCODES() -> frozenset[int]:
    """Opcodes whose following 4 bytes are a text pointer (AXVJ map scripts).

    Classic ``loadword`` (``0F rr``) is handled separately. Defaults from
    extract config — not a per-string address list.
    """
    raw = _get("script_text_ptr_opcodes", [0x67])
    out: set[int] = set()
    for x in raw or []:
        try:
            out.add(int(x) & 0xFF)
        except (TypeError, ValueError):
            continue
    return frozenset(out)


def TRUSTED_LZ_BANDS() -> tuple:
    raw = _cfg().get("trusted_lz_bands", {}).get("addr_bands", [[0x200000, 0x800000]])
    return tuple(tuple(_parse_addr(v) for v in r) for r in raw)


# S1 registries (intro_addrs + naming/confirm sites)
BIRCH_PTR_ALLOW = birch_ptr_allowlist()
TRAINER_UI_PTR_ALLOW = trainer_ui_ptr_allowlist()

class Geo(Enum):
    SCRIPT = auto()
    UI_BANK = auto()
    OPTION = auto()
    TITLE_LZ = auto()
    GFX = auto()
    LOW_ROM = auto()
    OTHER = auto()


def in_ranges(off: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(lo <= off < hi for lo, hi in ranges)


def geography_of(off: int) -> Geo:
    """S0: classify a ROM file offset."""
    tlz = TITLE_LZ_BAND()
    if tlz[0] <= off < tlz[1]:
        return Geo.TITLE_LZ
    if in_ranges(off, UI_BANKS()):
        return Geo.UI_BANK
    omb = OPTION_MENU_BAND()
    if omb[0] <= off < omb[1]:
        return Geo.OPTION
    if in_ranges(off, GFX_PTR_SOURCE_DENY()) or in_ranges(off, GFX_STRING_TARGET_DENY()):
        return Geo.GFX
    if off < SCRIPT_BANK_MIN():
        return Geo.LOW_ROM
    if off >= SCRIPT_BANK_MIN():
        return Geo.SCRIPT
    return Geo.OTHER


def string_in_ui_text_bank(so: int) -> bool:
    """UI / facility chrome body: extract config banks ∪ dump high UI geo.

    Dump ``geo_ranges`` for 界面 and high-ROM 设施 pools (shop/PC menus past
    the old 0x3EB000 cut) are the source of truth — not a hand-extended ceiling.
    """
    if in_ranges(so, UI_BANKS()):
        return True
    return string_in_dump_high_ui_geo(so)


def string_in_dump_high_ui_geo(so: int) -> bool:
    """True if ``so`` falls in a dump-measured band in the high UI pool region.

    Region class: band starts at ≥ 0x3D0000 (same floor as FC UI / menu pools).
    Covers PC chrome past ``ui_text_bank`` end without raising a magic ceiling.
    """
    from .modules import HIGH_UI_GEO_FLOOR, iter_high_ui_geo_bands

    # Script/dialogue bodies never need this path — skip before band walk.
    if so < HIGH_UI_GEO_FLOOR:
        return False
    try:
        return any(lo <= so <= hi for lo, hi in iter_high_ui_geo_bands())
    except Exception:
        return False


def string_in_option_band(so: int) -> bool:
    omb = OPTION_MENU_BAND()
    return omb[0] <= so < omb[1]


def is_loadword_text_ptr(rom: bytes | bytearray, ptr_off: int) -> bool:
    """True if ``ptr_off`` is a script-embedded text-pointer operand.

    Class rules (not per-address):
    - Gen3 ``loadword``: ``0F rr`` (rr ≤ 3) then pointer
    - Configurable trailing opcodes (extract ``script_text_ptr_opcodes``),
      e.g. AXVJ ``nn <op> <ptr>`` message embeds
    """
    if ptr_off < 2 or ptr_off + 4 > len(rom):
        return False
    if rom[ptr_off - 2] == 0x0F and rom[ptr_off - 1] <= 0x03:
        return True
    if rom[ptr_off - 1] in SCRIPT_TEXT_PTR_OPCODES():
        return True
    return False


def is_registry_ptr(ptr_off: int) -> bool:
    return ptr_off in BIRCH_PTR_ALLOW or ptr_off in TRAINER_UI_PTR_ALLOW


def is_local_pool_ptr(ptr_off: int, string_off: int) -> bool:
    return (ptr_off & 3) == 0 and string_off < ptr_off < string_off + 0x80


def _bus(off: int) -> int:
    return off if off >= BASE() else off + BASE()


def _file(off: int) -> int:
    return off - BASE() if off >= BASE() else off


def iter_entry_ptr_offs(entry: dict) -> list[int]:
    """Normalize extract ``pointer_sources`` / ``pointer_addresses`` to file offs."""
    out: list[int] = []
    for ptr_src in entry.get("pointer_addresses") or entry.get("pointer_sources") or []:
        try:
            ptr_addr = int(str(ptr_src).replace("0x", ""), 16)
        except ValueError:
            continue
        out.append(_file(ptr_addr))
    return out


def collect_entry_text_spans(entries: Iterable[dict]) -> list[tuple[int, int]]:
    """Corpus text bodies as ``[lo, hi)`` file offsets (for mid-body fake-ptr reject)."""
    spans: list[tuple[int, int]] = []
    for e in entries:
        raw = e.get("address")
        if raw in (None, ""):
            continue
        try:
            addr = _file(int(str(raw).replace("0x", ""), 16))
        except (TypeError, ValueError):
            continue
        bl = int(e.get("byte_length") or 0)
        if bl <= 0 or addr < 0:
            continue
        spans.append((addr, addr + bl))
    return spans


def ptr_site_in_text_body(
    ptr_off: int, text_spans: Iterable[tuple[int, int]] | None
) -> bool:
    """True if pointer *site* lies inside any corpus text body (PCS coincidence)."""
    if not text_spans:
        return False
    off = _file(ptr_off)
    for lo, hi in text_spans:
        if lo <= off < hi:
            return True
    return False


def is_live_aligned_text_ptr(
    rom: bytes | bytearray, ptr_off: int, string_off: int
) -> bool:
    """Aligned site whose current value is the string bus address."""
    if (ptr_off & 3) != 0 or ptr_off < 0x6000 or ptr_off + 4 > len(rom):
        return False
    cur = struct.unpack_from("<I", rom, ptr_off)[0]
    return _bus(cur) == _bus(string_off)


def is_nature_name_table_ptr(ptr_off: int) -> bool:
    from .tables import nature_names_cfg

    cfg = nature_names_cfg()
    if "table" not in cfg or "count" not in cfg:
        raise ValueError(
            "nature name table config missing (need module type=stride_ptr "
            "with start/end in texts.json modules)"
        )
    table = int(cfg["table"])
    count = int(cfg["count"])
    return table <= ptr_off < table + count * 4 and (ptr_off - table) % 4 == 0


def is_item_desc_table_ptr(ptr_off: int) -> bool:
    from .tables import item_data_cfg

    cfg = item_data_cfg()
    for req in ("offset", "count", "entry_size", "desc_ptr_offset"):
        if req not in cfg:
            return False
    base = int(cfg["offset"])
    count = int(cfg["count"])
    entry_size = int(cfg["entry_size"])
    desc_off = int(cfg["desc_ptr_offset"])
    if not (base <= ptr_off < base + count * entry_size):
        return False
    return (ptr_off - base) % entry_size == desc_off


def is_class_text_ptr(
    rom: bytes | bytearray, ptr_off: int, string_off: int
) -> bool:
    """S1 pointer class (loadword / registry / local-pool / UI band / name tables).

    No module-id lists. Used by target gate + pointer filter.
    """
    string_off = _file(string_off)
    ptr_off = _file(ptr_off)
    if is_registry_ptr(ptr_off) and (ptr_off & 3) == 0:
        return True
    if is_local_pool_ptr(ptr_off, string_off):
        return True
    if is_loadword_text_ptr(rom, ptr_off):
        return True
    if ptr_in_known_ui_band(ptr_off, string_off):
        return True
    if is_nature_name_table_ptr(ptr_off) or is_item_desc_table_ptr(ptr_off):
        return is_live_aligned_text_ptr(rom, ptr_off, string_off)
    if not is_live_aligned_text_ptr(rom, ptr_off, string_off):
        return False
    tlz = TITLE_LZ_BAND()
    if tlz[0] <= ptr_off < tlz[1] or ptr_off in title_gfx_ptr_deny():
        return False
    # Mid-ROM data / UI chrome bodies referenced from code or tables.
    if string_in_ui_text_bank(string_off) or string_in_option_band(string_off):
        return True
    if 0x300000 <= string_off < 0x400000 and ptr_off >= 0x6000:
        return True
    if 0x100000 <= ptr_off < 0x200000 and string_off >= 0x140000:
        return True
    return False


def entry_has_class_text_ptr(
    rom: bytes | bytearray, entry: dict, string_off: int
) -> bool:
    """True if extract listed a pointer site of a known text-pointer class."""
    string_off = _file(string_off)
    if entry_has_registry_ptr(entry):
        return True
    for ptr_off in iter_entry_ptr_offs(entry):
        if is_class_text_ptr(rom, ptr_off, string_off):
            return True
    return False


def ptr_in_known_ui_band(ptr_off: int, string_off: int) -> bool:
    if is_local_pool_ptr(ptr_off, string_off):
        return True
    if 0x37B000 <= ptr_off < 0x37C000:
        return True
    if 0x3D0000 <= ptr_off < 0x3EB000:
        return True
    if 0x100000 <= ptr_off < 0x200000 and string_off >= 0x140000:
        return True
    return False


def is_save_power_prompt(text: str, game_id: str = "") -> bool:
    """Save / battery / RTC prompts — rules from ``content_classes.存档与电源``."""
    if not text:
        return False
    return matches_content_class(text, "存档与电源", game_id)


def is_save_power_prompt_at(rom: bytes | bytearray, string_off: int) -> bool:
    """Decode PCS at ``string_off`` and test :func:`is_save_power_prompt`."""
    from .extract import read_pcs
    from .jp_pcs import decode_pcs

    raw = read_pcs(bytes(rom), string_off, 512)
    if not raw:
        return False
    try:
        return is_save_power_prompt(decode_pcs(raw))
    except Exception:
        return False


def ptr_source_ok(
    rom: bytes | bytearray,
    ptr_off: int,
    string_off: int,
    *,
    lz_spans: list[tuple[int, int]] | None = None,
    strict: bool = False,
) -> bool:
    """S1(+S5 core): safe to treat this site as a text pointer.

    ``strict=True`` (script / 未归类 inject): only loadword, registry, or
    local-pool — the loose mid-ROM aligned allow is too broad and white-screens.

    UI chrome bodies (config UI banks ∪ dump high-UI geo) may be referenced
    from tables inside ``GFX_PTR_SOURCE_DENY`` or low-ROM menus; aligned
    sites are allowed for that body class. Save/power prompts share that
    low-ROM table pattern (dialogue-bank duplicates of UI pool strings).
    """
    from .extract import ptr_in_trusted_lz, trusted_lz_spans

    if is_registry_ptr(ptr_off) and (ptr_off & 3) == 0:
        return True
    tlz = TITLE_LZ_BAND()
    if tlz[0] <= ptr_off < tlz[1]:
        return False
    if ptr_off in title_gfx_ptr_deny():
        return False
    if is_local_pool_ptr(ptr_off, string_off):
        return True
    ui_body = string_in_ui_text_bank(string_off) or string_in_option_band(string_off)
    save_body = (not ui_body) and is_save_power_prompt_at(rom, string_off)
    chrome_body = ui_body or save_body
    if in_ranges(ptr_off, GFX_PTR_SOURCE_DENY()) and not chrome_body:
        return False
    spans = lz_spans if lz_spans is not None else trusted_lz_spans(rom)
    # False LZ streams often cover real UI chrome pointer tables.
    if ptr_in_trusted_lz(ptr_off, spans) and not chrome_body:
        return False
    if is_loadword_text_ptr(rom, ptr_off):
        return True
    if strict:
        return False
    if chrome_body and (ptr_off & 3) == 0 and ptr_off >= 0x6000:
        # UI / save-power chrome: trust aligned ptr tables (incl. low ROM).
        return True
    if (
        (ptr_off & 3) == 0
        and 0x100000 <= ptr_off < 0x200000
        and string_off >= 0x140000
    ):
        return True
    return False


def is_struct_like_pcs(s: bytes) -> bool:
    if not s or s[-1] != 0xFF:
        return False
    body = s[:-1]
    if len(body) <= 8:
        if body.count(0x00) >= 2 and body.count(0xFE) >= 1:
            return True
        if body in (
            b"\x04\x00\x01\x00\xfe",
            b"\x00\x00\x00\x00",
            b"\x01\x00\x00\x00",
        ):
            return True
        if body and all(b in (0x00, 0x01, 0x04, 0xFE, 0xFA, 0xFB) for b in body):
            return True
    return False


def string_target_ok(
    so: int,
    *,
    allow: bool,
    lz_spans: list[tuple[int, int]] | None = None,
) -> bool:
    """S2: reject ARM/code, title-LZ, gfx false string targets."""
    del lz_spans
    if allow:
        return True
    if so < SCRIPT_BANK_MIN():
        return False
    tlz = TITLE_LZ_BAND()
    if tlz[0] <= so < tlz[1]:
        return False
    if string_in_ui_text_bank(so) or string_in_option_band(so):
        return True
    if in_ranges(so, GFX_STRING_TARGET_DENY()):
        return False
    return True


def text_target_ok(
    rom: bytearray | bytes,
    address: int,
    entry: dict,
    *,
    lz_spans: list[tuple[int, int]] | None = None,
) -> bool:
    """S2+S3 gate used at inject time for a string body."""
    from .extract import ptr_in_trusted_lz, trusted_lz_spans

    if address < 0 or address >= len(rom):
        return False

    address = _file(address)
    # Pointer class (not module-id lists): false LZ10 often covers real UI PCS.
    class_ptr = entry_has_class_text_ptr(rom, entry, address)
    if address < SCRIPT_BANK_MIN() and not class_ptr:
        return False
    tlz = TITLE_LZ_BAND()
    if tlz[0] <= address < tlz[1]:
        return False
    if not class_ptr:
        if not string_in_ui_text_bank(address) and not string_in_option_band(address):
            if in_ranges(address, GFX_STRING_TARGET_DENY()):
                return False

    spans = lz_spans if lz_spans is not None else trusted_lz_spans(rom)
    if ptr_in_trusted_lz(address, spans):
        if not (
            class_ptr
            or string_in_ui_text_bank(address)
            or string_in_option_band(address)
        ):
            return False

    hex_str = (entry.get("original_hex") or "").replace(" ", "")
    if hex_str:
        try:
            expected = bytes.fromhex(hex_str)
        except ValueError:
            expected = b""
        if expected and bytes(rom[address : address + len(expected)]) != expected:
            return False
        check = expected if expected.endswith(b"\xFF") else expected + b"\xFF"
        if not expected or not looks_like_jp_text(check):
            return False
        if is_struct_like_pcs(check):
            return False
    else:
        end = rom.find(0xFF, address, address + 201)
        if end < 0:
            return False
        expected = bytes(rom[address : end + 1])
        if not looks_like_jp_text(expected):
            return False
        if is_struct_like_pcs(expected):
            return False

    original = entry.get("original") or ""
    if not class_ptr and is_garbage_jp(original):
        return False
    return True


def is_garbage_jp(text: str) -> bool:
    if "がのく" in text or "なくけ" in text or "にくけ" in text:
        return True
    if text.count("そ ") >= 2 and "ポケモン" not in text:
        return True
    if re.search(r"[A-Za-z][ぁ-んァ-ン]{1,3}[A-Za-z]", text):
        return True
    if len(re.findall(r"[ぁ-ん]{1}\s+[ぁ-ん]{1}\s+", text)) >= 3:
        return True
    return False


def looks_like_translatable(text: str, body_len: int) -> bool:
    if body_len < 2 or body_len > 512:
        return False
    if is_garbage_jp(text):
        return False
    cleaned = text.replace("\\l", "").replace("\\p", "")
    cleaned = re.sub(r"\\CC[0-9A-Fa-f]+", "", cleaned)
    cleaned = re.sub(r"\\[0-9A-Fa-f]{2}", "", cleaned)
    cleaned = cleaned.replace("\n", "")
    if "<" in cleaned or "[" in cleaned:
        return False
    if text.count("とく") >= 2:
        return False
    if len(re.findall(r"[Ａ-Ｚａ-ｚ]{3,}", text)) >= 2:
        return False
    kana = sum(1 for ch in text if "\u3040" <= ch <= "\u30ff")
    if body_len <= 16:
        return kana >= 2
    if body_len <= 40:
        return kana >= 3
    return kana >= 4


def should_skip_zh_inject(original: str) -> bool:
    if not original:
        return False
    originals = skip_zh_inject_originals()
    if original in originals:
        return True
    compact = original.replace(" ", "")
    for jp in originals:
        if compact == jp.replace(" ", ""):
            return True
    for prefix in skip_zh_inject_prefixes():
        if original.startswith(prefix) or compact.startswith(prefix.replace(" ", "")):
            return True
    return False


def keep_for_stable_inject(entry: dict) -> bool:
    original = entry.get("original") or ""
    if should_skip_zh_inject(original):
        return False
    tr = (entry.get("translated") or "").strip()
    if not tr or tr == original:
        return False
    return True


def entry_has_registry_ptr(entry: dict) -> bool:
    for ptr_src in entry.get("pointer_addresses") or entry.get("pointer_sources") or []:
        try:
            ptr_addr = int(str(ptr_src).replace("0x", ""), 16)
        except ValueError:
            continue
        if ptr_addr >= BASE():
            ptr_addr -= BASE()
        if is_registry_ptr(ptr_addr):
            return True
    return False


def should_expand_shared_literal(
    original: str = "",
    category: str = "",
    pointer_sources: Iterable | None = None,
) -> bool:
    """Short shared UI literals: extract often lists 1 site; discover the rest.

    Class rule (not address allowlists): compact length ≤ 12, no newlines, and
    few registered pointer_sources. Used so ``やめる`` updates every menu table.
    """
    raw = original or ""
    if "\n" in raw:
        return False
    compact = raw.replace(" ", "").replace("\u3000", "")
    # Keep control/template strings (FD/FC) on listed sites only.
    if "\\" in raw or len(compact) == 0 or len(compact) > 12:
        return False
    n = len(list(pointer_sources or []))
    if n == 0 or n > 4:
        return False
    cat = (category or "").strip()
    # UI / short label modules; empty cat still OK for seed UI rows.
    if cat and cat not in (
        "UI界面",
        "界面",
        "ui",
        "UI",
        "性格名",
        "属性名",
        "特性名",
    ):
        return False
    return True


def discover_pointer_sources(
    rom: bytes | bytearray,
    text_address: int,
) -> list[str]:
    """S5 helper: every LE site whose word is the GBA pointer to ``text_address``.

    Shared UI literals (e.g. ``やめる``) often have dozens of menu-table consumers;
    extract may only register one (table sentinel). Discovery is class-based:
    same body → all current references, then ``filter_pointer_sources``.
    """
    text_off = _file(text_address)
    expected = text_off + BASE()
    pat = struct.pack("<I", expected)
    out: list[str] = []
    start = 0
    while True:
        i = rom.find(pat, start)
        if i < 0:
            break
        out.append(f"0x{i + BASE():08X}")
        start = i + 1
    return out


def expand_pointer_sources(
    rom: bytes | bytearray,
    text_address: int,
    pointer_sources: Iterable | None = None,
    *,
    category: str = "",
    original: str = "",
    expected_pointer: int | None = None,
    lz_spans: list[tuple[int, int]] | None = None,
    min_pointer_source: int = 0x6000,
    text_spans: list[tuple[int, int]] | None = None,
) -> list[int]:
    """Union listed + discovered pointer sites, then apply S5 filter."""
    text_off = _file(text_address)
    if expected_pointer is None:
        expected_pointer = text_off + BASE()
    merged: list[Any] = []
    seen: set[int] = set()
    for ptr_src in list(pointer_sources or []) + discover_pointer_sources(rom, text_off):
        try:
            ptr_addr = _file(int(str(ptr_src).replace("0x", ""), 16))
        except ValueError:
            continue
        if ptr_addr in seen:
            continue
        seen.add(ptr_addr)
        merged.append(ptr_src)
    return filter_pointer_sources(
        rom,
        merged,
        text_off,
        category=category,
        original=original,
        expected_pointer=expected_pointer,
        lz_spans=lz_spans,
        min_pointer_source=min_pointer_source,
        text_spans=text_spans,
    )


def filter_pointer_sources(
    rom: bytes | bytearray,
    pointer_sources: Iterable,
    text_address: int,
    *,
    category: str = "",
    original: str = "",
    expected_pointer: int,
    lz_spans: list[tuple[int, int]] | None = None,
    min_pointer_source: int = 0x6000,
    text_spans: list[tuple[int, int]] | None = None,
) -> list[int]:
    """S5: keep only pointer sites that currently reference ``text_address``.

    Drops sites that fall inside corpus text bodies (``text_spans``): those are
    almost always PCS bytes that coincidentally equal a bus address, not real
    pointer slots (e.g. move-desc stride colliding with story relocates).
    """
    from .extract import ptr_in_trusted_lz, trusted_lz_spans
    from .modules import entry_group_in, entry_is_script_like

    # Synthetic entry: category may already be Chinese module id after stamp
    _tag_entry = {"category": category, "module": category}
    text_address = _file(text_address)

    spans = lz_spans if lz_spans is not None else trusted_lz_spans(rom)
    compact = (original or "").replace(" ", "").replace("\n", "")
    valid: list[int] = []
    for ptr_src in pointer_sources:
        try:
            ptr_addr = int(str(ptr_src).replace("0x", ""), 16)
        except ValueError:
            continue
        ptr_addr = _file(ptr_addr)
        if ptr_addr + 4 > len(rom):
            continue
        if ptr_site_in_text_body(ptr_addr, text_spans):
            continue
        if ptr_addr in title_gfx_ptr_deny():
            continue
        tlz = TITLE_LZ_BAND()
        if tlz[0] <= ptr_addr < tlz[1]:
            continue
        # 弱化：不再按 GFX_PTR_SOURCE_DENY / min_pointer_source / 对齐 / 严格脚本
        # 过滤指针源（回归 relocate 为主，模拟器白屏可查 translate.build.json 地址）。
        # 保留：标题图形指针、标题 LZ、指针确实指向该文本、pointer_target 拒绝带。
        class_ptr = is_class_text_ptr(rom, ptr_addr, text_address)
        local_pool = is_local_pool_ptr(ptr_addr, text_address)
        script_like = entry_is_script_like(_tag_entry)
        if ptr_addr in BIRCH_PTR_ALLOW:
            pass
        elif ptr_in_trusted_lz(ptr_addr, spans) and not class_ptr and not local_pool:
            if not ptr_source_ok(
                rom, ptr_addr, text_address, lz_spans=spans, strict=False
            ):
                continue
        elif script_like:
            if not ptr_source_ok(
                rom, ptr_addr, text_address, lz_spans=spans, strict=False
            ):
                continue
        # Brand literals: site/string class, not module id.
        if compact in brand_compact_skip() and ptr_addr >= 0x100000:
            continue
        cur = struct.unpack_from("<I", rom, ptr_addr)[0]
        if cur != expected_pointer:
            continue
        deny_bands = _policy().get("reject", {}).get("pointer_target", {}).get("addr_bands")
        if deny_bands and _parse_addr(deny_bands[0][0]) <= cur <= _parse_addr(deny_bands[0][1]):
            continue
        valid.append(ptr_addr)
    return valid


def should_keep_relocated_local_pool(
    baseline: bytes,
    ptr_off: int,
    old_tgt: int,
) -> bool:
    """S6: keep intentional UI/option local-pool relocates."""
    from .extract import read_pcs
    from .tables import (
        item_data_cfg,
        nature_names_cfg,
    )

    BASE_VAL = BASE()
    nature_cfg = nature_names_cfg()
    item_cfg = item_data_cfg()
    if "table" not in nature_cfg or "count" not in nature_cfg:
        raise ValueError("nature_names_cfg incomplete for local-pool keep check")
    if not all(
        k in item_cfg
        for k in ("offset", "count", "entry_size", "desc_ptr_offset")
    ):
        raise ValueError("item_data_cfg incomplete for local-pool keep check")

    nature_table = int(nature_cfg["table"]) + BASE_VAL
    nature_count = int(nature_cfg["count"])

    item_offset = int(item_cfg["offset"]) + BASE_VAL
    item_count = int(item_cfg["count"])
    item_entry_size = int(item_cfg["entry_size"])
    item_desc_ptr_offset = int(item_cfg["desc_ptr_offset"])

    if nature_table <= ptr_off < nature_table + nature_count * 4:
        return True
    if item_offset <= ptr_off < item_offset + item_count * item_entry_size:
        if (ptr_off - item_offset) % item_entry_size == item_desc_ptr_offset:
            return True
    if 0x3E9B00 <= old_tgt < 0x3EB000:
        return True
    if 0x3DC000 <= old_tgt < 0x3DD800:
        return True

    if not (old_tgt < ptr_off < old_tgt + 0x80):
        return False
    if not (
        string_in_ui_text_bank(old_tgt) or string_in_option_band(old_tgt)
    ):
        return False
    s = read_pcs(baseline, old_tgt, 64)
    if not s or not looks_like_jp_text(s) or is_struct_like_pcs(s):
        return False
    from .jp_pcs import decode_pcs

    text = decode_pcs(s)
    return looks_like_translatable(text, len(s) - 1)


def ptr_site_in_danger(
    ptr_off: int,
    *,
    lz_spans: list[tuple[int, int]],
) -> bool:
    from .extract import ptr_in_trusted_lz

    tlz = TITLE_LZ_BAND()
    return (
        tlz[0] <= ptr_off < tlz[1]
        or in_ranges(ptr_off, GFX_PTR_SOURCE_DENY())
        or ptr_in_trusted_lz(ptr_off, lz_spans)
    )
