# -*- coding: utf-8 -*-
from PIL import Image
from pathlib import Path
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
# 区域: tile 行 3..6, 列 14..22  → px x 112..176, y 24..56
BOX = (112, 24, 176, 56)
K = 6
for tag in ("o_sum2", "t_sum2"):
    im = Image.open(T / ("bgview_%s_bg0.png" % tag)).convert("RGB")
    c = im.crop(BOX)
    c.resize((c.width*K, c.height*K), Image.NEAREST).save(T / ("zz_%s_Lv.png" % tag))
    print(tag, c.size)
# 上下拼接
a = Image.open(T / "zz_o_sum2_Lv.png"); b = Image.open(T / "zz_t_sum2_Lv.png")
cv = Image.new("RGB", (a.width, a.height*2+12), (40,40,40))
cv.paste(a, (0,0)); cv.paste(b, (0, a.height+12))
cv.save(T / "zz_Lv_cmp.png")
print("zz_Lv_cmp.png", cv.size, "上=原盘 下=我们")
