#!/usr/bin/env python3
"""把 gamecorner 的落点回退到 (8,10)（已验证可走动的位置）。

背景：实测 (8,10) 虽然 talk 打不到 NPC，但角色能走动、能产出帧；
(10,12) 会直接卡死（37 帧、全无对话）。两害相权取能动的那个，
NPC 位置留给后续单独调。
"""
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "scripts" / "gen_scenes.py"


def main() -> int:
    s = P.read_text(encoding="utf-8")
    old = '"gamecorner_mauville": ("10:3", 10, 12, "Mauville 游戏厅", "counter"),'
    new = '"gamecorner_mauville": ("10:3", 8, 10, "Mauville 游戏厅", "counter"),'
    if old not in s:
        if new in s:
            print("[skip] 已经是 (8,10)")
            return 0
        print("[ERR] 找不到 gamecorner 定义")
        return 1
    P.write_text(s.replace(old, new), encoding="utf-8")
    print("[OK] gamecorner 落点回退到 (8,10)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
