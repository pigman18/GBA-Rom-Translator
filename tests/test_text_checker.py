"""Unit tests for text_checker scoring + looks_like_jp_text katakana UI."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from meowth.jp_pcs import looks_like_jp_text  # noqa: E402
from meowth.text_checker import (  # noqa: E402
    WEIGHTS,
    _entropy,
    _glyph_ratio,
    _kana_stats,
    score_entries,
)


def _entry(
    hex_bytes: bytes,
    *,
    original: str = "",
    address: str = "0x08010000",
    is_fixed_table: bool = False,
    eid: str = "t1",
) -> dict:
    return {
        "id": eid,
        "address": address,
        "original": original,
        "original_hex": hex_bytes.hex(),
        "byte_length": len(hex_bytes),
        "is_fixed_table": is_fixed_table,
    }


class TestLooksLikeJpText(unittest.TestCase):
    def test_hiragana_dialogue(self) -> None:
        # あいうえおかきく + FF
        bs = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0xFF])
        self.assertTrue(looks_like_jp_text(bs))

    def test_katakana_ui_long(self) -> None:
        # 8+ pure katakana glyphs (no hiragana) — previously rejected
        bs = bytes([0x9F, 0x59, 0x73, 0x7E, 0x96, 0x64, 0x6E, 0x5D, 0xFF])
        self.assertTrue(looks_like_jp_text(bs))
        self.assertGreaterEqual(len(bs) - 1, 8)

    def test_rejects_no_terminator(self) -> None:
        bs = bytes([0x01, 0x02, 0x03, 0x04])
        self.assertFalse(looks_like_jp_text(bs))


class TestNewSignals(unittest.TestCase):
    def test_entropy_padding(self) -> None:
        bs = bytes([0x01] * 16 + [0xFF])
        self.assertTrue(_entropy(bs))

    def test_entropy_normal_kana(self) -> None:
        bs = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0xFF])
        self.assertFalse(_entropy(bs))

    def test_kana_stats_same_run(self) -> None:
        bs = bytes([0x01, 0x01, 0x01, 0x01, 0x01, 0x02, 0x03, 0xFF])
        self.assertTrue(_kana_stats(bs))

    def test_laughter_hohoho_not_kana_stats(self) -> None:
        # ふほほほほ‥‥ — 4×ほ is normal JP laughter, not mojibake
        # ふ=0x1E ほ=0x1C ; ellipsis 0xB0
        bs = bytes([0x1E, 0x1C, 0x1C, 0x1C, 0x1C, 0xB0, 0xB0, 0xFF])
        self.assertFalse(_kana_stats(bs))

    def test_kana_stats_mono_gojuon(self) -> None:
        # あいうえおかきくけこ (strict ascending)
        bs = bytes(list(range(0x01, 0x0B)) + [0xFF])
        self.assertTrue(_kana_stats(bs))

    def test_glyph_ratio_bad_bytes(self) -> None:
        # mostly illegal high bytes + FF
        bs = bytes([0xF8, 0xF9, 0x01, 0x02, 0xF8, 0xF9, 0xF8, 0xFF])
        self.assertTrue(_glyph_ratio(bs))


class TestScoreEntries(unittest.TestCase):
    def test_fixed_table_always_100(self) -> None:
        junk = _entry(bytes([0x00] * 20 + [0xFF]), is_fixed_table=True)
        scored = score_entries([junk], rom=None)
        self.assertEqual(scored[0][2], 100)
        self.assertEqual(scored[0][1], [])

    def test_real_dialogue_high_score(self) -> None:
        # はじめまして\nよろしく (non-monotonic dialogue; not gojuon dump)
        bs = bytes(
            [0x19, 0x3D, 0x22, 0x1F, 0x0C, 0x13, 0xFE, 0x48, 0x2C, 0x0C, 0x0B, 0xFF]
        )
        e = _entry(bs, original="はじめまして\nよろしく")
        (_e, hits, score) = score_entries([e], rom=None)[0]
        self.assertGreaterEqual(score, 90, f"hits={hits} score={score}")

    def test_katakana_ui_high_score(self) -> None:
        # ポケモンバトル (katakana UI, non-monotonic)
        bs = bytes([0x9F, 0x59, 0x73, 0x7E, 0x96, 0x64, 0x6E, 0xFF])
        e = _entry(bs, original="ポケモンバトル")
        (_e, hits, score) = score_entries([e], rom=None)[0]
        self.assertGreaterEqual(score, 90, f"hits={hits} score={score}")

    def test_authoritative_but_garbage_jp_rejected(self) -> None:
        # FF-terminated, low nulls, but garbage decoded text
        bs = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0xFF])
        e = _entry(bs, original="がのくあいうえおかきく")
        (_e, hits, score) = score_entries([e], rom=None)[0]
        self.assertIn("garbage_jp", hits)
        self.assertLess(score, 90)

    def test_repeat_tile_pattern_low(self) -> None:
        # xx yy repeated → repeat hit; also low entropy
        bs = bytes([0x12, 0x34] * 8 + [0xFF])
        e = _entry(bs, original="????")
        (_e, hits, score) = score_entries([e], rom=None)[0]
        self.assertTrue(
            "repeat" in hits or "entropy" in hits or "jp_text" in hits,
            f"hits={hits}",
        )
        self.assertLess(score, 90)

    def test_high_null_byte_profile(self) -> None:
        bs = bytes([0x00] * 12 + [0x01, 0x02, 0xFF])
        e = _entry(bs, original="  あい")
        (_e, hits, score) = score_entries([e], rom=None)[0]
        self.assertIn("byte_profile", hits)
        self.assertLess(score, 90)

    def test_weights_include_new_algorithms(self) -> None:
        for key in ("entropy", "glyph_ratio", "kana_stats"):
            self.assertIn(key, WEIGHTS)


if __name__ == "__main__":
    unittest.main()
