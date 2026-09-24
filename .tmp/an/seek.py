# -*- coding: utf-8 -*-
"""对每个模块抽样：target_hex 到底在不在成品 ROM 里（全文件搜）。"""
import json, collections
ROM=r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba"
JS =r"C:/code/GBA-Rom-Translator/work/POKEMON_RUBY_AXVJ00/translate.build.json"
rom=open(ROM,"rb").read()
d=json.load(open(JS,encoding="utf-8"))
stat=collections.Counter(); miss=collections.defaultdict(list); moved=collections.Counter()
for e in d["entries"]:
    if e.get("_reject"): continue
    th=e.get("target_hex") or ""
    if not th: continue
    want=bytes.fromhex(th.replace(" ",""))
    mod=e["module"]; addr=int(e["address"],16); off=addr-0x08000000
    at = rom[off:off+len(want)]==want
    pos = rom.find(want)
    if at: stat[(mod,"就地")]+=1
    elif pos>=0:
        stat[(mod,"他处")]+=1
        if len(miss[mod])<3: miss[mod].append((e.get("original"),e.get("translated"),hex(addr),hex(pos+0x08000000)))
    else:
        stat[(mod,"失踪")]+=1
        if len(miss[mod])<3: miss[mod].append((e.get("original"),e.get("translated"),hex(addr),None))
mods=sorted(set(m for m,_ in stat))
print("%-22s %6s %6s %6s"%("模块","就地","他处","失踪"))
for m in mods:
    print("%-22s %6d %6d %6d"%(m,stat[(m,"就地")],stat[(m,"他处")],stat[(m,"失踪")]))
print("\n样例（他处/失踪）:")
for m,v in miss.items():
    print("--",m)
    for x in v: print("    ",x)
