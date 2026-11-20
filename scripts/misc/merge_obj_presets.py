"""把 OBJ 文字条 preset 并进正式配置（文本拼接，保留原有手写格式）

规则：
- 现有 preset 里 `note` 含「OBJ 精灵」的整条删掉（旧 OBJ 结果）；
- 其余（title_banner / title_logo / type_icons / bag_pocket_name / BG 场景图块）
  原样保留；
- 再把 work/obj_presets.yaml 里的新条目接在后面。
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "src" / "util" / "configs" / "POKEMON_RUBY_AXVJ00.yaml"


def split_presets(text: str):
    """把 tiles.presets 段落按 '  - id:' 切开，返回 (前导, [块...], 尾巴)。"""
    m = re.search(r"^\s*presets:\s*$", text, re.M)
    if not m:
        raise SystemExit("找不到 tiles.presets")
    head = text[:m.end()] + "\n"
    rest = text[m.end():]
    # 结束点是下一个顶格的键（texts:/gdb: 等）
    m2 = re.search(r"^\S", rest, re.M)
    body, tail = (rest[:m2.start()], rest[m2.start():]) if m2 else (rest, "")
    starts = [mm.start() for mm in re.finditer(r"^  - id:", body, re.M)]
    blocks = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(body)
        blocks.append(body[s:e])
    return head, blocks, tail


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--obj", default=str(ROOT / "work" / "obj_presets.yaml"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    text = CFG.read_text(encoding="utf-8")
    head, blocks, tail = split_presets(text)

    kept, dropped = [], []
    for b in blocks:
        (dropped if "OBJ 精灵" in b else kept).append(b)
    print(f"保留 {len(kept)} 条，删除旧 OBJ {len(dropped)} 条")

    obj_text = Path(args.obj).read_text(encoding="utf-8")
    _h, obj_blocks, _t = split_presets(obj_text)
    print(f"并入新 OBJ {len(obj_blocks)} 条")

    out = head + "".join(b if b.endswith("\n") else b + "\n" for b in kept + obj_blocks)
    out = out.rstrip("\n") + "\n\n" + tail.lstrip("\n")

    if args.dry_run:
        print(out[:400])
        return 0

    bak = ROOT / "work" / "config_before_obj_merge2.yaml"
    shutil.copy2(CFG, bak)
    CFG.write_text(out, encoding="utf-8")
    print(f"已写入 {CFG}（备份 {bak}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
