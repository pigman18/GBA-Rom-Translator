"""PCS control code protection for translation (stage ``translate/``).

Reads ``translate/config.json`` → ``protect`` via :func:`load_codec`.
Related: font/charmap encodes the restored control codes at build; do not
strip codes here that font/patch still need (FD/FC/macros).
"""

from __future__ import annotations

import re
from typing import Any

from .pcs_codes import CONTROL_CODE_REGEX

# Gen3/HMA defaults when codec.json is absent
_DEFAULT_LINE_WIDTH = 32
_DEFAULT_SEMANTIC_RATIO = 0.75
_DEFAULT_PARAGRAPH_CODES = ("\\.", "\\p")
_DEFAULT_STRIP_LAYOUT = ("\\l", "\\n")

# Pattern to strip control codes / escape sequences for visible-length calc
_INVISIBLE_RE = re.compile(
    r"\\btn[0-9A-Fa-f]{2}"
    r"|\\CC[0-9A-Fa-f]{4}"
    r"|\\B[0-9A-Fa-f]"
    r"|\\\?[0-9A-Fa-f]{2}"
    r"|\\[.plnr]"
    r"|\[[a-zA-Z_]\w*\]"
)


def _protect_cfg() -> dict[str, Any]:
    try:
        from .config_loader import load_codec

        return dict(load_codec().get("protect") or {})
    except Exception:
        return {}


def _line_width() -> int:
    cfg = _protect_cfg()
    return int(cfg.get("line_width", _DEFAULT_LINE_WIDTH))


def _semantic_threshold() -> int:
    cfg = _protect_cfg()
    ratio = float(cfg.get("semantic_threshold_ratio", _DEFAULT_SEMANTIC_RATIO))
    return int(_line_width() * ratio)


def _paragraph_codes() -> tuple[str, ...]:
    cfg = _protect_cfg()
    raw = cfg.get("paragraph_codes")
    if not raw:
        return _DEFAULT_PARAGRAPH_CODES
    return tuple(str(x) for x in raw)


def _strip_layout_codes() -> tuple[str, ...]:
    cfg = _protect_cfg()
    raw = cfg.get("strip_layout_codes")
    if not raw:
        return _DEFAULT_STRIP_LAYOUT
    return tuple(str(x) for x in raw)


def _visible_length(line: str) -> int:
    """Return the visible character count of a line, ignoring control codes."""
    stripped = _INVISIBLE_RE.sub("", line)
    return len(stripped)


def _classify_newlines(text: str) -> str:
    """Replace newlines with semantic breaks or spaces.

    Three-level classification:
    - \\n\\n → paragraph break (page break in GBA, keep as \\n\\n)
    - \\n where the preceding line is short (< threshold)
      → semantic newline (same text box, keep as \\n)
    - \\n where the preceding line is long (filled the text box)
      → layout wrap (replace with space)
    """
    _PARA = "\x00PARA\x00"
    text = text.replace("\n\n", _PARA)
    threshold = _semantic_threshold()

    lines = text.split("\n")
    result_parts = []
    for i, line in enumerate(lines):
        result_parts.append(line)
        if i < len(lines) - 1:
            clean_line = line.replace(_PARA, "")
            vis_len = _visible_length(clean_line)
            if vis_len < threshold:
                result_parts.append("\n")
            else:
                result_parts.append(" ")

    result = "".join(result_parts)
    result = result.replace(_PARA, "\n\n")
    return result


def protect(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Replace control codes with numbered placeholders.

    Handles both HMA backslash codes and actual newline chars.
    Intelligently classifies literal newlines (three levels):
    - \\n\\n = paragraph break (page break / clear box)
    - short line + \\n = semantic newline (new line within same box)
    - long line + \\n = layout wrap (join with space, remove)

    Returns (protected_text, [(placeholder, original), ...])
    """
    codes: list[tuple[str, str]] = []

    def make_placeholder(original: str) -> str:
        idx = len(codes)
        placeholder = f"{{C{idx}}}"
        codes.append((placeholder, original))
        return placeholder

    # Pre-process: paragraph codes → \\n\\n; layout codes stripped (codec-driven)
    result = text
    for tok in _paragraph_codes():
        result = result.replace(tok, "\n\n")
    for tok in _strip_layout_codes():
        result = result.replace(tok, "")

    result = result.replace("\r\n", "\n")
    result = _classify_newlines(result)

    parts = []
    i = 0
    while i < len(result):
        if result[i] == "\n" and i + 1 < len(result) and result[i + 1] == "\n":
            parts.append(make_placeholder("\n\n"))
            i += 2
        elif result[i] == "\n":
            parts.append(make_placeholder("\n"))
            i += 1
        else:
            parts.append(result[i])
            i += 1
    result = "".join(parts)

    def replacer(m):
        return make_placeholder(m.group(0))

    protected = CONTROL_CODE_REGEX.sub(replacer, result)
    return protected, codes


def restore(text: str, codes: list[tuple[str, str]]) -> str:
    """Restore control code placeholders to original codes."""
    for placeholder, original in codes:
        text = text.replace(placeholder, original)
    return text
