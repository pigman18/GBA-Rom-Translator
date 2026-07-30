import struct
rom_path = r'C:\code\gba\roms\origin\POKEMON_RUBY_AXVJ00.gba'
with open(rom_path, 'rb') as f:
    data = f.read()

def decode(op, next_op=None):
    if next_op and (op>>11)==0x1E and (next_op>>11)==0x1F:
        S=(op>>10)&1; i10=op&0x3FF; J1=(next_op>>14)&1; J2=(next_op>>13)&1; i11=next_op&0x7FF
        I1=1-(J1^S); I2=1-(J2^S); off=(S<<24)|(I1<<23)|(I2<<22)|(i10<<12)|(i11<<1)
        if off&0x1000000: off-=0x2000000
        return f'BL 0x{0x08000000+4+off:08X}'
    if op>>13==0:
        opc=(op>>11)&3
        if opc==0: i5=(op>>6)&31; rm=(op>>3)&7; rd=op&7; return f'LSL r{rd}, r{rm}, #{i5}'
        if opc==1: i5=(op>>6)&31; rm=(op>>3)&7; rd=op&7; return f'LSR r{rd}, r{rm}, #{i5}'
        if opc==2: i5=(op>>6)&31; rm=(op>>3)&7; rd=op&7; return f'ASR r{rd}, r{rm}, #{i5}'
        if opc==3:
            op_bit=(op>>10)&1; S_bit=(op>>9)&1; rn=(op>>6)&7; rm=(op>>3)&7; rd=op&7
            if S_bit==0: return ('SUB' if op_bit else 'ADD')+f' r{rd}, r{rn}, #{rm}'
            else: return ('SUB' if op_bit else 'ADD')+f' r{rd}, r{rn}, r{rm}'
    if op>>13==1:
        opc=(op>>11)&3; rd=(op>>8)&7; i8=op&0xFF
        return f'{["MOV","CMP","ADD","SUB"][opc]} r{rd}, #0x{i8:02X}'
    if (op>>6)==0x40 and (op>>10)&3==0:
        opc=op&0xF; rd=op&7; rs=(op>>3)&7
        nms=['AND','EOR','LSL','LSR','ASR','ADC','SBC','ROR','TST','NEG','CMP','CMN','ORR','MUL','BIC','MVN']
        return f'{nms[opc]} r{rd}, r{rs}'
    if (op>>10)&0x3F==0b010001:
        D=(op>>7)&1; opc=(op>>8)&3; H1=(op>>6)&1; H2=(op>>5)&1
        rd=(op&7)|(D<<3); rm=((op>>3)&7)|(H2<<3)
        if opc==3: return f'BX r{rm}'
        return f'{["ADD","CMP","MOV","BX"][opc]} r{rd}, r{rm}'
    if op>>12==0b0101:
        L=(op>>11)&1; B=(op>>10)&1; ro=(op>>6)&7; rb=(op>>3)&7; rd=op&7
        return ('LDRB' if B else 'LDR')+f' r{rd}, [r{rb}, r{ro}]'
    if op>>13==0b011 and (op>>12)&1==0:
        L=(op>>11)&1; i5=(op>>6)&31; rb=(op>>3)&7; rd=op&7
        return ('LDR' if L else 'STR')+f' r{rd}, [r{rb}, #{i5*4}]'
    if op>>13==0b011 and (op>>12)&1==1:
        L=(op>>11)&1; i5=(op>>6)&31; rb=(op>>3)&7; rd=op&7
        return ('LDRB' if L else 'STRB')+f' r{rd}, [r{rb}, #{i5}]'
    if op>>12==0b1000:
        L=(op>>11)&1; i5=(op>>6)&31; rb=(op>>3)&7; rd=op&7
        return ('LDRH' if L else 'STRH')+f' r{rd}, [r{rb}, #{i5*2}]'
    if op>>12==0b1001:
        L=(op>>11)&1; rd=(op>>8)&7; i8=op&0xFF
        return ('LDR' if L else 'STR')+f' r{rd}, [SP, #{i8*4}]'
    if op>>12==0b1010:
        rd=(op>>8)&7; i8=op&0xFF
        return f'ADD r{rd}, SP, #{i8*4}'
    if (op>>8)==0xB0:
        S=(op>>7)&1; i7=op&0x7F
        return ('ADD' if S else 'SUB')+f' SP, #{i7*4}'
    if (op>>8)==0xBC:
        rl=op&0xFF
        regs=''.join(f'r{i},' for i in range(8) if rl&(1<<i))
        return 'POP {'+regs.strip(',')+'}'
    if (op>>12)==0b1011 and (op>>8)&0xF==0b0101:
        rl=op&0xFF
        regs=''.join(f'r{i},' for i in range(8) if rl&(1<<i))
        return 'PUSH {'+regs.strip(',')+'}'
    if op>>12==0b1101:
        cond=(op>>8)&0xF; off=op&0xFF
        cn=['EQ','NE','CS','CC','MI','PL','VS','VC','HI','LS','GE','LT','GT','LE','','NV']
        return f'B{cn[cond]} PC+{off*2+4}'
    if op>>11==0x1C:
        off=op&0x7FF
        if op&0x0400: off-=0x800
        return f'B PC+{off*2+4}'
    if op>>12==0b1100:
        L=(op>>11)&1; rb=(op>>8)&7; rl=op&0xFF
        regs=''.join(f'r{i},' for i in range(8) if rl&(1<<i))
        return ('LDMIA' if L else 'STMIA')+f' r{rb}!, {{{regs.strip(",")}}}'
    if op>>11==0b01001:
        rd=(op>>8)&7; i8=op&0xFF
        return f'LDR r{rd}, [PC, #{i8*4}]'
    return f'??? {op:04X}'

# Disassemble function at 0x080AE9xx
print('=== DMA3 Programming Function (0x080AE9xx) ===')
print(f'Watchpoint hit at PC=0x080AE9DA, LR=0x080AE9C7')
print()

# Find function prologue near 0x080AE9C7 (LR from watchpoint hit)
# Search backward for PUSH {...
for start in range(0xAE9C7 - 0x08000000, 0xAE900 - 0x08000000, -2):
    op = struct.unpack_from('<H', data, start)[0]
    if op>>8 == 0xB5:  # PUSH {r4-r7,lr} or similar
        # Check this is truly function start (no branch target before it)
        print(f'  Func start candidate at 0x{0x08000000+start:08X}: {op:04X}')
        for j in range(start, min(start+80, 0xAE9E0 - 0x08000000), 2):
            op2 = struct.unpack_from('<H', data, j)[0]
            dec = decode(op2)
            print(f'    0x{0x08000000+j:08X}: {op2:04X}  {dec}')
        print()
        break

# Also dump the literal pool near the function
print('=== Literal pools in 0x080AE9xx region ===')
for off in range(0xAE9D0 - 0x08000000, 0xAEA40 - 0x08000000, 4):
    val = struct.unpack_from('<I', data, off)[0]
    # Check if it looks like DMA addresses
    marker = ''
    if val in (0x040000D4, 0x040000D8, 0x040000DC): marker = ' (DMA3 reg!)'
    elif val >= 0x02000000 and val <= 0x02040000: marker = ' (WRAM)'
    elif val >= 0x06000000 and val <= 0x06020000: marker = ' (VRAM)'
    elif val >= 0x08000000 and val <= 0x09000000: marker = ' (ROM)'
    if marker:
        print(f'  0x{0x08000000+off:08X}: 0x{val:08X}{marker}')
