"""Japanese Emerald (BPEJ) — stub."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import GameBackend, UnsupportedGameError


class EmeraldJpBackend(GameBackend):
    id = "emerald_jp"
    name = "Pokémon Emerald (Japanese)"
    game_codes = ("BPEJ",)
    source_lang = "ja"
    implemented = False

    def extract(self, rom_path: Path, output_path: Path, **kwargs: Any) -> Path:
        raise UnsupportedGameError(
            "emerald_jp extract not implemented yet (BPEJ)."
        )
