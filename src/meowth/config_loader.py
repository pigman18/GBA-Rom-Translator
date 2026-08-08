"""Load per-game config packs under ``configs/<game_id>/``.

::

    configs/<game_id>/
      game.json
      extract/config.json
      translate/
        config.json            # protect / skip / allows / rejects
        texts.json             # entries + modules（含 write/read/word_count）
        texts_translated.json  # 翻译缓存（status 200/404 数组）
        lexicon/
      font/config.json + charmap.txt
      patch/                   # ARMIPS
      inject/config.json       # pointer deny / brand_compact_skip

模块定义与语料均在 ``translate/texts.json``；inject 的 ``read``/``write``/
``word_count`` 写在 texts.json 的 modules 上（一行最多汉字数，缺省 14）。
旧字段 ``line_width`` 读取时会映射为 ``word_count``，配置侧请改用 ``word_count``。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CONFIG_DIR_CWD = Path("configs")
_CONFIG_DIR_TOOL = Path(__file__).resolve().parents[2] / "configs"

_cache: dict[str, dict[str, Any]] = {}
_profile_cache: dict[str, dict[str, Any]] = {}
_modules_cache: dict[str, dict[str, Any]] = {}
_modules_inject_cache: dict[str, dict[str, Any]] = {}
_styles_cache: dict[str, dict[str, Any]] = {}
_style_alloc_cache: dict[str, dict[str, int]] = {}
_policy_cache: dict[str, dict[str, Any]] = {}
_codec_cache: dict[str, dict[str, Any]] = {}
_config_dirs: dict[str, Path] = {}
_active_game_id: str | None = None

STAGE_EXTRACT = "extract"
STAGE_TABLES = "tables"  # legacy folder name only
STAGE_TRANSLATE = "translate"
STAGE_FONT = "translate"  # font config lives under translate/font.config.json
FONT_CONFIG_FILE = "font.config.json"
STAGE_PATCH = "hook"
STAGE_HOOK = "hook"
STAGE_INJECT = "translate"  # inject policy merged into translate/config.json
STAGE_MODULES = "modules"

# Max 汉字 per line (texts.json module ``word_count``).
DEFAULT_WORD_COUNT = 14

# F9 channel protocol (AXVJ Chinese):
#   F9 00 …     — 旁载单字 (reserved)
#   F9 80 hi/lo — 默认短语（无 style；表内为 F9 00+PCS 流）
#   texts.styles 按列表顺序交错分配：01, 81, 02, 82, …（无需写 channel）
#   bare FA..FF — PCS controls / EOS (NOT F9 channels)
# Deprecated: write.type=op / styles.channel（改用 module.style → 自动交错）
F9_SIDE_GLYPH = 0x00
F9_PHRASE_DEFAULT = 0x80
F9_OP_MIN = 0x01
F9_OP_MAX = 0x7E
F9_STYLE_00_MIN = 0x01
F9_STYLE_00_MAX = 0x7F
F9_STYLE_80_MIN = 0x81
F9_STYLE_80_MAX = 0xF9  # before PCS FA–FF
F9_EOS = 0xFF
STYLE_CHANNEL_00 = 0x00  # legacy nested key only
STYLE_CHANNEL_80 = 0x80


def parse_int_addr(val: Any, default: int | None = None) -> int:
    """Parse config address/offset: int or ``0x…`` / bare-hex string.

    Accepts legacy decimal ints so older configs keep working.
    """
    if val is None or val == "":
        if default is not None:
            return int(default)
        raise ValueError("address value is empty")
    if isinstance(val, bool):
        raise ValueError(f"address must not be bool: {val!r}")
    if isinstance(val, int):
        return int(val)
    s = str(val).strip().lower().replace("_", "")
    try:
        if s.startswith("0x"):
            return int(s, 16)
        # bare hex (e.g. "080032F8") or decimal string
        if any(c in "abcdef" for c in s):
            return int(s, 16)
        return int(s, 0)
    except ValueError as exc:
        if default is not None:
            return int(default)
        raise ValueError(f"invalid address: {val!r}") from exc


WRITE_TYPE_OP = "op"
WRITE_TYPE_APPEND = "append"  # alias: type=append / append="0x02"


def _parse_write_op_value(raw: Any) -> int | None:
    """Parse op payload; None if missing. Raises ValueError if out of 0x01..0x7E."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        val = raw & 0xFF
    else:
        s = str(raw).strip().lower()
        try:
            val = int(s, 0) & 0xFF
        except ValueError:
            raise ValueError(f"write.op not an integer: {raw!r}") from None
    if not (F9_OP_MIN <= val <= F9_OP_MAX):
        raise ValueError(
            f"write.op must be 0x{F9_OP_MIN:02X}..0x{F9_OP_MAX:02X} "
            f"(got 0x{val:02X}; 0x00=side, 0x80=default phrase, "
            f"0xFA..0xFF=PCS — not F9 channels)"
        )
    return val


def module_write_op(game_id: str, module_id: str | None) -> int | None:
    """Deprecated: ``write.type=op``. Prefer ``module.style`` → ``alloc_style_channels``.

    Return F9 phrase-channel byte, or None if module has no ``write.type=op``.
    """
    if not module_id:
        return None
    inj = load_modules_inject(game_id).get(module_id) or {}
    write = _inject_write_block(inj)
    raw_typ = write.get("type")
    if raw_typ is None or raw_typ == "":
        return None
    typ = str(raw_typ).strip()
    if typ not in (WRITE_TYPE_OP, WRITE_TYPE_APPEND):
        return None
    return _parse_write_op_value(write.get(typ))


def _parse_style_channel(raw: Any) -> int:
    """Style family: ``00`` or ``80`` (default ``80``)."""
    if raw is None or raw == "":
        return STYLE_CHANNEL_80
    if isinstance(raw, bool):
        return STYLE_CHANNEL_80
    if isinstance(raw, int):
        val = int(raw) & 0xFF
    else:
        s = str(raw).strip().lower().replace("0x", "")
        try:
            val = int(s, 16) & 0xFF
        except ValueError:
            try:
                val = int(s, 0) & 0xFF
            except ValueError:
                return STYLE_CHANNEL_80
    if val == STYLE_CHANNEL_00:
        return STYLE_CHANNEL_00
    return STYLE_CHANNEL_80


def _style_meta_clean(meta: dict[str, Any]) -> dict[str, Any]:
    """Drop deprecated ``channel``; keep left / other fields."""
    return {k: v for k, v in meta.items() if k != "channel"}


def _normalize_styles_obj(raw: Any) -> dict[str, dict[str, Any]]:
    """texts.json / yaml styles → ``{style_id: meta}`` (meta has no ``id``).

    Accepts:
    - list ``[{id, left, …}, …]`` (preferred, same shape as modules)
    - flat dict ``{id: {left, …}}``
    - legacy nested ``{"00": {name: …}, "80": {name: …}}`` (order: 00 then 80)
    ``channel`` is ignored if present (alloc is interleaved, not per-family).
    """
    out: dict[str, dict[str, Any]] = {}
    if raw is None:
        return out
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            sid = str(item.get("id") or "").strip()
            if not sid:
                continue
            meta = _style_meta_clean({k: v for k, v in item.items() if k != "id"})
            out[sid] = meta
        return out
    if not isinstance(raw, dict):
        return out
    # Nested channel groups? Flatten in 00→80 key order (channel ignored for alloc).
    nested_keys = {str(k).strip().lower().replace("0x", "") for k in raw}
    if nested_keys and nested_keys <= {"00", "80", "0", "128"}:
        for fam in ("00", "80", "0", "128"):
            group = None
            for k, v in raw.items():
                if str(k).strip().lower().replace("0x", "") == fam:
                    group = v
                    break
            if not isinstance(group, dict):
                continue
            for sid, meta in group.items():
                name = str(sid).strip()
                if not name or not isinstance(meta, dict):
                    continue
                if name in out:
                    raise ValueError(f"duplicate style id {name!r} across channel groups")
                out[name] = _style_meta_clean(dict(meta))
        return out
    for sid, meta in raw.items():
        name = str(sid).strip()
        if not name or not isinstance(meta, dict):
            continue
        out[name] = _style_meta_clean(dict(meta))
    return out


def load_styles(game_id: str = "") -> dict[str, dict[str, Any]]:
    """Load ``texts.json`` → ``styles`` as ``{style_id: meta}``."""
    gid = game_id or _active_game_id or ""
    if not gid:
        return {}
    if gid in _styles_cache:
        return _styles_cache[gid]
    try:
        raw = load_texts_doc(gid)
    except FileNotFoundError:
        raw = {}
    styles = _normalize_styles_obj(raw.get("styles") if isinstance(raw, dict) else None)
    _styles_cache[gid] = styles
    return styles


def alloc_style_channels(game_id: str = "") -> dict[str, int]:
    """Auto-assign F9 second byte per style id (stable insertion order).

    Interleave low/high: 1st→``0x01``, 2nd→``0x81``, 3rd→``0x02``, 4th→``0x82``, …
    No ``channel`` field required.
    """
    gid = game_id or _active_game_id or ""
    if not gid:
        return {}
    if gid in _style_alloc_cache:
        return _style_alloc_cache[gid]
    styles = load_styles(gid)
    next_00 = F9_STYLE_00_MIN
    next_80 = F9_STYLE_80_MIN
    alloc: dict[str, int] = {}
    for i, sid in enumerate(styles):
        if (i & 1) == 0:
            if next_00 > F9_STYLE_00_MAX:
                raise ValueError(f"style 00-family exhausted (style {sid!r})")
            # Never emit reserved phrase/side bytes
            if next_00 == F9_SIDE_GLYPH or next_00 == F9_PHRASE_DEFAULT:
                next_00 += 1
            alloc[sid] = next_00
            next_00 += 1
        else:
            if next_80 > F9_STYLE_80_MAX:
                raise ValueError(f"style 80-family exhausted (style {sid!r})")
            alloc[sid] = next_80
            next_80 += 1
    _style_alloc_cache[gid] = alloc
    return alloc


def module_style_id(game_id: str, module_id: str | None) -> str | None:
    """Module ``style`` name, or None."""
    if not module_id:
        return None
    try:
        meta = load_modules(game_id).get(module_id) or {}
    except FileNotFoundError:
        return None
    sid = str(meta.get("style") or "").strip()
    return sid or None


def style_left_px(game_id: str, style_id: str | None) -> int:
    """``left`` px on a named style; missing → 0."""
    if not style_id:
        return 0
    meta = load_styles(game_id).get(style_id) or {}
    raw = meta.get("left")
    if raw is None:
        return 0
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


def module_phrase_channel(game_id: str, module_id: str | None) -> int:
    """F9 second byte for phrase refs of this module.

    Prefer allocated style channel; else deprecated ``write.type=op``;
    else default ``0x80``.
    """
    sid = module_style_id(game_id, module_id)
    if sid:
        alloc = alloc_style_channels(game_id)
        if sid not in alloc:
            raise ValueError(
                f"module {module_id!r} style {sid!r} not in texts.styles"
            )
        return int(alloc[sid])
    op = module_write_op(game_id, module_id)
    if op is not None:
        return int(op)
    return F9_PHRASE_DEFAULT


def apply_module_phrase_channel(
    encoded: bytes, game_id: str, module_id: str | None
) -> bytes:
    """Rewrite phrase refs ``F9 80 …`` → ``F9 <module.style alloc> …``.

    Hook: ``op == 0`` → 00 glyph; else → PhraseTable (``0x80`` clears sticky;
    other ops sticky + ``StyleLeft[op]`` one-shot X nudge).
    """
    if (
        not encoded
        or len(encoded) < 2
        or encoded[0] != 0xF9
        or encoded[1] != F9_PHRASE_DEFAULT
    ):
        return encoded
    ch = module_phrase_channel(game_id, module_id) & 0xFF
    if ch == F9_PHRASE_DEFAULT:
        return encoded
    return bytes([0xF9, ch]) + encoded[2:]

# Fields that may live on a module entry in ``translate/texts.json`` modules
# and feed inject-style readers.
_INJECT_MODULE_KEYS = (
    "read",
    "write",
    "layout",
    "word_count",
    "wrap_pages",
    "max_lines",
    "line_width",  # read-only migrate → word_count in load_modules_inject
    "style",  # → texts.styles; phrase F9 second byte via alloc_style_channels
    "left",  # deprecated: prefer styles[].left via module.style
    "chs_stride",
    "patch_type",
    "widen_fn",
)


def texts_json_path(game_id: str) -> Path:
    """``configs/<game_id>/translate/texts.json``（语料 + modules 定义）。"""
    return stage_dir(game_id, STAGE_TRANSLATE) / "texts.json"


def texts_translated_path(game_id: str) -> Path:
    """``configs/<game_id>/translate/texts_translated.json``（翻译缓存）。"""
    return stage_dir(game_id, STAGE_TRANSLATE) / "texts_translated.json"


def load_texts_doc(game_id: str) -> dict[str, Any]:
    """Load ``translate/texts.json`` object (entries + modules)."""
    path = texts_json_path(game_id)
    if not path.is_file():
        raise FileNotFoundError(
            f"No texts.json for game {game_id!r} (expected {path})"
        )
    data = _read_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid texts.json: {path}")
    return data


def _v2_extraction(game_id: str) -> dict[str, Any]:
    """Top-level scan/policy/modules_defaults/enrich from texts.json meta."""
    try:
        raw = load_texts_doc(game_id)
    except FileNotFoundError:
        return {}
    meta = raw.get("modules_meta") or raw.get("_meta") or {}
    if not isinstance(meta, dict) or meta.get("schema") != "v2":
        return {}
    out: dict[str, Any] = {}
    scan = raw.get("scan")
    if isinstance(scan, dict):
        for k in ("script_bank_min", "script_text_ptr_opcodes", "encoding", "trusted_lz_bands"):
            if k in scan:
                out[k] = scan[k]
    pol = raw.get("policy")
    if isinstance(pol, dict):
        for k in ("reject", "allow", "content_classes"):
            if k in pol:
                out[k] = pol[k]
    if "modules_defaults" in raw:
        out["modules_defaults"] = raw["modules_defaults"]
    if "enrich" in raw:
        out["enrich"] = raw["enrich"]
    return out


def set_active_game_id(game_id: str | None) -> None:
    global _active_game_id
    _active_game_id = (game_id or "").strip() or None


def get_active_game_id() -> str | None:
    return _active_game_id


def _resolve_config_dir(game_id: str) -> Path:
    for base in (_CONFIG_DIR_CWD, _CONFIG_DIR_TOOL):
        p = base / game_id
        if p.is_dir() and (p / "game.json").is_file():
            src = "当前目录" if base is _CONFIG_DIR_CWD else "内置目录"
            print(f"[配置] 读取游戏配置: {p / 'game.json'} ({src})")
            return p
    raise FileNotFoundError(
        f"No config folder for game {game_id!r}. "
        f"Looked in {_CONFIG_DIR_CWD.resolve()}/{game_id}/game.json "
        f"and {_CONFIG_DIR_TOOL}/{game_id}/game.json"
    )


def _ensure_cache() -> None:
    if _cache:
        return
    seen: set[str] = set()
    for base in (_CONFIG_DIR_CWD, _CONFIG_DIR_TOOL):
        if not base.is_dir():
            continue
        resolved = base.resolve()
        print(f"[配置] 扫描配置目录: {resolved}")
        for d in sorted(base.iterdir()):
            if not d.is_dir():
                continue
            game_json = d / "game.json"
            if not game_json.is_file():
                continue
            try:
                data = json.loads(game_json.read_text(encoding="utf-8"))
                gid: str = data.get("game_id", "")
                if gid and gid not in seen:
                    seen.add(gid)
                    _cache[gid] = data
                    _config_dirs[gid] = d.resolve()
                    print(f"[配置]   发现游戏: {gid} -> {d.resolve() / 'game.json'}")
            except (json.JSONDecodeError, OSError):
                continue


def list_available_games() -> list[str]:
    _ensure_cache()
    return sorted(_cache.keys())


def game_config_dir(game_id: str) -> Path:
    _ensure_cache()
    cfg_dir = _config_dirs.get(game_id)
    if cfg_dir is None:
        cfg_dir = _resolve_config_dir(game_id)
        _config_dirs[game_id] = cfg_dir
    return cfg_dir


def stage_dir(game_id: str, stage: str) -> Path:
    return game_config_dir(game_id) / stage


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    print(f"[配置] 读取: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid JSON object: {path}")
    return data


def _first_existing(game_id: str, *rel_paths: str) -> Path | None:
    root = game_config_dir(game_id)
    for rel in rel_paths:
        p = root / rel
        if p.is_file():
            return p
    return None


def load_stage_config(game_id: str, stage: str, *legacy_names: str) -> dict[str, Any]:
    names = ("config.json",) + legacy_names
    for name in names:
        data = _read_json(stage_dir(game_id, stage) / name)
        if data:
            return data
    return {}


def load_game_identity(game_id: str) -> dict[str, Any]:
    _ensure_cache()
    if game_id in _cache:
        return _cache[game_id]
    cfg_dir = _resolve_config_dir(game_id)
    data = _read_json(cfg_dir / "game.json")
    _cache[game_id] = data
    _config_dirs[game_id] = cfg_dir
    return data


def load_modules_inject(game_id: str = "") -> dict[str, dict[str, Any]]:
    """Inject config keyed by module id from ``texts.json`` modules only.

    Reads ``read`` / ``write`` / ``word_count`` / … from each module entry
    in ``translate/texts.json``. Legacy ``modules.inject.json`` is ignored.
    """
    gid = game_id or _active_game_id
    if not gid:
        return {}
    if gid in _modules_inject_cache:
        return _modules_inject_cache[gid]

    out: dict[str, dict[str, Any]] = {}
    try:
        raw_texts = load_texts_doc(gid)
    except FileNotFoundError:
        raw_texts = {}
    mods_v2 = raw_texts.get("modules") if isinstance(raw_texts, dict) else None
    if isinstance(mods_v2, dict):
        for mid, meta in mods_v2.items():
            if not isinstance(meta, dict):
                continue
            inj = {k: meta[k] for k in _INJECT_MODULE_KEYS if k in meta}
            # Migrate discarded line_width → word_count
            if "word_count" not in inj and "line_width" in inj:
                inj["word_count"] = inj["line_width"]
            inj.pop("line_width", None)
            if inj:
                out[mid] = inj

    _modules_inject_cache[gid] = out
    return out


def _parse_file_offset(val: Any) -> int | None:
    """Parse file offset from int or ``0x…`` string."""
    if val is None or val == "":
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        s = val.strip().lower().replace("0x", "")
        try:
            return int(s, 16)
        except ValueError:
            return None
    return None


def _derive_table_count(offset: int, end: int, unit: int) -> int:
    """Row count from inclusive ``[offset, end]`` span and row/unit size."""
    if unit <= 0:
        raise ValueError(f"invalid table unit {unit}")
    if end < offset:
        raise ValueError(f"table end 0x{end:X} < offset 0x{offset:X}")
    size = end - offset + 1
    if size % unit != 0:
        # ceil — dump end slightly short still yields usable count
        return (size + unit - 1) // unit
    return size // unit


def _inject_read_block(cfg: dict[str, Any]) -> dict[str, Any] | None:
    """Prefer ``read``; fall back to legacy ``layout``."""
    read = cfg.get("read")
    if isinstance(read, dict):
        return read
    layout = cfg.get("layout")
    if isinstance(layout, dict):
        return layout
    return None


def _inject_write_block(cfg: dict[str, Any]) -> dict[str, Any]:
    write = cfg.get("write")
    return write if isinstance(write, dict) else {}


def tables_from_modules_inject(game_id: str = "") -> dict[str, Any]:
    """Assemble legacy ``tables`` dict for extract / table_patch.

    Each table carries ``module`` (Chinese module id). No ``category``.
    ``read.type`` (or legacy ``layout.type``): fixed_table | struct_table | ptr_table
    (compat: kind / item_struct).

    Geo ``offset`` / ``end`` come from dump ``modules.json``; ``count`` is
    derived as ``(end-offset+1)/unit``. ``write.stride`` → legacy ``chs_stride``.
    """
    inject = load_modules_inject(game_id)
    mods = load_modules(game_id) if game_id or _active_game_id else {}
    tables: dict[str, Any] = {}
    for mid, cfg in inject.items():
        layout = _inject_read_block(cfg)
        if not isinstance(layout, dict):
            continue
        write = _inject_write_block(cfg)
        key = mid
        entry: dict[str, Any] = {"module": mid}
        mod_meta = mods.get(mid) or {}
        typ = (
            mod_meta.get("type")
            or layout.get("type")
            or layout.get("kind")
            or "fixed_table"
        )
        if typ == "item_struct":
            typ = "struct_table"
        # v3: scan/needle/prefix/pointer/hidden modules carry no name-table
        # extractor — they scan their own bands/needles. Legacy ``addr_bands``
        # also scanned bands. Only stride/ptr_stride/struct assemble tables here.
        if typ in (
            "addr_bands",
            "scan",
            "needle",
            "prefix",
            "pointer",
            "desc_table",
        ):
            continue
        if typ == "stride":
            typ = "fixed_table"
        elif typ in ("ptr_stride", "stride_ptr"):
            typ = "ptr_table"
        elif typ == "struct":
            typ = "struct_table"

        offset = _parse_file_offset(
            mod_meta.get("start")
            if mod_meta.get("start") is not None
            else mod_meta.get("offset")
        )
        end = _parse_file_offset(mod_meta.get("end"))
        # Legacy: offset still in inject read/layout
        if offset is None:
            offset = _parse_file_offset(layout.get("offset") or layout.get("table"))
        legacy_count = layout.get("count")

        if typ == "ptr_table":
            if offset is None:
                raise ValueError(f"module {mid}: missing start/offset")
            entry["table"] = offset
            unit = 4
            if end is not None:
                entry["count"] = _derive_table_count(offset, end, unit)
            elif legacy_count is not None:
                entry["count"] = int(legacy_count)
            else:
                raise ValueError(f"module {mid}: need end or layout.count for ptr_table")
        elif typ == "struct_table":
            # row size: entry_size only（不用 read.stride，避免与 type=stride 混淆）
            unit = int(layout.get("entry_size") or 0)
            if unit:
                entry["entry_size"] = unit
            # max name window for legacy readers (optional)
            name_win = (
                layout.get("name_max")
                or layout.get("name_stride")
                or layout.get("desc_ptr_offset")
                or unit
            )
            if name_win:
                entry["name_stride"] = int(name_win)
            if "desc_ptr_offset" in layout:
                entry["desc_ptr_offset"] = layout["desc_ptr_offset"]
            if "eos" in layout:
                entry["eos"] = layout["eos"]
            elif "suffix" in layout:
                entry["eos"] = layout["suffix"]
            if offset is None:
                raise ValueError(f"module {mid}: missing start/offset")
            entry["offset"] = offset
            if end is not None and unit:
                entry["count"] = _derive_table_count(offset, end, unit)
            elif legacy_count is not None:
                entry["count"] = int(legacy_count)
            else:
                raise ValueError(
                    f"module {mid}: need end+entry_size or layout.count"
                )
        else:  # fixed_table
            if "stride" in layout:
                entry["stride"] = layout["stride"]
            if offset is None:
                raise ValueError(f"module {mid}: missing start/offset")
            entry["offset"] = offset
            unit = int(layout.get("stride") or 0)
            if end is not None and unit:
                entry["count"] = _derive_table_count(offset, end, unit)
            elif legacy_count is not None:
                entry["count"] = int(legacy_count)
            else:
                raise ValueError(f"module {mid}: need end+stride or layout.count")

        # write.stride (preferred) or legacy top-level chs_stride
        chs = write.get("stride", cfg.get("chs_stride"))
        if chs is not None:
            entry["chs_stride"] = chs
        patch = write.get("patch", cfg.get("patch"))
        if patch:
            entry["patch_type"] = patch
        widen = write.get("widen", cfg.get("widen"))
        if widen:
            entry["widen_fn"] = widen
        if cfg.get("patch_type"):
            entry["patch_type"] = cfg["patch_type"]
        if cfg.get("widen_fn"):
            entry["widen_fn"] = cfg["widen_fn"]
        if write.get("patch_type"):
            entry["patch_type"] = write["patch_type"]
        if write.get("widen_fn"):
            entry["widen_fn"] = write["widen_fn"]
        tables[key] = entry
    return tables


def module_write_type_code(game_id: str, module_id: str | None) -> int | None:
    """Phrase channel if non-default, else None (keeps F9 80).

    Prefer style alloc; legacy ``write.type=op`` still honored.
    """
    ch = module_phrase_channel(game_id, module_id)
    if ch == F9_PHRASE_DEFAULT:
        return None
    return ch


def module_word_count(game_id: str, module_id: str | None) -> int:
    """Per-module wrap Hanzi count from texts.json; default 14."""
    if not module_id:
        return DEFAULT_WORD_COUNT
    inj = load_modules_inject(game_id).get(module_id) or {}
    raw = inj.get("word_count")
    if raw is None:
        return DEFAULT_WORD_COUNT
    try:
        return int(raw)
    except (TypeError, ValueError):
        return DEFAULT_WORD_COUNT


def module_word_counts(game_id: str = "") -> dict[str, int]:
    """Map module id → word_count for modules that override the default."""
    gid = game_id or _active_game_id or ""
    out: dict[str, int] = {}
    for mid, cfg in load_modules_inject(gid).items():
        if "word_count" not in cfg:
            continue
        try:
            out[mid] = int(cfg["word_count"])
        except (TypeError, ValueError):
            pass
    return out


def module_left_px(game_id: str, module_id: str | None) -> int:
    """Horizontal print nudge in px (dex species name etc.).

    Prefer ``styles[<module.style>].left``; fall back to deprecated module ``left``.
    Missing / invalid → 0.
    """
    if not module_id:
        return 0
    sid = module_style_id(game_id, module_id)
    if sid:
        return style_left_px(game_id, sid)
    inj = load_modules_inject(game_id).get(module_id) or {}
    raw = inj.get("left")
    if raw is None:
        try:
            meta = load_modules(game_id).get(module_id) or {}
            raw = meta.get("left")
        except FileNotFoundError:
            raw = None
    if raw is None:
        return 0
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


def collect_module_left_px(game_id: str) -> dict[str, int]:
    """All modules with non-zero ``left`` (via style or legacy) → ``{module_id: px}``."""
    out: dict[str, int] = {}
    try:
        mods = load_modules(game_id)
    except FileNotFoundError:
        return out
    for mid in mods:
        px = module_left_px(game_id, mid)
        if px:
            out[mid] = px
    return out


def collect_style_left_by_f9(game_id: str) -> dict[int, int]:
    """Allocated F9 second byte → style ``left`` px (nonzero only)."""
    out: dict[int, int] = {}
    styles = load_styles(game_id)
    alloc = alloc_style_channels(game_id)
    for sid, code in alloc.items():
        px = style_left_px(game_id, sid)
        if px:
            out[int(code)] = px
    return out


def module_wrap_kwargs(game_id: str, module_id: str | None) -> dict[str, Any]:
    """Kwargs for :func:`meowth.text_wrap.wrap_text` from module meta.

    ``wrap_pages`` default True (dialogue). Shop/item desc sets false + max_lines.
    """
    kwargs: dict[str, Any] = {
        "word_count": module_word_count(game_id, module_id),
        "wrap_pages": True,
    }
    if not module_id:
        return kwargs
    inj = load_modules_inject(game_id).get(module_id) or {}
    if "wrap_pages" in inj:
        kwargs["wrap_pages"] = bool(inj["wrap_pages"])
    if "max_lines" in inj:
        try:
            kwargs["max_lines"] = int(inj["max_lines"])
        except (TypeError, ValueError):
            pass
    elif not kwargs["wrap_pages"]:
        kwargs["max_lines"] = 2
    return kwargs


def load_game_config(game_id: str) -> dict[str, Any]:
    """Merged profile for legacy callers (``.get("tables")``, ``font_patch``, …)."""
    if game_id in _profile_cache:
        return _profile_cache[game_id]

    identity = dict(load_game_identity(game_id))
    profile: dict[str, Any] = {
        "game_id": identity.get("game_id", game_id),
        "label": identity.get("label", game_id),
    }

    geo = load_stage_config(game_id, STAGE_EXTRACT, "geo.json")
    if not geo and "extraction" in identity:
        geo = dict(identity.get("extraction") or {})
    if geo:
        profile["extraction"] = geo
    # v2 modules.json carries scan/policy/modules_defaults/enrich on top level;
    # when present they override/supply the extraction profile keys.
    v2 = _v2_extraction(game_id)
    if v2:
        merged = dict(geo or {})
        merged.update(v2)
        profile["extraction"] = merged

    tables = tables_from_modules_inject(game_id)
    if not tables:
        tables = load_stage_config(game_id, STAGE_TABLES, "tables.json")
    if not tables and "tables" in identity:
        tables = dict(identity.get("tables") or {})
    if tables:
        profile["tables"] = tables

    # Wrap default for legacy callers (prefer module word_count at use sites)
    profile["word_count"] = DEFAULT_WORD_COUNT

    font_cfg = load_font_config(game_id)
    patch_cfg = load_stage_config(game_id, STAGE_PATCH)
    legacy_fp = dict(identity.get("font_patch") or {})
    fp: dict[str, Any] = {}
    if legacy_fp:
        fp.update(legacy_fp)
    if patch_cfg:
        fp.update(patch_cfg)
    if font_cfg.get("font_slots"):
        fp["font_slots"] = font_cfg["font_slots"]
    if "shadow" in font_cfg:
        fp["shadow"] = font_cfg["shadow"]
    if fp:
        profile["font_patch"] = fp

    if "charmap" in identity:
        profile["charmap"] = identity["charmap"]
    if "features" in identity:
        profile["features"] = identity["features"]

    _profile_cache[game_id] = profile
    return profile


def load_modules(game_id: str) -> dict[str, dict[str, Any]]:
    """Load module defs from ``translate/texts.json`` → ``modules`` object."""
    if game_id in _modules_cache:
        return _modules_cache[game_id]

    path = texts_json_path(game_id)
    if not path.is_file():
        raise FileNotFoundError(
            f"No modules for game {game_id!r} "
            f"(expected {path} with modules object)"
        )
    print(f"[配置] 读取模块: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    mods = data.get("modules") if isinstance(data, dict) else None
    if not isinstance(mods, dict):
        raise ValueError(
            f"{path}: modules must be an object {{id: meta}}, "
            f"got {type(mods).__name__}"
        )

    # Keep word_count on modules; drop discarded line_width if any
    cleaned = {}
    for mid, meta in mods.items():
        if not isinstance(meta, dict):
            continue
        m = dict(meta)
        if "word_count" not in m and "line_width" in m:
            m["word_count"] = m["line_width"]
        m.pop("line_width", None)
        cleaned[mid] = m
    _modules_cache[game_id] = cleaned
    print(f"[配置]   模块数: {len(cleaned)}")
    return cleaned


def get_game_patch_dir(game_id: str) -> Path:
    root = game_config_dir(game_id)
    patch = root / STAGE_PATCH
    if (patch / "main.asm").is_file() or (patch / "config.json").is_file():
        return patch
    return root


def get_charmap_path(game_id: str) -> Path:
    root = game_config_dir(game_id)
    staged = root / STAGE_FONT / "charmap.txt"
    if staged.is_file():
        return staged
    return root / "charmap.txt"


def load_font_config(game_id: str = "") -> dict[str, Any]:
    gid = game_id or _active_game_id
    if not gid:
        return {}
    return _read_json(stage_dir(gid, STAGE_TRANSLATE) / FONT_CONFIG_FILE)


def load_policy(game_id: str = "") -> dict[str, Any]:
    """Merged write/translate gates from stage packs (+ legacy ``policy.json``)."""
    gid = game_id or _active_game_id
    if not gid:
        return {}
    if gid in _policy_cache:
        return _policy_cache[gid]

    merged: dict[str, Any] = {}
    legacy = _read_json(game_config_dir(gid) / "policy.json")
    if legacy:
        merged.update(legacy)

    inject = load_stage_config(gid, STAGE_INJECT, "inject_policy.json")
    if not inject:
        inject = _read_json(stage_dir(gid, STAGE_PATCH) / "inject_policy.json")
    if inject:
        for key, val in inject.items():
            if key not in ("modules", "protect", "skip", "word_count", "line_width", "_meta"):
                merged[key] = val

    tr = load_stage_config(gid, STAGE_TRANSLATE, "codec.json", "skip.json")
    skip = tr.get("skip") if isinstance(tr.get("skip"), dict) else None
    if not skip and (tr.get("originals") or tr.get("prefixes") or tr.get("skip_zh_inject")):
        skip = tr
    if not skip:
        skip = _read_json(stage_dir(gid, STAGE_TRANSLATE) / "skip.json") or None
    if skip:
        if "originals" in skip or "prefixes" in skip:
            merged["skip_zh_inject"] = {
                "originals": list(skip.get("originals") or []),
                "prefixes": list(skip.get("prefixes") or []),
            }
        elif "skip_zh_inject" in skip:
            merged["skip_zh_inject"] = skip["skip_zh_inject"]

    _policy_cache[gid] = merged
    return merged


def load_codec(game_id: str = "") -> dict[str, Any]:
    """Translate protect + font charmap knobs."""
    gid = game_id or _active_game_id
    if not gid:
        return {}
    if gid in _codec_cache:
        return _codec_cache[gid]

    out: dict[str, Any] = {}
    legacy = _read_json(game_config_dir(gid) / "codec.json")
    if legacy:
        out.update(legacy)
        out.pop("line_width", None)
        out.pop("word_count", None)

    tr = load_stage_config(gid, STAGE_TRANSLATE, "codec.json")
    if tr.get("protect"):
        out["protect"] = tr["protect"]

    font_cfg = load_font_config(gid)
    charmap_keys = (
        "escape",
        "escape_bytes",
        "ideospace_bytes",
        "chinese_leads",
        "punct_map",
    )
    cm = {k: font_cfg[k] for k in charmap_keys if k in font_cfg}
    if cm:
        out["charmap"] = {**(out.get("charmap") or {}), **cm}
    elif "charmap" in tr:
        out["charmap"] = tr["charmap"]

    _codec_cache[gid] = out
    return out


def load_custom_translations(game_id: str) -> dict[str, str]:
    root = game_config_dir(game_id)
    candidates = [
        root / STAGE_TRANSLATE / "lexicon",
        root / "custom_translations",
    ]
    ct_dir = next((p for p in candidates if p.is_dir()), None)
    if ct_dir is None:
        print(f"[配置] 自定义翻译目录不存在: {candidates[0]}")
        return {}
    merged: dict[str, str] = {}
    files = sorted(ct_dir.glob("*.json"))
    print(f"[配置] 读取自定义翻译目录: {ct_dir} ({len(files)} 个文件)")
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                before = len(merged)
                merged.update(data)
                added = len(merged) - before
                print(f"[配置]   {f.name}: {added} 条")
        except (json.JSONDecodeError, OSError) as e:
            print(f"[配置]   {f.name}: 读取失败 - {e}")
    print(f"[配置] 自定义翻译总计: {len(merged)} 条")
    return merged
