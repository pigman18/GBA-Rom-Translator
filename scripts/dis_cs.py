"""dis_cs.py — 用 capstone 做 Thumb 反汇编（权威，替代手写解码器）。

用法:
  python scripts/dis_cs.py <addr_hex> [len_hex] [--rom path]

为什么存在：scripts/b2_dis.py 是手写解码器，对 00011 (add/sub imm3) /
0Cxx / 1Cxx 等编码有 bug，会把 `adds r3,r0,#0` 印成 `?shift`。
本项目已有「手算 Thumb 边界必错」的血案，反汇编一律走本脚本。
"""
import sys
import capstone

ROM_DEFAULT = 'roms/origin/POKEMON_RUBY_AXVJ00.gba'
BASE = 0x08000000


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    rom = ROM_DEFAULT
    for i, a in enumerate(sys.argv):
        if a == '--rom':
            rom = sys.argv[i + 1]

    addr = int(args[0], 16)
    n = int(args[1], 16) if len(args) > 1 else 0x40

    data = open(rom, 'rb').read()
    off = addr - BASE
    code = data[off:off + n]

    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    md.detail = False
    for ins in md.disasm(code, addr):
        print(f'{ins.address:08X}: {ins.bytes.hex():<10} {ins.mnemonic:<8} {ins.op_str}')


if __name__ == '__main__':
    main()
