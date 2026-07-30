import struct

rom_path = r'C:\code\gba\roms\origin\POKEMON_RUBY_AXVJ00.gba'
with open(rom_path, 'rb') as f:
    data = f.read()

def d(op, next_op=None):
    """Decode THUMB instruction with corrected ADD/SUB and PUSH/POP"""
    if next_op and (op >> 11) == 0x1E and (next_op >> 11) == 0x1F:
        S = (op >> 10) & 1; imm10 = op & 0x3FF
        J1 = (next_op >> 14) & 1; J2 = (next_op >> 13) & 1; imm11 = next_op & 0x7FF
        I1 = 1 - (J1 ^ S); I2 = 1 - (J2 ^ S)
        off = (S << 24) | (I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1)
        if off & 0x1000000: off -= 0x2000000
        return f'BL {off:+d}'
    # --- shift (000xx) ---
    if (op >> 13) == 0:
        imm5 = (op >> 6) & 31; rm = (op >> 3) & 7; rd = op & 7
        opc = (op >> 11) & 3
        nms = ['LSL', 'LSR', 'ASR', 'UND']
        return f'{nms[opc]} r{rd}, r{rm}, #{imm5}'
    # --- 3-arg ADD/SUB immediate/register (00011) ---
    if (op >> 11) == 0b00011:
        op_bit = (op >> 10) & 1  # 0=ADD, 1=SUB
        S_bit = (op >> 9) & 1     # 0=imm3, 1=register
        rd_bits = op & 7
        rn_bits = (op >> 6) & 7   # bits 8-6 = Rn for both forms
        if S_bit == 0:  # immediate
            imm3 = (op >> 3) & 7   # bits 5-3
            rd = op & 7
            return f'{"SUB" if op_bit else "ADD"} r{rd}, r{rn_bits}, #{imm3}'
        else:  # register
            rm = (op >> 3) & 7
            rd = op & 7
            return f'{"SUB" if op_bit else "ADD"} r{rd}, r{rn_bits}, r{rm}'
    # --- MOV/CMP/ADD/SUB immediate (001xx) ---
    if (op >> 13) == 1:
        opc = (op >> 11) & 3; rd = (op >> 8) & 7; imm8 = op & 0xFF
        instr = ['MOV', 'CMP', 'ADD', 'SUB'][opc]
        return f'{instr} r{rd}, #0x{imm8:02X}'
    # --- ALU (010000) ---
    if (op >> 10) == 0b010000 and ((op >> 6) & 0xF) == 0:
        opc = op & 0xF; rd = op & 7; rs = (op >> 3) & 7
        nms = ['AND','EOR','LSL','LSR','ASR','ADC','SBC','ROR','TST','NEG','CMP','CMN','ORR','MUL','BIC','MVN']
        return f'{nms[opc]} r{rd}, r{rs}'
    # --- HI reg ops ADD/CMP/MOV/BX (010001) ---
    if (op >> 10) == 0b010001:
        D = (op >> 7) & 1; opc = (op >> 8) & 3
        H1 = (op >> 6) & 1; H2 = (op >> 5) & 1
        rd = (op & 7) | (D << 3); rm = ((op>>3) & 7) | (H2 << 3)
        nms = ['ADD', 'CMP', 'MOV', 'BX']
        if opc == 0: return f'ADD r{rd}, r{rm}'
        if opc == 1: return f'CMP r{rd}, r{rm}'
        if opc == 2: return f'MOV r{rd}, r{rm}'
        if opc == 3: return f'BX r{rm}'
    # --- LDR/STR with register offset (0101xx) ---
    if (op >> 12) == 0b0101:
        L = (op >> 11) & 1; B = (op >> 10) & 1
        ro = (op >> 6) & 7; rb = (op >> 3) & 7; rd = op & 7
        return f'{"LDRB" if B else "LDR"} r{rd}, [r{rb}, r{ro}]'
    # --- LDR/STR with immediate offset, word (011xx) ---
    if (op >> 13) == 0b011:
        L = (op >> 11) & 1
        B = (op >> 12) & 1  # B=0: word, B=1: byte
        imm5 = (op >> 6) & 31; rb = (op >> 3) & 7; rd = op & 7
        if B == 1:
            return f'{"LDRB" if L else "STRB"} r{rd}, [r{rb}, #{imm5}]'
        else:
            return f'{"LDR" if L else "STR"} r{rd}, [r{rb}, #{imm5*4}]'
    # --- LDRH/STRH (1000xx) ---
    if (op >> 12) == 0b1000:
        L = (op >> 11) & 1; imm5 = (op >> 6) & 31
        rb = (op >> 3) & 7; rd = op & 7
        return f'{"LDRH" if L else "STRH"} r{rd}, [r{rb}, #{imm5*2}]'
    # --- LDR/STR SP-relative (1001xx) ---
    if (op >> 12) == 0b1001:
        L = (op >> 11) & 1; rd = (op >> 8) & 7; imm8 = op & 0xFF
        return f'{"LDR" if L else "STR"} r{rd}, [SP, #{imm8*4}]'
    # --- ADD SP-relative (1010x) ---
    if (op >> 12) == 0b1010:
        rd = (op >> 8) & 7; imm8 = op & 0xFF
        return f'ADD r{rd}, SP, #{imm8*4}'
    # --- ADD/SUB SP (10110000 xxxxxxx) ---
    if (op & 0xFF00) == 0xB000:
        S = (op >> 7) & 1; imm7 = op & 0x7F
        return f'{"ADD" if S else "SUB"} SP, #{imm7*4}'
    # --- PUSH/POP (1011x10x) ---
    if (op >> 10) == 0b101110:  # PUSH = 1011_01_0_x_xxxxx
        L = 0; R = (op >> 8) & 1; rl = op & 0xFF
        regs = ''.join(f'r{i},' for i in range(8) if rl & (1<<i))
        if R: regs += 'LR,'
        return f'PUSH {{{regs.strip(",")}}}'
    if (op >> 10) == 0b101111:  # POP = 1011_11_0_x_xxxxx
        L = 1; R = (op >> 8) & 1; rl = op & 0xFF
        regs = ''.join(f'r{i},' for i in range(8) if rl & (1<<i))
        if R: regs += 'PC,'
        return f'POP {{{regs.strip(",")}}}'
    # --- conditional B (1101xxxx) ---
    if (op >> 12) == 0b1101:
        cond = (op >> 8) & 0xF; offset = op & 0xFF
        cn = ['EQ','NE','CS/HS','CC/LO','MI','PL','VS','VC','HI','LS','GE','LT','GT','LE','','NV']
        return f'B{cn[cond]} PC+{offset*2+4}'
    # --- unconditional B (11100xxxxxxxxxxx) ---
    if (op >> 11) == 0x1C:
        offset = op & 0x7FF
        if op & 0x0400: offset -= 0x800
        return f'B PC+{offset*2+4}'
    # --- LDMIA/STMIA (1100xx) ---
    if (op >> 12) == 0b1100:
        L = (op >> 11) & 1; rb = (op >> 8) & 7
        rl = op & 0xFF
        regs = ''.join(f'r{i},' for i in range(8) if rl & (1<<i))
        return f'{"LDMIA" if L else "STMIA"} r{rb}!, {{{regs.strip(",")}}}'
    # --- LDR literal (01001xxx) ---
    if (op >> 11) == 0b01001:
        rd = (op >> 8) & 7; imm8 = op & 0xFF
        return f'LDR r{rd}, [PC, #{imm8*4}]'
    # --- CBZ/CBNZ (1011) ---
    if (op >> 12) == 0b1011:
        imm5 = (op >> 2) & 0x1F; i = (op >> 9) & 1; rn = op & 7; op_bit = (op >> 11) & 1
        imm = (i << 5) | imm5
        return f'{"CBNZ" if op_bit else "CBZ"} r{rn}, PC+{imm*2+4}'
    return f'??? {op:04X}'

print('=== FillBgTilemapRect (0x080041BC) ===')
print('r0 = first param (window ptr)')
print()
i = 0x41BC; end = 0x4260
while i < end:
    offset = 0x08000000 + i
    op = struct.unpack_from('<H', data, i)[0]
    is_bl = False
    decoded = ''
    if (op >> 11) == 0x1E and i + 2 < end:
        next_op = struct.unpack_from('<H', data, i+2)[0]
        if (next_op >> 11) == 0x1F:
            decoded = d(op, next_op)
            print(f'  0x{offset:08X}: {op:04X} {next_op:04X}  {decoded}')
            i += 4
            continue
    decoded = d(op)
    # Show comment for jump table targets and literal pool
    comment = ''
    if i == 0x41EC:
        comment = '  ; jump table base (LDR target)'
    for j, idx in [(0x41F0,0),(0x41F4,1),(0x41F8,2),(0x41FC,3),(0x4200,4),(0x4204,5),(0x4208,6)]:
        if i == j:
            val = struct.unpack_from('<I', data, j)[0]
            comment = f'  ; case {idx}: -> 0x{val:08X}'
    if decoded.startswith('LDR ') and 'PC' in decoded and not comment:
        load_addr = None
        import re
        m = re.search(r'#(\d+)$', decoded)
        if m:
            pc_aligned = offset + 4
            load_addr = pc_aligned + int(m.group(1))
        # just check if in range
    print(f'  0x{offset:08X}: {op:04X}  {decoded}{comment}')
    i += 2

# Also show branch target analysis
print()
print('=== Branch targets ===')
branch_info = [
    (0x41C4, 'D009', 'BEQ'), (0x41C8, 'DC02', 'BHI'),
    (0x41CC, 'D021', 'BEQ'), (0x41CE, 'E027', 'B'),
    (0x41D2, 'D025', 'BEQ'), (0x41D6, 'D01E', 'BEQ'),
    (0x41D8, 'E022', 'B'),
    (0x41DE, 'D81F', 'BHI'),
    (0x4210, 'E003', 'B'), (0x4214, 'E005', 'B'),
    (0x421E, 'E000', 'B'),
]
for addr, op_str, name in branch_info:
    off = addr - 0x08000000
    op = struct.unpack_from('<H', data, off)[0]
    if op_str.startswith('D') or op_str.startswith('E'):
        if op_str.startswith('D'):
            offset = op & 0xFF
            target = addr + 4 + offset*2
        else:  # E (unconditional B)
            offset = op & 0x7FF
            if op & 0x0400: offset -= 0x800
            target = addr + 4 + offset*2
        # decode target
        top = struct.unpack_from('<H', data, target - 0x08000000)[0]
        print(f'  0x{addr:08X}: {name} -> 0x{target:08X}  ({d(top)})')
