import numpy as np
from PIL import Image
g=np.load(r"C:/code/GBA-Rom-Translator/.tmp/an/shot_native.npy").astype(np.uint8)
Z=12
c1=g[24:40, 14:34]
Image.fromarray(np.repeat(np.repeat(c1,Z,axis=0),Z,axis=1)).save(r"C:/code/GBA-Rom-Translator/.tmp/an/z_blob1.png")
c2=g[42:58, 14:34]
Image.fromarray(np.repeat(np.repeat(c2,Z,axis=0),Z,axis=1)).save(r"C:/code/GBA-Rom-Translator/.tmp/an/z_blob2.png")
c3=g[24:40, 70:90]
Image.fromarray(np.repeat(np.repeat(c3,Z,axis=0),Z,axis=1)).save(r"C:/code/GBA-Rom-Translator/.tmp/an/z_blob3.png")
c4=g[24:40, 186:224]
Image.fromarray(np.repeat(np.repeat(c4,Z,axis=0),Z,axis=1)).save(r"C:/code/GBA-Rom-Translator/.tmp/an/z_blob4.png")
print("ok")
