# -*- coding: utf-8 -*-
"""判定：org 的 BG0 数字字形是否 = cb2(预取图集) 里的副本 ⇒ P32 关预取是否是元凶。
"""
from pathlib import Path

D = Path(r"C:/code/GBA-Rom-Translator/.tmp")
vr_o = (D / "drive_orgparty_vram.bin").read_bytes()
vr_p = (D / "drive_party_vram.bin").read_bytes()

CB1 = 0x4000   # BG0 charBase 1
CB2 = 0x8000   # BG0 charBase 2（原盘预取图集落点）


def nz(b):
    return sum(1 for x in b if x)


def show(blob):
    return "/".join(
        "".join("#" if (((blob[r * 4 + (c >> 1)]) >> (0 if (c & 1) else 4)) & 0xF) else "."
                for c in range(8))
        for r in range(8))


print("org cb1 120..131 各号在 cb2 里有没有同字节副本：")
for n in range(112, 132):
    b = vr_o[CB1 + n * 32: CB1 + n * 32 + 32]
    hits = [off // 32 for off in range(0, 0x4000, 32) if vr_o[CB2 + off: CB2 + off + 32] == b] if any(b) else []
    if any(b):
        print("  cb1[%-4d] nz=%-3d cb2 同字节号=%s" % (n, nz(b), hits[:5] if hits else "无"))

print()
print("org cb2 全块非零 tile 数 =", sum(1 for n in range(512) if nz(vr_o[CB2 + n * 32:CB2 + n * 32 + 32])))
print("ours cb2 全块非零 tile 数 =", sum(1 for n in range(512) if nz(vr_p[CB2 + n * 32:CB2 + n * 32 + 32])))

print()
print("ours cb1 非零 tile 号（0..511 中）:")
lst = [n for n in range(512) if nz(vr_p[CB1 + n * 32:CB1 + n * 32 + 32])]
print("  共 %d 个: %s" % (len(lst), lst))
print("org  cb1 非零 tile 号（0..511 中）:")
lst2 = [n for n in range(512) if nz(vr_o[CB1 + n * 32:CB1 + n * 32 + 32])]
print("  共 %d 个" % len(lst2))
print("  org 独有(ours 为 0):", [n for n in lst2 if n not in lst])
print("  ours 独有(org 为 0):", [n for n in lst if n not in lst2])
