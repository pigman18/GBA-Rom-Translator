#!/bin/bash
# 用指定 ROM 跑指定 savestate 并 dump，产物存到 .tmp/<tag>_*.bin
# 用法: bash .tmp/dump_with.sh <tag> <rom> <savestate>
set -u
export PATH="/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/bin:$PATH"
cd "C:/code/GBA-Rom-Translator" || exit 1

GDB="/c/Program Files (x86)/Arm GNU Toolchain arm-none-eabi/14.2 rel1/bin/arm-none-eabi-gdb.exe"
EMU="./tools/mGBA-0.10.5-win32/mGBA.exe"
TAG="$1"; ROM="$2"; STATE="$3"

"$EMU" -g -1 -t "$STATE" "$ROM" > ".tmp/emu_$TAG.log" 2>&1 &
EMUPID=$!
sleep 7
"$GDB" -nx -batch -x .tmp/dump.gdb 2>&1 | grep -E "PC=|vram done"

kill "$EMUPID" 2>/dev/null; sleep 1; kill -9 "$EMUPID" 2>/dev/null

for k in vram pal oam io ewram; do
  [ -f ".tmp/gdb_$k.bin" ] && cp ".tmp/gdb_$k.bin" ".tmp/${TAG}_$k.bin"
done
echo "saved .tmp/${TAG}_*.bin"
