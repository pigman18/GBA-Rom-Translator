import numpy as np
from PIL import Image
im = Image.open(r"C:/Users/Administrator/.workbuddy/clipboard-images/clipboard-2026-09-22T08-09-07-691Z-95ff2422.png").convert("RGB")
a=np.array(im); oy,ox,sc=51,1,3
g=a[np.ix_(oy+np.arange(160)*sc, ox+np.arange(240)*sc)].astype(np.uint8)
np.save(r"C:/code/GBA-Rom-Translator/.tmp/an/nav_game_exact.npy", g)
big=np.repeat(np.repeat(g,4,axis=0),4,axis=1)
Image.fromarray(big).save(r"C:/code/GBA-Rom-Translator/.tmp/an/nav_frame4x_exact.png")
# 只保留「纯蓝 ink」的二值图，排除重采样干扰
ink=np.all(g==[33,132,255],axis=2)
bw=np.where(ink[:,:,None], np.array([0,0,0],np.uint8), np.array([255,255,255],np.uint8))
bw=np.repeat(np.repeat(bw,6,axis=0),6,axis=1)
Image.fromarray(bw[18*6:60*6, 8*6:80*6]).save(r"C:/code/GBA-Rom-Translator/.tmp/an/nav_ink_bw.png")
print("ok", big.shape)
