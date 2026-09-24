# -*- coding: utf-8 -*-
"""mkdiagrom.py -- 把刚编出的 hook（out/game.bin）直接烧进当前成品 ROM 的副本，
不跑 meowth 流水线。仅用于调试（诊断日志版）。

用法: python .tmp/mkdiagrom.py <out.gba> [src.gba]
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(r"C:/code/GBA-Rom-Translator")
HOOK = (ROOT / "configs/POKEMON_RUBY_AXVJ00/hook/out/game.bin").read_bytes()
hook_base = 0x00800000          # 0x08800000 - 0x08000000
src = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba"
dst = Path(sys.argv[1])

shutil.copyfile(src, dst)
b = bytearray(dst.read_bytes())
old_len = 8076
tail = bytes(b[hook_base + old_len:hook_base + len(HOOK)])
print("旧 hook 长度外 %d 字节: %s" % (len(HOOK) - old_len, tail.hex(" ") if tail else "(无)"))
assert all(x == 0 for x in tail), "hook 之后不是零，不能直接加长覆盖！"
b[hook_base:hook_base + len(HOOK)] = HOOK
dst.write_bytes(bytes(b))
print("saved %s  hook=%d bytes" % (dst, len(HOOK)))
