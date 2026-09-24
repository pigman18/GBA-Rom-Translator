import struct
ROM=open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()
for name,a in [('V1_KEY_TAB',0x0203FE00),('V1_SLOT_N',0x0203FFC0),('V1_MAGIC',0x0203FFC2),
               ('V1_SIG_TPL',0x0203FFC4),('V1_SIG_CB',0x0203FFC8),('FONT_MIDDLE',0x09400000)]:
    p=struct.pack('<I',a)
    hits=[];st=0
    while True:
        i=ROM.find(p,st)
        if i<0: break
        hits.append(i); st=i+1
    print(f"{name} {a:#010x} 字面量出现 {len(hits)} 次: {[hex(h) for h in hits[:10]]}")
