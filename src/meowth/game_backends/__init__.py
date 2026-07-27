"""Per-ROM game backends (Japanese Gen3 only).

Import flow: ROM header ``0xAC`` → game id → backend.
Shared pipeline (GUI / LLM / JSON) stays in ``meowth.core``;
extract / font / inject quirks live under each backend.
"""
from __future__ import annotations

from .base import GameBackend, UnsupportedGameError
from .registry import (
    detect_game,
    detect_game_code,
    get_backend,
    list_backends,
    read_game_code,
)

__all__ = [
    "GameBackend",
    "UnsupportedGameError",
    "detect_game",
    "detect_game_code",
    "get_backend",
    "list_backends",
    "read_game_code",
]
