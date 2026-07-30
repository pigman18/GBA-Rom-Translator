import struct
rom_path = r'C:\code\gba\roms\origin\POKEMON_RUBY_AXVJ00.gba'
with open(rom_path, 'rb') as f:
    data = f.read()

def decode(op, nop=None):
    if nop and (op>>11)==0x1E and (nop>>11)==0x1F:
        S=(op>>10)&1; i10=op&0x3FF; J1=(nop>>14)&1; J2=(nop>>13)&1; i11=nop&0x7FF
        I1=1-(J1^S); I2=1-(J2^S)
        off=(S<<24)|(I1<<23)|(I2<<22)|(i10<<12)|(i11<<1)
        if off&0x1000000: off-=0x2000000
        t=0x08000000+4+off
        return f'BL 0x{t:08X}'
    if op>>13==0:
        opc=(op>>11)&3
        if opc==0: i5=(op>>6)&31; rm=(op>>3)&7; rd=op&7; return f'LSL r{rd}, r{rm}, #{i5}'
        if opc==1: i5=(op>>6)&31; rm=(op>>3)&7; rd=op&7; return f'LSR r{rd}, r{rm}, #{i5}'
        if opc==2: i5=(op>>6)&31; rm=(op>>3)&7; rd=op&7; return f'ASR r{rd}, r{rm}, #{i5}'
        if opc==3:
            op_bit=(op>>10)&1; S_bit=(op>>9)&1; rn=(op>>6)&7; rm=(op>>3)&7; rd=op&7
            if S_bit==0:
                return ('SUB' if op_bit else 'ADD') + f' r{rd}, r{rn}, #{rm}'
            else:
                return ('SUB' if op_bit else 'ADD') + f' r{rd}, r{rn}, r{rm}'
    if op>>13==1:
        opc=(op>>11)&3; rd=(op>>8)&7; i8=op&0xFF
        nms=['MOV','CMP','ADD','SUB']
        return f'{nms[opc]} r{rd}, #0x{i8:02X}'
    if (op>>6)==0x40 and (op>>10)&3==0:
        opc=op&0xF; rd=op&7; rs=(op>>3)&7
        nms=['AND','EOR','LSL','LSR','ASR','ADC','SBC','ROR','TST','NEG','CMP','CMN','ORR','MUL','BIC','MVN']
        return f'{nms[opc]} r{rd}, r{rs}'
    if (op>>10)&0x3F==0b010001:
        D=(op>>7)&1; opc=(op>>8)&3; H1=(op>>6)&1; H2=(op>>5)&1
        rd=(op&7)|(D<<3); rm=((op>>3)&7)|(H2<<3)
        if opc==3: return f'BX r{rm}'
        nms=['ADD','CMP','MOV','BX']
        return f'{nms[opc]} r{rd}, r{rm}'
    if op>>12==0b0101:
        L=(op>>11)&1; B=(op>>10)&1; ro=(op>>6)&7; rb=(op>>3)&7; rd=op&7
        return ('LDRB' if B else 'LDR') + f' r{rd}, [r{rb}, r{ro}]'
    if op>>13==0b011 and (op>>12)&1==0:
        L=(op>>11)&1; i5=(op>>6)&31; rb=(op>>3)&7; rd=op&7
        return ('LDR' if L else 'STR') + f' r{rd}, [r{rb}, #{i5*4}]'
    if op>>13==0b011 and (op>>12)&1==1:
        L=(op>>11)&1; i5=(op>>6)&31; rb=(op>>3)&7; rd=op&7
        return ('LDRB' if L else 'STRB') + f' r{rd}, [r{rb}, #{i5}]'
    if op>>12==0b1000:
        L=(op>>11)&1; i5=(op>>6)&31; rb=(op>>3)&7; rd=op&7
        return ('LDRH' if L else 'STRH') + f' r{rd}, [r{rb}, #{i5*2}]'
    if op>>12==0b1001:
        L=(op>>11)&1; rd=(op>>8)&7; i8=op&0xFF
        return ('LDR' if L else 'STR') + f' r{rd}, [SP, #{i8*4}]'
    if op>>12==0b1010:
        rd=(op>>8)&7; i8=op&0xFF
        return f'ADD r{rd}, SP, #{i8*4}'
    if (op>>8)==0xB0:
        S=(op>>7)&1; i7=op&0x7F
        return ('ADD' if S else 'SUB') + f' SP, #{i7*4}'
    if (op>>8)==0xBC:
        rl=op&0xFF
        regs=''.join(f'r{i},' for i in range(8) if rl&(1<<i))
        return 'POP {' + regs.strip(',') + '}'
    if (op>>12)==0b1011 and (op>>8)&0xF==0b0101:
        rl=op&0xFF
        regs=''.join(f'r{i},' for i in range(8) if rl&(1<<i))
        return 'PUSH {' + regs.strip(',') + '}'
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
        return ('LDMIA' if L else 'STMIA') + f' r{rb}!, {{{regs.strip(",")}}}'
    if op>>11==0b01001:
        rd=(op>>8)&7; i8=op&0xFF
        return f'LDR r{rd}, [PC, #{i8*4}]'
    return f'??? {op:04X}'

# Print function with branch targets resolved
for i, cmt in [
    (0x41BC, 'r2 = r0 (window ptr)'),
    (0x41C0, 'r0 = window[0x0A] = font'),
    (0x41C2, ''),
    (0x41C4, 'if font==1 -> font1_path (reads window[0x0B], jump table)'),
    (0x41C6, ''),
    (0x41C8, 'if font > 1 -> check font==2/3'),
    (0x41CA, ''),
    (0x41CC, 'if font==0 -> font0_path: r0=window[0x16], return'),
    (0x41CE, '(unreachable -> default r0=0)'),
    (0x41D0, ''),
    (0x41D2, 'if font==2 -> default (r0=0)'),
    (0x41D4, ''),
    (0x41D6, 'if font==3 -> font3_path: r0=window[0x16]+1, zero-ext, return'),
    (0x41D8, 'default -> r0=0'),
    (0x41DA, 'font1: r0 = window[0x0B] (index for jump table)'),
    (0x41DC, ''),
    (0x41DE, 'if index > 6 -> default (r0=0)'),
    (0x41E0, 'font1: r0 = index * 4'),
    (0x41E2, 'r1 = jump_table_base(0x080041F0)'),
    (0x41E4, 'r0 += r1 = &jump_table[index]'),
    (0x41E6, 'r0 = *r0  (load target addr)'),
    (0x41E8, 'JUMP to target'),
    (0x41EA, 'padding'),
    (0x41EC, 'jump_table[0] = 0x080041F0  (base)'),
    (0x41F0, 'case 0: 0x08004212'),
    (0x41F4, 'case 1: 0x0800420C'),
    (0x41F8, 'case 2: 0x0800420C'),
    (0x41FC, 'case 3: 0x08004212'),
    (0x4200, 'case 4: 0x0800420C'),
    (0x4204, 'case 5: 0x0800420C'),
    (0x4208, 'case 6: 0x08004212'),
    (0x420C, 'case 1,2,4,5: r0 = window[0x16] + 0xD4'),
    (0x420E, ''),
    (0x4210, '-> common_output'),
    (0x4212, 'case 0,3,6 + font0: r0 = window[0x16]'),
    (0x4214, '-> common_output'),
    (0x4216, 'font3: r0 = window[0x16] + 1'),
    (0x4218, ''),
    (0x421A, 'common_output: LSL r0, #16'),
    (0x421C, 'LSR r0, #16  (zero-extend to u16)'),
    (0x421E, '-> return'),
    (0x4220, 'default: r0 = 0'),
    (0x4222, 'POP {r1}; BX r1'),
]:
    op = struct.unpack_from('<H', data, i)[0]
    dec = decode(op)
    print(f'0x{0x08000000+i:08X}: {op:04X}  {dec}')
    if cmt:
        print(f'                   ; {cmt}')
print()
