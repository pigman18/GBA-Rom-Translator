"""Seed / offline translate extracts (no API required for known UI).

Exact seeds: ``configs/{ROM_ID}/translate/lexicon/`` (+ optional resources glossaries).
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_GLOSSARY_PATH = (
    Path(__file__).resolve().parents[2] / "resources" / "glossary_ja_zh-Hans.json"
)
_ITEM_DESC_SEEDS_PATH = (
    Path(__file__).resolve().parents[2] / "resources" / "item_desc_seeds.json"
)


@lru_cache(maxsize=1)
def _ja_zh_glossary() -> dict[str, str]:
    """PokeAPI JA→ZH terms (moves/items/abilities/types/species)."""
    if not _GLOSSARY_PATH.is_file():
        return {}
    try:
        data = json.loads(_GLOSSARY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(data.get("source_to_target") or {})


@lru_cache(maxsize=1)
def _compact_glossary() -> dict[str, str]:
    """Whitespace-stripped glossary keys for flavor/desc matching."""
    out: dict[str, str] = {}
    for ja, zh in _ja_zh_glossary().items():
        ck = re.sub(r"[\s\u3000]+", "", ja)
        if ck and ck not in out:
            out[ck] = zh
    return out


@lru_cache(maxsize=1)
def _item_desc_seeds() -> dict[str, str]:
    if not _ITEM_DESC_SEEDS_PATH.is_file():
        return {}
    try:
        return dict(json.loads(_ITEM_DESC_SEEDS_PATH.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return {}


@lru_cache(maxsize=4)
def _lexicon(game_id: str) -> dict[str, str]:
    from .config_loader import load_custom_translations

    if not game_id:
        return {}
    return dict(load_custom_translations(game_id))


@lru_cache(maxsize=4)
def _lexicon_compact(game_id: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for ja, zh in _lexicon(game_id).items():
        ck = re.sub(r"[\s\u3000\n\r]+", "", ja)
        if ck and ck not in out:
            out[ck] = zh
    return out


def _normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


_FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")


def _seed_route_name(compact: str) -> str | None:
    """Fullwidth-digit route names: １０１ばんどうろ → 101号道路."""
    m = re.fullmatch(r"([０-９]+)ばん(どうろ|すいどう)", compact)
    if not m:
        return None
    num = m.group(1).translate(_FULLWIDTH_DIGITS)
    kind = "道路" if m.group(2) == "どうろ" else "水路"
    return f"{num}号{kind}"


def seed_translate_entry(original: str) -> str | None:
    key = _normalize_ws(original.replace("\n", "").replace("\r", ""))
    compact = key.replace(" ", "")
    from .config_loader import get_active_game_id

    gid = get_active_game_id() or ""
    lex = _lexicon(gid)
    if original in lex:
        return lex[original]
    if key in lex:
        return lex[key]
    if compact in lex:
        return lex[compact]
    lex_c = _lexicon_compact(gid)
    if compact in lex_c:
        return lex_c[compact]
    # Name tables / short terms from PokeAPI glossary
    gloss = _ja_zh_glossary()
    if original in gloss:
        return gloss[original]
    if key in gloss:
        return gloss[key]
    if compact in gloss:
        return gloss[compact]
    # Item bag descriptions (ROM-faithful seeds)
    idesc = _item_desc_seeds()
    if original in idesc:
        return idesc[original]
    if key in idesc:
        return idesc[key]
    for ja, zh in idesc.items():
        if re.sub(r"[\s\u3000\n\r]+", "", ja) == compact:
            return zh
    # Flavor/desc lines: match ignoring whitespace / fullwidth spaces
    compact_gloss = _compact_glossary()
    if compact in compact_gloss:
        return compact_gloss[compact]
    route = _seed_route_name(compact)
    if route:
        return route
    return None


def looks_like_failed_zh_translation(original: str, translated: str) -> bool:
    """True when a ja→zh result is still Japanese dialogue (format-only fake)."""
    if not translated:
        return True
    if not re.search(r"[\u3040-\u30ff]", original or ""):
        return False
    if re.search(r"[\u4e00-\u9fff]", translated):
        return False
    # Still kana, no Hanzi — not a usable Simplified Chinese line
    return bool(re.search(r"[\u3040-\u30ff]", translated))


def seed_translate_file(inp: Path, out: Path, *, only_seeded: bool = False) -> tuple[int, int]:
    data = json.loads(Path(inp).read_text(encoding="utf-8"))
    entries = data.get("entries") or []
    if not entries and "free_texts" in data:
        entries = list(data.get("free_texts") or [])
        for t in data.get("tables") or []:
            entries.extend(t.get("entries") or [])

    n_seed = 0
    n_total = len(entries)
    kept = []
    for e in entries:
        orig = e.get("original", "")
        if e.get("translated"):
            kept.append(e)
            n_seed += 1
            continue
        zh = seed_translate_entry(orig)
        if zh:
            e["translated"] = zh
            n_seed += 1
            kept.append(e)
        elif not only_seeded:
            kept.append(e)

    if only_seeded:
        data["entries"] = kept
        data.pop("tables", None)
        data.pop("free_texts", None)
        data["count"] = len(kept)
    else:
        data["entries"] = entries

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return n_seed, n_total
