import sys, struct
D = open('roms/origin/POKEMON_RUBY_AXVJ00.gba', 'rb').read()
REG = ['r0','r1','r2','r3','r4','r5','r6','r7','r8','r9','r10','r11','r12','sp','lr','pc']
def u16(a): return struct.unpack_from('<H', D, a - 0x08000000)[0]

def d16(h, a):
    r = lambda x: REG[x]

    # ---- Shift (immediate) : 000 op imm5 Rm Rd ----
    if (h & 0xE000) == 0x0000:
        op = (h >> 11) & 3
        imm5 = (h >> 6) & 0x1F
        if op <= 2:
            n = {0: imm5, 1: (32 if imm5 == 0 else imm5), 2: (32 if imm5 == 0 else imm5)}[op]
            return f'{"lsls" if op==0 else "lsrs" if op==1 else "asrs"} {r((h>>3)&7)}, {r(h&7)}, #{n}'
        return f'?shift {h:04X}'

    # ---- Add/subtract : 00011 op I 0 Rn/imm3 Rs/imm3 Rd ----
        I = (h >> 10) & 1
        op = (h >> 9) & 1
        nm = 'subs' if op else 'adds'
        if I:
            imm3 = (h >> 6) & 7
            Rn = (h >> 3) & 7
            return f'{nm} {r(h&7)}, {r(Rn)}, #{imm3}'
        Rn = (h >> 3) & 7
        Rs = (h >> 6) & 7
        return f'{nm} {r(h&7)}, {r(Rn)}, {r(Rs)}'

    # ---- ALU ops : 010000 op Rm Rdn ----
    if (h & 0xFC00) == 0x4000:
        ALU = {0:'ands',1:'eors',2:'lsls',3:'lsrs',4:'asrs',5:'adcs',6:'sbcs',7:'rors',
               8:'tst',9:'rsbs',10:'cmp',11:'cmn',12:'orrs',13:'muls',14:'bics',15:'mvns'}
        op = (h >> 6) & 0xF
        if op == 9:
            return f'rsbs {r(h&7)}, {r((h>>3)&7)}, #0'
        return f'{ALU[op]:<4} {r(h&7)}, {r((h>>3)&7)}'

    if (h & 0xF800) == 0x2000: return f'movs {r((h>>8)&7)}, #{h&0xFF}'
    if (h & 0xF800) == 0x2800: return f'cmp  {r((h>>8)&7)}, #{h&0xFF}'
    if (h & 0xF800) == 0x3000: return f'adds {r((h>>8)&7)}, #{h&0xFF}'
    if (h & 0xF800) == 0x3800: return f'subs {r((h>>8)&7)}, #{h&0xFF}'

    # ---- Hi-reg ops : 010001 00 h1 h2 Rm Rd ----
    if (h & 0xFC00) == 0x4400 or ((h & 0xFC00) == 0x4000 and False):
        pass
    if (h & 0xFC00) == 0x4400:
        op = (h >> 8) & 3
        Rdn = (h & 7) | (((h >> 7) & 1) << 3)
        Rm = (h >> 3) & 0xF
        name = {0:'add', 1:'cmp', 2:'mov', 3:'?'}[op]
        if op == 3:
            return f'bx   {r(Rm)}' if (h & 0x80) == 0 else f'blx  {r(Rm)}'
        return f'{name:<4} {r(Rdn)}, {r(Rm)}'

    # ---- LDR literal : 01001 Rd imm8 ----
    if (h & 0xF800) == 0x4800:
        return f'ldr  {r((h>>8)&7)}, [pc, #{(h&0xFF)*4}]      @ =0x{a+4+((h&0xFF)*4):X}'

    # ---- Load/store register offset : 0101 op L B 0 Ro Rb Rd ----
    if (h & 0xF000) == 0x5000:
        op = (h >> 9) & 7
        name = ['str','strh','strb','ldsb','ldr','ldrh','ldrb','ldsh'][op]
        return f'{name:<4} {r(h&7)}, [{r((h>>3)&7)}, {r((h>>6)&7)}]'

    # ---- immediate word/byte/half : 011/100/101 ----
    if (h & 0xF000) == 0x6000:
        L = (h >> 11) & 1; B = (h >> 12) & 1
        name = 'str' if not L else 'ldr'
        return f'{name:<4} {r(h&7)}, [{r((h>>3)&7)}, #{((h>>6)&0x1F)*4}]'
    if (h & 0xF000) == 0x7000:
        return f'{"strb" if (h>>11)&1 else "ldrb"} {r(h&7)}, [{r((h>>3)&7)}, #{(h>>6)&0x1F}]'
    if (h & 0xF000) == 0x8000:
        return f'{"strh" if (h>>11)&1 else "ldrh"} {r(h&7)}, [{r((h>>3)&7)}, #{((h>>6)&0x1F)*2}]'

    if (h & 0xF000) == 0x9000:
        return f'{"str" if (h>>11)&1 else "ldr"} {r((h>>8)&7)}, [sp, #{(h&0xFF)*4}]'

    if (h & 0xF000) == 0xA000:
        return f'add  {r((h>>8)&7)}, pc, #{(h&0xFF)*4}   @ 0x{a+4+((h&0xFF)*4):X}'

    if (h & 0xF000) == 0xB000:
        if (h & 0xFF00) == 0xB000: return f'add  sp, #{((h&0x7F))*4}'
        if (h & 0xFE00) == 0xB400:
            l = ', '.join(REG[x] for x in range(8) if (h>>x)&1)
            return f'push {{{l}{", lr}" if (h>>8)&1 else ""}}}'
        if (h & 0xFE00) == 0xBC00:
            l = ', '.join(REG[x] for x in range(8) if (h>>x)&1)
            return f'pop  {{{l}{", pc}" if (h>>8)&1 else ""}}}'
        if (h & 0xFFC0) == 0xB200:
            return f'{"sxth" if not (h>>6)&1 else "sxth"} {r(h&7)}, {r((h>>3)&7)}'
        if (h & 0xFF00) == 0xBA00: return f'rev  {r(h&7)}, {r((h>>3)&7)}'
        if (h & 0xFF87) == 0xB080: return f'sub  sp, #{(h&0x7F)*4}'
        return f'B0xx {h:04X}'

    if (h & 0xFF00) == 0xBF00:
        if h & 0xFF: return f'it/cond {h:04X}'
        return 'nop'

    if (h & 0xFFC0) == 0xBF00: return f'it   {h:04X}'

    if (h & 0xFF87) == 0x4700:
        return f'bx   {r((h>>3)&0xF)}'
    if (h & 0xFF87) == 0x4780:
        return f'blx  {r((h>>3)&0xF)}'

    if (h & 0xF000) == 0xC000:
        rn = (h>>8)&7
        l = [REG[x] for x in range(8) if (h>>x)&1] + (['pc'] if (h>>8)&1 else [])
        return f'stmia {r(rn)}!, {{{", ".join(l)}}}'
    if (h & 0xF000) == 0xC800:
        rn = (h>>8)&7
        l = [REG[x] for x in range(8) if (h>>x)&1] + (['pc'] if (h>>8)&1 else [])
        return f'ldmia {r(rn)}!, {{{", ".join(l)}}}'

    if (h & 0xF000) == 0xD000:
        c = (h>>8)&0xF
        if c == 15: return f'svc  #{h&0xFF}'
        if c == 14: return f'undef {h:04X}'
        nm = {0:'beq',1:'bne',2:'bcs',3:'bcc',4:'bmi',5:'bpl',6:'bvs',7:'bvc',8:'bhi',9:'bls',10:'bge',11:'blt',12:'bgt',13:'ble'}
        off = h & 0xFF
        if off > 127: off -= 256
        return f'{nm[c]} 0x{a+4+off*2:X}'

    if (h & 0xF800) == 0xE000:
        o = h & 0x7FF
        if o > 1023: o -= 2048
        return f'b    0x{a+4+o*2:X}'

    if (h & 0xF800) == 0xF000:
        h2 = u16(a+2)
        if (h2 & 0xF800) == 0xF800 or (h2 & 0xF800) == 0xE800:
            S=(h>>10)&1; imm10=h&0x3FF; J1=(h2>>13)&1; J2=(h2>>11)&1; imm11=h2&0x7FF
            I1=(~(J1^S))&1; I2=(~(J2^S))&1
            imm=(S<<24)|(I1<<23)|(I2<<22)|(imm10<<12)|(imm11<<1)
            if imm >= (1<<25): imm -= (1<<26)
            return f'{"bl  " if (h2&0xF800)==0xF800 else "blx "} 0x{a+4+imm:X}'
    return f'?    {h:04X}'

def dis(a, n):
    i = a
    while i < a + n:
        h = u16(i)
        print(f'{i:08X}: {h:04X}    {d16(h, i)}')
        i += 2

if __name__ == '__main__':
    a = int(sys.argv[1], 16)
    n = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x40
    dis(a, n)
