#!/bin/bash
# gdbrun.sh <state|-> <gdb-script> [wait_sec]
set -u
export PATH="/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/bin:$PATH"
ROOT="C:/code/GBA-Rom-Translator"
EMU="$ROOT/tools/mGBA-0.10.5-win32/mGBA.exe"
GDB="/c/Program Files (x86)/Arm GNU Toolchain arm-none-eabi/14.2 rel1/bin/arm-none-eabi-gdb.exe"
STATE="${1:--}"
SCRIPT="$2"
WAIT="${3:-40}"
OUT="/c/code/GBA-Rom-Translator/.tmp/gdb_out.txt"

taskkill //F //IM mGBA.exe //T >/dev/null 2>&1
sleep 1

ARGS=(-g -3)
if [ "$STATE" != "-" ]; then
  ARGS+=(-t "$STATE")
fi
ARGS+=("$ROOT/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba")
(cd "$ROOT/tools/mGBA-0.10.5-win32" && exec ./mGBA.exe "${ARGS[@]}" >/dev/null 2>&1 &)
sleep 6

: > "$OUT"
"$GDB" -nx -batch -x "$SCRIPT" > "$OUT" 2>&1 &
GPID=$!
for _ in $(seq 1 "$WAIT"); do
  sleep 1
  kill -0 "$GPID" 2>/dev/null || break
done
if kill -0 "$GPID" 2>/dev/null; then
  echo "[gdbrun] gdb 仍在跑 ${WAIT}s，强杀（输出为部分结果）"
  kill -9 "$GPID" 2>/dev/null
fi
sleep 1
cat "$OUT"
taskkill //F //IM mGBA.exe //T >/dev/null 2>&1
