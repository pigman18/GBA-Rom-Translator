"""调研(288) 追 0x08B74000 的引用者 —— 汉化小字页表的真正使用者。

═══ 为什么查它 ═══
小字页表 0x08B74000（11 页，每页原版 100% FF）**是汉化新写入的**，
一定是中文小字的来源。我用两种公式都解不出能读的字：
    lo * 64        -> 满格乱码
    (code>>4)*512  -> 满格乱码
⇒ 说明公式还没找对，必须先找到**引用这张表的代码**。

本脚本：
 ① 全 ROM 搜 0x08B74000 的 u32 引用
 ② 每处反汇编半径 0x80，看它怎么算地址
 ③ 同样查 0x08B6C000（配置表里的"默认页"）
"""
from __future__ import annotations

import struct
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
BASE = 0x08000000
N = len(zh)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)

TARGETS = {
    "小字页表 0x08B74000": 0x08B74000,
    "默认页 0x08B6C000": 0x08B6C000,
    "解码缓冲 0x020228FC": 0x020228FC,
}


def rd32(a):
    o = a - BASE
    return struct.unpack_from('<I', zh, o)[0] if 0 <= o <= N - 4 else None


for name, addr in TARGETS.items():
    print("=" * 78)
    print(f"{name}")
    print("=" * 78)
    nd = struct.pack('<I', addr)
    pos = zh.find(nd)
    hits = []
    while pos >= 0:
        hits.append(pos)
        pos = zh.find(nd, pos + 1)
    print(f"  引用 {len(hits)} 处: {[hex(BASE + h) for h in hits[:12]]}")

    for h in hits[:6]:
        o = h - BASE
        old = 0
        print(f"\n  --- 引用点 0x{BASE + h:08X} ---")
        # 往前找函数头
        fs = None
        for k in range(h, max(0, h - 0x400), -2):
            hw = struct.unpack_from('<H', zh, k)[0]
            if (hw & 0xFE00) == 0xB400 and (hw & 0x0100):
                fs = k
                break
        if fs is None:
            print("    未找到函数头")
            continue
        faddr = BASE + fs
        print(f"    所在函数 0x{faddr:08X}")
        # 反汇编函数头到字面量之后 0x30
        ln = min(h - fs + 0x30, 0x300)
        i = fs
        end = fs + ln
        a = faddr
        while i < end:
            hw = struct.unpack_from('<H', zh, i)[0]
            n = 4 if (hw & 0xF800) in (0xF000, 0xF800, 0xE800) else 2
            if i + n > end:
                break
            got = list(md.disasm(zh[i:i + n], a))
            if got:
                ins = got[0]
                raw = zh[i:i + n]
                mk = ""
                if i + n <= len(ja) and zh[i:i + n] != ja[i:i + n]:
                    mk = " *"
                star = " <<<" if i == h else ""
                print(f"    0x{a:08X}{mk:<2} {raw.hex():<9} "
                      f"{ins.mnemonic:<7} {ins.op_str}{star}")
            i += n
            a += n
