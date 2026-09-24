"""dump AXVJ00 模板表原始字节，找 tm 字段的真实偏移。

模板表：0x081BB3DC 起 53×0x18（来自 docs/15-0b）。
本脚本不假设任何字段位置，只用「可判别的物理约束」反推：
  S1  tileData 指针字段：53 条全部落在 0x06000000..0x06018000（4 对齐）
  S2  tm 字段：取值 ⊆ {0,1,2,3} 且分布接近 (tm0×14, tm1×36, tm2×1, tm3×2)
  S3  charBase：取值 ⊆ {0,1,2,3}
  S4  font：取值 ⊆ {1..6}
"""
from pathlib import Path
import struct

ROOT = Path(r"C:\code\GBA-Rom-Translator")
rom = (ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba").read_bytes()
BASE_ADDR = 0x08000000
TPL_BASE = 0x081BB3DC
STRIDE = 0x18
N = 53

recs = []
for i in range(N):
    o = TPL_BASE - BASE_ADDR + i * STRIDE
    recs.append(rom[o:o + STRIDE])

print("=== 原始 53×24 字节 ===")
for i, r in enumerate(recs):
    print(f"{i:2d} {TPL_BASE + i*STRIDE:#010x}  " + " ".join(f"{b:02X}" for b in r))

print("\n=== 逐偏移统计（看哪一列像什么） ===")
for off in range(STRIDE):
    col = [r[off] for r in recs]
    hist = {}
    for v in col:
        hist[v] = hist.get(v, 0) + 1
    mx = max(hist)
    uniq = len(hist)
    tag = ""
    if uniq <= 4:
        tag = f"  <= 小域 {dict(sorted(hist.items()))}"
    print(f"+{off:#04x} uniq={uniq:2d} maxval={mx:3d} {tag}")

print("\n=== 4 字节对齐字段（u32 LE）候选 ===")
for off in (0, 4, 8, 0x0C, 0x10, 0x14):
    vals = [struct.unpack_from("<I", r, off)[0] for r in recs]
    inrom = sum(1 for v in vals if 0x08000000 <= v < 0x08800000)
    invram = sum(1 for v in vals if 0x06000000 <= v < 0x06018000)
    print(f"+{off:#04x}  ROM指针 {inrom:2d}/53   VRAM指针 {invram:2d}/53   "
          f"样本 {[hex(v) for v in vals[:4]]}")

print("\n=== 反推：哪个偏移能命中 36 处 tm1 ===")
for off in range(STRIDE):
    ones = [i for i, r in enumerate(recs) if r[off] == 1]
    if len(ones) >= 10:
        print(f"+{off:#04x}  值==1 的条数 = {len(ones)}  idx={ones}")

print("\n=== 补丁文件里的 36 个地址，落回 idx/偏移 ===")
asm = (ROOT / "configs/POKEMON_RUBY_AXVJ00/hook/patches/textmode_tm1_to_tm0.asm"
       ).read_text(encoding="utf-8")
addrs = [int(l.split()[1], 16) for l in asm.splitlines() if l.strip().lower().startswith(".org")]
for a in addrs:
    d = a - TPL_BASE
    print(f"{a:#010x}  idx={d//STRIDE:2d}  off=+{d%STRIDE:#04x}  byte={rom[a-BASE_ADDR]:02X}")
