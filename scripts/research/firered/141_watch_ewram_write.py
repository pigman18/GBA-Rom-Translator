#!/usr/bin/env python3
"""调研(141) 用 watchpoint 追「谁写了 EWRAM 0x0200553C」—— 字形的真正源头。

═══════════════════════════════════════════════════════════════════════════
【(140) 的决定性发现】
═══════════════════════════════════════════════════════════════════════════
DMA 源地址全在 EWRAM。其中两条直接是字形：

  [11] 源 0x0200553C → 目标 0x06001000（BG charBase 区）
       数据: 11 11 11 11 ... 31 12 11 11 22 11 11 11 32 11 11 11 13 11 33 12
             ↑ nibble 只有 1/2/3 —— **这就是字形数据！**

  [12] 源 0x0200653C → 目标 0x06002000
       数据: cc cc cc cc ce cc c1 cc 1e 3c e1 cc 51 1e e5 c3 ...

  [13] 源 0x020076EC → 目标 0x0600E000（tilemap 区）

⇒ 字形先被加载到 **EWRAM 0x0200553C / 0x0200653C**，再 DMA 到 VRAM。

【下一步：抓「谁往 EWRAM 写」】
 在 0x0200553C 上设**写 watchpoint（Z2）**，
 命中时 PC 就是「加载字形的代码」，r0/r1 可能指向 ROM！

 这是最后一步，能直接拿到 ROM 里的字库地址。

【本脚本】
 ① 先跑到标题，等 DMA 把数据搬进 VRAM
 ② 在 0x0200553C 设写 watchpoint
 ③ 触发画面重绘（用 GDB 反复 continue 让游戏自然重绘）
 ④ 命中时看 PC / 寄存器 / 调用栈

⚠ 若 watchpoint 只在「写入」时触发，可能需要等画面重绘。
 标题画面有动画，会反复重绘，有机会命中。

用法：python scripts/research/firered/141_watch_ewram_write.py
"""
from __future__ import annotations

import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from util.debug_patcher import GdbClient, GdbError   # noqa: E402

OUT = ROOT / "work" / "_probe" / "ewwatch"
ROM = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
SAVE = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"

# (140) 里确认含字形数据的 EWRAM 地址
GLYPH_BUF = [0x0200553C, 0x0200653C, 0x020076EC, 0x0200453C]


def find_mgba():
    base = ROOT / "tools" / "mgba_dev"
    if base.is_dir():
        c = sorted(base.glob("mGBA-build-*/mGBA.exe"))
        if c:
            return c[0]
    return ROOT / "tools" / "mGBA-0.10.5-win32" / "mGBA.exe"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    rom_copy = OUT / (ROM.stem + ".gba")
    shutil.copy2(ROM, rom_copy)
    shutil.copy2(SAVE, OUT / (ROM.stem + ".sav"))

    mgba = find_mgba()
    m = subprocess.Popen([str(mgba), "--gdb", str(rom_copy)],
                         cwd=str(OUT), stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    time.sleep(4)

    records = []
    try:
        c = GdbClient("127.0.0.1", 2345, timeout=10.0)
        c.connect()

        print("① 跑到标题（3 秒）")
        try:
            c.cont(timeout=3.0)
        except GdbError:
            pass

        # 在字形缓冲上设写 watchpoint
        print("\n② 在字形缓冲设写 watchpoint（Z2）")
        ok = []
        for a in GLYPH_BUF:
            try:
                r = c.cmd(f"Z2,{a:x},4")
                if r.startswith("OK"):
                    ok.append(a)
            except GdbError:
                pass
        print(f"  设置成功 {len(ok)} 个: {[f'0x{x:08X}' for x in ok]}")

        print("\n③ continue 等写入（最多 40 轮）")
        for i in range(40):
            try:
                why = c.cont(timeout=2.0)
            except GdbError:
                continue

            regs = c.cmd("g")
            # g 包有时返回 "T05watch:...;" 之类，先剥离出 hex 部分
            hexpart = "".join(ch for ch in regs if ch in "0123456789abcdefABCDEF")
            # g 包长度应为 68 或 100 字符（17 或 25 个寄存器 × 4 字节 × 2）
            if len(hexpart) < 68:
                continue
            hexpart = hexpart[:68]
            try:
                raw = bytes.fromhex(hexpart)
            except ValueError:
                continue

            def r(n):
                return int.from_bytes(raw[n * 4:(n + 1) * 4], "little")

            pc, lr, sp = r(15), r(14), r(13)
            vals = [r(k) for k in range(8)]

            # 读栈找返回地址
            try:
                stk = c.read_mem(sp, 96)
                stack_addrs = [int.from_bytes(stk[k:k + 4], "little")
                               for k in range(0, 96, 4)]
            except GdbError:
                stack_addrs = []

            records.append((pc, lr, sp, vals, stack_addrs, why))
            print(f"\n  [{i}] {why}")
            print(f"      PC=0x{pc:08X} LR=0x{lr:08X} SP=0x{sp:08X}")
            print(f"      r0..r7 = {[f'0x{v:08X}' for v in vals]}")
            # 找 ROM 地址
            rom_ptrs = [v for v in vals
                        if 0x08000000 <= v < 0x0A000000]
            if rom_ptrs:
                print(f"      ★ ROM 地址: "
                      f"{[f'0x{v:08X}' for v in rom_ptrs]}")
                for v in rom_ptrs[:2]:
                    try:
                        blk = c.read_mem(v, 48)
                        print(f"        0x{v:08X}: {blk.hex(' ')}")
                    except GdbError:
                        pass
            # 栈里的 ROM 返回地址
            rs = [a for a in stack_addrs if 0x08000000 <= a < 0x0A000000]
            if rs:
                print(f"      栈里 ROM 返回地址: "
                      f"{[f'0x{v:08X}' for v in rs[:5]]}")

            if len(records) >= 8:
                break

        c.close()

        print("\n" + "=" * 78)
        print("④ 汇总")
        print("=" * 78)
        print(f"  命中 {len(records)} 次")
        from collections import Counter
        cc = Counter(pc for pc, *_ in records)
        for p, n in cc.most_common(10):
            print(f"    PC 0x{p:08X}: {n} 次")

    except GdbError as e:
        print(f"GDB 错误：{e}")
    finally:
        try:
            m.terminate(); m.wait(timeout=5)
        except Exception:
            m.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
