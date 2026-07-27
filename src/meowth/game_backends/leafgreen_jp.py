"""Japanese LeafGreen (BPGJ) — stub."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import GameBackend, UnsupportedGameError


class LeafGreenJpBackend(GameBackend):
    id = "leafgreen_jp"
    name = "Pokémon LeafGreen (Japanese)"
    game_codes = ("BPGJ",)
    source_lang = "ja"
    implemented = False

    def extract(self, rom_path: Path, output_path: Path, **kwargs: Any) -> Path:
        raise UnsupportedGameError(
            "leafgreen_jp extract not implemented yet (BPGJ)."
        )
