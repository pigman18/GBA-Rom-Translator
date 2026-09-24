# -*- coding: utf-8 -*-
"""cen2.py <tag...> — 紧凑占用普查：每层引用号范围 + 全局被引用号并集 + 内容非零段"""
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
    print("=== %s ===" % tag)
    dc = reg.get("DISPCNT",0)
    for n in range(4):
        c = reg.get("BG%dCNT" % n, 0)
        if False:
            print("  BG%d off" % n); continue
        cb = ((c>>2)&3)*512; sb = ((c>>8)&0x1F)*0x800
        cnt = {}
        for ty in range(32):
            for tx in range(32):
                t = struct.unpack_from("<H", v, sb+(ty*32+tx)*2)[0] & 0x3FF
                if t: cnt[t] = cnt.get(t,0)+1
        ks = sorted(cnt)
        print("  BG%d cb=%d(%05X) idx %s" % (n, (c>>2)&3, 0x06000000+((c>>2)&3)*0x4000, runs(ks) if ks else "-"))
    nz = [p for p in range(2048) if any(v[p*32:p*32+32])]
    print("  nz内容号 %s" % runs(nz))
