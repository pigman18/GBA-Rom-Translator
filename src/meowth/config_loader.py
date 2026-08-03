"""Load per-game config packs under ``configs/<game_id>/``.

::

    configs/<game_id>/
      game.json
      extract/config.json
      translate/
        config.json            # protect / skip
        modules.json           # dump scope: addr_bands + offset/end
        modules.inject.json    # read / write.type / write.stride / line_width
        lexicon/
      font/config.json + charmap.txt
      patch/                   # ARMIPS
      inject/config.json       # pointer deny / brand_compact_skip

Name-table geo (offset/end) comes from dump ``modules.json``; inject ``read``
holds row shape; ``write`` holds Chinese widen/patch and VRAM write behavior.
``count`` is derived. ``line_width`` defaults to 20 when omitted.
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

DEFAULT_LINE_WIDTH = 20

# F9 channel protocol (AXVJ Chinese):
#   F9 00 01  — 旁载单字 (auto)
#   F9 80 hi/lo — 短语表 (default; keep=0 / geometry)
#   F9 01..7E hi lo — phrase + write.op sticky (02=footer 03=linear 04=slot)
#   bare FA..FF       — PCS controls / EOS (NOT F9 channels)
F9_SIDE_GLYPH = 0x00
F9_PHRASE_DEFAULT = 0x80
F9_OP_MIN = 0x01
F9_OP_MAX = 0x7E
F9_EOS = 0xFF

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
    """Return F9 phrase-channel byte, or None if module has no ``write.type=op``.

    When set, phrase encoding becomes ``F9 <op> hi lo``.
    ``F9 00`` / default ``F9 7F`` keep auto write unless patched.
    Op must be in ``0x01..0x7E``.
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

# modules.inject.json module id → legacy tables.py key
_INJECT_TO_TABLE_KEY = {
    "物种名": "species_names",
    "招式名": "move_names",
    "特性名": "ability_names",
    "属性名": "type_names",
    "道具名": "item_data",
    "性格名": "nature_names",
}

# Fields that may live on a module entry in v2 ``translate/modules.json``
# (migrated from modules.inject.json) and feed inject-style readers.
_INJECT_MODULE_KEYS = (
    "read",
    "write",
    "layout",
    "line_width",
    "chs_stride",
    "patch_type",
    "widen_fn",
)


def _v2_extraction(game_id: str) -> dict[str, Any]:
    """Top-level scan/policy/modules_defaults/enrich from v2 modules.json."""
    raw = _read_json(stage_dir(game_id, STAGE_TRANSLATE) / "modules.json")
    if not isinstance(raw, dict):
        return {}
    meta = raw.get("_meta") or {}
    if meta.get("schema") != "v2":
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
    """Inject config keyed by module id (skips ``_meta``).

    v2: read/write/line_width live on ``translate/modules.json`` module
    entries; legacy ``modules.inject.json`` fills any gaps.
    """
    gid = game_id or _active_game_id
    if not gid:
        return {}
    if gid in _modules_inject_cache:
        return _modules_inject_cache[gid]

    out: dict[str, dict[str, Any]] = {}
    raw_v2 = _read_json(stage_dir(gid, STAGE_TRANSLATE) / "modules.json")
    mods_v2 = raw_v2.get("modules") if isinstance(raw_v2, dict) else None
    if isinstance(mods_v2, dict):
        for mid, meta in mods_v2.items():
            if not isinstance(meta, dict):
                continue
            inj = {k: meta[k] for k in _INJECT_MODULE_KEYS if k in meta}
            if inj:
                out[mid] = inj

    raw = _read_json(stage_dir(gid, STAGE_TRANSLATE) / "modules.inject.json")
    for k, v in raw.items():
        if k == "_meta" or not isinstance(v, dict):
            continue
        merged = dict(v)
        merged.update(out.get(k, {}))
        out[k] = merged
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
        key = _INJECT_TO_TABLE_KEY.get(mid) or mid
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
        elif typ == "ptr_stride":
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
                raise ValueError(f"module {mid}: missing offset (dump modules.json)")
            entry["table"] = offset
            unit = 4
            if end is not None:
                entry["count"] = _derive_table_count(offset, end, unit)
            elif legacy_count is not None:
                entry["count"] = int(legacy_count)
            else:
                raise ValueError(f"module {mid}: need end or layout.count for ptr_table")
        elif typ == "struct_table":
            for f in ("entry_size", "name_stride", "desc_ptr_offset"):
                if f in layout:
                    entry[f] = layout[f]
            if offset is None:
                raise ValueError(f"module {mid}: missing offset (dump modules.json)")
            entry["offset"] = offset
            unit = int(layout.get("entry_size") or 0)
            if end is not None and unit:
                entry["count"] = _derive_table_count(offset, end, unit)
            elif legacy_count is not None:
                entry["count"] = int(legacy_count)
            else:
                raise ValueError(f"module {mid}: need end+entry_size or layout.count")
        else:  # fixed_table
            if "stride" in layout:
                entry["stride"] = layout["stride"]
            if offset is None:
                raise ValueError(f"module {mid}: missing offset (dump modules.json)")
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
    """Alias of ``module_write_op`` (None = phrase keeps default F9 7F)."""
    return module_write_op(game_id, module_id)


def module_line_width(game_id: str, module_id: str | None) -> int:
    """Per-module wrap width from ``modules.inject.json``; default 20."""
    if not module_id:
        return DEFAULT_LINE_WIDTH
    inj = load_modules_inject(game_id).get(module_id) or {}
    lw = inj.get("line_width")
    if lw is None:
        return DEFAULT_LINE_WIDTH
    try:
        return int(lw)
    except (TypeError, ValueError):
        return DEFAULT_LINE_WIDTH


def module_line_widths(game_id: str = "") -> dict[str, int]:
    """Map module id → line_width for modules that override the default."""
    gid = game_id or _active_game_id or ""
    out: dict[str, int] = {}
    for mid, cfg in load_modules_inject(gid).items():
        if "line_width" in cfg:
            try:
                out[mid] = int(cfg["line_width"])
            except (TypeError, ValueError):
                pass
    return out


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

    # No global translate line_width — default 20 at use sites
    profile["line_width"] = DEFAULT_LINE_WIDTH

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
    """Load ``translate/modules.json`` (dump addr-band scope)."""
    if game_id in _modules_cache:
        return _modules_cache[game_id]

    path = _first_existing(
        game_id,
        f"{STAGE_TRANSLATE}/modules.json",
        f"{STAGE_MODULES}/modules.json",
        "modules.json",
    )
    mods: dict[str, Any] | None = None
    if path is not None:
        print(f"[配置] 读取模块: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("modules"), dict):
            mods = data["modules"]
        elif isinstance(data, dict):
            mods = {
                k: v
                for k, v in data.items()
                if isinstance(v, dict) and k not in ("_meta",)
            }
    if mods is None:
        # Legacy: modules nested in translate/config.json
        tr = load_stage_config(game_id, STAGE_TRANSLATE, "codec.json")
        if isinstance(tr.get("modules"), dict):
            mods = tr["modules"]
            print(f"[配置] 读取模块(兼容 config.json): {len(mods)} 个")
    if mods is None:
        raise FileNotFoundError(
            f"No modules for game {game_id!r} "
            f"(expected {STAGE_TRANSLATE}/modules.json under {game_config_dir(game_id)})"
        )

    # Ensure no line_width left on dump modules (inject owns wrap width)
    cleaned = {}
    for mid, meta in mods.items():
        if not isinstance(meta, dict):
            continue
        cleaned[mid] = {k: v for k, v in meta.items() if k != "line_width"}
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
            if key not in ("modules", "protect", "skip", "line_width", "_meta"):
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
    """Translate protect + font charmap knobs. No global line_width."""
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
