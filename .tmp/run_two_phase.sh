#!/bin/bash
# 分段 gdb：先用一次会话「跑 N 秒」再断开（游戏继续跑），然后重新连上抓帧。
set -u
export PATH="/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/bin:$PATH"
cd "C:/code/GBA-Rom-Translator" || exit 1

GDB="/c/Program Files (x86)/Arm GNU Toolchain arm-none-eabi/14.2 rel1/bin/arm-none-eabi-gdb.exe"
EMU="./tools/mGBA-0.10.5-win32/mGBA.exe"
ROM="roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba"
RUNSEC="${1:-12}"
TAG="${2:-run}"

"$EMU" -g -1 "$ROM" > ".tmp/emu_$TAG.log" 2>&1 &
EMUPID=$!
sleep 6

echo "--- 会话 A：跑 ${RUNSEC}s ---"
( timeout "$RUNSEC" "$GDB" -nx -batch -ex "target remote 127.0.0.1:2345" -ex "continue" > /dev/null 2>&1 ) &
GPID=$!
wait $GPID
echo "  gdb A 结束（timeout 杀）"

sleep 3
echo "--- 会话 B：重新连上抓帧 ---"
timeout 120 "$GDB" -nx -batch -x .tmp/dump_now.gdb 2>&1 | grep -v "GAME ERROR" | head -12

kill "$EMUPID" 2>/dev/null; sleep 1; kill -9 "$EMUPID" 2>/dev/null
for k in vram pal oam io ewram; do
  [ -f ".tmp/gdb_$k.bin" ] && cp ".tmp/gdb_$k.bin" ".tmp/${TAG}_$k.bin"
done
echo "saved .tmp/${TAG}_*.bin"
