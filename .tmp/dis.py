# -*- coding: utf-8 -*-
"""dis.py <addr_hex> <len_hex> [thumb|arm]  —— 反汇编 origin ROM 指定区域
地址采用 ROM 绝对地址(0x08xxxxxx)。objdump 用 --adjust-vma=addr 使得打印地址 == 实际地址。
"""
import subprocess, sys, re
from pathlib import Path
ROM = Path(r"C:/code/GBA-Rom-Translator/roms/origin/POKEMON_RUBY_AXVJ00.gba")
OD  = r"C:/Program Files (x86)/Arm GNU Toolchain arm-none-eabi/14.2 rel1/bin/arm-none-eabi-objdump.exe"
TMP = Path(r"C:/code/GBA-Rom-Translator/.tmp")

def dump(addr, ln, mode="thumb", label="", rom=None):
    rb = (rom or ROM).read_bytes()
    off = addr - 0x08000000
    seg = rb[off:off+ln]
    f = TMP / ("_d_%08X.bin" % addr)
    f.write_bytes(seg)
    cmd = [OD, "-D", "-b", "binary", "-m", "armv4t"]
    if mode == "thumb":
        cmd += ["-M", "force-thumb"]
    cmd += ["--adjust-vma=0x%08X" % addr, str(f)]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    lines = [l.rstrip() for l in out.splitlines() if re.match(r"^\s*[0-9a-f]{6,8}:", l)]
    if label:
        print("======== %s ========" % label)
    print("\n".join(lines))
    return lines

if __name__ == "__main__":
    a = int(sys.argv[1], 16)
    n = int(sys.argv[2], 16)
    m = sys.argv[3] if len(sys.argv) > 3 else "thumb"
    dump(a, n, m)
