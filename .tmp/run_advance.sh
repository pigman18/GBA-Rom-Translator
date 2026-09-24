#!/bin/bash
# 加载电池存档 -> 用 IRQ 断点做帧步进 -> 按 A 推进 -> dump
set -u
export PATH="/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/bin:$PATH"
cd "C:/code/GBA-Rom-Translator" || exit 1

GDB="/c/Program Files (x86)/Arm GNU Toolchain arm-none-eabi/14.2 rel1/bin/arm-none-eabi-gdb.exe"
EMU="./tools/mGBA-0.10.5-win32/mGBA.exe"
ROM="roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba"
SCRIPT="${1:-.tmp/advance.gdb}"
TAG="${2:-advance}"

"$EMU" -g -1 "$ROM" > ".tmp/emu_$TAG.log" 2>&1 &
EMUPID=$!
sleep 7

timeout 300 "$GDB" -nx -batch -x "$SCRIPT" 2>&1 | grep -v "GAME ERROR" | head -30

kill "$EMUPID" 2>/dev/null; sleep 1; kill -9 "$EMUPID" 2>/dev/null

for k in vram pal oam io ewram; do
  [ -f ".tmp/gdb_$k.bin" ] && cp ".tmp/gdb_$k.bin" ".tmp/${TAG}_$k.bin"
done
echo "saved .tmp/${TAG}_*.bin"
