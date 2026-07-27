"""AXVJ Geo layer — ROM address-band filters for inject bisect.

「缩小范围」= 收窄注入目标的地址区间，不是关掉整个 script 域。

Env (build-time):

  MEOWTH_AXVJ_ADDR_INCLUDE=0x100000-0x180000,0x1a0000-0x200000
      仅注入落在这些闭区间内的条目（可多项，逗号分隔）。

  MEOWTH_AXVJ_ADDR_EXCLUDE=0x104000-0x106000
      从候选中剔除这些区间（在 INCLUDE 之后应用）。

  MEOWTH_AXVJ_ADDR_OMIT_BAND=3/10
      按地址排序后均分成 N 带，整带剔除第 K 带（0-based）。
      用于 leave-one-out 黑屏二分；与 INCLUDE/EXCLUDE 可叠加（先算带，再套区间）。
"""
from __future__ import annotations

import os
import re
from typing import Any

_BAND_RE = re.compile(
    r"^\s*(0x[0-9a-fA-F]+|\d+)\s*-\s*(0x[0-9a-fA-F]+|\d+)\s*$"
)
_OMIT_RE = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*$")


def parse_int(token: str) -> int:
    t = token.strip().lower()
    if t.startswith("0x"):
        return int(t, 16)
    return int(t, 10)


def parse_bands(spec: str | None) -> list[tuple[int, int]]:
    """Parse ``lo-hi,lo-hi`` into inclusive ``(lo, hi)`` pairs."""
    if not (spec or "").strip():
        return []
    out: list[tuple[int, int]] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        m = _BAND_RE.match(part)
        if not m:
            raise ValueError(
                f"bad address band {part!r}; want lo-hi (e.g. 0x100000-0x180000)"
            )
        lo, hi = parse_int(m.group(1)), parse_int(m.group(2))
        if hi < lo:
            lo, hi = hi, lo
        out.append((lo, hi))
    return out


def parse_omit_band(spec: str | None) -> tuple[int, int] | None:
    """Parse ``K/N`` → (omit_index, n_bands). None if unset."""
    if not (spec or "").strip():
        return None
    m = _OMIT_RE.match(spec)
    if not m:
        raise ValueError(
            f"bad OMIT_BAND {spec!r}; want K/N (e.g. 3/10, 0-based K)"
        )
    k, n = int(m.group(1)), int(m.group(2))
    if n < 2:
        raise ValueError(f"OMIT_BAND N must be >= 2, got {n}")
    if not (0 <= k < n):
        raise ValueError(f"OMIT_BAND K must be in [0, {n}), got {k}")
    return k, n


def entry_rom_addr(entry: dict[str, Any]) -> int | None:
    raw = entry.get("address")
    if raw is None or raw == "":
        return None
    if isinstance(raw, int):
        return int(raw) & 0x1FFFFFF
    s = str(raw).strip().lower().replace("0x", "")
    try:
        return int(s, 16) & 0x1FFFFFF
    except ValueError:
        return None


def addr_in_bands(addr: int, bands: list[tuple[int, int]]) -> bool:
    return any(lo <= addr <= hi for lo, hi in bands)


def geo_filter_from_env() -> dict[str, Any]:
    """Snapshot of Geo env knobs for logging / build.json."""
    return {
        "include": os.environ.get("MEOWTH_AXVJ_ADDR_INCLUDE", "").strip(),
        "exclude": os.environ.get("MEOWTH_AXVJ_ADDR_EXCLUDE", "").strip(),
        "omit_band": os.environ.get("MEOWTH_AXVJ_ADDR_OMIT_BAND", "").strip(),
    }


def filter_entries_by_geo(
    entries: list[dict[str, Any]],
    *,
    include_spec: str | None = None,
    exclude_spec: str | None = None,
    omit_band_spec: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply Geo address filters. Returns (kept, meta)."""
    include_spec = (
        include_spec
        if include_spec is not None
        else os.environ.get("MEOWTH_AXVJ_ADDR_INCLUDE", "")
    )
    exclude_spec = (
        exclude_spec
        if exclude_spec is not None
        else os.environ.get("MEOWTH_AXVJ_ADDR_EXCLUDE", "")
    )
    omit_band_spec = (
        omit_band_spec
        if omit_band_spec is not None
        else os.environ.get("MEOWTH_AXVJ_ADDR_OMIT_BAND", "")
    )

    include = parse_bands(include_spec)
    exclude = parse_bands(exclude_spec)
    omit = parse_omit_band(omit_band_spec)

    meta: dict[str, Any] = {
        "include": include_spec.strip() if include_spec else "",
        "exclude": exclude_spec.strip() if exclude_spec else "",
        "omit_band": omit_band_spec.strip() if omit_band_spec else "",
        "before": len(entries),
        "after": len(entries),
        "omit_range": None,
    }

    if not include and not exclude and omit is None:
        return list(entries), meta

    work = list(entries)

    if omit is not None:
        k, n = omit
        indexed: list[tuple[int, int, dict[str, Any]]] = []
        for i, e in enumerate(work):
            addr = entry_rom_addr(e)
            if addr is None:
                continue
            indexed.append((addr, i, e))
        indexed.sort(key=lambda t: (t[0], t[1]))
        m = len(indexed)
        if m == 0:
            meta["after"] = 0
            return [], meta
        # Equal-count bands; last band absorbs remainder.
        base, rem = divmod(m, n)
        bounds: list[tuple[int, int]] = []
        cursor = 0
        for bi in range(n):
            size = base + (1 if bi < rem else 0)
            bounds.append((cursor, cursor + size))
            cursor += size
        lo_i, hi_i = bounds[k]
        if lo_i < hi_i:
            omit_lo = indexed[lo_i][0]
            omit_hi = indexed[hi_i - 1][0]
            meta["omit_range"] = {
                "k": k,
                "n": n,
                "count": hi_i - lo_i,
                "addr_lo": f"0x{omit_lo:X}",
                "addr_hi": f"0x{omit_hi:X}",
            }
            drop_ids = {id(indexed[j][2]) for j in range(lo_i, hi_i)}
            work = [e for e in work if id(e) not in drop_ids]
        else:
            meta["omit_range"] = {"k": k, "n": n, "count": 0}

    if include:
        work = [
            e
            for e in work
            if (a := entry_rom_addr(e)) is not None and addr_in_bands(a, include)
        ]
    if exclude:
        work = [
            e
            for e in work
            if (a := entry_rom_addr(e)) is None or not addr_in_bands(a, exclude)
        ]

    meta["after"] = len(work)
    return work, meta
