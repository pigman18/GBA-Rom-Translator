"""Japanese Ruby (AXVJ) 鈥?implemented."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import GameBackend


class RubyJpBackend(GameBackend):
    id = "POKEMON_RUBY_AXVJ00"
    name = "Pok茅mon Ruby (Japanese)"
    game_codes = ("AXVJ",)
    source_lang = "ja"
    implemented = True

    def extract(self, rom_path: Path, output_path: Path, **kwargs: Any) -> Path:
        import warnings

        warnings.warn(
            "RubyJpBackend.extract is deprecated; use texts_patcher → texts.json",
            DeprecationWarning,
            stacklevel=2,
        )
        from ..extract import extract_axvj

        return extract_axvj(rom_path, output_path, game_id=self.id, modules=kwargs.get("modules"))
