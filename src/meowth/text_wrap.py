"""Auto line-wrapping for translated GBA Pokemon text.

``word_count`` = max **汉字个数** per line. Inserts ``\\n`` (and optionally
``\\p``) so text fits GBA text boxes.

Shop / item-desc boxes only honor ``FE`` (``\\n``); ``FB`` (``\\p``) does not
page-clear — set ``wrap_pages=False`` + ``max_lines`` for those modules.
"""

from __future__ import annotations

import re

LINES_PER_BOX = 2  # lines per text box (dialogue)

# Default max Hanzi per line (module ``word_count`` may override).
DEFAULT_WORD_COUNT = 14

# Player/rival name vars: ~6 halfwidth slots → count as 6 units
_VAR_UNITS = {"player": 6, "rival": 6}
_DEFAULT_VAR_UNITS = 8

# HMA color/style bracket codes (zero display width)
_COLOR_NAMES = {
    "white", "white2", "white3", "black",
    "grey", "gray", "darkgrey", "darkgray", "lightgrey", "lightgray",
    "red", "orange", "green", "lightgreen",
    "blue", "lightblue", "lightblue2", "lightblue3",
    "cyan", "navyblue", "darknavyblue",
    "transp", "yellow", "magenta", "skyblue", "darkskyblue", "black2",
}

# CJK punctuation that must not start a line
_NO_BREAK_BEFORE = set("。，！？、）」』】〉》：；…～")

# CJK punctuation that must not end a line (next char must stay with it)
_NO_BREAK_AFTER = set("（「『【〈《")

# Common compound words that should not be split across lines
# (still count as len(chars) toward word_count — never as 1).
_COMPOUNDS = [
    "宝可梦", "红白机", "精灵球", "训练师", "道馆主", "冠军联盟",
    "大木博士", "小智", "小茂", "火箭队", "四天王",
    "妙蛙种子", "小火龙", "杰尼龟", "皮卡丘",
]

# Tokenizer: control codes, variables, compound words, ASCII words, or single chars
_TOKEN_RE = re.compile(
    r"\\btn[0-9A-Fa-f]{2}"
    r"|\\CC[0-9A-Fa-f]{4}"
    r"|\\B[0-9A-Fa-f]"
    r"|\\\?[0-9A-Fa-f]{2}"
    r"|\\[plnr]"
    r"|\[[a-zA-Z_]\w*\]"
    r"|" + "|".join(re.escape(w) for w in sorted(_COMPOUNDS, key=len, reverse=True))
    + r"|[A-Za-z0-9]+"
    r"|.",
    re.DOTALL,
)

# Hard line-break markers (literal backslash codes or real newlines)
_HARD_BREAK_RE = re.compile(r"\\n|\n")


def wrap_text(
    text: str,
    word_count: int | None = None,
    lines_per_box: int = LINES_PER_BOX,
    target_lang: str = "zh-Hans",
    *,
    wrap_pages: bool = True,
    max_lines: int | None = None,
) -> str:
    """Wrap translated text to fit GBA text boxes.

    ``word_count`` is max Hanzi per line.
    ``wrap_pages``: if True (dialogue), insert ``\\p`` every ``lines_per_box``
    lines; if False (shop/item desc), only ``\\n``, never ``\\p``.
    ``max_lines``: when set (typical 2 with wrap_pages=False), truncate.
    For ``wrap_pages=False`` (shop/desc): seed ``\\n``/``\\p`` are stripped and
    the string is reflowed by ``word_count`` — otherwise early hard breaks
    plus ``max_lines`` truncate causes short lines and missing text.
    """
    if not text:
        return text

    if word_count is None:
        word_count = DEFAULT_WORD_COUNT

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    if not wrap_pages:
        # Shop/desc: only FE works; flatten seed layout then reflow by count.
        return _wrap_lines_only(text, word_count, max_lines or lines_per_box)

    # Dialogue: paragraph breaks → \\p between boxes
    _PARA = "\x00PARA\x00"
    text = text.replace("\\.", _PARA)
    text = text.replace("\\p", _PARA)
    text = text.replace("\n\n", _PARA)

    paragraphs = text.split(_PARA)
    wrapped_paras: list[str] = []
    for para in paragraphs:
        if not para.strip() and "\\l" not in para:
            continue
        all_lines = _segment_and_wrap(para, word_count)
        if all_lines:
            wrapped_paras.append(_distribute_lines(all_lines, lines_per_box, wrap_pages=True))

    return "\\p".join(wrapped_paras)


def _wrap_lines_only(text: str, word_count: int, max_lines: int) -> str:
    """Shop/desc: strip seed ``\\n``/``\\p``, reflow by word_count, no ``\\p``.

    Seed translations often insert ``\\n`` mid-phrase (e.g. after 「比精灵球」).
    Preserving those as hard breaks + truncating to ``max_lines`` yields
    under-full lines and drops the rest of the sentence.
    """
    # Keep \\l; drop layout breaks so word_count owns line cuts.
    flat = (
        text.replace("\\.", "")
        .replace("\\p", "")
        .replace("\\n", "")
        .replace("\n", "")
    )
    all_lines = _wrap_to_lines(flat, word_count)
    if max_lines is not None and max_lines > 0:
        all_lines = all_lines[: max(1, int(max_lines))]
    return _distribute_lines(all_lines, lines_per_box=10**9, wrap_pages=False)


def _segment_and_wrap(text: str, word_count: int) -> list[str]:
    """Split on hard ``\\n`` / real newlines, wrap each segment at word_count."""
    # Keep \\l inside segments; split only on \\n / \\n
    parts = _HARD_BREAK_RE.split(text)
    all_lines: list[str] = []
    for seg in parts:
        # Drop empty pieces from consecutive breaks; keep \\l-only
        if not seg.strip() and "\\l" not in seg:
            continue
        # Remove any stray \\n left inside (should not remain after split)
        seg = seg.replace("\\n", "")
        if not seg.strip() and "\\l" not in seg:
            continue
        all_lines.extend(_wrap_to_lines(seg, word_count))
    return all_lines


def _token_units(token: str) -> int:
    """How many ``word_count`` slots a token consumes (汉字个数).

    Compounds like 「精灵球」 count as 3, never 1.
    """
    if token.startswith("\\btn"):
        return 2
    if token.startswith("\\"):
        return 0
    if token.startswith("[") and token.endswith("]"):
        name = token[1:-1].lower()
        if name in _COLOR_NAMES:
            return 0
        return _VAR_UNITS.get(name, _DEFAULT_VAR_UNITS)
    cjk = 0
    narrow = 0
    for ch in token:
        if _is_cjk(ch):
            cjk += 1
        else:
            narrow += 1
    # Halfwidth: 2 glyphs ≈ 1 汉字 slot
    return cjk + ((narrow + 1) // 2 if narrow else 0)


def _is_cjk(ch: str) -> bool:
    """CJK / fullwidth — one word_count unit."""
    cp = ord(ch)
    return (
        0x4E00 <= cp <= 0x9FFF
        or 0x3400 <= cp <= 0x4DBF
        or 0x3000 <= cp <= 0x303F
        or 0xFF01 <= cp <= 0xFF60
        or 0xFE30 <= cp <= 0xFE4F
    )


def _can_break_before(tokens: list[str], idx: int) -> bool:
    """Check whether we may insert a line break before tokens[idx]."""
    tok = tokens[idx]
    if tok in _NO_BREAK_BEFORE:
        return False
    if idx > 0 and tokens[idx - 1] in _NO_BREAK_AFTER:
        return False
    return True


def _wrap_to_lines(text: str, word_count: int) -> list[str]:
    """Wrap by Hanzi count; ``word_count`` = max 汉字 per line."""
    tokens = _TOKEN_RE.findall(text)
    if not tokens:
        return [text] if text else []

    budget = max(1, int(word_count))
    lines: list[list[str]] = [[]]
    line_units = 0

    for i, tok in enumerate(tokens):
        w = _token_units(tok)

        if w > 0 and line_units > 0 and line_units + w > budget:
            if _can_break_before(tokens, i):
                lines.append([])
                line_units = 0

        lines[-1].append(tok)
        line_units += w

    return ["".join(line) for line in lines if line]


def _distribute_lines(
    lines: list[str],
    lines_per_box: int,
    *,
    wrap_pages: bool = True,
) -> str:
    """Join lines with ``\\n``; optionally ``\\p`` every ``lines_per_box``."""
    if not lines:
        return ""

    parts: list[str] = []
    line_in_box = 0

    for i, line in enumerate(lines):
        if i > 0:
            if wrap_pages and line_in_box >= lines_per_box:
                parts.append("\\p")
                line_in_box = 0
            else:
                parts.append("\\n")
        parts.append(line)
        line_in_box += 1

    return "".join(parts)
