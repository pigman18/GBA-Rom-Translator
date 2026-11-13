"""Per-glyph vertical alignment for BDF / font bin packing.

「一」等矮汉字要在墨迹框里居中；句读标点（，。！？…）应贴墨迹框底
（中文排版基线），不能跟着居中，否则图鉴说明里逗号/句号会浮在行中。
"""
from __future__ import annotations

from typing import Literal

Valign = Literal["top", "center", "bottom", "baseline"]

# 默认贴底的句读/点号（可被 --valign / overlays 覆盖）
DEFAULT_BOTTOM_CHARS: frozenset[str] = frozenset(
    "，。、！？：；.…‥·・,.;:!?"
    "／/．*%＊％＋＋＝＆＃@＠×÷±"
    "､｡､"
)


def parse_valign_map(spec: str | None) -> dict[str, Valign]:
    """Parse ``，=bottom;一=center`` or comma-separated pairs."""
    out: dict[str, Valign] = {}
    if not spec:
        return out
    for part in spec.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError(f"valign 项需 ch=mode，收到 {part!r}")
        ch, _, mode = part.partition("=")
        ch = ch.strip()
        mode = mode.strip().lower()
        if len(ch) != 1:
            raise ValueError(f"valign 左边必须是单字符，收到 {ch!r}")
        if mode not in ("top", "center", "bottom", "baseline"):
            raise ValueError(f"未知 valign {mode!r}（top|center|bottom|baseline）")
        out[ch] = mode  # type: ignore[assignment]
    return out


def resolve_valign(
    ch: str,
    overrides: dict[str, Valign] | None = None,
    *,
    default: Valign = "center",
) -> Valign:
    if overrides and ch in overrides:
        return overrides[ch]
    if ch in DEFAULT_BOTTOM_CHARS:
        return "bottom"
    return default
