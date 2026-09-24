#!/bin/bash
# 启动 mGBA(+gdb stub) → 用标准 arm-none-eabi-gdb dump 一帧 → 杀模拟器
# 用法: bash .tmp/run_dump.sh [savestate|-]
set -u
export PATH="/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/bin:$PATH"
cd "C:/code/GBA-Rom-Translator" || exit 1

GDB="/c/Program Files (x86)/Arm GNU Toolchain arm-none-eabi/14.2 rel1/bin/arm-none-eabi-gdb.exe"
EMU="./tools/mGBA-0.10.5-win32/mGBA.exe"
ROM="roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba"
STATE="${1:--}"
WAIT="${2:-7}"

ARGS=(-g -1)
if [ "$STATE" != "-" ]; then
  ARGS+=(-t "$STATE")
fi
ARGS+=("$ROM")

"$EMU" "${ARGS[@]}" > .tmp/emu_run.log 2>&1 &
EMUPID=$!
sleep "$WAIT"

"$GDB" -nx -batch -x .tmp/dump.gdb 2>&1 | grep -v "GAME ERROR"

kill "$EMUPID" 2>/dev/null
sleep 1
kill -9 "$EMUPID" 2>/dev/null
echo "=== 产物 ==="
ls -la .tmp/gdb_*.bin 2>/dev/null
