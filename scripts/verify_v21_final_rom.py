#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对**最终 ROM**（roms/outputs/..._translated.gba）做 v21 落地校验。

与 scripts/verify_v21_armips.py（校验 armips 中间产物 output.gba）互补：
本脚本校验「meowth 全流程打完的成品」，是交付前的最后一道闸门。

闸门：
  A. 0x080029E0 == 01 20 70 47（P32 预取短接桩进了成品）
  B. 模板表 53×0x18 中 `+0x09` 分布 == {0:14, 1:36, 2:1, 3:2}
     且**除 charmap 无关的 0 处外，模板区与 origin 逐字节相同**
  C. hook 区 @0x08800000 与 hook/out/game.bin 逐字节一致
"""
import sys
from pathlib import Path

ROOT = Path(r"C:\code\GBA-Rom-Translator")
ORIG = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
FINAL = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"
GAMEBIN = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "hook" / "out" / "game.bin"

BASE = 0x08000000
TPL_BASE = 0x081BB3DC
TPL_STRIDE = 0x18
TPL_N = 53

WORKER = 0x080029E0
STUB = bytes((0x01, 0x20, 0x70, 0x47))
ORIGW = bytes((0x10, 0xB5, 0x07, 0x48))

o = ORIG.read_bytes()
f = FINAL.read_bytes()
gb = GAMEBIN.read_bytes()
fail = []

print(f"origin   = {len(o)} B")
print(f"final    = {len(f)} B")
print(f"game.bin = {len(gb)} B")

# ---- A. P32 桩 ----
w = WORKER - BASE
print(f"A 0x080029E0: origin={o[w:w+4].hex()}  final={f[w:w+4].hex()}  expect={STUB.hex()}")
if o[w:w+4] != ORIGW:
    fail.append("A origin 字节与预期不符（基线漂移）")
if f[w:w+4] != STUB:
    fail.append("A 最终 ROM 里没有 P32 桩")

# ---- B. 模板表 ----
tm = {}
diff = []
for i in range(TPL_N):
    a = TPL_BASE - BASE + i * TPL_STRIDE
    tm[f[a + 9]] = tm.get(f[a + 9], 0) + 1
    if o[a:a + TPL_STRIDE] != f[a:a + TPL_STRIDE]:
        diff.append(i)
print(f"B 模板表 tm 分布 = {dict(sorted(tm.items()))}  (期望 {{0:14, 1:36, 2:1, 3:2}})")
print(f"B 模板表与 origin 不同的记录 = {diff if diff else '0 条'}")
if tm != {0: 14, 1: 36, 2: 1, 3: 2}:
    fail.append(f"B tm 分布异常 {tm}")
if diff:
    fail.append(f"B 模板区被改动: {diff}")

# ---- C. hook 区 ----
seg = f[0x800000:0x800000 + len(gb)]
if seg == gb:
    print(f"C hook 区 @0x08800000 ({len(gb)} B) 与 game.bin 逐字节一致 OK")
else:
    d = next(k for k in range(len(gb)) if seg[k] != gb[k])
    print(f"C hook 区不一致：首个差异 @{0x08800000+d:#010x} final={seg[d]:#04x} bin={gb[d]:#04x}")
    fail.append("C hook 区不一致")

if fail:
    print("\nFAIL")
    for x in fail:
        print("   " + x)
    sys.exit(1)
print("\n全部通过 —— 最终 ROM 已含 P32 且模板表干净")
