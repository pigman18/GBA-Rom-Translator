"""Auto line-wrapping for translated GBA Pokemon text.

配置只写 ``word_count``（一行最多汉字个数）。中文折行时代码按 CHS
12px 步进 + 16px 字模自动留行末余量（``word_count`` 按 12px 格理解窗宽，
再换算实折字数），无需 ``wrap_width_px``。

Shop / item-desc boxes only honor ``FE`` (``\\n``); ``FB`` (``\\p``) does not
page-clear — set ``wrap_pages=False`` + ``max_lines`` for those modules.
"""

from __future__ import annotations

import re

LINES_PER_BOX = 2  # lines per text box (dialogue)

# Default max Hanzi per line (module ``word_count`` may override).
DEFAULT_WORD_COUNT = 14

# Match hook CHS metrics (FONT_12PX_DRAW / CHS_GLYPH_ADVANCE_PX).
CHS_ADVANCE_PX = 12
CHS_CELL_PX = 16  # last glyph needs full cell; cursor only advances 12


def chs_line_width_px(word_count: int) -> int:
    """Pixel width needed for ``word_count`` Hanzi (12px step, 16px last cell)."""
    n = max(1, int(word_count))
    return (n - 1) * CHS_ADVANCE_PX + CHS_CELL_PX


def chs_word_count_for_width_px(width_px: int) -> int:
    """Inverse of :func:`chs_line_width_px` — max Hanzi in ``width_px``."""
    w = max(int(width_px), CHS_CELL_PX)
    return max(1, (w - CHS_CELL_PX) // CHS_ADVANCE_PX + 1)


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

    ``word_count``：texts.json 里配置的一行汉字上限。中文时代码自动按
    「窗宽 ≈ word_count×12px」再用 16px 字模反算实折字数（例：填 16 → 折 15，
    避免行末 ``。`` 被裁半）。要视觉满 16 字可填 ``17``。
    ``wrap_pages`` / ``max_lines``：对话翻页与说明窗截断。
    """
    if not text:
        return text

    if word_count is None:
        word_count = DEFAULT_WORD_COUNT
    word_count = max(1, int(word_count))

    # 配置只认 word_count；CHS 度量在代码里从 word_count 自动换算
    if str(target_lang).startswith("zh"):
        width_px = word_count * CHS_ADVANCE_PX
        word_count = chs_word_count_for_width_px(width_px)

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    if not wrap_pages:
        return _wrap_lines_only(text, word_count, max_lines or lines_per_box)

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
    """Shop/desc: strip seed ``\\n``/``\\p``, reflow by word_count, no ``\\p``."""
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
    parts = _HARD_BREAK_RE.split(text)
    all_lines: list[str] = []
    for seg in parts:
        if not seg.strip() and "\\l" not in seg:
            continue
        seg = seg.replace("\\n", "")
        if not seg.strip() and "\\l" not in seg:
            continue
        all_lines.extend(_wrap_to_lines(seg, word_count))
    return all_lines


def _token_units(token: str) -> int:
    """How many ``word_count`` slots a token consumes (汉字个数)."""
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
    """Wrap by Hanzi count; ``word_count`` = max 汉字 per line (already CHS-adjusted)."""
    tokens = _TOKEN_RE.findall(text)
    if not tokens:
        return [text] if text else []

    budget = max(1, int(word_count))
    lines: list[list[str]] = [[]]
    line_units = 0

    def _units_of(seq: list[str]) -> int:
        return sum(_token_units(t) for t in seq)

    for i, tok in enumerate(tokens):
        w = _token_units(tok)

        if w > 0 and line_units > 0 and line_units + w > budget:
            if _can_break_before(tokens, i):
                lines.append([])
                line_units = 0
            elif lines[-1]:
                # 「字。」不可在句号前断 → 末字+句号一起到下一行
                prev = lines[-1].pop()
                line_units = _units_of(lines[-1])
                lines.append([prev])
                line_units = _token_units(prev)

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
