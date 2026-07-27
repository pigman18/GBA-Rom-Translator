"""AXVJ intro / early-UI address registry — S1 data for ``policy``.

These are NOT ordinary mid-ROM ``loadword`` story lines. Birch's new-game
speech loads text from **Thumb literal pools** in low ROM; some strings even
live in the UI bank and can sit inside false LZ streams.

This module is a **pointer registry** (funnel stage S1), not a parallel
inject policy. Rewrite safety lives in ``policy``.
"""
from __future__ import annotations


def _parse_addr(val):
    if val is None:
        return None
    if isinstance(val, int):
        return val
    s = str(val).strip().lower().replace("0x", "")
    return int(s, 16)


def _intro_items(game_id: str = "") -> dict:
    from .config_loader import get_active_game_id, list_available_games, load_stage_config, STAGE_INJECT
    gid = game_id or get_active_game_id()
    if not gid:
        games = list_available_games()
        if games:
            gid = games[0]
    if not gid:
        return {}
    return load_stage_config(gid, STAGE_INJECT, "config.json") or {}


def _allow_sites(key: str, game_id: str = "") -> frozenset[int]:
    raw = _intro_items(game_id).get("allow", {}).get(key, {}).get("sites", [])
    return frozenset(_parse_addr(v) for v in raw if v is not None)


def birch_ptr_allowlist(game_id: str = "") -> frozenset[int]:
    return _allow_sites("birch_early_pool", game_id)


def trainer_ui_ptr_allowlist(game_id: str = "") -> frozenset[int]:
    return _allow_sites("trainer_ui", game_id)


def summary_lines() -> list[str]:
    lines = ["AXVJ intro address registry:", ""]
    cfg = _intro_items()
    allow = cfg.get("allow", {})
    for key in ("birch_early_pool", "trainer_ui"):
        entry = allow.get(key, {})
        sites = entry.get("sites", [])
        desc = entry.get("description", "")
        lines.append(f"  [{key}] {len(sites)} sites — {desc}")
        for s in sites:
            lines.append(f"    site=0x{_parse_addr(s):X}" if s is not None else "    site=—")
    return lines
