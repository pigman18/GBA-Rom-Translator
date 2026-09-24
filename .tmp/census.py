# -*- coding: utf-8 -*-
"""census.py <tag...> — 物理 tile 占用普查。
物理地址 = 0x06000000 + 物理号*32（物理号 0..2047 = cb0..cb5）。
对每个 BG 层：tilemap 索引 i → 物理号 = charBase*512 + i。
统计「被任何 BG map 引用」的物理号 + 「非零内容」的物理号，给出空闲段。
"""
import re, struct, sys
from pathlib import Path
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
def io(tag):
    txt = (T / ("drive_%s.log" % tag)).read_text(encoding="utf-8", errors="replace")
    return {m.group(1): int(m.group(2), 16)
            for m in re.finditer(r"IO (\w+) 0x[0-9a-f]+:\s*(0x[0-9a-fA-F]+)", txt)}
def runs(xs):
    if not xs: return "-"
    out, s, p = [], xs[0], xs[0]
    for x in xs[1:]:
        if x == p+1: p = x
        else: out.append((s,p)); s=p=x
    out.append((s,p))
    return " ".join(("%d-%d" % r) if r[0]!=r[1] else str(r[0]) for r in out)
for tag in sys.argv[1:]:
    reg = io(tag); v = (T / ("drive_%s_vram.bin" % tag)).read_bytes()
    used = set()
    print("=== %s ===" % tag)
    for n in range(4):
        c = reg.get("BG%dCNT" % n, 0)
        if not (reg.get("DISPCNT",0) >> n) & 1: 
            print("  BG%d 未使能" % n); continue
        cb = ((c>>2)&3)*512; sb = ((c>>8)&0x1F)*0x800
        cnt = {}
        for ty in range(32):
            for tx in range(32):
                t = struct.unpack_from("<H", v, sb+(ty*32+tx)*2)[0] & 0x3FF
                if t: cnt[t] = cnt.get(t,0)+1
        physical = sorted(cb+t for t in cnt)
        used |= set(physical)
        print("  BG%d cb=%d(%d) 引用 %d 个索引 → 物理号 %d 个，范围 %d..%d"
              % (n, cb//512, cb*32+0x06000000, len(cnt), len(physical),
                 physical[0] if physical else -1, physical[-1] if physical else -1))
    nz = set()
    for p in range(2048):
        if any(v[p*32:p*32+32]): nz.add(p)
    print("  内容非零物理号 %d 个，范围 %s" % (len(nz), runs(sorted(nz))[:400]))
    print("  ⚠ 全空闲（未被引用）物理号段: %s" % runs([p for p in range(2048) if p not in used])[:400])
