"""把采集图按批切给子代理逐字读图审核。

产出：
  work/_review/<batch>/<sid>.png   —— 每只一张小图（已裁到名字行并放大）
  work/_review/<batch>/list.txt    —— 该批的 sid + 期望名字

用法：
  python scripts/verify/prep_review_batches.py --size 40
  -> 生成 work/_review/b01 .. b10，交给子代理逐字校对
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

ROOT = Path.cwd()
SWEEP = ROOT / "work/POKEMON_RUBY_AXVJ00/sweep"
INDEX = ROOT / "work/_species_index.json"
OUT = ROOT / "work/_review"

# 裁剪：敌方血条整块（含框线，便于同时看缺口）
CROP = (8, 12, 150, 36)
SCALE = 6


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=40)
    ap.add_argument("--end", type=int, default=386)
    args = ap.parse_args()

    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    rec = json.loads((SWEEP / "index.json").read_text(encoding="utf-8"))

    items = []
    for sid in range(1, args.end + 1):
        k = str(sid)
        if k not in rec:
            continue
        img = Path(rec[k].get("dir", "")) / "translated.png"
        if not img.exists():
            continue
        items.append((sid, idx.get(k, {}).get("zh", "?"), img))

    OUT.mkdir(parents=True, exist_ok=True)
    nb = (len(items) + args.size - 1) // args.size
    for b in range(nb):
        batch = items[b * args.size:(b + 1) * args.size]
        d = OUT / f"b{b + 1:02d}"
        d.mkdir(parents=True, exist_ok=True)
        lines = []
        for sid, zh, img in batch:
            im = Image.open(img).convert("RGB").crop(CROP)
            im = im.resize((im.width * SCALE, im.height * SCALE), Image.NEAREST)
            im.save(d / f"{sid:03d}.png")
            lines.append(f"{sid:03d}.png\tspecies={sid}\t期望={zh}")
        (d / "list.txt").write_text("\n".join(lines), encoding="utf-8")
        print(f"{d.name}: {len(batch)} 张  ({batch[0][0]}..{batch[-1][0]})")

    print(f"\n共 {nb} 批 -> {OUT}")
    print("每批交给一个子代理：逐张读出名字，与 list.txt 的「期望」对比，报出不一致项。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
