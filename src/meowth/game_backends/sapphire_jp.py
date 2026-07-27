"""Japanese Sapphire (AXPJ) — stub."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import GameBackend, UnsupportedGameError


class SapphireJpBackend(GameBackend):
    id = "sapphire_jp"
    name = "Pokémon Sapphire (Japanese)"
    game_codes = ("AXPJ",)
    source_lang = "ja"
    implemented = False

    def extract(self, rom_path: Path, output_path: Path, **kwargs: Any) -> Path:
        raise UnsupportedGameError(
            "sapphire_jp extract not implemented yet (AXPJ). "
            "Fill game_backends/sapphire_jp after ruby_jp is stable."
        )
