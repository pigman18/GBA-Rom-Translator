#!/usr/bin/env python3
"""量测某一帧里文字行的「字形段宽」，用来验证标点是不是被画宽了。

为什么要它：肉眼只能看出「挤在一起」，说不出具体哪个字宽了多少。
本脚本把一行文字的墨迹切成连续段并给出每段宽度，配合已知的
「一个汉字 12px / 半角 8px」基准，就能直接判定哪一段异常。

用法：
  python scripts/measure_text_row.py <png> --y0 126 --y1 136
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("png")
    ap.add_argument("--y0", type=int, default=126)
    ap.add_argument("--y1", type=int, default=136)
    ap.add_argument("--thr", type=int, default=150)
    a = ap.parse_args()

    p = Path(a.png)
    im = Image.open(p).convert("RGB")
    arr = np.asarray(im).astype(int)
    # 背景色 = 该行里**出现最多的颜色**（对话框内部是大片纯底色）。
    # ⚠ 不能取行尾取样：对话框右侧是红色边框，会把边框当底色，
    #   于是整行文字都被判成「墨迹」，段数恒为 1（踩过）。
    row = arr[a.y0:a.y1]
    flat = row.reshape(-1, 3)
    key = (flat // 8).astype(np.int32)
    k = key[:, 0] * 4096 + key[:, 1] * 64 + key[:, 2]
    vals, counts = np.unique(k, return_counts=True)
    mode = vals[counts.argmax()]
    bg = flat[k == mode].mean(axis=0)

    mask = (np.abs(row - bg).sum(axis=2) > a.thr).any(axis=0)

    segs, s = [], None
    for x in range(arr.shape[1]):
        if mask[x] and s is None:
            s = x
        elif not mask[x] and s is not None:
            segs.append((s, x - 1))
            s = None
    if s is not None:
        segs.append((s, arr.shape[1] - 1))

    print(f"{p.name}  y={a.y0}..{a.y1}  bg={bg.round(1).tolist()}")
    print(f"文字段数={len(segs)}")
    for s, e in segs:
        w = e - s + 1
        note = ""
        if w >= 20:
            note = "  <<< 异常宽（疑似标点被画成全角/叠字）"
        elif w <= 3:
            note = "  <<< 碎片"
        print(f"  x={s:3d}..{e:3d}  w={w:2d}{note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
