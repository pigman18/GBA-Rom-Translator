import struct

rom_path = r'C:\code\gba\roms\origin\POKEMON_RUBY_AXVJ00.gba'
with open(rom_path, 'rb') as f:
    data = f.read()

def decode_thumb(op, next_op=None):
    if next_op is not None and (op >> 11) == 0x1E and (next_op >> 11) == 0x1F:
        S = (op >> 10) & 1
        imm10 = op & 0x3FF
        J1 = (next_op >> 14) & 1
        J2 = (next_op >> 13) & 1
        imm11 = next_op & 0x7FF
        I1 = 1 - (J1 ^ S)
        I2 = 1 - (J2 ^ S)
        off = (S << 24) | (I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1)
        if off & 0x1000000:
            off -= 0x2000000
        return f'BL {off:+d}', True
    if (op >> 13) == 0:
        opc = (op >> 11) & 3
        if opc == 0:
            return f'LSL r{op&7}, r{(op>>3)&7}, #{(op>>6)&31}', False
        elif opc == 1:
            return f'LSR r{op&7}, r{(op>>3)&7}, #{(op>>6)&31}', False
        elif opc == 2:
            return f'ASR r{op&7}, r{(op>>3)&7}, #{(op>>6)&31}', False
        elif opc == 3:
            if op & 0x0400:
                return f'ADD r{op&7}, r{(op>>3)&7}', False
            else:
                return f'SUB r{op&7}, r{(op>>3)&7}', False
    if (op >> 9) == 0b000110:
        rd = op & 7; rn = (op >> 3) & 7; imm3 = (op >> 6) & 7
        return f'ADD r{rd}, r{rn}, #${imm3:02X}', False
    if (op >> 9) == 0b000111:
        rd = op & 7; rn = (op >> 3) & 7; imm3 = (op >> 6) & 7
        return f'SUB r{rd}, r{rn}, #${imm3:02X}', False
    if (op >> 13) == 1:
        opc = (op >> 11) & 3; rd = (op >> 8) & 7; imm8 = op & 0xFF
        instr = ['MOV', 'CMP', 'ADD', 'SUB'][opc]
        return f'{instr} r{rd}, #${imm8:02X}', False
    if (op >> 8) == 0x40 and ((op >> 6) & 3) == 0:
        opc = op & 0xF; rd = op & 7; rs = (op >> 3) & 7
        names = ['AND', 'EOR', 'LSL', 'LSR', 'ASR', 'ADC', 'SBC', 'ROR',
                  'TST', 'NEG', 'CMP', 'CMN', 'ORR', 'MUL', 'BIC', 'MVN']
        return f'{names[opc]} r{rd}, r{rs}', False
    if (op >> 12) == 0b0101:
        L = (op >> 11) & 1; B = (op >> 10) & 1
        ro = (op >> 6) & 0x1F; rb = (op >> 3) & 7; rd = op & 7
        if B:
            return f'{"LDRB" if L else "STRB"} r{rd}, [r{rb}, r{ro}]', False
        else:
            return f'{"LDR" if L else "STR"} r{rd}, [r{rb}, r{ro}]', False
    if (op >> 13) == 0b011:
        L = (op >> 11) & 1; B = (op >> 12) & 1
        imm5 = (op >> 6) & 31; rb = (op >> 3) & 7; rd = op & 7
        if B:
            return f'{"LDRB" if L else "STRB"} r{rd}, [r{rb}, #${imm5:02X}]', False
        else:
            return f'{"LDR" if L else "STR"} r{rd}, [r{rb}, #${imm5<<2:02X}]', False
    if (op >> 12) == 0b1000:
        L = (op >> 11) & 1; imm5 = (op >> 6) & 31; rb = (op >> 3) & 7; rd = op & 7
        return f'{"LDRH" if L else "STRH"} r{rd}, [r{rb}, #${imm5<<1:02X}]', False
    if (op >> 12) == 0b1001:
        L = (op >> 11) & 1; rd = (op >> 8) & 7; imm8 = op & 0xFF
        return f'{"LDR" if L else "STR"} r{rd}, [SP, #${imm8<<2:02X}]', False
    if (op >> 12) == 0b1010:
        rd = (op >> 8) & 7; imm8 = op & 0xFF
        return f'ADD r{rd}, SP, #${imm8<<2:02X}', False
    if op == 0xB080 or (op & 0xFF00) == 0xB000:
        S = (op >> 7) & 1; imm7 = op & 0x7F
        return f'{"ADD" if S else "SUB"} SP, #${imm7<<2:02X}', False
    if (op & 0xFE00) == 0xB400:
        L = (op >> 11) & 1; R = (op >> 8) & 1
        regs = op & 0xFF
        if L:
            rl = ''; pc = False
            for i in range(8):
                if regs & (1 << i): rl += f'r{i},'
            if R: rl += 'PC '
            return f'POP {{{rl.strip(",")}}}', False
        else:
            rl = ''
            for i in range(8):
                if regs & (1 << i): rl += f'r{i},'
            if R: rl += 'LR '
            return f'PUSH {{{rl.strip(",")}}}', False
    if (op >> 12) == 0b1101:
        cond = (op >> 8) & 0xF; offset = op & 0xFF
        cn = ['EQ','NE','CS/HS','CC/LO','MI','PL','VS','VC','HI','LS','GE','LT','GT','LE','','NV']
        return f'B{cn[cond]} {offset*2+4:+d}', False
    if (op >> 11) == 0x1C:
        offset = op & 0x7FF
        if op & 0x0400: offset = offset - 0x800
        return f'B {offset*2+4:+d}', False
    if (op >> 12) == 0b1100:
        L = (op >> 11) & 1; rb = (op >> 8) & 7
        regs = op & 0xFF; rl = ''
        for i in range(8):
            if regs & (1 << i): rl += f'r{i},'
        return f'{"LDMIA" if L else "STMIA"} r{rb}!, {{{rl.strip(",")}}}', False
    if (op >> 11) == 0b01001:
        rd = (op >> 8) & 7; imm8 = op & 0xFF
        return f'LDR r{rd}, [PC, #${imm8<<2:02X}]', False
    if (op >> 10) == 0b010001:
        D = (op >> 7) & 1; opc = (op >> 8) & 3
        H1 = (op >> 6) & 1; H2 = (op >> 5) & 1
        rd = (op & 7) | (D << 3); rm = ((op>>3) & 7) | (H2 << 3)
        n = ['ADD', 'CMP', 'MOV', 'BX'][opc]
        if opc == 3: return f'BX r{rm}', False
        return f'{n} r{rd}, r{rm}', False
    return f'??? {op:04X}', False

print('=== FillBgTilemapRect (0x080041BC) ===')
print()
i = 0x41BC; end = 0x4260
skip_next = False
while i < end:
    if skip_next:
        skip_next = False
        i += 2
        continue
    offset = 0x08000000 + i
    op = struct.unpack_from('<H', data, i)[0]
    is_bl = False
    decoded = ''
    # Check for BL
    if (op >> 11) == 0x1E and i + 2 < end:
        next_op = struct.unpack_from('<H', data, i+2)[0]
        if (next_op >> 11) == 0x1F:
            decoded, is_bl = decode_thumb(op, next_op)
            print(f'  0x{offset:08X}: {op:04X} {next_op:04X}  {decoded}')
            i += 4
            continue
    decoded, _ = decode_thumb(op)
    print(f'  0x{offset:08X}: {op:04X}  {decoded}')
    i += 2

print()
print('=== Literal pool / jump table at 0x080041EC ===')
for i in range(0x41EC, 0x4254, 4):
    val = struct.unpack_from('<I', data, i)[0]
    print(f'  0x{0x08000000+i:08X}: 0x{val:08X}')
