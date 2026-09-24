# -*- coding: utf-8 -*-
"""把 org 的数字字形 tile 拿到 ours 的全 VRAM 里找 —— 判定「我们是画了但没登记」还是「根本没画」。
用法: python .tmp/an_dig.py
"""
from pathlib import Path

D = Path(r"C:/code/GBA-Rom-Translator/.tmp")
vr_p = (D / "drive_party_vram.bin").read_bytes()
vr_o = (D / "drive_orgparty_vram.bin").read_bytes()

CB = 0x4000  # BG0 charBase

DIG = {}
for n in (120, 121, 122, 125, 127, 116, 332, 334):
    DIG[n] = vr_o[CB + n * 32: CB + n * 32 + 32]

print("org 数字字形：")


def show(blob):
    out = []
    for r in range(8):
        row = ""
        for c in range(8):
            b = blob[r * 4 + (c >> 1)]
            v = (b >> 4) if (c & 1) else (b & 0xF)
            row += "#" if v else "."
        out.append(row)
    return "/".join(out)


for n, b in DIG.items():
    nzp = sum(1 for x in vr_p[CB + n * 32: CB + n * 32 + 32] if x)
    print("  tile %-4d org: %s   oursNZ=%d" % (n, show(b), nzp))

print()
print("--- 在 ours 全 VRAM(0x0000-0x17FFF) 里搜这些字形 ---")
for n, b in DIG.items():
    if not any(b):
        continue
    hits = []
    for base in (0x0000, 0x4000, 0x8000, 0xC000, 0x10000, 0x14000):
        for off in range(0, 0x4000, 32):
            if vr_p[base + off: base + off + 32] == b:
                hits.append((base, off // 32))
    print("  tile %-4d -> %s" % (n, hits[:6] if hits else "NOT FOUND"))

print()
print("--- 反查：ours 里 120..127 / 116 附近的号有没有内容 ---")
for n in range(112, 132):
    a = sum(1 for x in vr_p[CB + n * 32: CB + n * 32 + 32] if x)
    o = sum(1 for x in vr_o[CB + n * 32: CB + n * 32 + 32] if x)
    print("  tile %-4d oursNZ=%-3d orgNZ=%-3d" % (n, a, o))
