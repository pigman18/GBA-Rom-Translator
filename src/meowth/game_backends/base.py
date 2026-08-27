"""Game backend protocol."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class UnsupportedGameError(RuntimeError):
    """ROM game code is known but not implemented / not in scope."""


class GameBackend(ABC):
    """One ROM family (e.g. AXVJ Japanese Ruby)."""

    #: Internal id used in config / JSON (``POKEMON_RUBY_AXVJ00``, ``POKEMON_SAPP_AXPJ00``, …)
    id: str
    #: Human label
    name: str
    #: ROM header codes (4 chars at 0xAC), e.g. ``("AXVJ",)``
    game_codes: tuple[str, ...]
    #: Default source language for extract/translate
    source_lang: str = "ja"
    #: Whether extract/inject/font are implemented
    implemented: bool = False

    @abstractmethod
    def extract(self, rom_path: Path, output_path: Path, **kwargs: Any) -> Path:
        """Extract texts to JSON at ``output_path``."""

    def prepare_config(self, config: Any) -> None:
        """Adjust ``TranslationConfig`` after detection (source lang, etc.)."""
        if getattr(config, "source_lang", None) in (None, "", "en"):
            config.source_lang = self.source_lang
