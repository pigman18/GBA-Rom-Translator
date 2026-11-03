#!/usr/bin/env python3
"""从备份取回 BODY_COUNTER_LEFT 并插回 gen_scenes.py。

背景：_patch_interior_talk.py 用「BODY_INTERIOR 起、BODIES 止」替换，
而 BODY_COUNTER_LEFT 恰好在这两者之间（在备份里它在 BODY_INTERIOR 之后），
于是被一起删掉了。本脚本把它补回去。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "scripts" / "gen_scenes.py"
BAK = ROOT / "scripts" / "gen_scenes.py.bak"


def main() -> int:
    s = GEN.read_text(encoding="utf-8")
    # 注意：BODIES 里会引用 BODY_COUNTER_LEFT，所以不能只判断字符串是否存在，
    # 要判断**定义行**是否存在（实测踩过：只判断字符串导致误以为已存在）。
    if "BODY_COUNTER_LEFT = '''" in s:
        print("[skip] BODY_COUNTER_LEFT 定义已存在")
        return 0
    if not BAK.is_file():
        print("[ERR] 没有备份 gen_scenes.py.bak")
        return 1
    bak = BAK.read_text(encoding="utf-8")
    a = bak.index("BODY_COUNTER_LEFT = '''")
    b = bak.index("BODIES = {")
    block = bak[a:b]

    # 插到 BODIES = { 之前
    i = s.index("BODIES = {")
    s = s[:i] + block + s[i:]
    GEN.write_text(s, encoding="utf-8")
    print(f"[OK] 补回 BODY_COUNTER_LEFT（{len(block)} 字节）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
