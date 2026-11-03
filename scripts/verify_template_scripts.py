#!/usr/bin/env python3
"""验证找到的 template 布局：把 script 指针指向的 ROM 数据反汇编/解码。

── 上一版发现 ─────────────────────────────────────────────────────────
用「坐标合理 + ROM 指针」扫 SaveBlock1，最佳候选：
    base=0x0C0C  step=0x18  coord@+0x00  script@+0x0C
明细：
    [1] (1,3) script=0x08162668
    [2] (5,4) script=0x0816269C
    [3] (5,5) script=0x081626A5

── 本脚本要回答 ────────────────────────────────────────────────────────
这些 script 指针指向的 ROM 内容，**是不是真正的 NPC 脚本**？
（GBA 脚本是一串字节，常见开头是 0x00/0x02 之类，结尾 0x02 或 0x03）

做法：读 ROM 中这三个地址起 16 字节，打印十六进制；
若看到明显的脚本 opcode 序列（而不是随机数据），说明布局对了。

用法：python scripts/verify_template_scripts.py [sav路径]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot" / "tools"))
from savedit import rebuild, SB1_OFF  # noqa: E402

ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BASE_ADDR = 0x08000000
SB1_SIZE = 0x3AC0
TPL_BASE = 0x0C0C
TPL_STEP = 0x18
F_COORD = 0x00          # 上一版扫出来的
F_SCRIPT = 0x0C


def s16(b, o): return int.from_bytes(b[o:o + 2], "little", signed=True)
def u32(b, o): return int.from_bytes(b[o:o + 4], "little")


def main() -> int:
    sav = (Path(sys.argv[1]) if len(sys.argv) > 1
           else ROOT / "work" / "_probe" / "teleport.sav")
    logical, _ = rebuild(sav.read_bytes())
    sb1 = logical[SB1_OFF:SB1_OFF + SB1_SIZE]
    rom = ROM.read_bytes()

    print(f"{sav.name}  map={sb1[4]}:{sb1[5]}")
    print(f"template base=0x{TPL_BASE:04X} step=0x{TPL_STEP:02X}\n")

    found = 0
    for i in range(16):
        o = TPL_BASE + i * TPL_STEP
        if o + TPL_STEP > SB1_SIZE:
            break
        x, y = s16(sb1, o + F_COORD), s16(sb1, o + F_COORD + 2)
        sp = u32(sb1, o + F_SCRIPT)
        if not (0x08000000 <= sp < 0x0A000000):
            continue
        found += 1
        off = sp - BASE_ADDR
        body = rom[off:off + 24] if off + 24 <= len(rom) else b""
        print(f"[{i}] coord=({x},{y}) script=0x{sp:08X}")
        print(f"     原始 24 字节: {body.hex(' ')}")

        # 粗判：GBA 事件脚本常见 opcode
        #   0x00-0x0F 多为参数/比较；0x02 = end；0x03 = return
        #   0x4F/0x5x = msgbox 相关；0x51 = msgbox
        ops = []
        k = 0
        while k < len(body) and k < 20:
            op = body[k]
            if op == 0x02:
                ops.append("end(0x02)")
                break
            elif op == 0x03:
                ops.append("return(0x03)")
                break
            elif op == 0x4F:
                ops.append("compare(0x4F)")
                k += 3
            elif op == 0x51:
                ops.append("msgbox(0x51)")
                k += 1
            elif op == 0x66:
                ops.append("goto(0x66)")
                break
            else:
                ops.append(f"0x{op:02X}")
                k += 1
        print(f"      粗解 opcode: {ops}")
        print()

    print(f"共 {found} 个带 script 指针的 template")
    if found:
        print("\n⇒ 若上面的 opcode 里出现 msgbox/compare/goto 这类正常序列，")
        print("   说明 template 布局正确，可以据此定位所有可对话 NPC。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
