import numpy as np
from PIL import Image
g=np.load(r"C:/code/GBA-Rom-Translator/.tmp/an/shot_native.npy").astype(np.uint8)
R,G,B=g[:,:,0].astype(int),g[:,:,1].astype(int),g[:,:,2].astype(int)
ink=(B>200)&(R<120)
# 二值图：ink 黑，其余白
bw=np.where(ink[:,:,None], np.array([0,0,0],np.uint8), np.array([255,255,255],np.uint8))
Z=8
big=np.repeat(np.repeat(bw,Z,axis=0),Z,axis=1)
Image.fromarray(big[20*Z:58*Z, 12*Z:132*Z]).save(r"C:/code/GBA-Rom-Translator/.tmp/an/shot_row1_bw.png")
Image.fromarray(big[36*Z:74*Z, 12*Z:132*Z]).save(r"C:/code/GBA-Rom-Translator/.tmp/an/shot_row2_bw.png")
# 带网格
crop=bw[20:58, 12:132].copy()
Z2=8
big2=np.repeat(np.repeat(crop,Z2,axis=0),Z2,axis=1)
for x in range(16,132,8):
    px=(x-12)*Z2
    if 0<=px<big2.shape[1]: big2[:,px]=[255,0,0]
for y in range(24,58,16):
    py=(y-20)*Z2
    if 0<=py<big2.shape[0]: big2[py,:]=[0,160,0]
Image.fromarray(big2).save(r"C:/code/GBA-Rom-Translator/.tmp/an/shot_row1_grid.png")
print("ok")
