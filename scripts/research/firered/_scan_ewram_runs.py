#!/usr/bin/env python3
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
n = min(len(zh), len(ja))
BASE = 0x08000000
ew = (ROOT / "work/_probe/ewram/d1.ewram.bin").read_bytes()
best = []
i = 0
m = len(ew) // 4 * 4
while i < m:
    v = struct.unpack_from("<I", ew, i)[0]
    if BASE <= v < BASE + n:
        j = i
        cnt = 0
        while j < m and BASE <= struct.unpack_from("<I", ew, j)[0] < BASE + n:
            cnt += 1
            j += 4
        if cnt >= 16:
            ok = 0
            samples = []
            for k in range(cnt):
                p = struct.unpack_from("<I", ew, i + k * 4)[0] - BASE
                e = zh.find(b"\xff", p, p + 64)
                src = zh
                if e < 0:
                    e = ja.find(b"\xff", p, p + 64)
                    src = ja
                if e > 0:
                    ok += 1
                    if len(samples) < 3:
                        samples.append(src[p:e][:16].hex(" "))
            best.append((ok / cnt, cnt, 0x02000000 + i, ok, samples))
        i = j
    else:
        i += 4
best.sort(reverse=True)
print("top textlike pointer runs:")
for score, cnt, addr, ok, samples in best[:20]:
    print(f"  0x{addr:08X} n={cnt} ff={ok}/{cnt} ({score:.0%}) samples={samples}")
for lit in (0x081DB6D8, 0x081DB85C):
    print(f"lit 0x{lit:08X}=0x{struct.unpack_from('<I', zh, lit - BASE)[0]:08X}")
# also check all d*.f7table
for f in sorted((ROOT / "work/_probe/ewram").glob("d*.f7table.bin")):
    b = f.read_bytes()
    nz = sum(1 for x in b if x)
    print(f"{f.name}: nonzero={nz}")
