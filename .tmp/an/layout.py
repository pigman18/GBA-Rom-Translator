import numpy as np
B=np.load('.tmp/zoom3/one_x.npy')
print("=== 1x 每行主色 ===")
prev=None
for y in range(160):
    row=B[y]
    u,c=np.unique(row.reshape(-1,3),axis=0,return_counts=True)
    o=np.argsort(-c)
    top=[(tuple(int(v) for v in u[i]),int(c[i])) for i in o[:3]]
    key=top[0][0]
    if key!=prev:
        print(f"y{y:3d} {top}")
        prev=key
