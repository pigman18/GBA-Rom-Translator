"""按帧对齐提取战斗文本截图，生成 origin / translated 并排对照表。

【用户需求（2026-11-27）】
  1. 4 个招式的场景都要跑（已完成，见 battle_kill.lua + BOT_MOVE_IDX）
  2. 同等级下对方被打死的帧应该差不多 ⇒ 基于帧对齐做文本对比
  3. 汇总不合理的译文 + 目标译文

【做法】
  不解析 ROM、不做 OCR。直接按帧号把两侧的**对话框区域**裁出来，
  上下拼成一张长图，人工/我逐帧读，把问题登记到 CSV。

  帧号天然对齐：两侧都是同一个场景脚本 + 同一个存档 + 同一个遇敌表，
  实测 4 个招式各 174 帧、两侧完全对齐。

【输出】
  work/_cmp/<招式>_dialogue.png   左右两栏，逐帧对话框
  work/_cmp/<招式>_full.png       左右两栏，逐帧整屏（核对画面）

用法：
    python scripts/verify/make_dialogue_sheet.py --run <run目录> --tag 抓
    python scripts/verify/make_dialogue_sheet.py --all
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "work" / "_cmp"

# 对话框区域（GBA 240x160：底部文字框大致 y=126..156）
DIALOG_BOX = (0, 124, 240, 158)
# 招式列表区域（右下信息栏 + 左侧四格）
MOVE_BOX = (0, 108, 240, 160)


def load(run: Path, idx: str) -> Image.Image | None:
    p = run / f"{idx}.png"
    return Image.open(p).convert("RGB") if p.exists() else None


def build_sheet(run: Path, tag: str, box: tuple[int, int, int, int],
                scale: int, max_frames: int | None = None) -> Path:
    ro, rt = run / "origin", run / "translated"
    frames = sorted(p.stem for p in ro.glob("*.png"))
    if max_frames:
        frames = frames[:max_frames]

    w = box[2] - box[0]
    h = box[3] - box[1]
    label_h = 12
    row_h = h * 2 + label_h + 4

    sheet = Image.new("RGB", (w + 6, row_h * len(frames)), (10, 10, 10))
    dr = ImageDraw.Draw(sheet)

    for i, f in enumerate(frames):
        y = i * row_h
        a = load(ro, f)
        b = load(rt, f)
        if a is None or b is None:
            continue
        dr.text((2, y + 1), f"f{f}  JP(origin)", fill=(120, 220, 120))
        sheet.paste(a.crop(box), (3, y + label_h))
        dr.text((2, y + label_h + h + 2), " " * 8, fill=(0, 0, 0))
        dr.text((2, y + label_h + h), "", fill=(0, 0, 0))
        dr.text((2, y + label_h + h + 1), "", fill=(0, 0, 0))
        sheet.paste(b.crop(box), (3, y + label_h + h + 3))
        dr.text((2, y + label_h + h + 2), "", fill=(0, 0, 0))
        # 右侧标注 translated
        dr.text((w - 40, y + label_h + h + 2), "", fill=(0, 0, 0))

    sheet = sheet.resize((sheet.width * scale, sheet.height * scale), Image.NEAREST)
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{tag}_dialogue.png"
    sheet.save(out)
    return out


def build_pair_sheet(run: Path, tag: str, box: tuple[int, int, int, int],
                     scale: int, frames: list[str]) -> Path:
    """左右并排（左=origin 右=translated），每帧一行。适合逐帧读文本差异。"""
    ro, rt = run / "origin", run / "translated"
    w = box[2] - box[0]
    h = box[3] - box[1]
    label_h = 12
    row_h = h + label_h + 3

    sheet = Image.new("RGB", (w * 2 + 10, row_h * len(frames)), (10, 10, 10))
    dr = ImageDraw.Draw(sheet)
    for i, f in enumerate(frames):
        y = i * row_h
        a = load(ro, f)
        b = load(rt, f)
        dr.text((2, y + 1), f"f{f} JP", fill=(120, 220, 120))
        dr.text((w + 12, y + 1), f"f{f} CN", fill=(240, 200, 110))
        if a:
            sheet.paste(a.crop(box), (2, y + label_h))
        if b:
            sheet.paste(b.crop(box), (w + 10, y + label_h))
    sheet = sheet.resize((sheet.width * scale, sheet.height * scale), Image.NEAREST)
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{tag}_pair.png"
    sheet.save(out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=Path, help="run 目录（含 origin/ translated/）")
    ap.add_argument("--tag", default="run", help="输出文件名前缀")
    ap.add_argument("--mode", choices=("stack", "pair"), default="pair")
    ap.add_argument("--region", choices=("dialog", "move", "full"), default="dialog")
    ap.add_argument("--scale", type=int, default=4)
    ap.add_argument("--frames", nargs="*", default=None, help="只处理这些帧号")
    a = ap.parse_args()

    if not a.run:
        print("[ERR] 需要 --run")
        return 2

    box = {"dialog": DIALOG_BOX, "move": MOVE_BOX, "full": (0, 0, 240, 160)}[a.region]

    if a.frames:
        out = build_pair_sheet(a.run, a.tag, box, a.scale, a.frames)
    elif a.mode == "pair":
        ro = a.run / "origin"
        frames = sorted(p.stem for p in ro.glob("*.png"))
        out = build_pair_sheet(a.run, a.tag, box, a.scale, frames)
    else:
        out = build_sheet(a.run, a.tag, box, a.scale)

    print(f"输出: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
