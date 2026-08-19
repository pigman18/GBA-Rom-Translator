#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regenerate the ADDR_* block in hook/src/game.h from hook/game_addrs.asm.

game_addrs.asm is the single source of truth for hook addresses. Equ lines
with a trailing ``; C: ADDR_X`` marker expose the value to the C layer; this
script rewrites the ``// <<<GEN_ADDR>>>`` block in game.h from those markers.

Usage:
    python scripts/gen_game_h_from_addrs.py [--game POKEMON_RUBY_AXVJ00]
    python scripts/gen_game_h_from_addrs.py --check   # fail if game.h is stale

Run before build.bat any time game_addrs.asm changes.
"""
import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_GAME = "POKEMON_RUBY_AXVJ00"

BEGIN = "// <<<GEN_ADDR>>>"
END = "// <<<GEN_ADDR_END>>>"

# name  equ 0xADDR   ; ... C: ADDR_MACRO
_EQU_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s+equ\s+"
    r"(?P<addr>0x[0-9A-Fa-f]+)\s*;.*\bC:\s*(?P<mac>ADDR_[A-Za-z0-9_]+)\s*$"
)


def collect(game_root: Path) -> dict[str, str]:
    """Return {ADDR_MACRO: 0xVALUE} from game_addrs.asm C: markers."""
    asm = game_root / "game_addrs.asm"
    if not asm.is_file():
        raise FileNotFoundError(f"missing {asm}")
    out: dict[str, str] = {}
    for ln in asm.read_text(encoding="utf-8").splitlines():
        m = _EQU_RE.match(ln)
        if not m:
            continue
        mac, addr = m.group("mac"), m.group("addr")
        if mac in out and out[mac] != addr:
            raise SystemExit(f"conflict for {mac}: {out[mac]} vs {addr} in {asm}")
        out[mac] = addr
    if not out:
        raise SystemExit(
            f"no ; C: ADDR_* markers found in {asm} — nothing to generate"
        )
    return out


def render_block(macros: dict[str, str]) -> str:
    lines = [
        BEGIN,
        "/* Auto-generated from game_addrs.asm by scripts/gen_game_h_from_addrs.py.",
        " * Do not edit by hand. Change the address in game_addrs.asm; `; C:` marker",
        " * on the equ line sets the ADDR_* macro name. */",
    ]
    for mac in sorted(macros):
        val = int(macros[mac], 16)
        lines.append(f"#define {mac:<34s} 0x{val:08X}u")
    lines.append(END)
    return "\n".join(lines)


def update_game_h(game_root: Path, macros: dict[str, str], check: bool = False) -> bool:
    h_path = game_root / "src" / "game.h"
    if not h_path.is_file():
        raise FileNotFoundError(f"missing {h_path}")
    text = h_path.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        raise SystemExit(
            f"game.h missing {BEGIN}/{END} markers — add them before running"
        )
    head, rest = text.split(BEGIN, 1)
    tail = rest.split(END, 1)[1]
    new_text = head + render_block(macros) + tail
    if new_text == text:
        return False
    if check:
        raise SystemExit(f"STALE: {h_path} ADDR_* block differs from {game_root.name}/game_addrs.asm")
    h_path.write_text(new_text, encoding="utf-8")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game", default=DEFAULT_GAME, help="configs/<game> dir name")
    ap.add_argument(
        "--check",
        action="store_true",
        help="fail (exit 1) if game.h ADDR_* block is out of date",
    )
    args = ap.parse_args()

    game_root = REPO / "configs" / args.game / "hook"
    if not game_root.is_dir():
        raise SystemExit(f"hook dir not found: {game_root}")
    macros = collect(game_root)
    try:
        changed = update_game_h(game_root, macros, check=args.check)
    except SystemExit:
        raise
    print(
        ("verified" if args.check else "written" if changed else "up-to-date")
        + f": {len(macros)} ADDR_* macros from {args.game}/hook/game_addrs.asm"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())