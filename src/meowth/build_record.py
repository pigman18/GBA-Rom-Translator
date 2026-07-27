"""Record Meowth-AXVJ build version + patch tree for bisect/rollback."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config_loader import get_game_patch_dir

_ROOT = Path(__file__).resolve().parents[2]
_HISTORY = _ROOT / "build_history.jsonl"
_PYPROJECT = _ROOT / "pyproject.toml"

_KEY_SRC = (
    "src/meowth/policy.py",
    "src/meowth/seed_translate.py",
    "src/meowth/rom_writer.py",
    "src/meowth/font_patch.py",
    "src/meowth/core/engine.py",
    "src/meowth/table_patch.py",
)


def package_version() -> str:
    if _PYPROJECT.is_file():
        for line in _PYPROJECT.read_text(encoding="utf-8").splitlines():
            if line.startswith("version = "):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return "0.0.0"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _hash_tree(root: Path) -> tuple[str, dict[str, str]]:
    files: dict[str, str] = {}
    if not root.is_dir():
        return hashlib.sha256(b"").hexdigest(), files
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() in {".gba", ".sav", ".ss0", ".ss1", ".ss2"}:
            continue
        rel = p.relative_to(root).as_posix()
        files[rel] = _sha256_file(p)
    blob = "\n".join(f"{k}={v}" for k, v in files.items()).encode("utf-8")
    return hashlib.sha256(blob).hexdigest(), files


def _hash_key_src() -> dict[str, str]:
    out: dict[str, str] = {}
    for rel in _KEY_SRC:
        p = _ROOT / rel
        if p.is_file():
            out[rel] = _sha256_file(p)
    return out


def record_build(
    *,
    output_rom: Path,
    game: str,
    inject_stats: dict[str, Any] | None = None,
    notes: str = "",
) -> dict[str, Any]:
    """Write sidecar + history line; return the record dict."""
    output_rom = Path(output_rom)
    ver = package_version()
    try:
        patch_dir = get_game_patch_dir(game)
    except FileNotFoundError:
        patch_dir = _ROOT / "configs" / game.lower()
    patch_sha, patch_files = _hash_tree(patch_dir)
    src_hashes = _hash_key_src()
    rom_sha = _sha256_file(output_rom) if output_rom.is_file() else ""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    build_id = f"{ver}+{ts.replace(':', '').replace('-', '')[:15]}.{patch_sha[:12]}"

    record: dict[str, Any] = {
        "build_id": build_id,
        "package_version": ver,
        "timestamp_utc": ts,
        "game": game,
        "output_rom": str(output_rom.resolve()),
        "output_rom_sha256": rom_sha,
        "patch_root": str(patch_dir.as_posix()),
        "patch_tree_sha256": patch_sha,
        "patch_file_count": len(patch_files),
        "patch_files": patch_files,
        "key_src_sha256": src_hashes,
        "inject_stats": inject_stats or {},
        "notes": notes,
    }

    sidecar = output_rom.with_suffix(output_rom.suffix + ".build.json")
    if output_rom.suffix.lower() == ".gba":
        sidecar = Path(str(output_rom) + ".build.json")
    sidecar.write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    _HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with _HISTORY.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record
