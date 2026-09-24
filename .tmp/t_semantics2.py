#!/usr/bin/env python3
"""实验2：验证按键注入真的生效 + 断点命中。

思路：
  1. 起 mGBA，连上
  2. 长 cont 让游戏跑到主循环（标题画面）
  3. 读 KEYINPUT + 检查画面（读 VRAM 是否有像素）
  4. 注入 START，跑几秒，看是否进入游戏（pc 分布变化 / KEYINPUT 读回）
  5. 全程挂 3 个断点统计命中
"""
import collections
import os
import subprocess
import sys
import time

ROOT = r"C:\code\GBA-Rom-Translator"
sys.path.insert(0, os.path.join(ROOT, "src", "util"))
from debug_patcher import GdbClient, GdbError  # noqa: E402

EXE = os.path.join(ROOT, "tools", "mGBA-0.10.5-win32", "mGBA.exe")
ROM = os.path.join(ROOT, "roms", "outputs", "POKEMON_RUBY_AXVJ00_translated.gba")

BREAKS = {
    0x08003630: "DrawGlyphTiles",
    0x08003708: "GetCursorTileNum",
    0x08003730: "GetGlyphTilePointers",
}

KEYIN = 0x04000130


def run(sec: float, g, keys=None):
    """跑 sec 秒（0.2s 步进），可选持续注入按键。返回 pc 采样列表。"""
    if keys is not None:
        v = 0x03FF
        for k in keys:
            v &= ~k
        try:
            g.cmd(f"M{KEYIN:x},2,{v:04x}".replace("m", "M").replace("M", "M", 1))
        except GdbError:
            pass
    pcs = []
    end = time.time() + sec
    while time.time() < end:
        try:
            g.cont(timeout=0.2)
        except GdbError:
            pass
        try:
            regs = g.read_regs()
            pcs.append(regs.get("r15", 0) & ~1)
        except GdbError:
            pass
    return pcs


def main() -> int:
    fo = open(os.path.join(ROOT, ".tmp", "t_sem2.out"), "wb")
    p = subprocess.Popen([EXE, "-g", ROM], cwd=ROOT,
                         stdin=subprocess.DEVNULL, stdout=fo, stderr=fo)
    print(f"mGBA pid={p.pid}", flush=True)
    time.sleep(4)

    g = GdbClient("127.0.0.1", 2345, timeout=6.0)
    g.connect()

    print(f"\n初始 KEYINPUT = {g.read_mem(KEYIN,2).hex()}", flush=True)
    print("初始 VRAM 0x06000000 前 32B:", g.read_mem(0x06000000, 32).hex(), flush=True)
    print("初始 DISPCNT =", g.read_mem(0x04000000,2).hex(), flush=True)

    # 挂断点
    for a in BREAKS:
        try:
            g.set_sw_break(a)
            print(f"  断点 OK 0x{a:08X} {BREAKS[a]}", flush=True)
        except GdbError as e:
            print(f"  断点失败 0x{a:08X}: {e}", flush=True)

    hits = collections.Counter()
    print("\n=== 阶段1：裸跑 6s（到标题）===", flush=True)
    pcs = run(6.0, g, keys=None)
    c = collections.Counter(f"0x{x:08X}" for x in pcs if x)
    print("  pc top5:", c.most_common(5), flush=True)
    print("  KEYINPUT =", g.read_mem(KEYIN,2).hex(), flush=True)
    print("  DISPCNT =", g.read_mem(0x04000000,2).hex(), flush=True)

    print("\n=== 阶段2：连按 START 8s ===", flush=True)
    pcs = run(8.0, g, keys=[0x0008])
    c = collections.Counter(f"0x{x:08X}" for x in pcs if x)
    print("  pc top5:", c.most_common(5), flush=True)
    print("  KEYINPUT =", g.read_mem(KEYIN,2).hex(), flush=True)

    print("\n=== 阶段3：连按 A 6s ===", flush=True)
    pcs = run(6.0, g, keys=[0x0001])
    c = collections.Counter(f"0x{x:08X}" for x in pcs if x)
    print("  pc top5:", c.most_common(5), flush=True)
    print("  DISPCNT =", g.read_mem(0x04000000,2).hex(), flush=True)
    print("  OAM 0x07000000 前16B:", g.read_mem(0x07000000,16).hex(), flush=True)

    print("\n=== 阶段4：按住 DOWN + A 交替 8s ===", flush=True)
    pcs = run(8.0, g, keys=[0x0080])
    c = collections.Counter(f"0x{x:08X}" for x in pcs if x)
    print("  pc top5:", c.most_common(5), flush=True)

    g.close()
    p.terminate()
    try:
        p.wait(timeout=5)
    except Exception:
        p.kill()
    fo.close()
    print("\n完成", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
