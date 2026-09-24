#!/usr/bin/env python3
"""实验：短超时 cont 循环 + 断点命中检测 —— 确定 mGBA stub 的真实语义。

要回答：
  Q1. cont(0.25) 超时后，GBA 是否仍在跑？（读 pc 推进即可知）
  Q2. 超时后 socket 里是否残留 stop reply？（下次 cmd 是否错位）
  Q3. 挂 Z0 断点后，cont(0.25) 循环能不能命中？

脚本自己起 mGBA（全程持有），跑完自己关。
"""
import os
import subprocess
import sys
import time

ROOT = r"C:\code\GBA-Rom-Translator"
sys.path.insert(0, os.path.join(ROOT, "src", "util"))
from debug_patcher import GdbClient, GdbError  # noqa: E402

EXE = os.path.join(ROOT, "tools", "mGBA-0.10.5-win32", "mGBA.exe")
ROM = os.path.join(ROOT, "roms", "outputs", "POKEMON_RUBY_AXVJ00_translated.gba")

# 心跳断点：DrawGlyphTiles + 一个肯定会被调的（VBlank 无关，先用 InitTextPrinter）
BP = 0x08003630

SEQDOWN = 0x0080  # DOWN


def main() -> int:
    fo = open(os.path.join(ROOT, ".tmp", "t_sem.out"), "wb")
    p = subprocess.Popen([EXE, "-g", ROM], cwd=ROOT,
                         stdin=subprocess.DEVNULL, stdout=fo, stderr=fo)
    print(f"mGBA pid={p.pid}", flush=True)
    time.sleep(4)

    g = GdbClient("127.0.0.1", 2345, timeout=6.0)
    g.connect()

    # Q1: 短超时循环 5 次，看 pc 推进
    print("\n=== Q1: 短超时 cont 循环，pc 是否推进 ===", flush=True)
    for i in range(5):
        t0 = time.time()
        try:
            g.cont(timeout=0.25)
            print(f"  [{i}] cont 返回(命中!)", flush=True)
        except GdbError as e:
            print(f"  [{i}] cont 超时({time.time()-t0:.2f}s)", flush=True)
        try:
            regs = g.read_regs()
            print(f"       pc=0x{regs.get('r15',0):08X}", flush=True)
        except GdbError as e:
            print(f"       read_regs 失败: {e}", flush=True)
            break

    # Q2: 超时后立刻发一个简单 cmd，看是否错位
    print("\n=== Q2: 超时后 cmd 是否错位 ===", flush=True)
    try:
        r = g.cmd("?")
        print(f"  '?' → {r!r}", flush=True)
    except GdbError as e:
        print(f"  '?' 失败: {e}", flush=True)

    # Q3: 挂断点 + 短超时循环，按键推进
    print("\n=== Q3: 挂 0x%08X 断点，短超时 + 按 START 推进 ===" % BP, flush=True)
    try:
        g.set_sw_break(BP)
        print("  断点已挂 OK", flush=True)
    except GdbError as e:
        print(f"  挂断点失败: {e}", flush=True)
        g.close(); p.terminate(); return 1

    hits = 0
    key_seq = [0x0008, 0x0001, 0x0001, 0x0008]  # START A A START
    ki = 0
    for i in range(400):
        # 注入按键：每 6 拍换一个
        if i % 6 == 0:
            k = key_seq[ki % len(key_seq)] if ki < 12 else 0
            ki += 1
            v = 0x03FF & ~k
            try:
                g.cmd(f"M4000130,2,{v:04x}")
            except GdbError:
                pass
        try:
            g.cont(timeout=0.20)
            regs = g.read_regs()
            pc = regs.get("r15", 0) & ~1
            if pc == BP:
                hits += 1
                if hits <= 5:
                    print(f"  ★ 命中 #{hits} @iter{i}: r0=0x{regs.get('r0',0):08X}"
                          f" lr=0x{regs.get('r14',0):08X}", flush=True)
        except GdbError:
            # 超时属正常；注意可能残留 stop reply，读一次 regs 同步
            try:
                regs = g.read_regs()
                pc = regs.get("r15", 0) & ~1
                if pc == BP:
                    hits += 1
                    if hits <= 5:
                        print(f"  ★(T)命中 #{hits} @iter{i}: r0=0x{regs.get('r0',0):08X}", flush=True)
            except GdbError:
                pass
    print(f"\n  总命中 {hits}", flush=True)

    print(f"  mGBA poll={p.poll()}", flush=True)
    g.close()
    p.terminate()
    try:
        p.wait(timeout=5)
    except Exception:
        p.kill()
    fo.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
