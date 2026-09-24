import numpy as np
from PIL import Image
g = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\nav3.npy").astype(np.uint8)

def save(y0, y1, x0, x1, f, name):
    sub = g[y0:y1, x0:x1]
    im = Image.fromarray(sub).resize(((x1-x0)*f, (y1-y0)*f), Image.NEAREST)
    p = r"C:\code\GBA-Rom-Translator\.tmp\an\%s" % name
    im.save(p)
    print("saved", p, sub.shape, "->", im.size)

save(22, 40, 8, 136, 7, "z_line1_left.png")
save(38, 56, 8, 136, 7, "z_line2_left.png")
save(22, 56, 180, 232, 7, "z_right.png")
save(0, 20, 0, 120, 7, "z_topbar.png")
