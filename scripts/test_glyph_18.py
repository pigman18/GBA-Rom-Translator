"""Assert Gen3 Chinese font slot: 128 B/glyph (16x16 4bpp), not 18/32."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_chinese_font as bcf  # noqa: E402


class TestGlyph128Slot(unittest.TestCase):
    def test_pack_length_is_128(self) -> None:
        ink = bytearray(12 * 12)
        ink[0] = 1
        ink[12 * 11 + 11] = 1
        slot = bcf.ink12_to_slot16(ink, shadow=False)
        packed = bcf.pack_slot16_4bpp(slot)
        self.assertEqual(len(packed), 128)
        self.assertNotEqual(len(packed), 18)
        self.assertNotEqual(len(packed), 32)

    def test_reject_wrong_bytes_per_glyph(self) -> None:
        with self.assertRaises(ValueError):
            bcf.build_font_bin({}, {}, font_ascent=10, glyph_count=1, bytes_per_glyph=18)
        with self.assertRaises(ValueError):
            bcf.build_font_bin({}, {}, font_ascent=10, glyph_count=1, bytes_per_glyph=32)

    def test_pad_top(self) -> None:
        self.assertEqual(bcf.PAD_TOP, 2)
        ink = bytearray(12 * 12)
        ink[0] = 1  # top-left of ink
        slot = bcf.ink12_to_slot16(ink, shadow=False)
        # ink row0 → slot row PAD_TOP
        self.assertEqual(slot[2 * 16 + 0], 15)
        self.assertEqual(slot[0 * 16 + 0], 0)


if __name__ == "__main__":
    unittest.main()
