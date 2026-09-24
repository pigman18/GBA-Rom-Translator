#!/bin/bash
# run_probe.sh <savestate|-> [seclimit]
set -u
export PATH="/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/bin:$PATH"
cd "C:/code/GBA-Rom-Translator" || exit 1

GDB="/c/Program Files (x86)/Arm GNU Toolchain arm-none-eabi/14.2 rel1/bin/arm-none-eabi-gdb.exe"
EMU="./tools/mGBA-0.10.5-win32/mGBA.exe"
ROM="C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba"
STATE="${1:--}"
SEC="${2:-40}"

ARGS=(-g -1)
[ "$STATE" != "-" ] && ARGS+=(-t "$STATE")
ARGS+=("$ROM")

"$EMU" "${ARGS[@]}" > .tmp/emu_probe.log 2>&1 &
EMUPID=$!
sleep 7

timeout "$SEC" "$GDB" -nx -batch -x .tmp/probe_bp.gdb 2>&1 \
  | grep -viE "GAME ERROR|warning|^$" | head -80

kill "$EMUPID" 2>/dev/null; sleep 1; kill -9 "$EMUPID" 2>/dev/null
