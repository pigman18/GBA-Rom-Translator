"""用现有 translate.build.json 重新生成 write.plan.json（不重新翻译、不重新提取）。

用法::

    PYTHONPATH=src python scripts/replan.py POKEMON_RUBY_AXVJ00

改完 ``write_plan.py`` 后要验证「计划层」的变化，用这个最快：
它只跑 build_write_plan 一步，几秒出结果，不碰 hook 编译、不碰 ROM 应用。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from meowth.charmap import Charmap
from meowth.config_loader import texts_json_path
from meowth.write_plan import build_write_plan


def main() -> int:
    gid = sys.argv[1] if len(sys.argv) > 1 else "POKEMON_RUBY_AXVJ00"
    work = Path("work") / gid
    rom = Path(f"roms/origin/{gid}.gba").read_bytes()
    build = json.loads((work / "translate.build.json").read_text(encoding="utf-8"))
    entries = [
        e for e in build["entries"]
        if e.get("id") and e.get("address") and e.get("translated")
    ]
    cm = Charmap()
    plan = build_write_plan(
        rom,
        texts_json_path(gid),
        entries,
        encoder=cm.encode,
        game_id=gid,
        out_path=work / "write.plan.json",
    )
    summ = plan.get("summary") or {}
    print(json.dumps(summ, ensure_ascii=False, indent=1))
    for key in ("rows", "tables", "redirects", "skip"):
        print(f"{key}: {len(plan.get(key) or [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
