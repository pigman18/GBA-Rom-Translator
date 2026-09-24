# -*- coding: utf-8 -*-
"""zoom2.py — 按区域裁剪+放大（6x）用户截图，判读细节。

用法: python .tmp/zoom2.py
"""
from pathlib import Path
from PIL import Image

SRC = Path(r"C:/Users/Administrator/.workbuddy/clipboard-images")
DST = Path(r"C:/code/GBA-Rom-Translator/.tmp")
SCREEN = (1, 55, 241, 215)          # 242x215 里 GBA 屏区 → 240x160

FILES = {
    1: "clipboard-2026-09-21T01-46-00-320Z-91d2f2eb.png",   # 背包(学习装置)
    2: "clipboard-2026-09-21T01-46-00-322Z-eaa130ea.png",   # 背包(PP单项小补剂)
    3: "clipboard-2026-09-21T01-46-00-326Z-fbe29dbc.png",   # 队伍+请选择
    4: "clipboard-2026-09-21T01-46-00-327Z-6adbefb8.png",   # 宝可梦信息
    5: "clipboard-2026-09-21T01-46-00-328Z-81cdf317.png",   # 对战技能
    6: "clipboard-2026-09-21T01-46-00-329Z-4798c951.png",   # 对战技能(选中)
}

# (图号, 名字, 左, 上, 右, 下)   —— 坐标以 240x160 屏区为准
CROPS = [
    (1, "bag_row6",      108, 78, 240, 108),   # 背包第 6 行
    (2, "bag_row6b",     108, 78, 240, 108),
    (1, "bag_desc",        0, 108, 112, 150),
    (3, "party_bottom",    0, 118, 240, 160),  # 「请选择」区
    (4, "sum_topleft",     0,  22,  72,  60),  # LV 行
    (4, "sum_topright",  160,   0, 240,  26),  # 取消+图标
    (4, "sum_right",     100,  22, 240, 150),  # 右面板全
    (5, "sum2_topleft",    0,  22,  72,  60),
    (5, "sum2_topright", 160,   0, 240,  26),
    (5, "sum2_pp",       100,  22, 240, 110),
    (6, "sum3_pp",       100,  22, 240, 110),
    (6, "sum3_bottom",     0, 100, 240, 160),
]


def main():
    for k, name, l, t, r, b in CROPS:
        im = Image.open(SRC / FILES[k]).convert("RGB").crop(SCREEN)
        sc = im.crop((l, t, r, b))
        f = 6 if (r - l) <= 130 else 4
        sc = sc.resize((sc.width * f, sc.height * f), Image.NEAREST)
        out = DST / ("uz%d_%s.png" % (k, name))
        sc.save(out)
        print("uz%d_%s.png %s x%d" % (k, name, (r - l, b - t), f))


if __name__ == "__main__":
    main()
