"""dumprange.py — 完整反汇编一段（不停在 bx lr），带字面量解析。静态只读。
用法: dumprange.py 0x08002950 0x08002C70
"""
import sys, struct, re
import capstone

ROM = r"C:\code\GBA-Rom-Translator\roms\origin\POKEMON_RUBY_AXVJ00.gba"
BASE = 0x08000000
SYMS = {
    0x08002950: "SetWindowTileCache?", 0x080029E0: "GlyphPrefetchWorker",
    0x08002A50: "InitWindowTileData", 0x08002C28: "?", 0x08002C68: "InitTextPrinter",
    0x08002DB4: "FdSubprint", 0x080032F8: "PrintNextChar", 0x0800338D: "FontFunc_tm2",
    0x08003495: "FontFunc_tm3", 0x08003520: "tm0_core", 0x08003569: "FontFunc_tm0",
    0x08003584: "FontSub_f0_f3", 0x080035A0: "FontSub_f1_f4", 0x080035C8: "FontSub_f2_f5",
    0x0800360C: "PrintGlyph_TextMode1", 0x08003630: "DrawGlyphTiles",
    0x080036DC: "UpdateTilemap", 0x08003708: "GetCursorTilemapPointer",
    0x08003730: "GetGlyphTilePointers", 0x08003830: "CopyGlyph1bppTo4bpp",
    0x080046D4: "FdResolver", 0x081B12DC: "CALL_VIA_R2",
    0x081BB3AC: "FontFuncTable", 0x081BB3BC: "FontSubTable", 0x081B34A8: "FontType1Map",
}


def main():
    a0 = int(sys.argv[1], 16)
    a1 = int(sys.argv[2], 16)
    d = open(ROM, "rb").read()
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    code = d[a0 - BASE:a1 - BASE]
    for ins in md.disasm(code, a0):
        note = ""
        if ins.mnemonic in ("bl", "blx", "b") and "#" in ins.op_str:
            m = re.search(r"#0x([0-9a-f]+)", ins.op_str)
            if m:
                t = int(m.group(1), 16)
                note = "   ; -> " + (SYMS.get(t) or hex(t))
        elif ins.mnemonic == "ldr" and "[pc" in ins.op_str:
            m = re.search(r"#(-?0x[0-9a-f]+)", ins.op_str)
            if m:
                lit = (ins.address + 4) & ~3
                lit += int(m.group(1), 16)
                if 0 <= lit - BASE + 4 <= len(d):
                    v = struct.unpack_from("<I", d, lit - BASE)[0]
                    note = "   ; [0x%08X]=0x%08X %s" % (lit, v, SYMS.get(v & ~1, ""))
        sym = SYMS.get(ins.address)
        print("%s%08X: %-18s %-26s%s" % ("  ", ins.address, ins.bytes.hex(), ins.mnemonic + " " + ins.op_str, note))
        if sym:
            print("        ^^^ " + sym)


if __name__ == "__main__":
    main()
