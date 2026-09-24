import numpy as np
B=np.load('.tmp/zoom3/one_x.npy')
blk=(B[:,:,0]<40)&(B[:,:,1]<40)&(B[:,:,2]<40)
blu=(B[:,:,2]>150)&(B[:,:,0]<120)&(B[:,:,1]>90)
def show(y0,y1,x0,x1,title):
    print("="*8,title,f"y{y0}..{y1} x{x0}..{x1}")
    print("    "+"".join(str((x//10)%10) if x%10==0 else " " for x in range(x0,x1)))
    print("    "+"".join(str(x%10) for x in range(x0,x1)))
    for y in range(y0,y1+1):
        print(f"{y:3d} "+"".join("#" if blk[y,x] else "." for x in range(x0,x1)))
show(12,20,14,50,"黑带1(4字)")
show(76,86,14,42,"黑带2(3字)")
show(108,118,14,34,"黑带3(2字)")
