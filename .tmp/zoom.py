# -*- coding: utf-8 -*-
"""把用户截图裁到 GBA 屏区并放大，便于逐像素判读。

用法：
    python .tmp/zoom.py                # 全部 6 张，整屏 3x
    python .tmp/zoom.py 1 4            # 只做第 1、4 张
"""
import sys
from pathlib import Path
from PIL import Image

SRC = Path(r"C:/Users/Administrator/.workbuddy/clipboard-images")
DST = Path(r"C:/code/GBA-Rom-Translator/.tmp")

FILES = {
    1: "clipboard-2026-09-21T01-46-00-320Z-91d2f2eb.png",  # 背包(学习装置)
    2: "clipboard-2026-09-21T01-46-00-322Z-eaa130ea.png",  # 背包(PP单项小补剂)
    3: "clipboard-2026-09-21T01-46-00-326Z-fbe29dbc.png",  # 队伍+请选择
    4: "clipboard-2026-09-21T01-46-00-327Z-6adbefb8.png",  # 宝可梦信息
    5: "clipboard-2026-09-21T01-46-00-328Z-81cdf317.png",  # 对战技能
    6: "clipboard-2026-09-21T01-46-00-329Z-4798c951.png",  # 对战技能(选中)
}

# mGBA 窗口 242x215：标题栏 ~22 + 菜单栏 ~19 ⇒ 屏幕 y 从 41 起，高 160
SCREEN = (1, 55, 241, 215)


def grid_auto(im):
    """自动找屏幕区：取非窗口装饰的最大矩形（按黑边/连续行检测）。"""
    return SCREEN


def main(argv):
    want = [int(a) for a in argv[1:]] or sorted(FILES)
    for k in want:
        p = SRC / FILES[k]
        im = Image.open(p).convert("RGB")
        sc = im.crop(SCREEN)
        out = DST / ("uz%d_full.png" % k)
        sc.resize((sc.width * 3, sc.height * 3), Image.NEAREST).save(out)
        print("%d %s %s  ->  %s" % (k, p.name[-14:], sc.size, out.name))


if __name__ == "__main__":
    main(sys.argv)
