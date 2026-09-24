import numpy as np
from PIL import Image
g=np.load(r"C:/code/GBA-Rom-Translator/.tmp/an/shot_native.npy").astype(np.uint8)
big=np.repeat(np.repeat(g,6,axis=0),6,axis=1)
Image.fromarray(big[0:64*6, 8*6:236*6]).save(r"C:/code/GBA-Rom-Translator/.tmp/an/read_top.png")
Image.fromarray(big[18*6:58*6, 8*6:236*6]).save(r"C:/code/GBA-Rom-Translator/.tmp/an/read_rows.png")
print(big.shape)
