#!/usr/bin/env python3
"""检查 interior plan 锚点是否唯一（防止补丁打到 gym 模板上）。"""
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "scripts" / "gen_scenes.py"


def main() -> int:
    s = P.read_text(encoding="utf-8")
    anchor = 'local dirs = {{ "UP", "LEFT", "RIGHT", "DOWN" }}\nlocal plan = {{'
    n = s.count(anchor)
    print(f"锚点出现次数: {n}")
    i = s.find(anchor)
    while i >= 0:
        # 找它属于哪个 BODY
        head = s.rfind("BODY_", 0, i)
        name = s[head:head + 40].split("=")[0].strip()
        print(f"  位置 {i}，属于 {name}")
        i = s.find(anchor, i + 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
