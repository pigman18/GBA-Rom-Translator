"""v21 armips 产物静态校验（一次性）。

校验 3 件事：
  A. P32 预取短接桩落地：0x080029E0..E3 == 01 20 70 47（movs r0,#1 ; bx lr）
  B. **模板表 53 条 0x18 字节与 origin 逐字节相同**（证明已彻底回退 P31 的 tm 改动）
  C. output.gba @0x08800000 与 out/game.bin 逐字节一致（hook 层落盘）
"""
import sys
from pathlib import Path

ROOT = Path(r"C:\code\GBA-Rom-Translator")
HOOK = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "hook"

BASE = HOOK / "baserom.gba"
OUT = HOOK / "output.gba"
GAMEBIN = HOOK / "out" / "game.bin"

TPL_BASE = 0x081BB3DC
TPL_STRIDE = 0x18
TPL_N = 53
BASE_ADDR = 0x08000000

WORKER = 0x080029E0
WORKER_STUB = bytes((0x01, 0x20, 0x70, 0x47))     # movs r0,#1 ; bx lr
WORKER_ORIG = bytes((0x10, 0xB5, 0x07, 0x48))     # push {r4,lr} ; ldr r0,[pc,#28]

base = BASE.read_bytes()
out = OUT.read_bytes()
gamebin = GAMEBIN.read_bytes()
fail = []

# ---- A. 预取短接桩 ----
o = WORKER - BASE_ADDR
if base[o:o + 4] != WORKER_ORIG:
    fail.append(f"A baserom @{WORKER:#010x} 原始字节 {base[o:o+4].hex()} != {WORKER_ORIG.hex()}"
                "（说明基线变了，桩的前提要重核）")
if out[o:o + 4] != WORKER_STUB:
    fail.append(f"A output  @{WORKER:#010x} = {out[o:o+4].hex()} != {WORKER_STUB.hex()}")

# ---- B. 模板表必须与 origin 完全一致 ----
diff = 0
for i in range(TPL_N):
    a = TPL_BASE - BASE_ADDR + i * TPL_STRIDE
    if base[a:a + TPL_STRIDE] != out[a:a + TPL_STRIDE]:
        diff += 1
        fail.append(f"B 模板 idx{i} @{TPL_BASE + i*TPL_STRIDE:#010x} 被改动了")

# tm 分布（应为 0:14 / 1:36 / 2:1 / 3:2）
hist = {}
for i in range(TPL_N):
    v = out[TPL_BASE - BASE_ADDR + i * TPL_STRIDE + 0x09]
    hist[v] = hist.get(v, 0) + 1

# ---- C. hook 落盘 ----
seg = out[0x800000:0x800000 + len(gamebin)]
if seg != gamebin:
    d = next(k for k in range(len(gamebin)) if seg[k] != gamebin[k])
    fail.append(f"C hook 区不一致：首个差异 @{0x08800000+d:#010x} "
                f"rom={seg[d]:#04x} bin={gamebin[d]:#04x}")

# ---- 报告 ----
print(f"baserom  = {len(base)} B")
print(f"output   = {len(out)} B")
print(f"game.bin = {len(gamebin)} B")
print(f"A 预取桩 {WORKER:#010x}: {base[o:o+4].hex()} -> {out[o:o+4].hex()}")
print(f"B 模板表 53×0x18：改动 {diff} 条；tm 分布 = {dict(sorted(hist.items()))}")
print(f"C hook 区 @0x08800000: {'逐字节一致 OK' if seg == gamebin else '不一致'}")

if fail:
    print("\nFAIL:")
    for f in fail[:30]:
        print("   " + f)
    sys.exit(1)
print("\n全部通过")
