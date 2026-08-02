"""Config-driven extract pipeline — schedule ops from ``extract/config.json``.

Engine / ``extract_axvj`` only walk ``pipeline`` (and optional ``build_enrich``);
game-specific discovery lives in configs, not call-site if-chains.
"""
from __future__ import annotations

from typing import Any, Callable

from .config_loader import get_active_game_id
from .policy import _cfg

# Historic AXVJ pipeline used when config has no ``pipeline`` key (v2
# modules.json drops it; discovery is data-driven per module instead).
_DEFAULT_PIPELINE = [
    {"op": "fixed_table", "table": "species_names"},
    {"op": "fixed_table", "table": "move_names"},
    {"op": "fixed_table", "table": "ability_names"},
    {"op": "fixed_table", "table": "item_names"},
    {"op": "fixed_table", "table": "item_descriptions"},
    {"op": "fixed_table", "table": "nature_names"},
    {"op": "fixed_table", "table": "type_names"},
    {"op": "ui_block"},
    {"op": "option_menu"},
    {"op": "fc_prefixed_ui"},
    {"op": "battle_hud"},
    {"op": "battle_prompt"},
    {"op": "summary_ui"},
    {"op": "short_menu"},
    {"op": "save_power"},
    {"op": "script_pointers"},
    {"op": "addr_bands"},
]


def extract_pipeline(game_id: str = "") -> list[dict[str, Any]]:
    """Ordered ops from ``extract/config.json`` → ``pipeline`` (or default)."""
    gid = (game_id or get_active_game_id() or "").strip()
    raw = _cfg(gid).get("pipeline")
    if not raw:
        raw = _DEFAULT_PIPELINE
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
    if op == "addr_bands":
        return E.extract_addr_bands_pool(rom, path=str(step.get("path") or ""))
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


# ---------------------------------------------------------------------------
# Module-driven extraction (v2): each module declares its type.
#   type=addr_bands (default) → scan the module's own read.addr_bands
#   type=fixed_table / struct_table / ptr_table → table extractor
# Global UI scanners (short_menu, save_power, …) stay pipeline ops and are
# combined with the module-driven entries by address.
# ---------------------------------------------------------------------------

_MODULE_TABLE_EXTRACTOR = {
    "物种名": "species_names",
    "招式名": "move_names",
    "特性名": "ability_names",
    "属性名": "type_names",
    "道具名": "item_data",
    "道具说明": "item_descriptions",
    "性格名": "nature_names",
}


def module_driven_ops(game_id: str = "") -> list[dict[str, Any]]:
    """Pipeline ops NOT owned by module-driven extraction (global UI scanners)."""
    return [
        dict(op)
        for op in extract_pipeline(game_id)
        if op.get("op") not in ("fixed_table", "addr_bands")
    ]


def _bands_from_read(read: dict[str, Any]) -> list:
    """v3 scan bands live at ``read.scan_addr_bands``; keep v2 ``addr_bands`` / top-level as fallback."""
    return (
        read.get("scan_addr_bands")
        or read.get("addr_bands")
        or []
    )


# Hidden UI modules (v3): module_id → existing global scanner (still config-driven
# via policy/game blocks for enrich internals). Plain ``scan/stride/…`` deferred below.
_UI_EXTRACTOR = {
    "选项菜单扫描": "option_menu",
    "FC彩窗扫描": "fc_prefixed_ui",
    "战斗HUD采集": "battle_hud",
    "短标菜单采集": "short_menu",
    "状态背包采集": "summary_ui",
    "战斗提示扫描": "battle_prompt",
    "存档提示扫描": "save_power",
    "主脚本指针": "script_pointers",
}


def _run_ui_op(rom: bytes, op: str) -> list[dict]:
    from . import extract as E

    return {
        "option_menu": E.extract_option_menu,
        "fc_prefixed_ui": E.extract_fc_prefixed_ui,
        "battle_hud": E.extract_battle_hud_labels,
        "short_menu": E.extract_short_menu_labels,
        "summary_ui": E.extract_summary_ui_pool,
        "battle_prompt": E.extract_battle_prompt_pool,
        "save_power": E.extract_save_power_prompts,
        "script_pointers": E.extract_script_pointers,
    }.get(op, lambda _: [])(rom)


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
    """Per-module extraction keyed by each module's v3 ``type`` / ``read``.

    Profile entry ``"type":"scan"`` → scan the module's own
    ``read.scan_addr_bands`` bands; ``stride``/``ptr_stride``/``struct`` →
    the matching ``tables`` extractor (config-driven offset/stride/count);
    hidden UI modules (needle/prefix/pointer) → existing global UI scanners.
    When ``verbose``, per-module hit counts are printed for audit.
    """
    from . import tables as T
    from .config_loader import load_modules
    from .extract import scan_addr_bands

    gid = (game_id or get_active_game_id() or "").strip()
    table_dispatch = {
        "species_names": T.extract_species_names,
        "move_names": T.extract_move_names,
        "ability_names": T.extract_ability_names,
        "type_names": T.extract_type_names,
        "item_data": T.extract_item_names,
        "item_descriptions": T.extract_item_descriptions,
        "nature_names": T.extract_nature_names,
    }

    def stamp(e: dict, mid: str):
        e.setdefault("module", mid)
        e.setdefault("_axvj_module", mid)

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

        # Hidden UI modules → reuse existing global scanners.
        if rtype in ("needle", "prefix", "pointer") and mid in _UI_EXTRACTOR:
            op = _UI_EXTRACTOR[mid]
            for e in _run_ui_op(rom, op):
                if op == "script_pointers" and not include_scripts:
                    continue
                addr = e.get("address") or ""
                if addr and addr in seen:
                    continue
                if addr:
                    seen.add(addr)
                _stamp_entry_module(e, mid)
                out.append(e)
            counts[mid] = len(out) - start_n
            continue

        if rtype in ("addr_bands", "scan"):
            bands = _bands_from_read(read) or m.get("addr_bands") or []
            if not bands:
                continue
            for e in scan_addr_bands(rom, bands):
                _stamp_entry_module(e, mid)
                out.append(e)
            counts[mid] = len(out) - start_n
            continue

        fn = table_dispatch.get(_MODULE_TABLE_EXTRACTOR.get(mid) or "")
        if fn:
            for e in fn(rom):
                _stamp_entry_module(e, mid)
                out.append(e)
            counts[mid] = len(out) - start_n
    if verbose:
        print(f"[抽取] 模块命中汇总 ({len(out)} 条):")
        for mid in sorted(counts):
            print(f"[抽取]   {mid}: {counts[mid]}")
    return out
