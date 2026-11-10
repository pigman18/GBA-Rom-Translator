"""Regenerate charmap.txt with clean UTF-8 entries for punctuation."""
from pathlib import Path

charmap_path = Path(r"C:\code\gba\configs\POKEMON_RUBY_AXVJ00\font\charmap.txt")

# Read existing file up to last valid entry
data = charmap_path.read_bytes()
text = data.decode("utf-8", errors="replace")
last_good = text.rfind("1E64=")
cut = text.index("\n", last_good) + 1
text = text[:cut]

entries = [
    (0x1E5E, "\uff0c"),   # ，
    (0x1E5F, "\u3002"),   # 。
    (0x1E60, "\uff01"),   # ！
    (0x1E61, "\uff1f"),   # ？
    (0x1E62, "\uff1a"),   # ：
    (0x1E63, "\u3001"),   # 、
    (0x1E64, "\uff5e"),   # ～
    (0x1E65, "\u300c"),   # 「
    (0x1E66, "\u300d"),   # 」
    (0x1E67, "\u300e"),   # 『
    (0x1E68, "\u300f"),   # 』
    (0x1E69, "\u2025"),   # ‥
    (0x1E6A, "\u2026"),   # …
    (0x1E6B, "\u30fc"),   # ー
    (0x1E6C, "\uff08"),   # （
    (0x1E6D, "\uff09"),   # ）
    (0x1E6E, "\u3010"),   # 【
    (0x1E6F, "\u3011"),   # 】
    (0x1E70, "\uff3b"),   # ［
    (0x1E71, "\uff3d"),   # ］
    (0x1E72, "\uff5b"),   # ｛
    (0x1E73, "\uff5d"),   # ｝
    (0x1E74, "\u2014"),   # —
    (0x1E75, "\u2013"),   # –
    (0x1E76, "\u00b7"),   # ·
    (0x1E77, "\u300a"),   # 《
    (0x1E78, "\u300b"),   # 》
    (0x1E79, "\u3014"),   # 〔
    (0x1E7A, "\u3015"),   # 〕
    (0x1E7B, "\u2500"),   # ─
    (0x1E7C, "\u2605"),   # ★
    (0x1E7D, "\u2606"),   # ☆
    (0x1E7E, "\u2190"),   # ←
    (0x1E7F, "\u2191"),   # ↑
    (0x1E80, "\u2192"),   # →
    (0x1E81, "\u2193"),   # ↓
    (0x1E82, "\u25a0"),   # ■
    (0x1E83, "\u25a1"),   # □
    (0x1E84, "\u25cb"),   # ○
    (0x1E85, "\u25cf"),   # ●
    (0x1E86, "\u2260"),   # ≠
    (0x1E87, "\u2264"),   # ≤
    (0x1E88, "\u2265"),   # ≥
    (0x1E89, "\u00a7"),   # §
    (0x1E8A, "\u00b0"),   # °
    (0x1E8B, "\u203b"),   # ※
    (0x1E8C, "\u2018"),   # '
    (0x1E8D, "\u2019"),   # '
    (0x1E8E, "\u201c"),   # "
    (0x1E8F, "\u201d"),   # "
    (0x1E90, "\u30fb"),   # ・
]

lines = [f"{hv:04X}={ch}" for hv, ch in entries]
text += "\n" + "\n".join(lines) + "\n"
charmap_path.write_bytes(text.encode("utf-8"))
print(f"Wrote {len(lines)} entries, total {len(text.encode('utf-8'))} bytes")
