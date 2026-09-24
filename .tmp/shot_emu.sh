#!/bin/bash
# shot_emu.sh <savestate|-> <tag> [rom] [wait_sec]
# 启动真实 mGBA 窗口 → 截取窗口位图（不经自写渲染器）→ 杀进程
set -u
export PATH="/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/bin:$PATH"
cd "C:/code/GBA-Rom-Translator" || exit 1

EMU="C:/code/GBA-Rom-Translator/tools/mGBA-0.10.5-win32/mGBA.exe"
ROM="${3:-C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba}"
STATE="${1:--}"
TAG="${2:-emu}"
WAIT="${4:-9}"
OUT="C:/code/GBA-Rom-Translator/.tmp/emu_${TAG}.png"

ARGS=(-3)
if [ "$STATE" != "-" ]; then
  ARGS+=(-t "$STATE")
fi
ARGS+=("$ROM")

"$EMU" "${ARGS[@]}" > ".tmp/emu_${TAG}.log" 2>&1 &
EMUPID=$!
sleep "$WAIT"

powershell.exe -NoProfile -ExecutionPolicy Bypass \
  -File "C:\\code\\GBA-Rom-Translator\\.tmp\\cap_win.ps1" -Out "$OUT" 2>&1 | tail -3

kill "$EMUPID" 2>/dev/null
sleep 1
kill -9 "$EMUPID" 2>/dev/null
echo "log: .tmp/emu_${TAG}.log"
