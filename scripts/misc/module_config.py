#!/usr/bin/env python3
"""External module config manager for Meowth-GBA-Translator-JP.

Usage:
    python scripts/module_config.py list [--game POKEMON_RUBY_AXVJ00]
    python scripts/module_config.py preset [--game POKEMON_RUBY_AXVJ00]
    python scripts/module_config.py info <module_id> [--game POKEMON_RUBY_AXVJ00]
    python scripts/module_config.py check <module_ids...> [--game POKEMON_RUBY_AXVJ00]
"""

import argparse
import json
import sys
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent.parent / "configs"
DEFAULT_GAME = "POKEMON_RUBY_AXVJ00"


def _game_dir(game_id: str) -> Path:
    # Prefer per-game folder layout
    folder = CONFIG_DIR / game_id
    if folder.is_dir() and (folder / "game.json").is_file():
        return folder
    raise FileNotFoundError(
        f"Config folder not found for {game_id!r}. "
        f"Expected {folder / 'game.json'}"
    )


def _load_game(game_id: str) -> dict:
    path = _game_dir(game_id) / "game.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _load_modules(game_id: str) -> dict:
    path = _game_dir(game_id) / "modules.json"
    if not path.is_file():
        print(f"modules.json not found: {path}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data.get("modules"), dict):
        return data["modules"]
    return {k: v for k, v in data.items() if isinstance(v, dict) and k != "_meta"}


def cmd_list(game_id: str):
    cfg = _load_game(game_id)
    mods = _load_modules(game_id)
    presets = cfg.get("presets", {})
    print(f"Game: {cfg.get('label', game_id)} ({game_id})")
    print(f"Game codes: {cfg.get('game_codes', [])}")
    print()
    print("Modules:")
    for mid, meta in mods.items():
        dirty = "!" if meta.get("dirty") else " "
        default = "+" if meta.get("default") else " "
        group = meta.get("group", "")
        label = meta.get("label", mid)
        print(f"  [{default}{dirty}] {mid:20s} {label}  ({group})")
    print()
    print("Presets:")
    for name, mids in presets.items():
        df = " [default]" if name == cfg.get("default_preset") else ""
        print(f"  {name:20s}{df}: {', '.join(mids)}")


def cmd_preset(game_id: str):
    cfg = _load_game(game_id)
    mods = _load_modules(game_id)
    dp = cfg.get("default_preset", "safe")
    presets = cfg.get("presets", {})
    if dp in presets:
        print(f"Default preset: {dp}")
        print(f"Modules ({len(presets[dp])}):")
        for m in presets[dp]:
            meta = mods.get(m, {})
            print(f"  {m:20s} {meta.get('label', '')}")
    else:
        # Fall back to modules with default: true
        defaults = [mid for mid, m in mods.items() if m.get("default")]
        print(f"No presets in game.json; default:true modules ({len(defaults)}):")
        for m in defaults:
            print(f"  {m:20s} {mods[m].get('label', '')}")


def cmd_info(module_id: str, game_id: str):
    mods = _load_modules(game_id)
    if module_id not in mods:
        print(f"Module {module_id!r} not found", file=sys.stderr)
        sys.exit(1)
    m = mods[module_id]
    print(f"Module: {module_id}")
    print(f"  Label:  {m.get('label', '')}")
    print(f"  Group:  {m.get('group', '')}")
    print(f"  Default:{' yes' if m.get('default') else ' no'}")
    if m.get("description"):
        print(f"  Desc:   {m['description']}")
    if m.get("dirty"):
        print("  Dirty:  yes")
    if m.get("notes"):
        print(f"  Notes:  {m['notes']}")
    bands = m.get("addr_bands", [])
    if bands:
        print("  Address bands:")
        for lo, hi in bands:
            print(f"    {lo} - {hi}")


def cmd_check(module_ids: list[str], game_id: str):
    mods = _load_modules(game_id)
    bad = [m for m in module_ids if m not in mods]
    if bad:
        print(f"Unknown modules: {bad}", file=sys.stderr)
        sys.exit(1)
    for m in module_ids:
        meta = mods[m]
        print(f"  {m:20s} {meta.get('label', '')} [{meta.get('group', '')}]")
    print(f"\nAll {len(module_ids)} modules valid for {game_id}")


def main():
    parser = argparse.ArgumentParser(description="Meowth module config manager")
    parser.add_argument(
        "--game", default=DEFAULT_GAME, help=f"Game ID (default: {DEFAULT_GAME})"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List all modules and presets")
    sub.add_parser("preset", help="Show default preset / default modules")

    info_p = sub.add_parser("info", help="Show module details")
    info_p.add_argument("module_id")

    check_p = sub.add_parser("check", help="Validate module IDs")
    check_p.add_argument("module_ids", nargs="+")

    args = parser.parse_args()

    if args.command == "list":
        cmd_list(args.game)
    elif args.command == "preset":
        cmd_preset(args.game)
    elif args.command == "info":
        cmd_info(args.module_id, args.game)
    elif args.command == "check":
        cmd_check(args.module_ids, args.game)


if __name__ == "__main__":
    main()
