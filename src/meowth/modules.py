"""Module scope loader — stage pack ``modules/``.

Pipeline: extract/tables emit entries → assign_module (addr_bands here) →
GUI checkboxes → translate/build only process checked modules.

Authoritative file: ``configs/<game_id>/translate/modules.json``.
Wrap width: ``translate/modules.inject.json`` → ``line_width`` (default 20).
Write behavior: ``write.type=op`` + ``write.op`` (0x01..0x7E) → phrase ``F9 <op> hi lo``;
default phrase channel is ``F9 7F`` (see ``module_write_op``).
"""

from __future__ import annotations

import os
from typing import Any

from .config_loader import load_modules


def _get_modules(game_id: str) -> dict[str, dict[str, Any]]:
    gid = (game_id or "").strip()
    if not gid:
        from .config_loader import get_active_game_id

        gid = (get_active_game_id() or "").strip()
    if not gid:
        raise ValueError(
            "game_id is required. "
            "Call sites must pass the detected game ID (e.g. from detect_game())."
        )
    return load_modules(gid)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_modules(game_id: str = "") -> list[str]:
    return list(_get_modules(game_id).keys())


def list_module_meta(game_id: str = "") -> list[dict[str, Any]]:
    mods = _get_modules(game_id)
    out = []
    for mid, meta in mods.items():
        badge = ""
        if meta.get("dirty"):
            badge += "!"
        if meta.get("star"):
            badge += "*"
        label = meta.get("label", mid)
        bands = meta.get("addr_bands", [])
        out.append(
            {
                "id": mid,
                "label": f"{badge}{label}" if badge else label,
                "label_raw": label,
                "group": meta.get("group", ""),
                "default": bool(meta.get("default")),
                "dirty": bool(meta.get("dirty")),
                "star": bool(meta.get("star")),
                "notes": meta.get("notes", ""),
                "description": meta.get("description", ""),
                "addr_bands": bands,
            }
        )
    return out


def list_groups(game_id: str = "") -> list[str]:
    groups: list[str] = []
    seen: set[str] = set()
    for meta in _get_modules(game_id).values():
        g = (meta.get("group") or "").strip()
        if g and g not in seen:
            seen.add(g)
            groups.append(g)
    return groups


def get_default_modules(game_id: str = "") -> list[str]:
    mods = _get_modules(game_id)
    return [mid for mid, meta in mods.items() if meta.get("default")]


# ---------------------------------------------------------------------------
# Module assignment logic
# ---------------------------------------------------------------------------

# Groups that use script-style strict pointer gates (dump taxonomy).
_SCRIPT_GROUPS = frozenset({"剧情", "设施"})


def _module_geo_bands(meta: dict[str, Any]) -> list[tuple[int, int]]:
    """addr_bands / geo_ranges, else dump offset/end (name tables often empty).

    Prefer tight ``geo_ranges`` (configured multi-ranges) when present so UI
    pools and nurse slices beat a neighbor's merged string band. Otherwise
    use dumped ``addr_bands``. When only those are present, do **not** also
    add the coarse offset/end envelope — multi-range UI modules would
    otherwise swallow mid-ROM tables between disjoint pools.
    """
    out: list[tuple[int, int]] = []
    for key in ("geo_ranges", "addr_bands"):
        for b in meta.get(key) or []:
            if not isinstance(b, (list, tuple)) or len(b) < 2:
                continue
            lo, hi = _parse_addr(b[0]), _parse_addr(b[1])
            if lo is not None and hi is not None and hi >= lo:
                out.append((lo, hi))
        if out:
            return out
    off = meta.get("offset")
    end = meta.get("end")
    if off is not None and end is not None:
        try:
            lo = int(off) if not isinstance(off, str) else _parse_addr(off)
            hi = int(end) if not isinstance(end, str) else _parse_addr(end)
        except (TypeError, ValueError):
            lo = hi = None
        if lo is not None and hi is not None and hi > lo > 0:
            out.append((lo, hi))
    return out


def _match_addr_to_module(addr: int, mods: dict[str, dict[str, Any]]) -> str | None:
    """Smallest containing geo band wins (same rule as dump assign_modules)."""
    best: tuple[int, str] | None = None
    for mid, meta in mods.items():
        if mid == "未归类":
            continue
        for lo, hi in _module_geo_bands(meta):
            if lo <= addr <= hi:
                span = hi - lo + 1
                if best is None or span < best[0] or (span == best[0] and mid < best[1]):
                    best = (span, mid)
    if best:
        return best[1]
    bands = _module_geo_bands(mods.get("未归类") or {})
    for lo, hi in bands:
        if lo <= addr <= hi:
            return "未归类"
    return None


def assign_module(entry: dict[str, Any], game_id: str = "") -> str | None:
    """Assign module by ROM address ∩ dump geo (bands / offset–end).

    Address match is authoritative so stale English ``category`` / old
    ``module`` stamps cannot override measured dump spans. Known Chinese
    ``module`` stamps are used only when address is missing.
    """
    try:
        mods = _get_modules(game_id)
    except ValueError:
        mods = {}
    if not mods:
        stamped = entry.get("module") or entry.get("_axvj_module")
        if isinstance(stamped, str) and stamped.strip():
            return stamped.strip()
        return None
    addr = _entry_rom_addr(entry)
    if addr is not None:
        hit = _match_addr_to_module(addr, mods)
        if hit:
            return hit
    stamped = entry.get("module") or entry.get("_axvj_module")
    if isinstance(stamped, str) and stamped.strip():
        s = stamped.strip()
        if s in mods:
            return s
    return None


def entry_module(entry: dict[str, Any], game_id: str = "") -> str | None:
    """Resolve module id for an entry (address geo, else known Chinese stamp)."""
    return assign_module(entry, game_id=game_id)


def entry_tags(entry: dict[str, Any], game_id: str = "") -> set[str]:
    """Module id tags for matching (Chinese module ids only)."""
    mid = entry_module(entry, game_id=game_id)
    return {mid} if mid else set()


def entry_matches(entry: dict[str, Any], *candidates: str, game_id: str = "") -> bool:
    """True if entry's module id is one of ``candidates``."""
    if not candidates:
        return False
    tags = entry_tags(entry, game_id=game_id)
    return any(c in tags for c in candidates)


def entry_group(entry: dict[str, Any], game_id: str = "") -> str:
    """Dump taxonomy group for this entry's module (e.g. 设施 / 界面 / 剧情)."""
    mid = entry_module(entry, game_id=game_id)
    if not mid:
        return ""
    try:
        mods = _get_modules(game_id)
    except ValueError:
        return ""
    return str((mods.get(mid) or {}).get("group") or "").strip()


def entry_group_in(entry: dict[str, Any], *groups: str, game_id: str = "") -> bool:
    g = entry_group(entry, game_id=game_id)
    return bool(g) and g in groups


# High UI pool floor — same class as FC_UI / menu banks (not a per-string addr).
HIGH_UI_GEO_FLOOR = 0x3D0000
_HIGH_UI_GEO_CACHE: dict[str, tuple[tuple[int, int], ...]] = {}


def iter_high_ui_geo_bands(game_id: str = "") -> tuple[tuple[int, int], ...]:
    """Dump ``geo_ranges``/``addr_bands`` that live in the high UI pool region.

    Used so PC/shop chrome past a coarse ``ui_text_bank`` cut still count as
    UI bodies — driven by measured module bands, not a hand-raised ceiling.

    Cached per game: ``string_in_ui_text_bank`` is hit from the full-ROM
    pointer scan; rebuilding bands every call made extract look hung.
    """
    from .config_loader import get_active_game_id

    gid = (game_id or "").strip() or (get_active_game_id() or "").strip() or "_"
    cached = _HIGH_UI_GEO_CACHE.get(gid)
    if cached is not None:
        return cached
    try:
        mods = _get_modules(gid if gid != "_" else "")
    except ValueError:
        _HIGH_UI_GEO_CACHE[gid] = ()
        return ()
    out: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for meta in mods.values():
        for lo, hi in _module_geo_bands(meta):
            if lo < HIGH_UI_GEO_FLOOR:
                continue
            key = (lo, hi)
            if key in seen:
                continue
            seen.add(key)
            out.append(key)
    frozen = tuple(out)
    _HIGH_UI_GEO_CACHE[gid] = frozen
    return frozen


def clear_high_ui_geo_cache() -> None:
    _HIGH_UI_GEO_CACHE.clear()


def entry_is_script_like(entry: dict[str, Any], game_id: str = "") -> bool:
    """剧情 / 设施 / 未归类 → strict script pointer policy."""
    mid = entry_module(entry, game_id=game_id)
    if mid == "未归类":
        return True
    if not mid:
        return False
    try:
        mods = _get_modules(game_id)
    except ValueError:
        return False
    g = ((mods.get(mid) or {}).get("group") or "").strip()
    return g in _SCRIPT_GROUPS


def stamp_entry_module(entry: dict[str, Any], game_id: str = "") -> str | None:
    """Write ``module`` / ``_axvj_module`` from geo resolver; align category."""
    mid = entry_module(entry, game_id=game_id)
    if mid:
        entry["module"] = mid
        entry["_axvj_module"] = mid
        entry["category"] = mid  # same Chinese id; no parallel English taxonomy
    else:
        entry.pop("module", None)
        entry.pop("_axvj_module", None)
        entry.pop("category", None)
    return mid


def _parse_addr(val: Any) -> int | None:
    """Parse an address value (int or hex string)."""
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        s = val.strip().lower().replace("0x", "")
        try:
            return int(s, 16)
        except ValueError:
            return None
    return None


def _entry_rom_addr(entry: dict[str, Any]) -> int | None:
    raw = entry.get("address")
    if raw is None or raw == "":
        return None
    if isinstance(raw, int):
        return raw & 0x1FFFFFF
    s = str(raw).strip().lower().replace("0x", "")
    try:
        return int(s, 16) & 0x1FFFFFF
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Module resolution
# ---------------------------------------------------------------------------


def resolve_modules(
    modules: list[str] | tuple[str, ...] | None = None,
    preset: str | None = None,
    game_id: str = "",
) -> list[str]:
    if modules:
        return _normalize(modules, game_id)

    env = os.environ.get("MEOWTH_AXVJ_MODULES", "").strip()
    if env:
        parsed = _parse_csv(env, game_id)
        if parsed is not None:
            return parsed

    env_csv = (
        (preset or "").strip()
        or os.environ.get("MEOWTH_AXVJ_PRESET", "").strip()
        or os.environ.get("MEOWTH_AXVJ_FUNNEL", "").strip()
    )
    if env_csv:
        parsed = _parse_csv(env_csv, game_id)
        if parsed:
            return parsed

    return get_default_modules(game_id)


def _normalize(modules: list[str] | tuple[str, ...], game_id: str) -> list[str]:
    mods = _get_modules(game_id)
    # id → canonical key (exact; ASCII also matched case-insensitively)
    by_lower = {k.lower(): k for k in mods}
    out: list[str] = []
    for m in modules:
        raw = str(m).strip()
        if raw in ("*",):
            return list(mods.keys())
        key = raw if raw in mods else by_lower.get(raw.lower())
        if key and key not in out:
            out.append(key)
    return out or get_default_modules(game_id)


def _parse_csv(value: str, game_id: str) -> list[str] | None:
    if not (value or "").strip():
        return None
    parts = [p.strip() for p in value.split(",") if p.strip()]
    if not parts:
        return None
    mods = _get_modules(game_id)
    by_lower = {k.lower(): k for k in mods}
    resolved: list[str] = []
    unknown: list[str] = []
    for p in parts:
        key = p if p in mods else by_lower.get(p.lower())
        if key is None:
            unknown.append(p)
        elif key not in resolved:
            resolved.append(key)
    if unknown:
        raise ValueError(
            f"unknown modules {unknown} for game {game_id}; "
            f"known={sorted(mods)}"
        )
    return resolved


def filter_entries_by_modules(
    entries: list[dict], modules: list[str] | None, game_id: str = ""
) -> list[dict]:
    mods = set(resolve_modules(modules, game_id=game_id))
    out: list[dict] = []
    for e in entries:
        mid = stamp_entry_module(e, game_id=game_id)
        if mid is not None and mid in mods:
            out.append(e)
    return out


# Public CSV parser for CLI
def parse_modules_csv(value: str | None) -> list[str] | None:
    if not (value or "").strip():
        return None
    parts = [p.strip() for p in value.split(",") if p.strip()]
    return parts if parts else None


# Legacy compatibility shims
MODULE_PRESETS: dict[str, tuple[str, ...]] = {}
AXVJ_MODULES: dict[str, dict[str, Any]] = {}
DEFAULT_MODULES: tuple[str, ...] = ()


def _init_legacy():
    global AXVJ_MODULES, MODULE_PRESETS, DEFAULT_MODULES
    from .config_loader import list_available_games
    games = list_available_games()
    if games:
        gid = games[0]
        try:
            AXVJ_MODULES = load_modules(gid)
            DEFAULT_MODULES = tuple(get_default_modules(gid))
        except Exception:
            pass


_init_legacy()
