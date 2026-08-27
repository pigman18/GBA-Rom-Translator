"""Japanese Sapphire (AXPJ) — RS 族，与 Ruby 共用 Meowth 流水线。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import GameBackend


class SapphireJpBackend(GameBackend):
    id = "POKEMON_SAPP_AXPJ00"
    name = "Pokémon Sapphire (Japanese)"
    game_codes = ("AXPJ",)
    source_lang = "ja"
    implemented = True

    def extract(self, rom_path: Path, output_path: Path, **kwargs: Any) -> Path:
        import warnings

        warnings.warn(
            "SapphireJpBackend.extract is deprecated; use texts_patcher → texts.json",
            DeprecationWarning,
            stacklevel=2,
        )
        from ..extract import extract_axvj

        return extract_axvj(rom_path, output_path, game_id=self.id, modules=kwargs.get("modules"))
