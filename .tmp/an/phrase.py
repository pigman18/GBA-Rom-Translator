# -*- coding: utf-8 -*-
"""核短语表：PhraseOffsets @0x08810000 (u32) → PhraseTable @0x08820000 + off, 0xFF 终止。"""
import json, struct, collections
ROM=r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba"
JS =r"C:/code/GBA-Rom-Translator/work/POKEMON_RUBY_AXVJ00/translate.build.json"
rom=open(ROM,"rb").read()
OFFS=0x08810000-0x08000000
TAB =0x08820000-0x08000000
n_off=(TAB-OFFS)//4
print("offsets 条目数 =",n_off)
raw=rom[OFFS:OFFS+n_off*4]
offs=list(struct.unpack("<%dI"%n_off, raw))
valid=[o for o in offs if o<0x01000000]
print("offset<0x01000000 的个数 =",len(valid)," 最大 =",hex(max(valid)) if valid else None)
print("前 12 个 offset:",[hex(o) for o in offs[:12]])
print("前 12 个非哨兵:",[hex(o) for o in valid[:12]])
def stream(code):
    o=offs[code]
    if o>=0x01000000: return None
    p=TAB+o
    end=rom.find(b"\xff",p,p+64)
    if end<0: return None
    return rom[p:end+1]
for c in (1,2,3,298,0x15c):
    s=stream(c)
    print("code %5d (0x%04X) -> %s"%(c,c," ".join("%02x"%b for b in s) if s else "INVALID"))
# 逐条核 道具名 / 宝可梦名 / UI界面 的 phrase_code
d=json.load(open(JS,encoding="utf-8"))
bad=collections.Counter(); good=collections.Counter(); samples=[]
for e in d["entries"]:
    if e.get("_reject"): continue
    pc=e.get("phrase_code")
    if pc is None: continue
    s=stream(pc)
    if s is None:
        bad[e["module"]]+=1
        if len(samples)<10: samples.append((e["module"],e["original"],e["translated"],pc))
    else:
        good[e["module"]]+=1
print("\nphrase_code 有效:",dict(good))
print("phrase_code 无效:",dict(bad))
for s in samples: print("   无效样例:",s)
