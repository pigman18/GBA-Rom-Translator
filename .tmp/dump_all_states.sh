#!/bin/bash
# 依次 dump 每个 savestate 并渲染成 PNG
set -u
export PATH="/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/bin:$PATH"
cd "C:/code/GBA-Rom-Translator" || exit 1

PY="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

for i in 1 2 3 4 5 6; do
  S="roms/outputs/POKEMON_RUBY_AXVJ00_translated.ss$i"
  [ -f "$S" ] || continue
  echo "########## ss$i ##########"
  bash .tmp/run_dump.sh "$S" 2>&1 | grep -E "PC=|vram done" | head -3
  if [ -f .tmp/gdb_vram.bin ]; then
    cp .tmp/gdb_vram.bin ".tmp/ss${i}_vram.bin"
    cp .tmp/gdb_pal.bin  ".tmp/ss${i}_pal.bin"
    cp .tmp/gdb_oam.bin  ".tmp/ss${i}_oam.bin"
    cp .tmp/gdb_io.bin   ".tmp/ss${i}_io.bin"
    "$PY" scripts/render_dump.py ".tmp/ss$i" ".tmp/shot_ss$i.png" 2>&1 | tail -2
  fi
done
echo "=== 完成 ==="
ls -la .tmp/shot_ss*.png 2>/dev/null
