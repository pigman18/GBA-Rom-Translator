"""Japanese FireRed (BPRJ) — stub."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import GameBackend, UnsupportedGameError


class FireRedJpBackend(GameBackend):
    id = "firered_jp"
    name = "Pokémon FireRed (Japanese)"
    game_codes = ("BPRJ",)
    source_lang = "ja"
    implemented = False

    def extract(self, rom_path: Path, output_path: Path, **kwargs: Any) -> Path:
        raise UnsupportedGameError(
            "firered_jp extract not implemented yet (BPRJ)."
        )
