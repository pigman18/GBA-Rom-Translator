# -*- coding: utf-8 -*-
from PIL import Image
from pathlib import Path
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
SC = (1, 55, 241, 215)
tags = ["t_bag", "t_party", "t_sum", "t_sum2"]
K = 2
cw, ch = 240*K, 160*K
cv = Image.new("RGB", (cw*2, ch*2), (25,25,25))
for i, tg in enumerate(tags):
    im = Image.open(T / ("emu_%s_final.png" % tg)).convert("RGB").crop(SC)
    cv.paste(im.resize((cw, ch), Image.NEAREST), ((i%2)*cw, (i//2)*ch))
cv.save(T / "chk_v24.png")
print("chk_v24.png", cv.size, "左上=背包 右上=队伍 左下=详情 右下=技能")
