#!/usr/bin/env python3
"""按已验证的日版布局，列出任意地图上的**可交互对象**（带 script 的）。

═══════════════════════════════════════════════════════════════════════════
【已实证的日版 ObjectEventTemplate 布局】（2026-11-03）
    SaveBlock1 + 0x0C0C 起，每项 0x18 字节：
        +0x00  s16 x        （上一版扫出来的 coord 偏移）
        +0x02  s16 y
        +0x04  u8  ...
        +0x0C  u32 script   ← 指向 ROM 事件脚本
    ⚠ 与 pokeruby 注释的 `/*0xC20*/ templates[64]` 不同（差 0x14），
      也与 `sizeof=0x18` 的字段顺序不同。**日版就是这样，别再照抄美版。**

【为什么可信】
    商店（map=10:7）解出 3 个 script 指针，读 ROM 得到标准 GBA 脚本：
      0f 00 ae 26 16 08 09 02 02      ← loadword + callstd + end
    这是真脚本，不是随机数据。

【用法】需要一份**已经在那张地图上**的存档。
  · 想查道馆，就得先用 bot 跳到道馆并保存 ram.bin
  · 本脚本也支持直接读 bot 的 ram.bin（更准，因为 template 是运行时载入的）

  python scripts/list_interactables.py --ram <run_dir> <帧名>
  python scripts/list_interactables.py --sav <路径>
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot" / "tools"))
from savedit import rebuild, SB1_OFF  # noqa: E402

EWRAM_BASE, EWRAM_LEN = 0x02000000, 0x40000
IWRAM_BASE = 0x03000000
SB1_DELTA = 0x890
TPL_BASE = 0x0C0C
TPL_STEP = 0x18
F_X, F_Y, F_SCRIPT = 0x00, 0x02, 0x0C


def s16(b, o): return int.from_bytes(b[o:o + 2], "little", signed=True)
def u32(b, o): return int.from_bytes(b[o:o + 4], "little")


def scan(sb1: bytes, label: str) -> int:
    print(f"\n=== {label} ===")
    print(f"  map={sb1[4]}:{sb1[5]}  pos=({s16(sb1,0)},{s16(sb1,2)})")
    px, py = s16(sb1, 0), s16(sb1, 2)
    hits = []
    for i in range(64):
        o = TPL_BASE + i * TPL_STEP
        if o + TPL_STEP > len(sb1):
            break
        x, y = s16(sb1, o + F_X), s16(sb1, o + F_Y)
        sp = u32(sb1, o + F_SCRIPT)
        if not (0x08000000 <= sp < 0x0A000000):
            continue
        if not (0 <= x <= 120 and 0 <= y <= 120):
            continue
        hits.append((i, x, y, sp))
    print(f"  带 script 的可交互对象：{len(hits)} 个")
    for i, x, y, sp in hits:
        d = abs(x - px) + abs(y - py)
        print(f"    [{i:>2}] ({x:>3},{y:>3})  script=0x{sp:08X}  距玩家 {d} 格")
    if hits:
        print("\n  建议：选离玩家最近的那个，warp 到它的**相邻格**再朝它按 A：")
        for i, x, y, sp in sorted(hits, key=lambda t: abs(t[1]-px)+abs(t[2]-py))[:6]:
            print(f"    api.warp{{ map = \"<g:n>\", x = {x}, y = {y+1} }}  "
                  f"-- 朝 UP 对 [{i}] ({x},{y})")
    return len(hits)


def from_ram(run: Path, key: str | None) -> int:
    side = run / "translated"
    if not side.is_dir():
        side = run / "origin"
    num, label = None, "?"
    if key:
        for line in (side / "index.csv").read_text(encoding="utf-8", errors="replace").splitlines():
            p = line.split(",")
            if len(p) >= 4 and (p[2] == key or p[0] == key):
                num, label = p[3].replace(".png", ""), p[2]
                break
    if num is None:
        for f in sorted(side.glob("*.ram.bin")):
            num, label = f.name.replace(".ram.bin", ""), f.stem
            break
    f = side / f"{num}.ram.bin"
    if not f.is_file():
        print(f"[ERR] 没有 {f}")
        return 0
    data = f.read_bytes()

    sb1addr = None
    for sd in ("translated", "origin"):
        log = run / sd / "scene.log"
        if log.is_file():
            m = re.search(r"sb1=0x([0-9A-Fa-f]{8})",
                          log.read_text(encoding="utf-8", errors="replace"))
            if m:
                sb1addr = int(m.group(1), 16)
                break
    if sb1addr is None:
        print("[ERR] scene.log 里没有 sb1 地址")
        return 0
    o = sb1addr - EWRAM_BASE
    if sb1addr >= IWRAM_BASE:
        o = EWRAM_LEN + (sb1addr - IWRAM_BASE)
    return scan(data[o:o + 0x3AC0], f"ram 帧 {num} ({label})")


def from_sav(path: Path) -> int:
    logical, _ = rebuild(path.read_bytes())
    return scan(logical[SB1_OFF:SB1_OFF + 0x3AC0], path.name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ram", help="bot run 目录")
    ap.add_argument("--frame", default=None)
    ap.add_argument("--sav", default=None)
    a = ap.parse_args()
    if a.ram:
        return 0 if from_ram(Path(a.ram), a.frame) >= 0 else 1
    if a.sav:
        return 0 if from_sav(Path(a.sav)) >= 0 else 1
    # 默认扫 teleport.sav
    from_sav(ROOT / "work" / "_probe" / "teleport.sav")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
