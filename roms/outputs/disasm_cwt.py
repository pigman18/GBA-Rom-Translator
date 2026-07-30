"""Disassemble ClearWindowTilemap at 0x08003C00"""
import struct

rom_path = r'C:\code\gba\roms\origin\POKEMON_RUBY_AXVJ00.gba'
with open(rom_path, 'rb') as f:
    data = f.read()

BASE = 0x08000000

def thumb_asm(op, rom_addr):
    rd = op & 7
    rn = (op >> 3) & 7
    rm = (op >> 6) & 7
    imm5 = (op >> 6) & 0x1F
    imm8 = op & 0xFF
    
    kn = {
        0x4770: 'bx lr', 0x4700: 'bx r1', 0x4708: 'bx r1', 0x4718: 'bx r3',
        0x46C0: 'nop',
        0xB510: 'push {r4, lr}', 0xB530: 'push {r4, r5, lr}',
        0xB570: 'push {r4-r6, lr}', 0xB5F0: 'push {r4-r7, lr}',
        0xB401: 'push {r0}', 0xB403: 'push {r0, r1}',
        0xBC10: 'pop {r4}', 0xBC01: 'pop {r1}', 0xBC08: 'pop {r3}',
        0xBCF0: 'pop {r4-r7}',
        0xBD10: 'pop {r4, pc}', 0xBD70: 'pop {r4-r6, pc}', 0xBDF0: 'pop {r4-r7, pc}',
        0x1C04: 'add r4, r0, #0', 0x1C05: 'add r5, r0, #0',
        0x1C06: 'add r6, r0, #0', 0x1C07: 'add r7, r0, #0',
        0x1C08: 'add r0, r1, #0', 0x1C09: 'add r1, r1, #0',
        0x1C12: 'add r2, r2, #0', 0x1C1B: 'add r3, r3, #0',
        0x1C20: 'add r0, r4, #0', 0x1C28: 'add r0, r5, #0',
        0x1C30: 'add r0, r6, #0', 0x1C38: 'add r0, r7, #0',
        0x2000: 'mov r0, #0', 0x2001: 'mov r0, #1',
        0x2002: 'mov r0, #2', 0x2003: 'mov r0, #3',
        0x2004: 'mov r0, #4', 0x2005: 'mov r0, #5', 0x2006: 'mov r0, #6',
        0x2008: 'mov r0, #8', 0x2010: 'mov r0, #0x10',
        0x2100: 'mov r1, #0', 0x2101: 'mov r1, #1',
        0x2102: 'mov r1, #2', 0x2104: 'mov r1, #4',
        0x2200: 'mov r2, #0', 0x2201: 'mov r2, #1', 0x2202: 'mov r2, #2',
        0x2204: 'mov r2, #4', 0x2208: 'mov r2, #8', 0x2210: 'mov r2, #0x10',
        0x2300: 'mov r3, #0', 0x2301: 'mov r3, #1',
        0x2400: 'mov r4, #0', 0x2401: 'mov r4, #1',
        0x2500: 'mov r5, #0', 0x2600: 'mov r6, #0',
        0x2700: 'mov r7, #0',
        0x3001: 'add r0, #1', 0x3002: 'add r0, #2', 0x3004: 'add r0, #4',
        0x3008: 'add r0, #8', 0x3010: 'add r0, #0x10',
        0x3101: 'add r1, #1', 0x3102: 'add r1, #2',
        0x3201: 'add r2, #1', 0x3208: 'add r2, #8', 0x3210: 'add r2, #0x10',
        0x3301: 'add r3, #1',
        0x3401: 'add r4, #1', 0x3402: 'add r4, #2',
        0x3501: 'add r5, #1', 0x3601: 'add r6, #1', 0x3701: 'add r7, #1',
        0x3801: 'sub r0, #1', 0x3802: 'sub r0, #2', 0x3804: 'sub r0, #4',
        0x3901: 'sub r1, #1', 0x3A01: 'sub r2, #1',
        0x3B01: 'sub r3, #1', 0x3C01: 'sub r4, #1',
        0x3E01: 'sub r6, #1', 0x3F01: 'sub r7, #1',
    }
    if op in kn:
        return kn[op]
    
    opc2 = op >> 11
    # LSL Rd, Rm, #imm5
    if (op >> 10) == 0b000000 and ((op>>9)&1) == 0:
        return 'lsl r%d, r%d, #%d' % (rd, rm, imm5)
    # LSR Rd, Rm, #imm5
    if opc2 == 0b00001:
        return 'lsr r%d, r%d, #%d' % (rd, rm, imm5)
    # ASR Rd, Rm, #imm5
    if opc2 == 0b00010:
        return 'asr r%d, r%d, #%d' % (rd, rm, imm5)
    # ADD/SUB
    if opc2 == 0b00011:
        op3 = (op >> 9) & 3
        if op3 == 0: return 'add r%d, r%d, r%d' % (rd, rn, rm)
        if op3 == 1: return 'sub r%d, r%d, r%d' % (rd, rn, rm)
        if op3 == 2: return 'add r%d, r%d, #%d' % (rd, rn, imm5)
        if op3 == 3: return 'sub r%d, r%d, #%d' % (rd, rn, imm5)
    # MOV Rd, #imm8
    if opc2 == 0b00100:
        return 'mov r%d, #0x%X' % (rd, imm8)
    # CMP Rn, #imm8
    if opc2 == 0b01011:
        return 'cmp r%d, #0x%X' % (rn, imm8)
    # ADD Rd, #imm8
    if opc2 == 0b00110 and ((op>>9)&1) == 0:
        return 'add r%d, #0x%X' % (rd, imm8)
    # SUB Rd, #imm8
    if opc2 == 0b00111:
        return 'sub r%d, #0x%X' % (rd, imm8)
    # LDR Rd, [PC, #imm8]
    if opc2 == 0b01001:
        pc = (rom_addr + 4) & ~3
        target = pc + imm8 * 4
        return 'ldr r%d, [pc, #%d] -> 0x%08X' % (rd, imm8*4, target)
    # STR Rd, [Rn, #imm5]
    if opc2 == 0b01010:
        return 'str r%d, [r%d, #%d]' % (rd, rn, imm5*4)
    # LDR Rd, [Rn, #imm5]
    if opc2 == 0b01100:
        return 'ldr r%d, [r%d, #%d]' % (rd, rn, imm5*4)
    # STRB Rd, [Rn, #imm5]
    if opc2 == 0b01110:
        return 'strb r%d, [r%d, #%d]' % (rd, rn, imm5)
    # LDRB Rd, [Rn, #imm5]
    if opc2 == 0b01101:
        return 'ldrb r%d, [r%d, #%d]' % (rd, rn, imm5)
    # STRH Rd, [Rn, #imm5]
    if opc2 == 0b10000:
        return 'strh r%d, [r%d, #%d]' % (rd, rn, imm5*2)
    # LDRH Rd, [Rn, #imm5]
    if opc2 == 0b10001:
        return 'ldrh r%d, [r%d, #%d]' % (rd, rn, imm5*2)
    # LDR Rd, [Rn, Rm]
    if (op >> 9) == 0b010100 and ((op>>6)&3) == 0 and ((op>>10)&1)==0:
        # check for STR vs LDR
        if (op >> 9) == 0b010100:
            return 'str r%d, [r%d, r%d]' % (rd, rn, rm)
    # LDRB Rd, [Rn, Rm]
    if opc2 == 0b01010 and ((op>>9)&3) == 1:
        return 'ldrb r%d, [r%d, r%d]' % (rd, rn, rm)
    # High reg ops
    if (op >> 10) == 0b010001:
        h = (op >> 6) & 3
        dn = (op >> 7) & 1
        rd2 = rd | (dn << 3)
        if h == 0: return 'add r%d, r%d' % (rd2, rm)
        if h == 1: return 'cmp r%d, r%d' % (rd2, rm)
        if h == 2: return 'mov r%d, r%d' % (rd2, rm)
        if h == 3: 
            if (op >> 7) & 1: return 'blx r%d' % rm
            else: return 'bx r%d' % rm
    return None

# Disassemble from 0x08003C00
print("=" * 70)
print("ClearWindowTilemap 0x08003C00 (file offset 0x3C00)")
print("=" * 70)

i = 0x3C00
while i < 0x3C58:  # Until next function or end
    op = struct.unpack_from('<H', data, i)[0]
    rom_addr = BASE + i
    
    # BL check
    if (op >> 11) == 0b11101 and i + 2 < len(data):
        hw2 = struct.unpack_from('<H', data, i+2)[0]
        if (hw2 >> 11) == 0b11111:
            s = (op >> 10) & 1
            imm10 = op & 0x3FF
            j1 = (hw2 >> 14) & 1
            j2 = (hw2 >> 13) & 1
            imm11 = hw2 & 0x7FF
            i1 = 0 if (j1 ^ s) else 1
            i2 = 0 if (j2 ^ s) else 1
            off = (s << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
            if s: off -= 0x2000000
            target = rom_addr + 4 + off
            kind = ""
            if target == 0x08003628: kind = " <-- (GetBlankTileNum helper?)"
            print('0x%08X: %04X %04X  bl 0x%08X%s' % (rom_addr, op, hw2, target, kind))
            i += 4; continue
    
    # B conditional
    if (op >> 12) == 0b1101:
        cond_names = {0:'eq',1:'ne',2:'hs',3:'lo',4:'mi',5:'pl',6:'vs',7:'vc',8:'hi',9:'ls',0xA:'ge',0xB:'lt',0xC:'gt',0xD:'le'}
        cond = (op >> 8) & 0xF
        imm8 = op & 0xFF
        off = (imm8 * 2) if imm8 < 0x80 else ((imm8 - 256) * 2)
        target = rom_addr + 4 + off
        print('0x%08X: %04X  b%s 0x%08X' % (rom_addr, op, cond_names.get(cond,'?'), target))
        i += 2; continue
    
    # B unconditional
    if (op >> 11) == 0b11100:
        imm11 = op & 0x7FF
        off = (imm11 * 2) if imm11 < 0x400 else ((imm11 - 2048) * 2)
        target = rom_addr + 4 + off
        print('0x%08X: %04X  b 0x%08X' % (rom_addr, op, target))
        i += 2; continue
    
    mnem = thumb_asm(op, rom_addr)
    if mnem:
        print('0x%08X: %04X  %s' % (rom_addr, op, mnem))
        i += 2; continue
    
    # Data word
    if i + 4 <= len(data):
        w32 = struct.unpack_from('<I', data, i)[0]
        mark = ""
        if w32 in (0x03002503, 0x03002501, 0x03002500): mark = " WIDTH_PTR?"
        if w32 in (0x040000D4,): mark = " DMA3SAD"
        if w32 in (0x040000D8,): mark = " DMA3DAD"
        if w32 in (0x040000DC,): mark = " DMA3CNT"
        if mark:
            print('0x%08X: %04X  ; .word 0x%08X%s' % (rom_addr, op, w32, mark))
        else:
            print('0x%08X: %04X  ; .word 0x%08X' % (rom_addr, op, w32))
    else:
        print('0x%08X: %04X' % (rom_addr, op))
    i += 2
