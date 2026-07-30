#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
text_patcher.py
===============
从日版 Gen3 GBA ROM 导出文本 addr_bands，并按 configs/{ROM_ID}.json 归类 modules。

用法：
  python text_patcher.py rom.gba

配置：
  configs/POKEMON_RUBY_AXVJ00.json   ← 按 ROM id 命名的 module_map

输出：
  works/POKEMON_RUBY_AXVJ00/addr_bands.json
  works/POKEMON_RUBY_AXVJ00/modules.json
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from assign_modules import assign_bands, load_module_map

SUPPORTED = {
    b"AXVJ": "Pokemon Ruby (JP)",
    b"AXPJ": "Pokemon Sapphire (JP)",
    b"BPEJ": "Pokemon Emerald (JP)",
    b"BPRJ": "Pokemon FireRed (JP)",
    b"BPGJ": "Pokemon LeafGreen (JP)",
}

# game_code → 标准 ROM id（与 configs / works 目录名一致）
ROM_ID_BY_CODE = {
    "AXVJ": "POKEMON_RUBY_AXVJ00",
    "AXPJ": "POKEMON_SAPP_AXPJ00",
    "BPRJ": "POKEMON_FIRE_BPRJ00",
    "BPGJ": "POKEMON_LEAF_BPGJ00",
    "BPEJ": "POKEMON_EMERALD_BPEJ00",
}

BASE = 0x08000000
EOS = 0xFF
CTRL = {0xFA, 0xFB, 0xFC, 0xFD, 0xFE, 0xFF}
BODY_LO = 0x100000
MIN_LEN = 2
MAX_LEN = 512
PTR_ALIGN = 4
MERGE_GAP = 0

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIGS_DIR = SCRIPT_DIR / "configs"
WORKS_DIR = SCRIPT_DIR / "works"


def identify(rom: bytes) -> Tuple[bytes, str]:
    if len(rom) < 0xB0:
        raise ValueError("ROM too small")
    code = rom[0xAC:0xB0]
    if code not in SUPPORTED:
        raise ValueError(
            f"Unsupported game code {code!r}; need "
            + ", ".join(k.decode() for k in SUPPORTED)
        )
    return code, SUPPORTED[code]


def resolve_rom_id(rom_path: Path, game_code: str) -> str:
    """优先用已知文件名 stem，否则按 game code 映射。"""
    stem = rom_path.stem
    if stem in ROM_ID_BY_CODE.values():
        return stem
    rid = ROM_ID_BY_CODE.get(game_code)
    if not rid:
        raise ValueError(f"no ROM id for game code {game_code}")
    return rid


def u32(rom: bytes, off: int) -> int:
    return struct.unpack_from("<I", rom, off)[0]


def read_pcs(rom: bytes, start: int, max_len: int = 512) -> Optional[bytes]:
    if start < 0 or start >= len(rom):
        return None
    i = start
    n = len(rom)
    while i < n and i - start < max_len:
        b = rom[i]
        i += 1
        if b == EOS:
            raw = rom[start:i]
            return bytes(raw) if len(raw) >= 2 else None
        if b == 0xFC and i < n:
            i += 1
            continue
        if b == 0xFD and i < n:
            i += 1
            continue
    return None


def pcs_looks_plausible(raw: bytes) -> bool:
    if not raw or raw[-1] != EOS:
        return False
    body = raw[:-1]
    if not body:
        return False
    if body.count(0x00) > len(body) * 0.4:
        return False
    if len(body) >= 8 and len(set(body)) == 1 and body[0] not in CTRL:
        return False
    printable = sum(1 for b in body if b not in CTRL and 0x01 <= b <= 0xF6)
    return (printable / len(body)) >= 0.45


def prev_ok_for_string_start(rom: bytes, so: int) -> bool:
    if so <= 0:
        return True
    prev = rom[so - 1]
    if prev in (0x00, 0xFF, 0xFE, 0xFA, 0xFB, 0xAA, 0xBB):
        return True
    if prev >= 0xF7:
        return True
    return False


def collect_pointer_targets(rom: bytes, body_hi: int) -> Dict[int, List[int]]:
    body_hi = min(body_hi, len(rom))
    hits: Dict[int, List[int]] = {}
    off = 0
    while off + 4 <= len(rom):
        step = 1 if 0x100000 <= off < 0x200000 else max(1, PTR_ALIGN)
        v = u32(rom, off)
        if not (BASE <= v < BASE + len(rom)):
            off += step
            continue
        so = v - BASE
        if not (BODY_LO <= so < body_hi):
            off += step
            continue
        if so <= off < so + 2:
            off += step
            continue
        if not prev_ok_for_string_start(rom, so):
            off += step
            continue
        raw = read_pcs(rom, so, MAX_LEN + 1)
        if raw is None:
            off += step
            continue
        body_len = len(raw) - 1
        if body_len < MIN_LEN or body_len > MAX_LEN:
            off += step
            continue
        if not pcs_looks_plausible(raw):
            off += step
            continue
        hits.setdefault(so, []).append(off)
        off += step
    return hits


def blocks_from_hits(
    rom: bytes, hits: Dict[int, List[int]]
) -> List[Tuple[int, int]]:
    blocks: List[Tuple[int, int]] = []
    for so in sorted(hits):
        raw = read_pcs(rom, so, MAX_LEN + 1)
        if not raw:
            continue
        blocks.append((so, so + len(raw) - 1))
    return blocks


def merge_bands(
    blocks: Sequence[Tuple[int, int]], gap: int
) -> List[Tuple[int, int]]:
    if not blocks:
        return []
    ordered = sorted(blocks)
    out: List[Tuple[int, int]] = []
    cs, ce = ordered[0]
    for s, e in ordered[1:]:
        if s <= ce + 1 + gap:
            ce = max(ce, e)
        else:
            out.append((cs, ce))
            cs, ce = s, e
    out.append((cs, ce))
    return out


def config_path_for(rom_id: str) -> Path:
    return CONFIGS_DIR / f"{rom_id}.json"


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: python text_patcher.py <rom.gba>", file=sys.stderr)
        sys.exit(0 if len(sys.argv) == 2 else 1)

    rom_path = Path(sys.argv[1])
    if not rom_path.is_file():
        print(f"[x] not found: {rom_path}", file=sys.stderr)
        sys.exit(1)

    rom = rom_path.read_bytes()
    code, name = identify(rom)
    game_code = code.decode("ascii")
    rom_id = resolve_rom_id(rom_path, game_code)
    work_dir = WORKS_DIR / rom_id

    hits = collect_pointer_targets(rom, body_hi=len(rom))
    blocks = blocks_from_hits(rom, hits)
    bands = merge_bands(blocks, MERGE_GAP)

    bands_path = work_dir / "addr_bands.json"
    bands_doc = {
        "_meta": {
            "rom_id": rom_id,
            "source_rom_path": str(rom_path.resolve()),
            "source_rom": name,
            "game_code": game_code,
            "address_space": "file_offset",
            "string_blocks": len(blocks),
            "band_count": len(bands),
            "ptr_backed_starts": len(hits),
            "exported_by": "text_patcher.py",
        },
        "addr_bands": [[f"0x{s:08X}", f"0x{e:08X}"] for s, e in bands],
    }
    write_json(bands_path, bands_doc)
    print(f"[ok] {len(blocks)} strings -> {len(bands)} addr_bands -> {bands_path}")

    map_path = config_path_for(rom_id)
    modules_path = work_dir / "modules.json"
    if not map_path.is_file():
        print(
            f"[!] missing config {map_path}; skip modules.json "
            f"(copy configs/_template.json -> configs/{rom_id}.json)",
            file=sys.stderr,
        )
        return

    mmap = load_module_map(map_path)
    result = assign_bands(bands, mmap)
    result["_meta"]["rom_id"] = rom_id
    result["_meta"]["source_rom_path"] = str(rom_path.resolve())
    result["_meta"]["game_code"] = game_code
    result["_meta"]["module_map"] = str(map_path.resolve())
    result["_meta"]["exported_by"] = "text_patcher.py"
    write_json(modules_path, result)

    counts = result["_meta"]["module_band_counts"]
    nonempty = sum(1 for v in counts.values() if v)
    print(f"[ok] modules ({nonempty} nonempty) via {map_path.name} -> {modules_path}")


if __name__ == "__main__":
    main()
