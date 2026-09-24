"""nav_zoom.py — 放大领航员截图，量化「发虚」到底长什么样。
只做读取+放大+像素统计，不改任何东西。
"""
import sys
from PIL import Image
import numpy as np

SRC = r"C:\Users\Administrator\.workbuddy\clipboard-images\clipboard-2026-09-22T08-09-07-691Z-95ff2422.png"
OUT = r"C:\code\GBA-Rom-Translator\.tmp\an"

im = Image.open(SRC).convert("RGB")
W, H = im.size
print("size =", W, "x", H)

# 找游戏视口：mGBA 240x160 视口，先按整图找「非菜单栏」区域
# 直接裁几个候选块并放大 8 倍
crops = {
    "nav_line1": (30, 78, 210, 128),      # 第 1 行（标题）
    "nav_line2": (30, 128, 210, 232),     # 第 2~3 行
    "nav_top_left": (30, 78, 130, 130),   # 左上角 3~4 字
}
for name, box in crops.items():
    c = im.crop(box)
    c = c.resize((c.width * 6, c.height * 6), Image.NEAREST)
    p = f"{OUT}\\{name}_x6.png"
    c.save(p)
    print("saved", p, c.size)

# 像素统计：游戏文字是蓝色系，统计视口内的颜色直方图（找主色）
arr = np.array(im)
# 视口猜测：y 60..480（含边框），统计出现最多的颜色
flat = arr.reshape(-1, 3)
cols, cnts = np.unique(flat, axis=0, return_counts=True)
order = np.argsort(-cnts)[:12]
print("\n== 全图 Top12 颜色 (R,G,B) : count ==")
for i in order:
    print("  ", tuple(int(v) for v in cols[i]), int(cnts[i]))

# 文字行内的颜色（只在第 2~3 行文字区取）
sub = arr[128:232, 30:210].reshape(-1, 3)
cols2, cnts2 = np.unique(sub, axis=0, return_counts=True)
order2 = np.argsort(-cnts2)[:10]
print("\n== 文字区 Top10 颜色 ==")
for i in order2:
    print("  ", tuple(int(v) for v in cols2[i]), int(cnts2[i]))
