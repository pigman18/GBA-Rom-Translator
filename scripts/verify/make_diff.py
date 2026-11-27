"""生成 origin vs translated 的逐帧对比图（含差异高亮）。

用途：眼睛看不出的细小文本差异，靠逐像素 diff 定位；再人工判断是不是问题。

用法：
    python scripts/verify/make_diff.py <run目录>
    python scripts/verify/make_diff.py <run目录> --tags bk_moves bk_r1_cast
    python scripts/verify/make_diff.py <run目录> --all

输出：
    <run目录>/diff/NNN_cmp.png   左 origin | 中 translated | 右 差异高亮
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

W, H = 240, 160
SCALE = 3


def diff_image(a: Image.Image, b: Image.Image) -> tuple[Image.Image, int]:
    """返回(差异图, 差异像素数)。有差异的像素标红，其余压暗。"""
    pa, pb = a.load(), b.load()
    out = Image.new("RGB", (W, H))
    po = out.load()
    n = 0
    for y in range(H):
        for x in range(W):
            if pa[x, y] != pb[x, y]:
                po[x, y] = (255, 40, 40)
                n += 1
            else:
                r, g, bl = pa[x, y]
                # 相同部分压成灰，让红色差异更醒目
                v = (r * 30 + g * 59 + bl * 11) // 100
                po[x, y] = (v // 3, v // 3, v // 3)
    return out, n


def make_pair(ro: Path, rt: Path, out: Path, idx: str) -> tuple[int, int]:
    a = Image.open(ro / f"{idx}.png").convert("RGB")
    b = Image.open(rt / f"{idx}.png").convert("RGB")
    d, n = diff_image(a, b)

    canvas = Image.new("RGB", (W * 3 + 20, H + 22), (18, 18, 18))
    canvas.paste(a, (0, 22))
    canvas.paste(b, (W + 10, 22))
    canvas.paste(d, (W * 2 + 20, 22))
    dr = ImageDraw.Draw(canvas)
    dr.text((4, 4), f"origin  f{idx}", fill=(230, 230, 230))
    dr.text((W + 14, 4), f"translated  f{idx}", fill=(230, 230, 230))
    dr.text((W * 2 + 24, 4), f"diff  {n}px", fill=(255, 120, 120))
    if n:
        dr.text((W * 2 + 24 + 76, 4), "<== DIFF", fill=(255, 60, 60))
    canvas = canvas.resize((canvas.width * SCALE, canvas.height * SCALE),
                           Image.NEAREST)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return n, 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run", type=Path, help="bot 运行目录（含 origin/ 与 translated/）")
    ap.add_argument("--tags", nargs="*", default=None,
                    help="只处理这些 burst 前缀（如 bk_moves bk_r1_cast）")
    ap.add_argument("--all", action="store_true", help="处理全部帧")
    ap.add_argument("--out", type=Path, default=None, help="输出目录")
    a = ap.parse_args()

    ro, rt = a.run / "origin", a.run / "translated"
    if not ro.is_dir() or not rt.is_dir():
        print(f"[ERR] 缺少 origin/ 或 translated/: {a.run}")
        return 2
    out_dir = a.out or (a.run / "diff")

    frames = sorted(p.stem for p in ro.glob("*.png"))
    if not a.all:
        # 默认只处理有差异的帧 + 指定 tags
        keep = []
        for idx in frames:
            if a.tags:
                # burst 命名形如 bk_moves_001，按前缀过滤
                if any(idx.startswith(t) for t in a.tags):
                    keep.append(idx)
            else:
                keep.append(idx)
        frames = keep

    print(f"处理 {len(frames)} 帧 → {out_dir}")
    total_diff = 0
    report = []
    for idx in frames:
        if not (rt / f"{idx}.png").exists():
            continue
        n, _ = make_pair(ro, rt, out_dir / f"{idx}_cmp.png", idx)
        total_diff += n
        report.append((idx, n))

    report.sort(key=lambda x: -x[1])
    print(f"\n差异最大的前 20 帧：")
    for idx, n in report[:20]:
        flag = "  <== " if n > 200 else ""
        print(f"  f{idx:>4}  {n:6d} px{flag}")
    print(f"\n合计差异像素 {total_diff}，输出到 {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
