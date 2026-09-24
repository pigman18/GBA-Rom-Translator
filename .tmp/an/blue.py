import numpy as np
B=np.load('.tmp/zoom3/one_x.npy')
blu=(B[:,:,2]>150)&(B[:,:,0]<120)&(B[:,:,1]>90)
for (y0,y1,x0,x1,t) in [(24,39,150,230,"蓝带1右段"),(24,39,12,60,"蓝带1左段"),(40,55,12,60,"蓝带2左段"),(40,55,150,230,"蓝带2右段")]:
    print("="*6,t)
    print("    "+"".join(str(x%10) for x in range(x0,x1)))
    for y in range(y0,y1+1):
        print(f"{y:3d} "+"".join("#" if blu[y,x] else "." for x in range(x0,x1)))
