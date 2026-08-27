"""Map ROM header codes → backends (JP Gen3)."""
from __future__ import annotations

from pathlib import Path

from .base import GameBackend, UnsupportedGameError
from .emerald_jp import EmeraldJpBackend
from .firered_jp import FireRedJpBackend
from .leafgreen_jp import LeafGreenJpBackend
from .ruby_jp import RubyJpBackend
from .sapphire_jp import SapphireJpBackend

# US / out-of-scope codes → explicit reject (this fork is JP-only).
_US_REJECT: dict[str, str] = {
    "BPRE": "firered (US)",
    "BPGE": "leafgreen (US)",
    "BPEE": "emerald (US)",
    "AXVE": "ruby (US)",
    "AXPE": "sapphire (US)",
}

_BACKENDS: list[GameBackend] = [
    RubyJpBackend(),
    SapphireJpBackend(),
    EmeraldJpBackend(),
    FireRedJpBackend(),
    LeafGreenJpBackend(),
]

_BY_ID: dict[str, GameBackend] = {b.id: b for b in _BACKENDS}
_BY_CODE: dict[str, GameBackend] = {}
for _b in _BACKENDS:
    for _code in _b.game_codes:
        _BY_CODE[_code] = _b


def read_game_code(rom_path: Path) -> str:
    with open(rom_path, "rb") as f:
        f.seek(0xAC)
        return f.read(4).decode("ascii", errors="replace")


def detect_game_code(rom_path: Path) -> str:
    """Return raw 4-letter code from ROM header."""
    return read_game_code(rom_path)


def detect_game(rom_path: Path, *, reject_us: bool = True) -> str:
    """Return backend id (``POKEMON_RUBY_AXVJ00``, …) or ``unknown``.

    If ``reject_us`` and the ROM is a US Gen3 title, raises
    ``UnsupportedGameError`` (this tree targets JP ROMs in ``roms/origin``).
    """
    code = read_game_code(rom_path)
    if reject_us and code in _US_REJECT:
        raise UnsupportedGameError(
            f"US ROM {code} ({_US_REJECT[code]}) is out of scope; "
            f"use Japanese ROMs (AXVJ/AXPJ/BPEJ/BPRJ/BPGJ)."
        )
    backend = _BY_CODE.get(code)
    if backend is None:
        return "unknown"
    return backend.id


def get_backend(game_id: str) -> GameBackend:
    if game_id not in _BY_ID:
        raise KeyError(f"unknown game backend: {game_id}")
    return _BY_ID[game_id]


def get_backend_for_rom(rom_path: Path) -> GameBackend:
    game_id = detect_game(rom_path)
    if game_id == "unknown":
        code = read_game_code(rom_path)
        raise UnsupportedGameError(f"unsupported ROM header code: {code!r}")
    return get_backend(game_id)


def list_backends() -> list[GameBackend]:
    return list(_BACKENDS)
