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
_DEFAULT_WORD_COUNT = 32
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


def _word_count() -> int:
    cfg = _protect_cfg()
    raw = cfg.get("word_count", cfg.get("line_width", _DEFAULT_WORD_COUNT))
    return int(raw)


def _semantic_threshold() -> int:
    cfg = _protect_cfg()
    ratio = float(cfg.get("semantic_threshold_ratio", _DEFAULT_SEMANTIC_RATIO))
    return int(_word_count() * ratio)


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


def unwrap_quotes(text: str) -> str:
    """Strip a single layer of wrapping ASCII quotes if present."""
    s = text or ""
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s


def format_original(text: str) -> str:
    """Canonical original for translation-cache keys (and protect head).

    Same structural steps as :func:`protect` before ``{Cn}`` placeholders:
    unwrap quotes, map paragraph/layout tokens, normalize CR, classify
    layout vs semantic newlines.  Layout ``\\n`` becomes a space — so a cache
    written after formatting still hits when lookup uses the raw extract.

    Idempotent: ``format_original(format_original(x)) == format_original(x)``.
    ``_classify_newlines`` can keep collapsing remaining breaks after a prior
    pass changes line lengths; run to fixpoint so cache keys do not drift
    across save/load cycles (which would inflate pending on re-runs).
    """
    result = unwrap_quotes(text)
    for tok in _paragraph_codes():
        result = result.replace(tok, "\n\n")
    for tok in _strip_layout_codes():
        result = result.replace(tok, "")
    result = result.replace("\r\n", "\n").replace("\r", "\n")
    # Fixpoint: classify until stable (pathological strings may need many passes).
    for _ in range(32):
        nxt = _classify_newlines(result)
        if nxt == result:
            break
        result = nxt
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

    result = format_original(text)

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


_DOUBLE_BRACE_C = re.compile(r"\{\{C(\d+)\}\}")
# LLM sometimes mangles newline into the placeholder: {{C7}\n} / {C7\n}
_MANGLED_C_NL = re.compile(r"\{\{?C(\d+)\}?\\n\}")
_WRAPPED_CODE = re.compile(r"\{(\\[pln]|\\CC[0-9A-Fa-f]+)\}")


def normalize_placeholders(text: str) -> str:
    """Normalize LLM-mangled placeholder spellings before restore.

    Prompt examples historically used ``{{C0}}`` (double braces); models often
    emit that form or glue ``\\n`` into the token.  Real control codes wrapped
    as ``{\\p}`` are unwrapped here too.
    """
    text = _MANGLED_C_NL.sub(r"{C\1}\n", text)
    text = _DOUBLE_BRACE_C.sub(r"{C\1}", text)
    text = _WRAPPED_CODE.sub(r"\1", text)
    return text


def restore(text: str, codes: list[tuple[str, str]]) -> str:
    """Restore control code placeholders to original codes."""
    text = normalize_placeholders(text)
    for placeholder, original in codes:
        text = text.replace(placeholder, original)
    return text
