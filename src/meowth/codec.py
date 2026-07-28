"""Text codec plugins — decode/encode/looks_like for the active game.

``extract/config.json`` (or translate/codec) may set ``encoding``:
  - ``pcs_gen3`` (default): Japanese Gen3 PCS via ``jp_pcs``
  - other ids: register via ``register_codec`` or return stubs until implemented
"""
from __future__ import annotations

from functools import lru_cache
from typing import Callable, Protocol


class TextCodec(Protocol):
    name: str

    def decode(self, raw: bytes) -> str: ...
    def looks_like_text(self, raw: bytes) -> bool: ...


_CODECS: dict[str, Callable[[], TextCodec]] = {}


def register_codec(name: str, factory: Callable[[], TextCodec]) -> None:
    _CODECS[name] = factory


class PcsGen3Codec:
    name = "pcs_gen3"

    def decode(self, raw: bytes) -> str:
        from .jp_pcs import decode_pcs

        return decode_pcs(raw)

    def looks_like_text(self, raw: bytes) -> bool:
        from .jp_pcs import looks_like_jp_text

        return looks_like_jp_text(raw)


register_codec("pcs_gen3", PcsGen3Codec)


def _encoding_name(game_id: str = "") -> str:
    from .config_loader import get_active_game_id, load_stage_config, STAGE_EXTRACT, STAGE_TRANSLATE
    from .policy import _cfg

    gid = (game_id or get_active_game_id() or "").strip()
    # Prefer extract/config.json encoding, then translate/config.json
    for stage in (STAGE_EXTRACT, STAGE_TRANSLATE):
        block = load_stage_config(gid, stage) if gid else {}
        enc = (block or {}).get("encoding")
        if enc:
            return str(enc).strip()
    # Legacy: nested under extraction already loaded
    enc = (_cfg(gid) or {}).get("encoding")
    if enc:
        return str(enc).strip()
    return "pcs_gen3"


@lru_cache(maxsize=8)
def get_codec(game_id: str = "") -> TextCodec:
    name = _encoding_name(game_id)
    factory = _CODECS.get(name)
    if factory is None:
        # Unknown encoding: fall back to pcs_gen3 so extract does not crash;
        # non-PCS packs should register a real codec before production use.
        factory = _CODECS["pcs_gen3"]
    return factory()


def decode_text(raw: bytes, game_id: str = "") -> str:
    return get_codec(game_id).decode(raw)


def looks_like_text(raw: bytes, game_id: str = "") -> bool:
    return get_codec(game_id).looks_like_text(raw)
