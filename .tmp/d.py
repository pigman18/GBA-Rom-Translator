# -*- coding: utf-8 -*-
"""d.py — 从 ROM 抓一段做 Thumb 反汇编（逐指令，不做任何地址推算）。

用法:  python .tmp/d.py <hex起始> <hex结束>
"""
import subprocess
import sys
from pathlib import Path

ROM = Path(r"C:/code/GBA-Rom-Translator/roms/origin/POKEMON_RUBY_AXVJ00.gba")
OBJDUMP = (r"C:/Program Files (x86)/Arm GNU Toolchain arm-none-eabi/14.2 rel1"
           r"/bin/arm-none-eabi-objdump")


def main(a, b):
    start = int(a, 16)
    end = int(b, 16)
    data = ROM.read_bytes()[start:end]
    tmp = Path(r"C:/code/GBA-Rom-Translator/.tmp/_dis_tmp.bin")
    tmp.write_bytes(data)
    r = subprocess.run([OBJDUMP, "-D", "-b", "binary", "-m", "armv4t",
                        "-M", "force-thumb",
                        "--adjust-vma=0x%08X" % start, str(tmp)],
                       capture_output=True, text=True)
    for ln in r.stdout.splitlines():
        if ln.strip().startswith("0"):
            print(ln.rstrip())


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
