import glob,os,numpy as np
files=sorted(glob.glob('.tmp/drive_*_vram.bin'))
print(f"{'tag':<14}{'pair-rows':>10}{'pair-tiles':>11}  tiles")
for f in files:
    tag=os.path.basename(f)[6:-9]
    d=open(f,'rb').read()
    if len(d)!=0x18000: continue
    A=np.frombuffer(d,np.uint8).reshape(-1,32)
    R=A.reshape(-1,8,4)
    ok=(R[:,:,0]==R[:,:,1])&(R[:,:,2]==R[:,:,3])
    allok=ok.all(1)
    # 也统计“至少6行成对”
    cnt6=(ok.sum(1)>=6)
    if allok.sum()>0 or cnt6.sum()>0:
        idx=np.where(allok)[0]
        print(f"{tag:<14}{ok.sum():>10}{allok.sum():>11}  {[hex(i*32) for i in idx[:12]]}")
