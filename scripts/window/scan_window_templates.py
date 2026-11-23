"""scan_window_templates.py — 静态定位 Ruby 所有 WindowTemplate 及其使用点

思路（全部静态，不跑模拟器）：
1. WindowTemplate 是 28 字节记录，字段已由 Text_InitWindow 反汇编确认：
     tpl[4]=paletteNum, tpl[5]=fgColor, tpl[6]=bgColor, tpl[7]=shadowColor,
     tpl[8]=fontNum, tpl[9]=textMode
   其余（bg/left/top/width/height/baseBlock/tilemap）由绘制代码读取。
2. 真模板必然被代码以**字面量**引用（ldr rX,=tpl 或 add rX,=base+off），
   而不是凭空出现在符号表里。所以：扫 ROM 里所有 0x08xxxxxx 字面量，
   统计哪些地址被引用，再验证被引用处是否符合模板字段约束。
3. 字段约束（用于判定“像不像模板”）：
     - paletteNum 0..15
     - fg/bg/shadow 0..15
     - fontNum 0..6
     - textMode 0..7
     合法模板必须六项全部满足。

输出：候选模板地址 + 引用点 + 字段值，供人工/后续脚本复核。
"""
from __future__ import annotations

import struct
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
ROM_BASE = 0x08000000
TPL_SIZE = 28


def main() -> None:
    rom = ROM_PATH.read_bytes()

    # 1) 收集所有被字面量引用的 ROM 地址
    refs: dict[int, list[int]] = defaultdict(list)
    for o in range(0, len(rom) - 4, 4):
        v = struct.unpack_from("<I", rom, o)[0]
        if ROM_BASE <= v < ROM_BASE + len(rom):
            refs[v].append(o + ROM_BASE)

    print(f"ROM 内被引用的地址数: {len(refs)}")

    # 2) 逐个验证像不像 WindowTemplate
    def field(addr: int, off: int) -> int:
        return rom[addr - ROM_BASE + off]

    def plausible(addr: int) -> tuple[bool, dict]:
        if addr - ROM_BASE + TPL_SIZE > len(rom):
            return False, {}
        pal = field(addr, 4)
        fg = field(addr, 5)
        bg = field(addr, 6)
        sh = field(addr, 7)
        fn = field(addr, 8)
        tm = field(addr, 9)
        ok = (
            pal <= 15 and fg <= 15 and bg <= 15 and sh <= 15
            and fn <= 6 and tm <= 7
        )
        return ok, dict(pal=pal, fg=fg, bg=bg, sh=sh, fontNum=fn, textMode=tm)

    cands: list[tuple[int, dict, list[int]]] = []
    for addr, srcs in refs.items():
        ok, f = plausible(addr)
        if ok:
            cands.append((addr, f, srcs))

    print(f"满足模板字段约束的候选: {len(cands)}\n")
    print(f"{'地址':<12} {'pal':>3} {'fg':>3} {'bg':>3} {'sh':>3} {'font':>4} {'mode':>4}  引用点")
    print("-" * 100)
    for addr, f, srcs in sorted(cands):
        s = ", ".join(f"0x{x:08X}" for x in srcs[:4])
        if len(srcs) > 4:
            s += f" ...(+{len(srcs)-4})"
        print(f"0x{addr:08X}  {f['pal']:3d} {f['fg']:3d} {f['bg']:3d} {f['sh']:3d} "
              f"{f['fontNum']:4d} {f['textMode']:4d}  {s}")

    # 3) 连续模板块检测（相邻 0x1C）
    cand_addrs = sorted(c[0] for c in cands)
    print("\n连续块（相邻 0x1C）:")
    run = [cand_addrs[0]] if cand_addrs else []
    for a in cand_addrs[1:]:
        if a - run[-1] == TPL_SIZE:
            run.append(a)
        else:
            if len(run) >= 3:
                print(f"  0x{run[0]:08X}..0x{run[-1]:08X}  {len(run)} 个")
            run = [a]
    if len(run) >= 3:
        print(f"  0x{run[0]:08X}..0x{run[-1]:08X}  {len(run)} 个")


if __name__ == "__main__":
    main()
