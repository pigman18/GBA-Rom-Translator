import numpy as np, itertools
B=np.load('.tmp/zoom3/one_x.npy')
blk=(B[:,:,0]<40)&(B[:,:,1]<40)&(B[:,:,2]<40)
ROM=open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()
print("ROM",len(ROM))

def mask(y0,x0):
    m=np.zeros((16,8),bool)
    for r in range(16):
        for c in range(8):
            m[r,c]=blk[y0+r,x0+c]
    return m

cells={'b1c0':mask(8,16),'b1c1':mask(8,24),'b1c2':mask(8,32),'b1c3':mask(8,40),
       'b2c0':mask(72,16),'b2c1':mask(72,24),'b2c2':mask(72,32),
       'b3c0':mask(104,16),'b3c1':mask(104,24)}

def enc_4bpp_TLBL(m):   # 4bpp [TL][BL] 64B：上砖=row0-7, 下砖=row8-15
    out=bytearray()
    for half in (0,1):
        for r in range(8*half,8*half+8):
            for c in range(0,8,2):
                hi=0xF if m[r,c] else 0
                lo=0xF if m[r,c+1] else 0
                out.append((hi<<4)|lo)
    return bytes(out)

def enc_1bpp_rowmajor(m):  # 1B/行 MSB-first
    out=bytearray()
    for r in range(16):
        v=0
        for c in range(8):
            v=(v<<1)|(1 if m[r,c] else 0)
        out.append(v)
    return bytes(out)

def enc_1bpp_16B_interlace(m):  # 常见 1bpp 字库：每行 1B，但按 16px 宽布局取前 8
    return enc_1bpp_rowmajor(m)

def enc_2bpp(m):
    out=bytearray()
    for half in (0,1):
        for r in range(8*half,8*half+8):
            for c in range(0,8,4):
                b=0
                for k in range(4):
                    b=(b<<2)|(3 if m[r,c+k] else 0)
                out.append(b)
    return bytes(out)

encs={'4bpp_TLBL64':enc_4bpp_TLBL,'1bpp_16':enc_1bpp_rowmajor,'2bpp':enc_2bpp}
for name,e in encs.items():
    print("\n##### 编码",name)
    for cname,m in cells.items():
        p=e(m)
        hits=[]
        st=0
        while True:
            i=ROM.find(p,st)
            if i<0: break
            hits.append(i); st=i+1
            if len(hits)>40: break
        print(f"  {cname}: len={len(p)} 命中{len(hits)}: {[hex(h) for h in hits[:12]]}")
