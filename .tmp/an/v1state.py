import glob, os, struct
EW=0x02000000
OFF_N   =0x0203FFC0-EW
OFF_MAG =0x0203FFC2-EW
OFF_TPL =0x0203FFC4-EW
OFF_CB  =0x0203FFC8-EW
OFF_KEY =0x0203FE00-EW

files=sorted(glob.glob('.tmp/drive_*_ewram.bin'))
print(f"{'tag':<16}{'magic':>8}{'N':>6}{'sigTpl':>12}{'sigCb':>7}  keys[0:8]")
for f in files:
    tag=os.path.basename(f)[6:-10]
    d=open(f,'rb').read()
    if len(d)!=262144: continue
    mag=struct.unpack_from('<H',d,OFF_MAG)[0]
    n  =struct.unpack_from('<H',d,OFF_N)[0]
    tpl=struct.unpack_from('<I',d,OFF_TPL)[0]
    cb =d[OFF_CB]
    keys=[struct.unpack_from('<H',d,OFF_KEY+2*i)[0] for i in range(8)] if mag==0x5631 else []
    mark='***' if mag==0x5631 else '   '
    print(f"{tag:<16}{mag:#8x}{n:6d}{tpl:#12x}{cb:7d}  {mark} {[hex(k) for k in keys]}")
