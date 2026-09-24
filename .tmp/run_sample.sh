#!/bin/bash
# 一次调用内跑完：驱动到「设置」高亮 → keep-alive → 立刻接 gdb 采样 InitTextPrinter
set -u
export PATH="/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/bin:$PATH"
cd "C:/code/GBA-Rom-Translator"
PY="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
GDB="/c/Program Files (x86)/Arm GNU Toolchain arm-none-eabi/14.2 rel1/bin/arm-none-eabi-gdb.exe"
SCHED="${SCHED:-A:240-280,A:330-370,A:420-460,A:510-550,A:600-640,A:690-730,A:780-820,A:870-910,A:960-1000,A:1050-1090,A:1140-1180,A:1230-1270,START:1500-1540,DOWN:1700-1740,DOWN:1850-1890,DOWN:2000-2040,DOWN:2150-2190,DOWN:2300-2340,DOWN:2450-2490}"
FRAMES="${FRAMES:-2700}"
TAG="${TAG:-tw1}"
GDBFILE="${GDBFILE:-.tmp/sample_itp.gdb}"
OUT="${OUT:-.tmp/itp_out.txt}"

"$PY" scripts/mgba_drive.py --schedule "$SCHED" --frames "$FRAMES" --tag "$TAG" \
      --keep-alive --no-capture > ".tmp/drive_${TAG}.stdout" 2>&1
echo "[run] drive rc=$? tail:"
tail -3 ".tmp/drive_${TAG}.stdout"

echo "[run] stub port:"
netstat -an | grep 2345 || echo "[run] !! 端口没开"

"$GDB" -nx -batch -x "$GDBFILE" > "$OUT" 2>&1
echo "[run] gdb rc=$?"
echo "[run] ITP 行数: $(grep -c '^ITP' "$OUT")"
grep "^ITP" "$OUT" | head -60
echo "--- tail ---"
tail -4 "$OUT"
