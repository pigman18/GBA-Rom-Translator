# -*- coding: utf-8 -*-
from PIL import Image
from pathlib import Path
C = Path(r"C:/Users/Administrator/.workbuddy/clipboard-images")
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
SC = (1, 55, 241, 215)
ids = {
 "6adb": "clipboard-2026-09-21T01-46-00-327Z-6adbefb8.png",
 "81cd": "clipboard-2026-09-21T01-46-00-328Z-81cdf317.png",
 "4798": "clipboard-2026-09-21T01-46-00-329Z-4798c951.png",
}
for k, v in ids.items():
    im = Image.open(C / v).convert("RGB").crop(SC)
    im.resize((im.width*3, im.height*3), Image.NEAREST).save(T / ("us_%s_3x.png" % k))
    print(k, im.size)
