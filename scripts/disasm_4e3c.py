
import struct
rom = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()
def thumb_bl_target(pc,h1,h2):
    s=(h1>>10)&1; i1=(h2>>13)&1; i2=(h2>>11)&1
    imm10=h1&0x3FF; imm11=h2&0x7FF
    I1=1-(i1^s); I2=1-(i2^s)
    off=(s<<24)|(I1<<23)|(I2<<22)|(imm10<<12)|(imm11<<1)
    if s: off-=(1<<25)
    return (pc+4+off)&0xFFFFFFFF

# 日版 Text_InitWindow8004E3C @ 0x08001E74（英文 0x08004e3c - 0x2FC8）
# 反汇编，带注释，看它写 TextPrinter 哪些偏移（找 tileData 字段）
pc = 0x08001E74
end = 0x08001EA0
while pc < end:
    off = pc - 0x08000000
    h1 = struct.unpack_from('<H', rom, off)[0]
    cmt = ''
    if (h1 & 0xF800) == 0xF000:
        h2 = struct.unpack_from('<H', rom, off+2)[0]
        cmt = f'  ; bl 0x{thumb_bl_target(pc,h1,h2):08X}'
    elif (h1 & 0xF800) == 0x6000:
        # str
        imm5=(h1>>6)&0x1F; rn=(h1>>3)&7; rt=h1&7
        cmt = f'  ; str r{rt}, [r{rn}, #0x{imm5*4:X}]'
    elif (h1 & 0xF800) == 0x8000:
        imm5=(h1>>6)&0x1F; rn=(h1>>3)&7; rt=h1&7
        cmt = f'  ; strh r{rt}, [r{rn}, #0x{imm5*2:X}]'
    elif (h1 & 0xFC00) == 0x7000:
        imm5=(h1>>6)&0x1F; rn=(h1>>3)&7; rt=h1&7
        cmt = f'  ; strb r{rt}, [r{rn}, #0x{imm5:X}]'
    print(f'  0x{pc:08X}: {h1:04X}{cmt}')
    pc += 2
