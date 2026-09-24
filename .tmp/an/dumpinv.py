import glob,os,re,collections
m=collections.defaultdict(set)
for f in glob.glob('.tmp/drive_*.bin'):
    b=os.path.basename(f)[6:-4]
    if '_' not in b: continue
    tag,kind=b.rsplit('_',1)
    m[tag].add(kind)
haveio=[t for t,k in m.items() if 'io' in k]
print("有 io.bin 的 tag (%d):"%len(haveio))
print(sorted(haveio))
print()
print("总 tag 数:",len(m))
