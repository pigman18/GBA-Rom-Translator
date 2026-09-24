# -*- coding: utf-8 -*-
"""atlas.py <tag> — 检测各 charBlock 是否被引擎图集填充。
判断：每 tile 32 字节里非零字节数 + 非零 tile 比例。
若某 16KB 块「非零 tile 占比」很高且字节分布呈字形特征 → 该块被图集占用。"""
import sys
from pathlib import Path
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tag = sys.argv[1]
v = (T / ("drive_%s_vram.bin" % tag)).read_bytes()
print("vram len=%d" % len(v))
for cb in range(4):
    off = cb * 0x4000
    blk = v[off:off + 0x4000]
    if len(blk) < 0x4000:
        print("cb%d: 块不完整" % cb); continue
    nz = sum(1 for t in range(0, 0x4000, 32) if any(blk[t:t + 32]))
    # 前 512 tile (=16KB) 内的非零分布
    first = sum(1 for t in range(0, 512 * 32, 32) if any(blk[t:t + 32]))
    print("cb%d  0x%08X  非零tile=%4d/512  首512占%d  尾(512..1024)=%d"
          % (cb, 0x06000000 + off, nz, first,
             sum(1 for t in range(512 * 32, 0x4000, 32) if any(blk[t:t + 32]))))
