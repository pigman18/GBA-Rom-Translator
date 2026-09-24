"""静态扫描：谁写过 Window[+0x18]（TILE_OFFSET）。

目的：判定「官方引擎是否在每个文本块开始时复位 TILE_OFFSET」。
我们自己的代码只累加不复位（PrintNextChar_hook.c 4 处引用）。
若官方也从不复位 ⇒ tm0 的落点 BASE+TILE_OFFSET 会随文本量单调增长
⇒ 「战斗久了文本乱飞」的直接机理。

做法：capstone 逐指令反汇编 0x08002800..0x08004000（日版文本引擎区），
找所有 mem.disp == 0x18 的 strh/str/strb。不猜边界、不手算。

自证：必须能同时找到
  · tm0 处理器的 `adds r?, #2` 后写 [+0x18]
  · 若存在复位点，应能读到 `strh r?, [r?, #0x18]` 且源寄存器刚被 movs 清零
"""
import sys
import capstone

ROM = r"C:\code\GBA-Rom-Translator\roms\origin\POKEMON_RUBY_AXVJ00.gba"
BASE = 0x08000000
LO, HI = 0x08002800, 0x08004000
OFF = 0x18


def main() -> int:
    rom = open(ROM, "rb").read()
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    md.detail = True

    code = rom[LO - BASE:HI - BASE]
    hits = []
    for ins in md.disasm(code, LO):
        for op in ins.operands:
            if op.type != capstone.arm.ARM_OP_MEM:
                continue
            if op.mem.base == 0:
                continue
            if op.mem.disp != OFF:
                continue
            hits.append((ins.address, ins.mnemonic, ins.op_str))

    print("=== 写/读 Window[+0x18] 的指令（0x%08x..0x%08x）===" % (LO, HI))
    for a, m, o in hits:
        kind = "WRITE" if m.startswith("str") else ("READ " if m.startswith("ldr") else "?    ")
        print("%s  0x%08x  %-6s %s" % (kind, a, m, o))
    print()
    print("总计 = %d 条" % len(hits))

    # 自证：已知 tm0 处理器 FontFuncTable[0] = 0x08003569，其体内应有 [+0x18] 写
    tm0 = [h for h in hits if 0x08003569 <= h[0] < 0x0800360D]
    print("自证 A：tm0 处理器(0x08003569..0x0800360D)内的 [+0x18] 访问 = %d 条" % len(tm0))
    for a, m, o in tm0:
        print("        0x%08x  %s %s" % (a, m, o))

    # 自证 B：整个区间内是否有「写 0」= 复位点
    writes = [h for h in hits if h[1].startswith("str")]
    print("自证 B：写入类指令共 %d 条（其中源寄存器为 r 的需人工看）" % len(writes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
