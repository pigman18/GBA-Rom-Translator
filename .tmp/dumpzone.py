# -*- coding: utf-8 -*-
import struct
from pathlib import Path
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tags = ["orgparty","v_opt","opt","coldOptDump","bypOpt","v_party","t_info","x_sum2","o_menu","t_moves"]
for t in tags:
    p = T / f"drive_{t}_ewram.bin"
    if not p.exists():
        continue
    b = p.read_bytes()[0x3FF00:0x40000]
    cur  = struct.unpack_from("<H", b, 0x42)[0]
    ph   = struct.unpack_from("<H", b, 0x44)[0]
    phr  = struct.unpack_from("<H", b, 0x46)[0]
    last = struct.unpack_from("<H", b, 0x48)[0]
    magic= struct.unpack_from("<H", b, 0x4A)[0]
    win  = struct.unpack_from("<I", b, 0x4C)[0]
    tpl  = struct.unpack_from("<I", b, 0x58)[0]
    print("%-12s CURSOR=%5d PHASE=%5d PHROW=%04X LAST=%5d MAGIC=%04X WIN=%08X TPL=%08X"
          % (t, cur, ph, phr, last, magic, win, tpl))
