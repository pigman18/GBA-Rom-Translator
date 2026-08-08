"""ROM data asms from ``translate.build.json`` (armips .org, not game.bin).

Parallel tables:

- ``phrase_data.asm`` ← ``phrases``  → PhraseOffsets @ 0x08810000 / PhraseTable @ 0x08820000
- ``styles_data.asm`` ← ``styles`` + ``style_alloc``
  → StyleLeft[256] @ 0x0880F000

game.bin only needs rebuild when C/hook logic changes; changing style left or
phrases is asm + armips only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

# Must match game.h ADDR_STYLE_* / ADDR_PHRASE_*
ADDR_STYLE_LEFT = 0x0880F000
ADDR_PHRASE_OFFSETS = 0x08810000
ADDR_PHRASE_TABLE = 0x08820000

MAX_PHRASE_STREAM = 512


def load_build_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_styles_data_asm(
    build: dict[str, Any],
    out_path: Path,
) -> Path:
    """Emit ``styles_data.asm`` from build.json styles / style_alloc."""
    left_by_f9 = [0] * 256
    styles = build.get("styles") or {}
    alloc_raw = build.get("style_alloc") or {}
    if isinstance(styles, dict) and isinstance(alloc_raw, dict):
        for sid, code_s in alloc_raw.items():
            meta = styles.get(sid) or {}
            if not isinstance(meta, dict):
                continue
            try:
                code = int(str(code_s), 0) & 0xFF
            except (TypeError, ValueError):
                continue
            try:
                left = max(0, int(meta.get("left") or 0))
            except (TypeError, ValueError):
                left = 0
            if left > 255:
                left = 255
            left_by_f9[code] = left

    lines = [
        "; auto-generated from translate.build.json styles — do not edit",
        f".org 0x{ADDR_STYLE_LEFT:08X}",
        ".align 4",
        "StyleLeft:",
    ]
    for i in range(0, 256, 16):
        chunk = left_by_f9[i : i + 16]
        hex_bytes = ", ".join(f"0x{b:02X}" for b in chunk)
        comment = ""
        for j, b in enumerate(chunk):
            if b:
                comment = f"  ; +0x{i + j:02X}={b}"
                break
        lines.append(f"  .byte {hex_bytes}{comment}")

    lines.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return out_path


def write_phrase_data_asm(
    phrases: list[str | None],
    encode_fn: Callable[[str], bytes],
    out_path: Path,
) -> tuple[Path, int, int]:
    """Emit ``phrase_data.asm`` from build.json ``phrases`` list (index = code).

    Returns ``(path, phrase_count, stream_bytes)``.
    """
    texts = [s for s in phrases if s]
    if not texts and not phrases:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            f"; empty PhraseTable\n"
            f".org 0x{ADDR_PHRASE_OFFSETS:08X}\n"
            f".align 4\n"
            f"PhraseOffsets:\n"
            f"  .word 0\n"
            f"\n"
            f".org 0x{ADDR_PHRASE_TABLE:08X}\n"
            f".align 4\n"
            f"PhraseTable:\n"
            f"  .byte 0xFF\n",
            encoding="utf-8",
            newline="\n",
        )
        return out_path, 0, 0

    # Preserve code indices: phrases[i] may be None for holes
    if phrases and any(p is None for p in phrases):
        max_code = len(phrases)
        streams: list[bytes | None] = [None] * max_code
        for code, text in enumerate(phrases):
            if not text:
                continue
            stream = bytearray(encode_fn(str(text)))
            if not stream or stream[-1] != 0xFF:
                stream.append(0xFF)
            if len(stream) > MAX_PHRASE_STREAM:
                stream = stream[: MAX_PHRASE_STREAM - 1]
                stream.append(0xFF)
            streams[code] = bytes(stream)
        offsets: list[int] = []
        table_lines: list[str] = [".align 4", "PhraseTable:"]
        byte_cursor = 0
        for code in range(max_code):
            offsets.append(byte_cursor)
            stream = streams[code]
            if stream is None:
                stream = b"\xFF"
            for i in range(0, len(stream), 16):
                chunk = stream[i : i + 16]
                hex_bytes = ", ".join(f"0x{b:02X}" for b in chunk)
                suffix = f"  ; code={code} {len(stream)}B" if i == 0 else ""
                table_lines.append(f"  .byte {hex_bytes}{suffix}")
            byte_cursor += len(stream)
        offsets.append(byte_cursor)
        n_phrases = sum(1 for s in streams if s is not None)
    else:
        if phrases and all(isinstance(p, str) or p is None for p in phrases):
            ordered = [str(p) for p in phrases if p]
        else:
            ordered = [str(s) for s in texts]
        offsets = []
        table_lines = [".align 4", "PhraseTable:"]
        byte_cursor = 0
        for text in ordered:
            offsets.append(byte_cursor)
            stream = bytearray(encode_fn(text))
            if not stream or stream[-1] != 0xFF:
                stream.append(0xFF)
            if len(stream) > MAX_PHRASE_STREAM:
                stream = stream[: MAX_PHRASE_STREAM - 1]
                stream.append(0xFF)
            for i in range(0, len(stream), 16):
                chunk = stream[i : i + 16]
                hex_bytes = ", ".join(f"0x{b:02X}" for b in chunk)
                suffix = f"  ; {len(stream)}B" if i == 0 else ""
                table_lines.append(f"  .byte {hex_bytes}{suffix}")
            byte_cursor += len(stream)
        offsets.append(byte_cursor)
        n_phrases = len(ordered)

    asm_lines = [
        "; auto-generated from translate.build.json phrases — do not edit",
        f".org 0x{ADDR_PHRASE_OFFSETS:08X}",
        ".align 4",
        "PhraseOffsets:",
    ]
    for off in offsets:
        asm_lines.append(f"  .word {off}")
    asm_lines.append("")
    asm_lines.append(f".org 0x{ADDR_PHRASE_TABLE:08X}")
    asm_lines.extend(table_lines)
    asm_lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(asm_lines), encoding="utf-8", newline="\n")
    return out_path, n_phrases, offsets[-1] if offsets else 0


def emit_data_asms_from_build_json(
    build_json_path: Path,
    out_dir: Path,
    *,
    encode_fn: Callable[[str], bytes] | None = None,
    write_phrases: bool = True,
    write_styles: bool = True,
) -> dict[str, Any]:
    """Write phrase_data.asm + styles_data.asm under ``out_dir`` from build.json."""
    build = load_build_json(build_json_path)
    stats: dict[str, Any] = {"build_json": str(build_json_path)}
    out_dir.mkdir(parents=True, exist_ok=True)

    if write_styles:
        styles_path = out_dir / "styles_data.asm"
        write_styles_data_asm(build, styles_path)
        stats["styles_data"] = str(styles_path)

    if write_phrases and encode_fn is not None:
        phrases = build.get("phrases") or []
        if isinstance(phrases, list):
            phrase_path = out_dir / "phrase_data.asm"
            _, n, nbytes = write_phrase_data_asm(phrases, encode_fn, phrase_path)
            stats["phrase_data"] = str(phrase_path)
            stats["phrase_count"] = n
            stats["phrase_bytes"] = nbytes

    return stats
