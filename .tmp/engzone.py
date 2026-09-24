# -*- coding: utf-8 -*-
"""用**原盘**采样（drive_o_*_vram.bin）测「引擎字模区」的实际占用范围。

原盘没有我们的中文 ⇒ 文本层 charBlock 里非零的砖 = 引擎自己写的（字模预取 + 图标）。

对每个被 BG 层使用的 charBlock（从 io.bin 读 BGxCNT 的 charBase），
统计非零砖的号分布，给出 min / max / 非零数 / 连续段。
"""
import glob, os, struct, sys

IO_BASE = 0x04000000
VR_BASE = 0x06000000


def bg_charbases(io):
    out = []
    for b in range(4):
        c = struct.unpack_from("<H", io, 0x08 + 2 * b)[0]
        out.append((c >> 2) & 3)
    return out


def main():
    pat = sys.argv[1] if len(sys.argv) > 1 else "o_"
    tags = []
    for p in sorted(glob.glob(".tmp/drive_%s*_vram.bin" % pat)):
        t = os.path.basename(p)[6:-9]
        if os.path.exists(".tmp/drive_%s_io.bin" % t):
            tags.append(t)
    for t in tags:
        io = open(".tmp/drive_%s_io.bin" % t, "rb").read()
        vr = open(".tmp/drive_%s_vram.bin" % t, "rb").read()
        cbs = sorted(set(bg_charbases(io)))
        print("===== %s   BG charBase=%s" % (t, cbs))
        for cb in cbs:
            base = 0x06000000 + cb * 0x4000
            if base + 0x4000 > 0x06000000 + len(vr):
                print("   cb%d 超出 dump 范围" % cb)
                continue
            o = base - VR_BASE
            nz = []
            for n in range(512):
                tile = vr[o + n * 32: o + n * 32 + 32]
                if any(tile):
                    nz.append(n)
            if not nz:
                print("   cb%d  全空" % cb)
                continue
            # 连续段
            segs = []
            s = nz[0]
            p = nz[0]
            for x in nz[1:]:
                if x == p + 1:
                    p = x
                    continue
                segs.append((s, p))
                s = p = x
            segs.append((s, p))
            print("   cb%d  非零 %3d 号，范围 [%d, %d]，号段: %s"
                  % (cb, len(nz), nz[0], nz[-1],
                     " ".join("[%d-%d]" % s for s in segs if s[1] - s[0] >= 0)))


main()
