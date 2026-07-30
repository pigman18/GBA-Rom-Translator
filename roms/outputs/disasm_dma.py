"""Disassemble around DMA buffer references"""
import struct

rom_path = r'C:\code\gba\roms\origin\POKEMON_RUBY_AXVJ00.gba'
with open(rom_path, 'rb') as f:
    data = f.read()

BASE = 0x08000000

def decode_thumb(op, rom_addr):
    """Decode a THUMB instruction. Returns (mnemonic, size_in_bytes)."""
    # LSL Rd, Rm, #imm5
    if (op >> 11) == 0b00000:
        rd = op & 7
        rm = (op >> 3) & 7
        imm5 = (op >> 6) & 0x1F
        return f'lsl r{rd}, r{rm}, #{imm5}', 2
    # MOV Rd, Rm (low reg)
    if (op >> 11) == 0b0001110:
        rd = op & 7
        rm = (op >> 3) & 7
        return f'mov r{rd}, r{rm}', 2
    # ADD Rd, Rm, Rn (low regs)
    if (op >> 9) == 0b0001100:
        rd = op & 7
        rn = (op >> 6) & 7
        rm = (op >> 3) & 7
        return f'add r{rd}, r{rn}, r{rm}', 2
    # ADD Rd, Rm, #imm3
    if (op >> 9) == 0b0001110:
        rd = op & 7
        rm = (op >> 6) & 7
        imm3 = (op >> 3) & 7
        return f'add r{rd}, r{rm}, #{imm3}', 2
    # LDR Rd, [PC, #imm8]
    if (op >> 12) == 0b01001:
        rd = (op >> 8) & 7
        imm8 = (op & 0xFF) * 4
        pc = (rom_addr + 4) & ~3
        target = pc + imm8
        return f'ldr r{rd}, [pc, #{imm8}]  ; 0x{target:08X}', 2
    # LDRH Rd, [Rn, #imm5]
    if (op >> 11) == 0b01001:  # actually 0b10001
        rd = (op >> 8) & 7
        rn = (op >> 3) & 7
        imm5 = (op & 0x1F) * 2
        return f'ldrh r{rd}, [r{rn}, #{imm5}]', 2
    # LDRB Rd, [Rn, #imm5]
    if (op >> 11) == 0b01101:  # 0b01101
        rd = (op >> 8) & 7
        rn = (op >> 3) & 7
        imm5 = (op & 0x1F)
        return f'ldrb r{rd}, [r{rn}, #{imm5}]', 2
    # STRH Rd, [Rn, #imm5]
    if (op >> 11) == 0b10001:
        rd = (op >> 8) & 7
        rn = (op >> 3) & 7
        imm5 = (op & 0x1F) * 2
        return f'strh r{rd}, [r{rn}, #{imm5}]', 2
    # STRB Rd, [Rn, #imm5]
    if (op >> 11) == 0b01110:
        rd = (op >> 8) & 7
        rn = (op >> 3) & 7
        imm5 = (op & 0x1F)
        return f'strb r{rd}, [r{rn}, #{imm5}]', 2
    # LDR Rd, [Rn, #imm5] (word)
    if (op >> 11) == 0b01100:
        rd = (op >> 8) & 7
        rn = (op >> 3) & 7
        imm5 = (op & 0x1F) * 4
        return f'ldr r{rd}, [r{rn}, #{imm5}]', 2
    # STR Rd, [Rn, #imm5] (word)
    if (op >> 11) == 0b01010:
        rd = (op >> 8) & 7
        rn = (op >> 3) & 7
        imm5 = (op & 0x1F) * 4
        return f'str r{rd}, [r{rn}, #{imm5}]', 2
    # CMP Rn, #imm8
    if (op >> 11) == 0b01011:
        rn = (op >> 8) & 7
        imm8 = op & 0xFF
        return f'cmp r{rn}, #{imm8}', 2
    # MOV Rd, #imm8
    if (op >> 11) == 0b00100:
        rd = (op >> 8) & 7
        imm8 = op & 0xFF
        return f'mov r{rd}, #{imm8}', 2
    # ADD Rd, #imm8
    if (op >> 11) == 0b00110:
        rd = (op >> 8) & 7
        imm8 = op & 0xFF
        return f'add r{rd}, #{imm8}', 2
    # ADD Rn, #imm8
    if (op >> 11) == 0b00110:
        rd = (op >> 8) & 7
        imm8 = op & 0xFF
        return f'add r{rd}, #{imm8}', 2
    # SUB Rd, #imm8
    if (op >> 11) == 0b00111:
        rd = (op >> 8) & 7
        imm8 = op & 0xFF
        return f'sub r{rd}, #{imm8}', 2
    # BEQ
    if (op >> 12) == 0b1101:
        cond = op & 0xF00
        imm8 = op & 0xFF
        off = (imm8 * 2) if imm8 < 0x80 else ((imm8 - 256) * 2)
        target = rom_addr + 4 + off
        return f'b 0x{target:08X}', 2
    # B (unconditional)
    if (op >> 11) == 0b11100:
        imm11 = op & 0x7FF
        off = (imm11 * 2) if imm11 < 0x400 else ((imm11 - 2048) * 2)
        target = rom_addr + 4 + off
        return f'b 0x{target:08X}', 2
    # BL / BLX
    if (op >> 11) == 0b11101:
        # First halfword of BL: op >> 11 = 0b11101
        s = op & 0x400  # bit 10
        return 'BL(hi)', 4  # 4-byte instruction
    
    return '', 2


def disasm_range(start_off, end_off):
    i = start_off
    while i < end_off - 1:
        if i >= len(data) - 1:
            break
        op = struct.unpack_from('<H', data, i)[0]
        rom_addr = BASE + i
        
        # Check for 32-bit word data
        if i + 4 <= len(data):
            w32 = struct.unpack_from('<I', data, i)[0]
            if 0x02000000 <= w32 <= 0x0A000000 and (i % 4) == 0:
                if w32 in (0x0600E000, 0x0600F000, 0x0600E800, 0x040000D4, 0x040000D8, 0x040000DC, 0x020219CC, 0x020221CC, 0x020229CC):
                    name = {0x0600E000:'TM_E0', 0x0600F000:'TM_F0', 0x0600E800:'TM_E8', 
                            0x040000D4:'DMA3SAD', 0x040000D8:'DMA3DAD', 0x040000DC:'DMA3CNT',
                            0x020219CC:'BUF1', 0x020221CC:'BUF2', 0x020229CC:'BUF3'}[w32]
                    print(f'0x{rom_addr:08X}: {op:04X}  ; .word 0x{w32:08X} [{name}]')
                    i += 4
                    continue
        
        # Check for THUMB BL
        if (op >> 11) == 0b11101 and i + 2 < len(data):
            hw2 = struct.unpack_from('<H', data, i+2)[0]
            if (hw2 >> 11) == 0b11111:
                # BL
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
                print(f'0x{rom_addr:08X}: {op:04X} {hw2:04X}  bl 0x{target:08X}')
                i += 4
                continue
            elif (hw2 >> 11) == 0b11100:
                # BLX
                print(f'0x{rom_addr:08X}: {op:04X} {hw2:04X}  blx')
                i += 4
                continue
        
        # PUSH/POP
        if op == 0xB510:
            print(f'0x{rom_addr:08X}: {op:04X}  push {{r4, lr}}')
            i += 2; continue
        if op == 0xB570:
            print(f'0x{rom_addr:08X}: {op:04X}  push {{r4-r6, lr}}')
            i += 2; continue
        if op == 0xB5F0:
            print(f'0x{rom_addr:08X}: {op:04X}  push {{r4-r7, lr}}')
            i += 2; continue
        if op == 0xBC10:
            print(f'0x{rom_addr:08X}: {op:04X}  pop {{r4}}')
            i += 2; continue
        if op == 0xBC01:
            print(f'0x{rom_addr:08X}: {op:04X}  pop {{r1}}')
            i += 2; continue
        if op == 0xBCF0:
            print(f'0x{rom_addr:08X}: {op:04X}  pop {{r4-r7}}')
            i += 2; continue
        if op == 0xBC08:
            print(f'0x{rom_addr:08X}: {op:04X}  pop {{r3}}')
            i += 2; continue
        if op == 0xBD10:
            print(f'0x{rom_addr:08X}: {op:04X}  pop {{r4, pc}}')
            i += 2; continue
        if op == 0xBD70:
            print(f'0x{rom_addr:08X}: {op:04X}  pop {{r4-r6, pc}}')
            i += 2; continue
        if op == 0xBDF0:
            print(f'0x{rom_addr:08X}: {op:04X}  pop {{r4-r7, pc}}')
            i += 2; continue
        if op == 0x4700:
            print(f'0x{rom_addr:08X}: {op:04X}  bx r1')
            i += 2; continue
        if op == 0x4770:
            print(f'0x{rom_addr:08X}: {op:04X}  bx lr')
            i += 2; continue
        if op == 0x46C0:
            print(f'0x{rom_addr:08X}: {op:04X}  nop')
            i += 2; continue
        if op == 0x1C04:
            print(f'0x{rom_addr:08X}: {op:04X}  add r4, r0, #0')
            i += 2; continue
        if op == 0x1C05:
            print(f'0x{rom_addr:08X}: {op:04X}  add r5, r0, #0')
            i += 2; continue
        if op == 0x1C06:
            print(f'0x{rom_addr:08X}: {op:04X}  add r6, r0, #0')
            i += 2; continue
        if op == 0x1C08:
            print(f'0x{rom_addr:08X}: {op:04X}  add r0, r1, #0')
            i += 2; continue
        if op == 0x1C20:
            print(f'0x{rom_addr:08X}: {op:04X}  add r0, r4, #0')
            i += 2; continue
        if op == 0x1C28:
            print(f'0x{rom_addr:08X}: {op:04X}  add r0, r5, #0')
            i += 2; continue
        if op == 0x1C30:
            print(f'0x{rom_addr:08X}: {op:04X}  add r0, r6, #0')
            i += 2; continue
        if op == 0x1C09:
            print(f'0x{rom_addr:08X}: {op:04X}  add r1, r1, #0')
            i += 2; continue

        # Common THUMB
        rd = op & 7
        rn = (op >> 3) & 7
        rm = (op >> 6) & 7
        
        # ADD Rd, Rm (high/low)
        if (op >> 8) == 0b01000100:
            dn = (op >> 7) & 1
            rd2 = rd | (dn << 3)
            return f'add r{rd2}, r{rm}', 2
        
        # CMP Rd, Rm (high/low)
        if (op >> 8) == 0b01000101:
            dn = (op >> 7) & 1
            rd2 = rd | (dn << 3)
            return f'cmp r{rd2}, r{rm}', 2
        
        # MOV Rd, Rm (high/low)
        if (op >> 8) == 0b01000110:
            dn = (op >> 7) & 1
            rd2 = rd | (dn << 3)
            return f'mov r{rd2}, r{rm}', 2
        
        # BX Rm
        if (op >> 8) == 0b01000111:
            return f'bx r{rm}', 2
        
        # BLX Rm  
        if (op >> 8) == 0b01000111:
            return f'blx r{rm}', 2
        
        # LDRB Rd, [Rn, Rm]
        if (op >> 6) == 0b01010010:
            return f'ldrb r{rd}, [r{rn}, r{rm}]', 2
        
        # LDR Rd, [Rn, Rm]
        if (op >> 6) == 0b01010000:
            return f'ldr r{rd}, [r{rn}, r{rm}]', 2
        
        # STR Rd, [Rn, Rm]
        if (op >> 6) == 0b01010000:
            return f'str r{rd}, [r{rn}, r{rm}]', 2
        
        mnem, _ = decode_thumb(op, rom_addr)
        if mnem:
            print(f'0x{rom_addr:08X}: {op:04X}  {mnem}')
        else:
            # Print as data
            if i + 4 <= len(data):
                w32 = struct.unpack_from('<I', data, i)[0]
                if w32 > 0:  # non-zero data
                    print(f'0x{rom_addr:08X}: {op:04X}  ; .word 0x{w32:08X}')
                else:
                    print(f'0x{rom_addr:08X}: {op:04X}')
            else:
                print(f'0x{rom_addr:08X}: {op:04X}')
        
        i += 2

# Disassemble the function at 0x54C00 to 0x54E00
# This covers the 0x020221CC reference
print("=" * 60)
print("Disassembly around 0x08054C98 (where 0x020221CC is stored)")
print("=" * 60)
print()
disasm_range(0x054C00, 0x054E00)
