import struct

rom_path = r'C:\code\gba\roms\origin\POKEMON_RUBY_AXVJ00.gba'
with open(rom_path, 'rb') as f:
    data = f.read()

BASE = 0x08000000

# Disassemble Text_ClearWindow region
for i in range(0x3BA8, 0x3C00, 2):
    op = struct.unpack_from('<H', data, i)[0]
    rom_addr = BASE + i
    desc = ''
    
    # THUMB instruction decoding
    if op == 0xB510:
        desc = 'push {r4, lr}'
    elif op == 0xBC10:
        desc = 'pop {r4}'
    elif op == 0xBC01:
        desc = 'pop {r1}'
    elif op == 0x4700:
        desc = 'bx r1'
    elif op == 0x4770:
        desc = 'bx lr'
    elif op == 0x1C04:
        desc = 'add r4, r0, #0'
    elif op == 0x1C20:
        desc = 'add r0, r4, #0'
    elif op == 0x1C05:
        desc = 'add r5, r0, #0'
    elif op == 0x1C28:
        desc = 'add r0, r5, #0'
    elif (op & 0xF800) == 0x4800:
        rd = (op >> 8) & 7
        imm = (op & 0xFF) * 4
        pc = (rom_addr + 4) & ~3
        target = pc + imm
        desc = 'ldr r%d, [pc, #%d] -> 0x%08X' % (rd, imm, target)
    elif (op & 0xF800) == 0x2000:
        desc = 'mov r0, #0x%X' % (op & 0xFF)
    elif (op & 0xF800) == 0x7800:
        rn = (op >> 3) & 7
        off = op & 0x1F
        desc = 'ldrb r0, [r%d, #0x%X]' % (rn, off)
    elif (op & 0xF800) == 0x7A00:
        rn = (op >> 3) & 7
        off = op & 0x1F
        desc = 'ldrb r0, [r%d, #0x%X]' % (rn, off)
    elif (op & 0xFF00) == 0x8300:
        desc = 'strh r0, [r4, #0x%X]' % (op & 0xFF)
    elif (op & 0xF800) == 0x2800:
        desc = 'cmp r0, #0x%X' % (op & 0xFF)
    elif (op & 0xF000) == 0xD000:
        cond = (op >> 8) & 0xF
        imm8 = op & 0xFF
        off = imm8 * 2
        if imm8 >= 0x80:
            off = (imm8 - 0x100) * 2
        target = rom_addr + 4 + off
        desc = 'b -> 0x%08X (cond=%x)' % (target, cond)
    elif op == 0xE00F:
        desc = 'b +0x1E -> 0x%08X' % (rom_addr + 4 + 30)
    elif op == 0xE006:
        desc = 'b +0xC -> 0x%08X' % (rom_addr + 4 + 12)
    elif op == 0xE01C:
        desc = 'b +0x38 -> 0x%08X' % (rom_addr + 4 + 56)
    elif op == 0xE017:
        desc = 'b +0x2E -> 0x%08X' % (rom_addr + 4 + 46)
    elif op == 0xB5F0:
        desc = 'push {r4-r7, lr}'
    elif op == 0xBCF0:
        desc = 'pop {r4-r7}'
    elif op == 0xB570:
        desc = 'push {r4-r6, lr}'
    elif (op & 0xF800) == 0xF000:
        # BL
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
            if s:
                off -= 0x2000000
            target = rom_addr + 4 + off
            desc = 'bl 0x%08X' % target
        else:
            desc = ''
    
    if desc:
        print('%08X: %04X  ; %s' % (rom_addr, op, desc))
    else:
        # Check 32-bit data
        if i+2 <= 0x3C00:
            val32 = struct.unpack_from('<I', data, i)[0]
            if val32 >= 0x02000000 and val32 <= 0x0A000000:
                print('%08X: %04X  ; data 0x%08X' % (rom_addr, op, val32))
            else:
                print('%08X: %04X' % (rom_addr, op))
