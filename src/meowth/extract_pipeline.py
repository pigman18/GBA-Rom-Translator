"""Config-driven extract pipeline — schedule ops from ``extract/config.json``.

Engine / ``extract_axvj`` only walk ``pipeline`` (and optional ``build_enrich``);
game-specific discovery lives in configs, not call-site if-chains.
"""
from __future__ import annotations

from typing import Any, Callable

from .config_loader import get_active_game_id
from .policy import _cfg


def extract_pipeline(game_id: str = "") -> list[dict[str, Any]]:
    """Ordered ops from ``extract/config.json`` → ``pipeline``."""
    gid = (game_id or get_active_game_id() or "").strip()
    raw = _cfg(gid).get("pipeline") or []
    return [dict(x) for x in raw if isinstance(x, dict) and x.get("op")]


def build_enrich_ops(game_id: str = "") -> list[dict[str, Any]]:
    """Subset of ops re-run at Build to merge UI seeds into inject list."""
    gid = (game_id or get_active_game_id() or "").strip()
    raw = _cfg(gid).get("build_enrich")
    if raw is None:
        # Default: same as historical engine._enrich_axvj_build_entries
        return [
            {"op": "ui_block"},
            {"op": "option_menu"},
            {"op": "short_menu"},
            {"op": "save_power"},
            {"op": "s1_registry"},
        ]
    return [dict(x) for x in raw if isinstance(x, dict) and x.get("op")]


def module_defaults(game_id: str = "") -> dict[str, str]:
    """Story/UI/IME category ids from config (no engine-hardcoded Chinese)."""
    block = _cfg(game_id).get("modules_defaults") or {}
    return {
        "story": str(block.get("story") or ""),
        "ui": str(block.get("ui") or ""),
        "ime": str(block.get("ime") or ""),
        "unclassified": str(block.get("unclassified") or ""),
    }


def _run_fixed_table(rom: bytes, table: str) -> list[dict]:
    from . import tables as T

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

    if op == "ui_block":
        return E.extract_ui_block(rom)
    if op == "option_menu":
        return E.extract_option_menu(rom)
    if op == "fc_prefixed_ui":
        return E.extract_fc_prefixed_ui(rom)
    if op == "battle_hud":
        return E.extract_battle_hud_labels(rom)
    if op == "battle_prompt":
        return E.extract_battle_prompt_pool(rom)
    if op == "summary_ui":
        return E.extract_summary_ui_pool(rom)
    if op == "short_menu":
        return E.extract_short_menu_labels(rom)
    if op == "save_power":
        return E.extract_save_power_prompts(rom)
    if op == "s1_registry":
        return E.extract_s1_registry_strings(rom)
    if op == "script_pointers":
        if not include_scripts:
            return []
        lim = int(step.get("limit", script_limit) or 0)
        return E.extract_script_pointers(rom, limit=lim)

    # Generic enrich aliases (plan shape)
    if op == "enrich_seed_find":
        # Currently only short_menu-style needles; enrich name selects config block
        name = str(step.get("enrich") or "")
        if name == "短标菜单" or not name:
            return E.extract_short_menu_labels(rom)
        return []
    if op == "enrich_band_scan":
        name = str(step.get("enrich") or "")
        if name in ("存档与电源", ""):
            return E.extract_save_power_prompts(rom)
        if name == "FC彩窗":
            return E.extract_fc_prefixed_ui(rom)
        if name == "战斗提示":
            return E.extract_battle_prompt_pool(rom)
        if name == "战斗HUD":
            return E.extract_battle_hud_labels(rom)
        if name == "状态背包":
            return E.extract_summary_ui_pool(rom)
        return []

    return []


def run_extract_pipeline(
    rom: bytes,
    *,
    game_id: str = "",
    include_scripts: bool = True,
    script_limit: int = 0,
    ops: list[dict[str, Any]] | None = None,
) -> list[dict]:
    """Run configured (or provided) extract ops; dedupe by address."""
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
