"""Parse Pokemon_GBA_Font_Patch charmap and provide encoding/decoding."""

import re
from pathlib import Path
from typing import Any

from .languages import is_latin_language, postprocess_for_language



def _resolve_project_root() -> Path:
    """Resolve project root (repo root) from this file's location."""
    return Path(__file__).resolve().parents[2]


def _build_chinese_leads(ranges: list[list[int]]) -> frozenset:
    s: set[int] = set()
    for lo, hi in ranges:
        s.update(range(lo, hi + 1))
    return frozenset(s)


# JP CJK pipeline defaults (game.json no longer carries these)
_DEFAULT_CHS_LEADS = [[1, 5], [7, 26], [28, 30]]
_DEFAULT_ESCAPE_BYTES = bytes([0xF9, 0x00])
_DEFAULT_IDEOSPACE = bytes([0x01, 0xF7])
# Sentence punct = JP PCS single-bytes (same hex as AXVJ original).
# Drawn from CHS Sym @ 0x091E0000 (glyph 0x36..), NEVER F9 00 1E5x Normal.
# Legal inject hex: 00 space, 37 。, 3A 、, 3B ，, 3C ！, 3D ？, 3E ：, B0 …, AE -, AF ·
_FONT3_SYM_PUNCT: dict[str, int] = {
    "。": 0x37,
    "、": 0x3A,
    "，": 0x3B,
    "！": 0x3C,
    "？": 0x3D,
    "：": 0x3E,
}
_DEFAULT_PUNCT_MAP: dict[str, int] = {
    # Dash / middot / ellipsis: Font3 single-byte (narrow).
    # Quotes 「」 use Normal via charmap 1E65–1E68 (F9) — no JP single-byte.
    "‥": 176,
    "…": 176,
    "ー": 174,
    "・": 175,
    **_FONT3_SYM_PUNCT,
}


def normalize_zh_punct(text: str) -> str:
    """Map halfwidth / ASCII punct to charmap fullwidth (JP PCS inject codes)."""
    if not text:
        return text
    # Ellipsis before single-dot rule
    out = text.replace("...", "…")
    repl = {
        ",": "，",
        "!": "！",
        "?": "？",
        "(": "（",
        ")": "）",
        "[": "【",
        "]": "】",
        ":": "：",
        "~": "ー",
        "～": "ー",
    }
    for a, b in repl.items():
        if a in out:
            out = out.replace(a, b)
    # Standalone ASCII '.' → 。 (not digit.digit)
    out = re.sub(r"(?<!\d)\.(?!\d)", "。", out)
    return out


class Charmap:
    def __init__(
        self,
        charmap_path: Path | None = None,
        target_lang: str = "zh-Hans",
        charmap_cfg: dict[str, Any] | None = None,
    ):
        self.char_to_bytes: dict[str, bytes] = {}
        self.bytes_to_char: dict[int, str] = {}
        self.target_lang = target_lang
        self._cfg: dict[str, Any] = charmap_cfg or {}
        self._escape: bool = False
        self._escape_bytes: bytes = _DEFAULT_ESCAPE_BYTES
        self._punct_map: dict[str, int] = {}
        self._chinese_leads: frozenset = frozenset()
        self._ideospace_bytes: bytes = _DEFAULT_IDEOSPACE

        if is_latin_language(target_lang):
            self._build_from_pcs()
            return

        # CJK: enable F9 escape + default punct/leads; optional cfg overrides
        self._escape = bool(self._cfg.get("escape", True))
        raw_escape = self._cfg.get("escape_bytes")
        if raw_escape and len(raw_escape) >= 2:
            self._escape_bytes = bytes(raw_escape[:2])
        raw_ideospace = self._cfg.get("ideospace_bytes")
        if raw_ideospace and len(raw_ideospace) >= 2:
            self._ideospace_bytes = bytes(raw_ideospace[:2])
        raw_leads = self._cfg.get("chinese_leads") or _DEFAULT_CHS_LEADS
        self._chinese_leads = _build_chinese_leads(raw_leads)
        punct = self._cfg.get("punct_map") or _DEFAULT_PUNCT_MAP
        self._punct_map = {k: int(v) for k, v in punct.items()}

        path = charmap_path
        if path is None:
            rel = self._cfg.get("charmap_path")
            if rel:
                path = Path(rel)
                if not path.is_absolute():
                    candidate = _resolve_project_root() / rel
                    if candidate.exists():
                        path = candidate
        if path is not None:
            self._parse(Path(path))
        for ch, b in self._punct_map.items():
            self.char_to_bytes[ch] = bytes([b])
        # Force Sym-band sentence punct to JP PCS single bytes (never F9 1E5x).
        for ch, b in _FONT3_SYM_PUNCT.items():
            self.char_to_bytes[ch] = bytes([b])
            self._punct_map[ch] = b
            self.bytes_to_char[b] = ch
        # ASCII / ideographic space → PCS 0x00 (JP space); 　 keeps ideospace opt.
        self.char_to_bytes[" "] = bytes([0x00])
        self.bytes_to_char[0x00] = " "
        self.char_to_bytes["　"] = self._ideospace_bytes

    def _parse(self, path: Path):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or "=" not in line:
                continue
            hex_part, char_part = line.split("=", 1)
            hex_val = int(hex_part.strip(), 16)

            if not char_part:
                if hex_val == 0x00:
                    char_part = " "  # 0x00 = space per PCS spec
                else:
                    continue  # skip malformed entries

            if hex_val <= 0xFF:
                self.char_to_bytes[char_part] = bytes([hex_val])
                self.bytes_to_char[hex_val] = char_part
            else:
                hi = (hex_val >> 8) & 0xFF
                lo = hex_val & 0xFF
                self.char_to_bytes[char_part] = bytes([hi, lo])
                self.bytes_to_char[hex_val] = char_part

    def _build_from_pcs(self):
        """Build charmap from the standard PCS character table (for Latin languages).

        Latin target languages don't use the Chinese font patch, so the ROM
        retains the original GBA PCS encoding.  We must encode using the same
        table the unpatched ROM expects.
        """
        from .pcs_codes import PCS_CHAR_TABLE

        for byte_val, char in PCS_CHAR_TABLE.items():
            if char:  # skip empty entries
                self.char_to_bytes[char] = bytes([byte_val])
                self.bytes_to_char[byte_val] = char

    def encode_char(self, ch: str) -> bytes | None:
        """Encode a single character to Font Patch bytes.

        Sym-band punct (，。！？、：) / space / ``punct_map`` are always
        JP PCS single-bytes — never wrapped as F9 00 lead trail.
        """
        if ch == " ":
            return bytes([0x00])
        if ch in self._punct_map:
            return bytes([self._punct_map[ch]])
        return self.char_to_bytes.get(ch)

    def encode_string(self, text: str) -> bytearray:
        """Encode a string to Font Patch bytes. Raises ValueError for unsupported chars."""
        result = bytearray()
        i = 0
        while i < len(text):
            ch = text[i]
            encoded = self.encode_char(ch)
            if encoded is None:
                raise ValueError(f"Character '{ch}' (U+{ord(ch):04X}) not in charmap")
            result.extend(encoded)
            i += 1
        return result

    def can_encode(self, text: str) -> tuple[bool, list[str]]:
        """Check if all characters in text can be encoded. Returns (ok, bad_chars)."""
        bad = [ch for ch in text if ch not in self.char_to_bytes]
        return len(bad) == 0, bad

    def supported_chars(self) -> set[str]:
        """Return set of all supported characters."""
        return set(self.char_to_bytes.keys())

    def byte_length(self, text: str) -> int:
        """Calculate the byte length of encoded text (without terminator)."""
        length = 0
        for ch in text:
            enc = self.encode_char(ch)
            if enc:
                length += len(enc)
            else:
                length += 1  # assume 1 byte for unknown
        return length

    # Fullwidth → halfwidth for digits/letters only.
    # Do NOT map （）～ here — normalize_zh_punct keeps （） as F900 Normal
    # and ～/～ → ー (PCS AE); undoing would break inject codes.
    _FULLWIDTH_MAP = str.maketrans(
        "０１２３４５６７８９"
        "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
        "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ",
        "0123456789"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "abcdefghijklmnopqrstuvwxyz",
    )

    # Characters to replace with charmap-safe alternatives
    _CHAR_REPLACEMENTS = {
        "\u2014": "-",    # em dash → hyphen
        "\u2013": "-",    # en dash → hyphen
        "\u2018": "'",    # left single quote
        "\u2019": "'",    # right single quote
        "\u201C": "\"",   # left double quote (will be skipped if not in charmap)
        "\u201D": "\"",   # right double quote
        "\u300A": "\"",   # 《 → "
        "\u300B": "\"",   # 》 → "
        # Keep 、 as Sym 0x3A — do not collapse to ASCII ',' (0xB8).
        "\uFF5E": "ー",   # ～ → chōon (PCS AE), not ASCII ~
        "\u00B7": "・",   # middle dot → Font3 AF
        "$": "",          # dollar sign (not in charmap, strip)
    }

    def _sanitize(self, text: str) -> str:
        """Normalize characters that aren't in the charmap to safe alternatives."""
        # Apply language-specific character replacements first
        text = postprocess_for_language(text, self.target_lang)

        # Fullwidth → halfwidth
        text = text.translate(self._FULLWIDTH_MAP)
        # Character replacements
        for old, new in self._CHAR_REPLACEMENTS.items():
            if old in text:
                text = text.replace(old, new)
        # Strip any remaining stray curly braces (not part of {XX} hex patterns)
        import re
        text = re.sub(r"\{(?![0-9A-Fa-f]{2}\})", "", text)
        text = re.sub(r"(?<!\{[0-9A-Fa-f]{2})\}", "", text)
        return text

    def encode(self, text: str) -> bytes:
        """Encode text to ROM bytes using pcs_codes for control codes + charmap for chars.

        This is a convenience alias that delegates to encode_string but also
        handles backslash codes and bracket macros from pcs_codes.
        """
        from .pcs_codes import BACKSLASH_CODES, BRACKET_MACROS

        # Pre-clean: strip stray curly braces around control codes from LLM output
        import re
        text = re.sub(r"\{(\\[pnlr.]|\n\n?)\}", r"\1", text)
        # Also strip {\\?XX}, {\\CCXXXX} etc.
        text = re.sub(r"\{(\\(?:\?[0-9A-Fa-f]{2}|CC[0-9A-Fa-f]{4}|btn[0-9A-Fa-f]{2}|B[0-9A-Fa-f]))\}", r"\1", text)
        # LLM often emits literal "{{\n}}" / "{{\p}}" with braces; normalize.
        text = text.replace("{\\n}", "\n").replace("{\\p}", "\n\n").replace("{\\l}", "\\l")
        text = text.replace("{{\n}}", "\n").replace("{{\\p}}", "\n\n")
        # Unrestored {Cn} must not be stripped to literal "C6"/"C7" (PCS letters).
        if re.search(r"\{\{?C\d+", text):
            raise ValueError(
                f"unrestored control placeholder in text: {text[:80]!r}"
            )
        # Drop any remaining lone braces left by bad LLM formatting
        text = text.replace("{", "").replace("}", "")

        # Sanitize unsupported characters
        text = self._sanitize(text)

        result = bytearray()
        i = 0
        while i < len(text):
            # Handle real newline characters (0x0A) from JSON
            if text[i] == "\n":
                if i + 1 < len(text) and text[i + 1] == "\n":
                    # \n\n = paragraph / wait-then-clear (vanilla AXVJ uses 0xFB).
                    # Do NOT emit 0xFA — ProcessCurrentChar FA sets state 0 (end).
                    result.append(0xFB)
                    i += 2
                else:
                    # single \n = newline (0xFE)
                    result.append(0xFE)
                    i += 1
                continue

            # Skip carriage returns
            if text[i] == "\r":
                i += 1
                continue

            # Try bracket macros: [player], [rival], [red], etc.
            if text[i] == "[":
                end = text.find("]", i)
                if end != -1:
                    token = text[i : end + 1]
                    if token in BRACKET_MACROS:
                        result.extend(BRACKET_MACROS[token])
                        i = end + 1
                        continue

            # Try backslash codes (longest first)
            matched = False
            if text[i] == "\\":
                # Escape: \\p / \\l / \\pn → 0xFB (wait + Text_ClearWindow).
                # Vanilla multi-box speech uses FF FB FF; 0xFA ends the printer.
                if self._escape:
                    for token, nbytes in (("\\pn", 3), ("\\p", 2), ("\\l", 2)):
                        if text[i:].startswith(token):
                            result.append(0xFB)
                            i += nbytes
                            matched = True
                            break
                if not matched:
                    for code_str, code_bytes in BACKSLASH_CODES:
                        if text[i:].startswith(code_str):
                            result.extend(code_bytes)
                            i += len(code_str)
                            matched = True
                            break
                # \\CC hex codes: \CCXXYY... -> FC XX YY ...
                if not matched and text[i:].startswith("\\CC"):
                    j = i + 3
                    hex_chars = []
                    while j < len(text) and j - (i + 3) < 20:
                        pair = text[j : j + 2]
                        if len(pair) == 2 and all(c in "0123456789ABCDEFabcdef" for c in pair):
                            hex_chars.append(int(pair, 16))
                            j += 2
                        else:
                            break
                    if hex_chars:
                        result.append(0xFC)
                        result.extend(hex_chars)
                        i = j
                        matched = True
                # \\btn hex codes: \btnXX -> F8 XX
                if not matched and text[i:].startswith("\\btn"):
                    pair = text[i + 4 : i + 6]
                    if len(pair) == 2 and all(c in "0123456789ABCDEFabcdef" for c in pair):
                        result.append(0xF8)
                        result.append(int(pair, 16))
                        i += 6
                        matched = True
                # \\XX (single backslash + 2 hex digits) = FD escape (runtime variables)
                # e.g. \00 = player pokemon, \0F = opponent pokemon, \34 = EXP amount
                if not matched and i + 2 < len(text):
                    pair = text[i + 1 : i + 3]
                    if len(pair) == 2 and all(c in "0123456789ABCDEFabcdef" for c in pair):
                        result.append(0xFD)
                        result.append(int(pair, 16))
                        i += 3
                        matched = True
            if matched:
                continue

            # Try raw byte placeholder {XX}
            if text[i] == "{" and i + 3 < len(text) and text[i + 3] == "}":
                hex_str = text[i + 1 : i + 3]
                if all(c in "0123456789ABCDEFabcdef" for c in hex_str):
                    result.append(int(hex_str, 16))
                    i += 4
                    continue

            # Regular character via charmap
            enc = self.encode_char(text[i])
            if enc is not None:
                if (
                    self._escape
                    and len(enc) == 2
                    and self._chinese_leads
                    and enc[0] in self._chinese_leads
                    and enc[1] < 0xFA
                ):
                    result.extend(self._escape_bytes)
                    result.extend(enc)
                else:
                    result.extend(enc)
            else:
                # Skip unsupported characters instead of crashing
                # (rare kanji, stray symbols, etc.)
                pass
            i += 1

        # Escape: 0xFE=newline, 0xFB=wait+clear, 0xFF=pause/EOS marker in data.
        # Always terminate like vanilla JP strings (0xFF).
        result.append(0xFF)
        return bytes(result)


def get_default_charmap() -> Charmap:
    """Return a Charmap instance with the default font patch charmap."""
    return Charmap()
