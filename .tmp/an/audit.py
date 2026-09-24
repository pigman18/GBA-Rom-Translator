# -*- coding: utf-8 -*-
"""成品 ROM 逐条 vs translate.build.json target_hex。"""
import json, collections, re
ROM=r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba"
JS =r"C:/code/GBA-Rom-Translator/work/POKEMON_RUBY_AXVJ00/translate.build.json"
rom=open(ROM,"rb").read()
d=json.load(open(JS,encoding="utf-8"))
ents=d["entries"]
mismatch=collections.Counter(); ok=collections.Counter(); truncated=[]
for e in ents:
    if e.get("_reject"): continue
    th=e.get("target_hex") or ""
    if not th: continue
    try: want=bytes.fromhex(th.replace(" ",""))
    except Exception: continue
    addr=int(e["address"],16)
    off=addr-0x08000000
    got=rom[off:off+len(want)]
    mod=e["module"]
    if got==want: ok[mod]+=1
    else:
        mismatch[mod]+=1
        if len(truncated)<25:
            truncated.append((mod,e.get("original"),e.get("translated"),e.get("byte_length"),
                              th, (" ".join("%02x"%b for b in got))))
print("总条目",len(ents))
print("\n一致(前 25 模块):")
for m,n in ok.most_common(25): print("   %-16s %5d"%(m,n))
print("\n不一致(前 25 模块):")
for m,n in mismatch.most_common(25): print("   %-16s %5d"%(m,n))
print("\n不一致样例:")
for t in truncated: print("   ",t)
