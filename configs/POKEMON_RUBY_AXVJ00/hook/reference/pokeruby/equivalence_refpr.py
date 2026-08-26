#!/usr/bin/env python3
"""mode2 门控窗桥接对照：现役 draw_tile(三段循环) vs refpr_draw_tile_shadowed 数学。

前置：mode2 grid spill 槽 idx+1 与主槽物理相邻(+32B)，textMode=UNKNOWN0。
裁决方式：穷举 startPixel×width×底图/墨迹/颜色，两种源映射候选
  (A) 原始 tile 字节流；  (B) 逐字节 nibble swap 后
与基线逐字节比对——bit-exact 的候选即为 runtime 采用格式。"""

import hashlib, importlib.util, random, re

spec = importlib.util.spec_from_file_location(
    "tables", r"reference/pokeruby/_tables_inc.py")
T = importlib.util.module_from_spec(spec); spec.loader.exec_module(T)

# ---- parse upstream mask table text into dict[(w,sp)] = (w0,w1,w2) ----
MASKS = {}
body = T.MASKS_SRC.split("\n", 1)[1]
cur_w = cur_sp = None
depth = 0
for l in body.splitlines():
    s = l.strip()
    if s.startswith("{ 0x"):            # row of three words for [width][sp]
        pass
    m = re.match(r"^static const u32 sGlyphMasks\[9\]\[8\]\[3\]", l)
    nums = re.findall(r"0x[0-9A-Fa-f]{8},|0x[0-9A-Fa-f]{8} ?,", l)
    # simpler: rely on explicit structural parse below
# robust parse: strip comments, walk braces
txt = T.MASKS_SRC
txt = re.sub(r"/\*.*?\*/", "", txt, flags=re.S)
head = txt[:txt.index("=")+1].strip()
inner = txt[txt.index("{"):]
nums = [int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{8})", inner)]
assert len(nums) == 9*8*3, len(nums)
it = iter(nums)
for w in range(9):
    for sp in range(8):
        MASKS[(w, sp)] = (next(it), next(it), next(it))

SHIFTS = dict(zip(range(8), T.SHIFTS))

# ---------- baseline (现役 draw_tile 直译，同 equivalence_test.py) ----------
def get_px(t,x,y):
    b=t[y*4+(x>>1)]; return (b&0xF) if (x&1) else (b>>4)
def put_px(t,x,y,ink):
    i=y*4+(x>>1)
    if x&1: t[i]=(t[i]&0xF0)|(ink&0xF)
    else:   t[i]=(t[i]&0x0F)|((ink&0xF)<<4)

def baseline(dest_in, spill_in, sp, w, cd, temp32):
    gw=sp+w; need=(spill_in is not None) and gw>8
    d=bytearray(dest_in); s=bytearray(spill_in) if need else None
    for r in range(8):
        for c in range(sp,min(gw,8)): put_px(d,c,r,cd)
        if need:
            for c in range(0,min(gw-8,8)): put_px(s,c,r,cd)
        for c in range(w):
            dc=sp+c
            if dc<8: put_px(d,dc,r,get_px(temp32,c,r))
            elif need: put_px(s,dc-8,r,get_px(temp32,c,r))
        if gw<8:
            for c in range(gw,8): put_px(d,c,r,cd)
        if need and gw>8:
            for c in range(gw-8,8): put_px(s,c,r,cd)
    return bytes(d),(bytes(s) if need else None)

# ---------- refpr 官方数学（upstream DrawGlyphTile_ShadowedFont + Shift 族直译） ----------
def rows_words(tile32, swap):
    """tile 字节流 → 每行一个 u32。swap=True 时逐字节高低调换。"""
    out=[]
    for i in range(8):
        b0,b1,b2,b3 = tile32[i*4:i*4+4]
        if swap:
            f=lambda b:((b>>4)|(b<<4))&0xFF
            b0,b1,b2,b3=f(b0),f(b1),f(b2),f(b3)
        out.append((b0<<24)|(b1<<16)|(b2<<8)|b3)   # upstream Shadowed src 是 u32 行,MSB-first nibble
    return out

def shift_combine(gb_pixel_row_hi_slot, gb_pixel_row_lo_slot, src_word, w, colors, sp):
    """按 width 变体展开 upstream shift 语义（各 WidthN 的组合模式一致化）。"""
    lo,right = SHIFTS[w] if w < 8 else (28,4)
    val = 0; sh = 0
    # width N consumes top-N nibbles of src word (MSB-first), each OR'd shifted left by k*4
    for k in range(w):
        v = colors[(src_word >> (28-4*k)) & 0xF]
        val |= v << (4*(w-1-k))     # 官方组合：第一消费位放低位端? 由两候选实验定 → 见调用处 A/B packing
    return val, lo, right

def refpr(dest_in, spill_in, sp, w, cd, temp32, swap, inkorder):
    gw=sp+w; need=(spill_in is not None) and gw>8
    d=bytearray(dest_in); s=bytearray(spill_in) if need else None
    dw=[int.from_bytes(d[i*4:i*4+4],"big") for i in range(8)]      # GBA 大端视觉序
    sw=[int.from_bytes(s[i*4:i*4+4],"big") for i in range(8)] if need else None
    masks=MASKS[(min(w,8),sp)]
    m1=masks[0]|masks[2]; m2=masks[1]
    pr=[dw[i]&m1 for i in range(8)]
    pr2=([sw[i]&m2 for i in range(8)] if need else [0]*8)
    colors=list(range(16)); colors[0]=cd  # LUT：nibble0→bg 终端色，其余直通
    rows=rows_words(temp32,swap)
    def setnib(prArr,i,col,v):
        if col<8:
            m=~(0xF<<(28-4*col))&0xFFFFFFFF
            prArr[i]=(prArr[i]&m)|((v&(0xF>>0))<<(28-4*col)&0xFFFFFFFF)|(v<<(28-4*col))
            prArr[i]&=0xFFFFFFFF
        else:
            c2=col-8
            m=~(0xF<<(28-4*c2))&0xFFFFFFFF
            pr2[i]=(pr2[i]&m)|(v<<(28-4*c2))
            pr2[i]&=0xFFFFFFFF
    gw=sp+w
    for i in range(8):
        roww=rows[i]
        acc_hi=0; acc_lo=0
        for k in range(min(w,8)):
            pass
        # main ink+n
        for k in range(w):
            v=colors[(roww>>(28-4*k))&0xF]
            pos=sp+k
            if pos<8: pr[i]=(pr[i]&~(0xF<<(28-4*pos)))|(v<<(28-4*pos))
            elif need: pr2[i]=(pr2[i]&~(0xF<<(28-4*(pos-8))))|(v<<(28-4*(pos-8)))
        # baseline-matching explicit bg sweeps:
        if not need and gw<8:
            for c in range(gw,8): setnib(pr,i,c,colors[0])
        if need:
            for c in range(8): setnib(pr2,i,c,colors[0])
    out_d=b"".join(x.to_bytes(4,"big") for x in pr)
    out_s=None
    if need:
        out_s=b"".join(x.to_bytes(4,"big") for x in pr2)
    return out_d,out_s,inkorder and swap

def run(name_expect, transform):
    rnd=random.Random(777)
    fails=0; total=0; first=None
    cases=[]
    for sp in range(8): cases.append((sp,8,True))
    for sp in range(8):
        for w in range(1,5): cases.append((sp,w,True)); cases.append((sp,w,False))
    for _ in range(20000):
        cases.append((rnd.randrange(8), rnd.choice([8]+list(range(1,5))), rnd.random()<.5))
    for sp,w,have_spill in cases:
        gw=sp+w; exists=have_spill and gw>8
        bd=bytes(rnd.getrandbits(8) for _ in range(32))
        bs=bytes(rnd.getrandbits(8) for _ in range(32)) if exists else None
        temp=bytes(rnd.getrandbits(8) for _ in range(32))
        cd=rnd.randrange(16)
        o_d,o_s=baseline(bd,bs,sp,w,cd,temp)
        n_d,n_s,_=refpr(bd,bs,sp,w,cd,temp,transform["swap"],transform["order"])
        total+=1
        same=(o_d==n_d) and ((o_s is None)==(n_s is None)) and (o_s is None or o_s==n_s)
        if not same:
            fails+=1
            if first is None: first=(sp,w,have_spill,o_d.hex(),o_s,n_d.hex(),n_s)
    print(f"[{name_expect}] cases={total} mismatches={fails}")
    if first: print("  first mismatch:", first[:4])
    return fails==0

if __name__=="__main__":
    ok_a=run("raw-bytes(no swap)",{"swap":False,"order":True})
    ok_b=run("byte-swizzled     ",{"swap":True ,"order":True})
    print("USE raw" if ok_a else ("USE swapped" if ok_b else "NEITHER MATCHES — deeper analysis required"))

# =====================================================================================
# 【状态 2026-08-27】host-oracle(clang 直跑 vendored C,_host/oracle*.exe)已证实:
#   · 无溢出域(startPixel+width<=8)与本工程 draw_tile 逐位一致;
#   · 有溢出域存在三处分歧待实机定位:
#     (1) spill 回写分支疑似未触发(spill 保持底图);
#     (2) gb.pixelRows 内容本身正确(mask/LUT/移位数学符合预期);
#     (3) TM!=2 分支预读 buffer[16..23] 越界读——调用方须保证 dest 后 >=64B 可读。
#   ⇒ 结论:剩余差异必须在 mGBA + gdb 断点会话内定位(HOOK_DEBUG_WORKFLOW),
#     离线脚本推演已到能力边界。runtime 未切换。
# =====================================================================================
