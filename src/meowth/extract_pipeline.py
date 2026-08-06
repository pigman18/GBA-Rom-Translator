"""Legacy ROM extract ops — product corpus is texts_patcher → texts.json.

Build / translate do not call this path. Kept for offline debugging only.
"""
from __future__ import annotations

import warnings
from typing import Any, Callable

from .config_loader import get_active_game_id
from .policy import _cfg

# No English fixed_table default — empty unless extract/config.json sets pipeline.
_DEFAULT_PIPELINE: list[dict[str, Any]] = []


def extract_pipeline(game_id: str = "") -> list[dict[str, Any]]:
    """Ordered ops from ``extract/config.json`` → ``pipeline`` (or empty)."""
    gid = (game_id or get_active_game_id() or "").strip()
    raw = _cfg(gid).get("pipeline")
    if not raw:
        raw = _DEFAULT_PIPELINE
    return [dict(x) for x in raw if isinstance(x, dict) and x.get("op")]


def build_enrich_ops(game_id: str = "") -> list[dict[str, Any]]:
    """DEPRECATED — Build uses texts.json only; never re-extracts ROM."""
    warnings.warn(
        "build_enrich_ops is deprecated; Build uses texts.json only",
        DeprecationWarning,
        stacklevel=2,
    )
    gid = (game_id or get_active_game_id() or "").strip()
    raw = _cfg(gid).get("build_enrich")
    if not raw:
        return []
    return [dict(x) for x in raw if isinstance(x, dict) and x.get("op")]


def _run_fixed_table(rom: bytes, table: str) -> list[dict]:
    from . import tables as T

    warnings.warn(
        f"fixed_table op {table!r} is deprecated; use extract_module(module_id)",
        DeprecationWarning,
        stacklevel=2,
    )
    key = (table or "").strip()
    dispatch = {
        "species_names": T.extract_species_names,
        "move_names": T.extract_move_names,
        "ability_names": T.extract_ability_names,
        "item_names": T.extract_item_names,
        "item_descriptions": T.extract_item_descriptions,
        "nature_names": T.extract_nature_names,
        "type_names": T.extract_type_names,
    }
    fn = dispatch.get(key)
    if not fn:
        return []
    return fn(rom)


_EXTRACT_OPS: dict[str, Callable[[bytes], list[dict]]] = {}


def _extract_op_dispatch() -> dict[str, Callable[[bytes], list[dict]]]:
    if _EXTRACT_OPS:
        return _EXTRACT_OPS
    from . import extract as E

    _EXTRACT_OPS.update(
        {
            "option_menu": E.extract_option_menu,
            "fc_prefixed_ui": E.extract_fc_prefixed_ui,
            "battle_hud": E.extract_battle_hud_labels,
            "short_menu": E.extract_short_menu_labels,
            "summary_ui": E.extract_summary_ui_pool,
            "battle_prompt": E.extract_battle_prompt_pool,
            "save_power": E.extract_save_power_prompts,
            "script_pointers": E.extract_script_pointers,
            "ui_block": E.extract_ui_block,
            "s1_registry": E.extract_s1_registry_strings,
        }
    )
    return _EXTRACT_OPS


def _run_ui_op(rom: bytes, op: str) -> list[dict]:
    fn = _extract_op_dispatch().get(op)
    if not fn:
        return []
    return fn(rom)


def _dispatch_op(
    rom: bytes,
    step: dict[str, Any],
    *,
    include_scripts: bool,
    script_limit: int,
) -> list[dict]:
    from . import extract as E

    op = str(step.get("op") or "").strip()
    if not op:
        return []

    if op == "fixed_table":
        return _run_fixed_table(rom, str(step.get("table") or ""))

    if op in _extract_op_dispatch():
        if op == "script_pointers" and not include_scripts:
            return []
        if op == "script_pointers":
            lim = int(step.get("limit", script_limit) or 0)
            return E.extract_script_pointers(rom, limit=lim)
        return _run_ui_op(rom, op)

    if op == "addr_bands":
        return E.extract_addr_bands_pool(rom, path=str(step.get("path") or ""))

    return []


def run_extract_pipeline(
    rom: bytes,
    *,
    game_id: str = "",
    include_scripts: bool = True,
    script_limit: int = 0,
    ops: list[dict[str, Any]] | None = None,
) -> list[dict]:
    """Run configured extract ops; dedupe by address. Offline only."""
    steps = ops if ops is not None else extract_pipeline(game_id)
    entries: list[dict] = []
    seen: set[str] = set()
    for step in steps:
        for e in _dispatch_op(
            rom,
            step,
            include_scripts=include_scripts,
            script_limit=script_limit,
        ):
            addr = e.get("address") or ""
            if not addr or addr in seen:
                continue
            seen.add(addr)
            entries.append(e)
    return entries


def module_driven_ops(game_id: str = "") -> list[dict[str, Any]]:
    return [
        dict(op)
        for op in extract_pipeline(game_id)
        if op.get("op") not in ("fixed_table", "addr_bands")
    ]


def _bands_from_read(read: dict[str, Any]) -> list:
    return (
        read.get("scan_addr_bands")
        or read.get("addr_bands")
        or []
    )


def _stamp_entry_module(e: dict, mid: str) -> None:
    e.setdefault("module", mid)
    e.setdefault("_axvj_module", mid)


def extract_modules(
    rom: bytes,
    game_id: str = "",
    *,
    include_scripts: bool = True,
    hidden_only: bool = False,
    verbose: bool = False,
) -> list[dict]:
    """Offline per-module ROM scan by ``type`` / ``read`` (no Chinese id maps).

    Product path uses texts.json; needle/prefix/pointer without bands are skipped.
    """
    del include_scripts  # script discovery is texts_patcher / curated texts only
    from . import tables as T
    from .config_loader import load_modules
    from .extract import scan_addr_bands
    from .modules import TABLE_LAYOUT_TYPES

    gid = (game_id or get_active_game_id() or "").strip()
    mods = load_modules(gid)
    out: list[dict] = []
    seen: set[str] = set()
    counts: dict[str, int] = {}
    for mid, m in mods.items():
        if hidden_only and not m.get("hidden"):
            continue
        read = m.get("read") or {}
        rtype = str(m.get("type") or read.get("type") or "scan")
        start_n = len(out)

        if rtype in ("addr_bands", "scan"):
            bands = _bands_from_read(read) or m.get("addr_bands") or []
            if not bands:
                continue
            for e in scan_addr_bands(rom, bands):
                addr = e.get("address") or ""
                if addr and addr in seen:
                    continue
                if addr:
                    seen.add(addr)
                _stamp_entry_module(e, mid)
                out.append(e)
            counts[mid] = len(out) - start_n
            continue

        if rtype in TABLE_LAYOUT_TYPES:
            for e in T.extract_module(rom, mid):
                addr = e.get("address") or ""
                if addr and addr in seen:
                    continue
                if addr:
                    seen.add(addr)
                _stamp_entry_module(e, mid)
                out.append(e)
            counts[mid] = len(out) - start_n
    if verbose:
        print(f"[抽取] 模块命中汇总 ({len(out)} 条):")
        for mid in sorted(counts):
            print(f"[抽取]   {mid}: {counts[mid]}")
    return out
