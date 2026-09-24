#!/bin/bash
# 领航员页采样：菜单 idx3（图鉴/宝可梦/背包/领航员）
# 与 run_sample.sh 同套路，参数写死在脚本内（避免 env 前缀触发 wsl.exe 拦截）
set -u
export PATH="/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/bin:$PATH"
cd "C:/code/GBA-Rom-Translator"
PY="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
GDB="/c/Program Files (x86)/Arm GNU Toolchain arm-none-eabi/14.2 rel1/bin/arm-none-eabi-gdb.exe"

SCHED="A:240-280,A:330-370,A:420-460,A:510-550,A:600-640,A:690-730,A:780-820,A:870-910,A:960-1000,A:1050-1090,A:1140-1180,A:1230-1270,START:1500-1540,DOWN:1700-1740,DOWN:1850-1890,DOWN:2000-2040"
FRAMES=2280
TAG="nav1"
GDBFILE=".tmp/sample_itp_nav.gdb"
OUT=".tmp/itp_nav1.txt"

"$PY" scripts/mgba_drive.py --schedule "$SCHED" --frames "$FRAMES" --tag "$TAG" \
      --keep-alive --no-capture > ".tmp/drive_${TAG}.stdout" 2>&1
echo "[run] drive rc=$?"
tail -3 ".tmp/drive_${TAG}.stdout"

echo "[run] stub port:"
netstat -an | grep 2345 || echo "[run] !! 端口没开"

"$GDB" -nx -batch -x "$GDBFILE" > "$OUT" 2>&1
echo "[run] gdb rc=$?"
echo "[run] ITP 行数: $(grep -c '^ITP' "$OUT")"
grep "^ITP" "$OUT" | head -80
echo "--- tail ---"
tail -4 "$OUT"
