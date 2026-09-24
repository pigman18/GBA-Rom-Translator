import numpy as np
B=np.load('.tmp/zoom3/one_x.npy')
blk=(B[:,:,0]<40)&(B[:,:,1]<40)&(B[:,:,2]<40)
# 找出这些黑带的“格顶行”：墨迹 11 行 → 若库行 2..12，则格顶=墨顶-2
def cell(y0,x0,title):
    print("---",title,f"格顶y={y0} x={x0}")
    for r in range(16):
        y=y0+r
        if y>=160: break
        row="".join("#" if blk[y,x0+c] else "." for c in range(8))
        print(f"r{r:2d} y{y:3d} {row}")
# 黑带1 y10..20 → 格顶 y=8
cell(8,16,"带1-字0")
cell(8,24,"带1-字1")
cell(8,32,"带1-字2")
cell(8,40,"带1-字3")
