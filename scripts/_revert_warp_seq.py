#!/usr/bin/env python3
"""把 warp 按键序列回退到「已验证成功」的那一版。

背景：验证过 `[WARP] hit ... OK 完全命中` 的那版序列是
  START → UP×8 → DOWN → A → DOWN×mon → A → A
之后我为了「重复调用」加了 B 清场和额外 UP，结果**两次都 TIMEOUT**，
比原版更差。所以回退到已验证版本，把「重复调用」记为已知限制。

用法：python scripts/_revert_warp_seq.py
"""
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "bot" / "bot.lua"

NEW = '''    tap("START", 4, 60)
    for _ = 1, 8 do tap("UP", 4, 6) end
    tap("DOWN", 4, 12)
    tap("A", 4, 80)
    for _ = 1, mon do tap("DOWN", 4, 22) end
    tap("A", 4, 70)
    tap("A", 4, 40)
'''


def main() -> int:
    s = P.read_text(encoding="utf-8")
    try:
        a = s.index("    tap(\"START\", 4, 60)")
    except ValueError:
        print("[ERR] 找不到序列起点")
        return 1
    end_marker = "    return seq\nend"
    try:
        b = s.index(end_marker, a)
    except ValueError:
        print("[ERR] 找不到序列终点")
        return 1
    print(f"替换 {a}..{b}")
    print("  原首行:", s[a:a+60].splitlines()[0])
    P.write_text(s[:a] + NEW + s[b:], encoding="utf-8")
    print("[OK] 已回退")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
