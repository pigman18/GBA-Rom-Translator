"""font_probe.py — 直接从 .bin 资产量清 4bpp 容器布局（不经 ROM）。
只读。
"""
import numpy as np

BIN = r"C:\code\GBA-Rom-Translator\work\POKEMON_RUBY_AXVJ00\graphic\fonts\PokeRSFontChsMiddle_unshadow(0xE0000).bin"
NG = 7168
STRIDE = 128

raw = open(BIN, "rb").read()
print("bin size =", len(raw), " expect", NG * STRIDE)


def art(blk32, n=8):
    out = []
    for r in range(8):
        row = blk32[r * 4:r * 4 + 4]
        s = ""
        for b in row:
            s += "#" if (b & 0xF) else "."
            s += "#" if (b >> 4) else "."
        out.append(s)
    return out


def show(gid, label=""):
    p = gid * STRIDE
    blk = raw[p:p + STRIDE]
    TL, BL, TR, BR = blk[0:32], blk[32:64], blk[64:96], blk[96:128]
    print(f"\n=== gid {gid} {label}  四象限非零: TL={sum(1 for x in TL if x)} "
          f"BL={sum(1 for x in BL if x)} TR={sum(1 for x in TR if x)} BR={sum(1 for x in BR if x)}")
    print("   [TL | TR] 并列 8 行 (若 TR 有墨=16px 宽):")
    for a, b in zip(art(TL), art(TR)):
        print("   ", a, "|", b)
    print("   [BL | BR]:")
    for a, b in zip(art(BL), art(BR)):
        print("   ", a, "|", b)
    print("   >>> 若按 TL+BL 竖拼(8x16)应为: ")
    for a, b in zip(art(TL), art(BL)):
        print("   ", a, "|", b)


show(1727, "领")
show(995, "航")
show(3517, "员")

# 全库统计：按 8x16(前64B) 解释，逐行墨迹占用
N = NG
rows = np.zeros(16)
cols = np.zeros(8)
q = np.zeros(4)
for g in range(N):
    blk = raw[g * STRIDE:(g + 1) * STRIDE]
    for i in range(4):
        q[i] += sum(1 for x in blk[i * 32:(i + 1) * 32] if x)
    for half, tb in ((0, 0), (1, 32)):
        for r in range(8):
            row = blk[tb + r * 4:tb + r * 4 + 4]
            for ci in range(4):
                b = row[ci]
                if b & 0xF:
                    rows[half * 8 + r] += 1
                    cols[ci * 2] += 1
                if b >> 4:
                    rows[half * 8 + r] += 1
                    cols[ci * 2 + 1] += 1

print(f"\n== 全库 {N} 字 四象限非零总量: TL={q[0]:.0f} BL={q[1]:.0f} TR={q[2]:.0f} BR={q[3]:.0f}")
print("== 行占用(按 TL+BL 竖拼 8x16):", " ".join(f"{v:5.0f}" for v in rows))
print("== 列占用(8 列):", " ".join(f"{v:9.0f}" for v in cols))
