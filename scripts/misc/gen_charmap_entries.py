"""Generate charmap entries for new punctuation/symbol slots."""
entries = [
    (0x300C, "\u300c"),  # 「
    (0x300D, "\u300d"),  # 」
    (0x300E, "\u300e"),  # 『
    (0x300F, "\u300f"),  # 』
    (0x2025, "\u2025"),  # ‥
    (0x2026, "\u2026"),  # …
    (0x30FC, "\u30fc"),  # ー
    (0xFF08, "\uff08"),  # （
    (0xFF09, "\uff09"),  # ）
    (0x3010, "\u3010"),  # 【
    (0x3011, "\u3011"),  # 】
    (0xFF3B, "\uff3b"),  # ［
    (0xFF3D, "\uff3d"),  # ］
    (0xFF5B, "\uff5b"),  # ｛
    (0xFF5D, "\uff5d"),  # ｝
    (0x2014, "\u2014"),  # —
    (0x2013, "\u2013"),  # –
    (0x00B7, "\u00b7"),  # ·
    (0x300A, "\u300a"),  # 《
    (0x300B, "\u300b"),  # 》
    (0x3014, "\u3014"),  # 〔
    (0x3015, "\u3015"),  # 〕
    (0x2500, "\u2500"),  # ─
    (0x2605, "\u2605"),  # ★
    (0x2606, "\u2606"),  # ☆
    (0x2190, "\u2190"),  # ←
    (0x2191, "\u2191"),  # ↑
    (0x2192, "\u2192"),  # →
    (0x2193, "\u2193"),  # ↓
    (0x25A0, "\u25a0"),  # ■
    (0x25A1, "\u25a1"),  # □
    (0x25CB, "\u25cb"),  # ○
    (0x25CF, "\u25cf"),  # ●
    (0x2260, "\u2260"),  # ≠
    (0x2264, "\u2264"),  # ≤
    (0x2265, "\u2265"),  # ≥
    (0x00A7, "\u00a7"),  # §
    (0x00B0, "\u00b0"),  # °
    (0x203B, "\u203b"),  # ※
    (0x2018, "\u2018"),  # '
    (0x2019, "\u2019"),  # '
    (0x201C, "\u201c"),  # "
    (0x201D, "\u201d"),  # "
]

trail = 0x65
lines = []
for cp, ch in entries:
    lines.append(f"{0x1E00 | trail:04X}={ch}")
    trail += 1
out = "\n".join(lines) + "\n"
print(f"Generated {len(lines)} entries (trail 0x65-0x{trail-1:02X})")
print(out, end="")
with open("charmap_punct_add.txt", "w", encoding="utf-8") as f:
    f.write(out)
