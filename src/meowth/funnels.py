"""Legacy shim: old銆屾紡鏂椼€峮ames 鈫?modules.

Prefer ``modules`` + ``MEOWTH_AXVJ_MODULES`` / GUI checkboxes.
Kept so old scripts setting ``MEOWTH_AXVJ_FUNNEL=鈥` still resolve.
"""

from __future__ import annotations

from typing import Any

from .modules import MODULE_PRESETS, resolve_modules

# Back-compat aliases
AXVJ_FUNNELS: dict[str, dict[str, Any]] = {
    k: {
        "label": k,
        "modules": v,
        "notes": "legacy preset 鈫?modules",
    }
    for k, v in MODULE_PRESETS.items()
}
DEFAULT_FUNNEL = "safe"


def list_funnels() -> list[str]:
    return list(MODULE_PRESETS.keys())


def get_funnel(name: str | None) -> dict[str, Any]:
    key = (name or "").strip().lower() or DEFAULT_FUNNEL
    if key not in MODULE_PRESETS:
        known = ", ".join(sorted(MODULE_PRESETS))
        raise ValueError(f"unknown preset {name!r}; known=[{known}]")
    mods = MODULE_PRESETS[key]
    return {
        "id": key,
        "label": key,
        "modules": mods,
        "notes": "legacy funnel preset 鈫?modules",
    }


def resolve_funnel_modules(
    funnel: str | None = None,
    modules: list[str] | None = None,
) -> list[str] | None:
    """Deprecated: use ``resolve_modules``."""
    return resolve_modules(modules=modules, preset=funnel)
