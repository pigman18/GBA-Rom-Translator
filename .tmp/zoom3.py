# -*- coding: utf-8 -*-
from PIL import Image
from pathlib import Path
C = Path(r"C:/Users/Administrator/.workbuddy/clipboard-images")
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
SC = (1, 55, 241, 215)   # GBA 屏区
def crop(name):
    im = Image.open(C / name).convert("RGB")
    return im.crop(SC)
def z(im, k):
    return im.resize((im.width * k, im.height * k), Image.NEAREST)
ids = {
 "91d2": "clipboard-2026-09-21T01-46-00-320Z-91d2f2eb.png",
 "eaa1": "clipboard-2026-09-21T01-46-00-322Z-eaa130ea.png",
 "fbe2": "clipboard-2026-09-21T01-46-00-326Z-fbe29dbc.png",
 "6adb": "clipboard-2026-09-21T01-46-00-327Z-6adbefb8.png",
 "81cd": "clipboard-2026-09-21T01-46-00-328Z-81cdf317.png",
 "4798": "clipboard-2026-09-21T01-46-00-329Z-4798c951.png",
}
imgs = {k: crop(v) for k, v in ids.items()}
# 拼 2x2：4=信息页LV, 5=对战技能PP, 6=选中态, 3=队伍请选择
order = [("6adb", "info-LV"), ("81cd", "battle-PP"), ("4798", "battle-sel"), ("fbe2", "party")]
K = 3
cols = 2
cellw, cellh = 240 * K, 160 * K
canvas = Image.new("RGB", (cellw * cols, cellh * 2), (30, 30, 30))
for i, (k, _) in enumerate(order):
    canvas.paste(z(imgs[k], K), ((i % cols) * cellw, (i // cols) * cellh))
canvas.save(T / "chk_sym.png")
print("chk_sym.png", canvas.size)
