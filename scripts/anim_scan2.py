import struct
orig = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()
trans = open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()

# 扫描 0x08150000 - 0x08200000（排除 0x081C 文本区），找成品新增 F9
# 但更精准：找"成品有 F9 且原版无 F9，且周围字节是动画命令流模式"
# 动画命令流：连续的小命令字节 + 指针/偏移

def looks_anim_stream(data, pos):
    """判断 pos 附近是否是动画命令流（含 0x00-0x0F 命令字节和跳转目标）"""
    window = data[max(0,pos-4):pos+8]
    # 命令流特征：含小命令字节，且不是 FF 填充，不是文本 F9 结构
    return True

# 先简单扫：找 0x08150000-0x081BFFFF 和 0x081D0000-0x081FFFFF 的 F9
ranges = [(0x08150000,0x081BFFFF), (0x081D0000,0x081FFFFF)]
for lo, hi in ranges:
    b = lo - 0x08000000
    e = hi - 0x08000000
    hits = []
    for i in range(b, e):
        if trans[i] == 0xF9:
            hits.append(0x08000000 + i)
    # 聚类
    clusters = []
    for h in hits:
        if clusters and h - clusters[-1][-1] <= 8:
            clusters[-1].append(h)
        else:
            clusters.append([h])
    print(f"范围 0x{lo:08X}-0x{hi:08X}: 成品 F9 共 {len(hits)}，聚类 {len(clusters)}")
    for c in clusters[:20]:
        print(f"  0x{c[0]:08X} len={len(c)}")
