#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apply_v21_buildbat.py — 补上 hook/build.bat 的两处改动（CRLF 已归一化）"""
import os
import sys

ROOT = r"C:\code\GBA-Rom-Translator\configs\POKEMON_RUBY_AXVJ00\hook"
N = 0


def patch(path, old, new, tag):
    global N
    full = os.path.join(ROOT, path)
    with open(full, "r", encoding="utf-8", newline="") as f:
        raw = f.read()
    crlf = "\r\n" in raw
    text = raw.replace("\r\n", "\n")
    n = text.count(old)
    if n != 1:
        print("❌ [%s] 期望 1 处，实得 %d 处" % (tag, n))
        sys.exit(2)
    with open(full, "w", encoding="utf-8", newline="") as f:
        f.write((text.replace(old, new)).replace("\n", "\r\n") if crlf
                else text.replace(old, new))
    N += 1
    print("✅ [%s]" % tag)


patch("build.bat",
      "echo === Compiling text\\tile_alloc.c ===\n"
      "%CC% %CFLAGS% %TEXT%\\tile_alloc.c -o %BUILD%\\tile_alloc.o\n"
      "if errorlevel 1 exit /b 1",
      "echo === Compiling text\\tile_alloc.c ===\n"
      "%CC% %CFLAGS% %TEXT%\\tile_alloc.c -o %BUILD%\\tile_alloc.o\n"
      "if errorlevel 1 exit /b 1\n"
      "\n"
      "echo === Compiling text\\chs_canvas.c ===\n"
      "%CC% %CFLAGS% %TEXT%\\chs_canvas.c -o %BUILD%\\chs_canvas.o\n"
      "if errorlevel 1 exit /b 1",
      "build.bat: 编译 chs_canvas")

patch("build.bat",
      "  %BUILD%\\tile_alloc.o ^",
      "  %BUILD%\\tile_alloc.o ^\n  %BUILD%\\chs_canvas.o ^",
      "build.bat: 链接 chs_canvas")

print("\n✅ %d 处完成" % N)
