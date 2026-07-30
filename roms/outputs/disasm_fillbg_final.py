import struct

rom_path = r'C:\code\gba\roms\origin\POKEMON_RUBY_AXVJ00.gba'
with open(rom_path, 'rb') as f:
    data = f.read()

def decode(op, next_op=None):
    if next_op and (op>>11)==0x1E and (next_op>>11)==0x1F:
        S=(op>>10)&1; i10=op&0x3FF; J1=(next_op>>14)&1; J2=(next_op>>13)&1; i11=next_op&0x7FF
        I1=1-(J1^S); I2=1-(J2^S)
        off=(S<<24)|(I1<<23)|(I2<<22)|(i10<<12)|(i11<<1)
        if off&0x1000000: off-=0x2000000
        return f'BL {off:+d}', True
    # shift (000xx)
    if op>>13==0:
        opc=(op>>11)&3
        if opc!=3:
            imm5=(op>>6)&31; rm=(op>>3)&7; rd=op&7
            return f'{"LSL" if opc==0 else "LSR" if opc==1 else "ASR"} r{rd}, r{rm}, #{imm5}', False
    # 3-arg ADD/SUB (00011xx) = opc == 3
    if (op>>11)==3:  # 00011 in bits 15-11
        op_bit=(op>>10)&1  # 0=ADD, 1=SUB
        S_bit=(op>>9)&1    # 0=imm, 1=reg
        rn=(op>>6)&7
        rm_imm=(op>>3)&7
        rd=op&7
        if S_bit==0:
            return f'{"SUB" if op_bit else "ADD"} r{rd}, r{rn}, #{rm_imm}', False
        else:
            return f'{"SUB" if op_bit else "ADD"} r{rd}, r{rn}, r{rm_imm}', False
    # MOV/CMP/ADD/SUB imm (001xx)
    if op>>13==1:
        opc=(op>>11)&3; rd=(op>>8)&7; i8=op&0xFF
        return f'{["MOV","CMP","ADD","SUB"][opc]} r{rd}, #0x{i8:02X}', False
    # ALU (010000xxxx)
    if (op>>6)==0x40 and (op>>10)&3==0:
        opc=op&0xF; rd=op&7; rs=(op>>3)&7
        return f'{["AND","EOR","LSL","LSR","ASR","ADC","SBC","ROR","TST","NEG","CMP","CMN","ORR","MUL","BIC","MVN"][opc]} r{rd}, r{rs}', False
    # HI reg ADD/CMP/MOV/BX (010001xxxx)
    if (op>>10)&0x3F==0b010001:
        D=(op>>7)&1; opc=(op>>8)&3; H1=(op>>6)&1; H2=(op>>5)&1
        rd=(op&7)|(D<<3); rm=((op>>3)&7)|(H2<<3)
        if opc==0: return f'ADD r{rd}, r{rm}', False
        if opc==1: return f'CMP r{rd}, r{rm}', False
        if opc==2: return f'MOV r{rd}, r{rm}', False
        if opc==3: return f'BX r{rm}', False
    # LDR/STR reg offset (0101xx)
    if op>>12==0b0101:
        L=(op>>11)&1; B=(op>>10)&1; ro=(op>>6)&7; rb=(op>>3)&7; rd=op&7
        return f'{"LDRB" if B else "LDR"} r{rd}, [r{rb}, r{ro}]', False
    # LDR/STR word imm offset (0110xx)
    if op>>13==0b011 and (op>>12)&1==0:
        L=(op>>11)&1; i5=(op>>6)&31; rb=(op>>3)&7; rd=op&7
        return f'{"LDR" if L else "STR"} r{rd}, [r{rb}, #{i5*4}]', False
    # LDRB/STRB imm offset (0111xx)
    if op>>13==0b011 and (op>>12)&1==1:
        L=(op>>11)&1; i5=(op>>6)&31; rb=(op>>3)&7; rd=op&7
        return f'{"LDRB" if L else "STRB"} r{rd}, [r{rb}, #{i5}]', False
    # LDRH/STRH (1000xx)
    if op>>12==0b1000:
        L=(op>>11)&1; i5=(op>>6)&31; rb=(op>>3)&7; rd=op&7
        return f'{"LDRH" if L else "STRH"} r{rd}, [r{rb}, #{i5*2}]', False
    # LDR/STR SP (1001xx)
    if op>>12==0b1001:
        L=(op>>11)&1; rd=(op>>8)&7; i8=op&0xFF
        return f'{"LDR" if L else "STR"} r{rd}, [SP, #{i8*4}]', False
    # ADD rd, SP, #imm (1010x)
    if op>>12==0b1010:
        rd=(op>>8)&7; i8=op&0xFF
        return f'ADD r{rd}, SP, #{i8*4}', False
    # ADD/SUB SP (10110000_xxxxxxx)
    if (op>>8)==0xB0:
        S=(op>>7)&1; i7=op&0x7F
        return f'{"ADD" if S else "SUB"} SP, #{i7*4}', False
    # PUSH (1011_01_0_1_Rlist) = 0xB5xx range
    if (op&0xF200)==0xB000 and (op>>9)&1==0 and (op>>8)&1==1:
        rl=op&0xFF; R=(op>>8)&1
        regs=''.join(f'r{i},' for i in range(8) if rl&(1<<i))
        return f'PUSH {{{regs.strip(",")}}}', False
    # POP (1011_11_0_1_Rlist) = 0xBCxx range? 
    if (op>>10)==0b101111:
        rl=op&0xFF; R=(op>>8)&1
        regs=''.join(f'r{i},' for i in range(8) if rl&(1<<i))
        if R: regs+='PC,'
        return f'POP {{{regs.strip(",")}}}', False
    # also try simpler: (op & 0xFF00) == 0xBC00
    if (op>>8)==0xBC:
        rl=op&0xFF; R=0
        if op>>7 & 1: R=1
        regs=''.join(f'r{i},' for i in range(8) if rl&(1<<i))
        if R: regs+='PC,'
        return f'POP {{{regs.strip(",")}}}', False
    # conditional B (1101xxxx)
    if op>>12==0b1101:
        cond=(op>>8)&0xF; off=op&0xFF
        cn=['EQ','NE','CS/HS','CC/LO','MI','PL','VS','VC','HI','LS','GE','LT','GT','LE','','NV']
        return f'B{cn[cond]} PC+{off*2+4}', False
    # B (11100xxxxxxxxxxx)
    if op>>11==0x1C:
        off=op&0x7FF
        if op&0x0400: off-=0x800
        return f'B PC+{off*2+4}', False
    # LDMIA/STMIA (1100xx)
    if op>>12==0b1100:
        L=(op>>11)&1; rb=(op>>8)&7; rl=op&0xFF
        regs=''.join(f'r{i},' for i in range(8) if rl&(1<<i))
        return f'{"LDMIA" if L else "STMIA"} r{rb}!, {{{regs.strip(",")}}}', False
    # LDR literal (01001xxx)
    if op>>11==0b01001:
        rd=(op>>8)&7; i8=op&0xFF
        return f'LDR r{rd}, [PC, #{i8*4}]', False
    return f'??? {op:04X}', False

print('='*70)
print('FillBgTilemapRect (0x080041BC)  —  Full THUMB Disassembly')
print('Entry: r0 = window pointer, returns tile_id in r0')
print('='*70)
print()

# Jump table at 0x080041EC
jt_base = 0x080041EC
jt_entries = []
for j in range(0x41EC, 0x420C, 4):
    val = struct.unpack_from('<I', data, j)[0]
    jt_entries.append(val)

i = 0x41BC; end = 0x4228
while i < end:
    offset = 0x08000000 + i
    op = struct.unpack_from('<H', data, i)[0]
    if (op>>11)==0x1E and i+2<end:
        nop = struct.unpack_from('<H', data, i+2)[0]
        if (nop>>11)==0x1F:
            dec, _ = decode(op, nop)
            print(f'  0x{offset:08X}: {op:04X} {nop:04X}  {dec}')
            i += 4
            continue
    dec, _ = decode(op)
    # show jump table data
    cmt = ''
    if i >= 0x41EC and i < 0x420A:
        idx = (i - 0x41EC) // 4
        if i % 4 == 0:
            val = struct.unpack_from('<I', data, i)[0]
            cmt = f'  ; jump_table[{idx}] = 0x{val:08X}'
    # for literal LDR, show what it loads
    if dec.startswith('LDR ') and 'PC' in dec:
        pc_aligned = (offset + 4) & ~3
        imm = int(dec.split('#')[1])
        load_addr = pc_aligned + imm
        if load_addr >= 0x08000000 and load_addr < 0x09000000:
            off = load_addr - 0x08000000
            val = struct.unpack_from('<I', data, off)[0]
            cmt = f'  ; -> mem[0x{load_addr:08X}] = 0x{val:08X}'
    # show branch targets
    if dec.startswith('B') and ('PC+' in dec):
        br_off = int(dec.split('PC+')[1])
        target = offset + 4 + br_off
        top = struct.unpack_from('<H', data, target - 0x08000000)[0]
        tdec, _ = decode(top)
        cmt = f'  ; -> 0x{target:08X}: {tdec}'
    print(f'  0x{offset:08X}: {op:04X}  {dec}{cmt}')
    i += 2

print()
print('='*70)
print('CASE ANALYSIS')
print('='*70)
print()
print('Font 0 (window[0x0A]==0):')
print('  Target 0x08004212: r0 = window[0x16] (LDRH), return directly')
print()
print('Font 1 (window[0x0A]==1):')
print('  Reads window[0x16], jump table dispatch:')
for idx, (lo, hi) in enumerate(zip(jt_entries, jt_entries[1:])):
    print(f'    case {idx} -> 0x{lo:08X}')
    if lo == 0x08004212:
        print(f'              r0 = window[0x16] (LDRH), return')
    elif lo == 0x0800420C:
        print(f'              r0 = window[0x16] + 0xD4, zero-ext, return')
print(f'    case >6 -> r0 = 0, return')
print()
print('Font 2: -> r0 = 0, return')
print()
print('Font 3:')
print('  Target 0x08004216: r0 = window[0x16] + 1, zero-ext, return')
print()
print('Default (font>3 or table overflow): r0 = 0')
print()
print('NOTE: window[0x16] offset = 22 decimal')
print('      This is the tile fill value used in DMA3 clear')
