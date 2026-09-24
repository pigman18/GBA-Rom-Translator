#!/usr/bin/env python3
"""生成 A/B 对照拼图：左=旧版(v8分配器) 右=新版(B2借道TILE_BASE)。纯 python PNG 处理。"""
import struct, zlib, os, sys

ROOT = r"C:\code\GBA-Rom-Translator"

def read_png(p):
    b = open(p, 'rb').read()
    i = 8; idat = b''; w = h = ct = None
    while i < len(b):
        ln = struct.unpack('>I', b[i:i+4])[0]; t = b[i+4:i+8]; d = b[i+8:i+8+ln]
        if t == b'IHDR':
            w, h, bd, ct, cm, fm, il = struct.unpack('>IIBBBBB', d)
        elif t == b'IDAT':
            idat += d
        i += 12 + ln
    raw = zlib.decompress(idat)
    stride = w * 3
    out = bytearray(w * h * 3)
    prev = bytearray(stride)
    pos = 0
    for y in range(h):
        ft = raw[pos]; pos += 1
        line = bytearray(raw[pos:pos+stride]); pos += stride
        if ft == 1:
            for x in range(3, stride):
                line[x] = (line[x] + line[x-3]) & 0xFF
        elif ft == 2:
            for x in range(stride):
                line[x] = (line[x] + prev[x]) & 0xFF
        elif ft == 3:
            for x in range(stride):
                a = line[x-3] if x >= 3 else 0
                line[x] = (line[x] + ((a + prev[x]) >> 1)) & 0xFF
        elif ft == 4:
            for x in range(stride):
                a = line[x-3] if x >= 3 else 0
                bb = prev[x]; c = prev[x-3] if x >= 3 else 0
                pa = abs(bb - c); pb = abs(a - c); pc = abs(a + bb - 2*c)
                pr = a if (pa <= pb and pa <= pc) else (bb if pb <= pc else c)
                line[x] = (line[x] + pr) & 0xFF
        out[y*stride:(y+1)*stride] = line
        prev = line
    return w, h, out


def write_png(path, w, h, rgb):
    def ck(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw += rgb[y*stride:(y+1)*stride]
    hdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    open(path, 'wb').write(b"\x89PNG\r\n\x1a\n" + ck(b"IHDR", hdr)
                           + ck(b"IDAT", zlib.compress(bytes(raw))) + ck(b"IEND", b""))


def scale(img, w, h, f):
    ow, oh = w*f, h*f
    out = bytearray(ow*oh*3)
    for y in range(oh):
        sy = y // f
        for x in range(ow):
            sx = x // f
            o = (sy*w + sx) * 3
            d = (y*ow + x) * 3
            out[d:d+3] = img[o:o+3]
    return ow, oh, out


# 有效游戏区：去掉窗口标题栏+菜单栏（上方 23px）
CROP_TOP = 23

def load_game(p):
    w, h, rgb = read_png(p)
    ch = h - CROP_TOP
    out = bytearray(w*ch*3)
    for y in range(ch):
        s = ((y+CROP_TOP)*w)*3
        out[y*w*3:(y+1)*w*3] = rgb[s:s+w*3]
    return w, ch, out


def main():
    pairs = [
        ("设置菜单（内容是否完整）",
         os.path.join(ROOT, ".tmp", "b2_verify_ab", "05_04_dialog_a.png"),
         os.path.join(ROOT, ".tmp", "b2_verify", "05_04_dialog_a.png")),
    ]
    GAP = 8
    F = 2
    tiles = []
    for _, pold, pnew in pairs:
        wo, ho, io = load_game(pold)
        wn, hn, inew = load_game(pnew)
        wo2, ho2, so = scale(io, wo, ho, F)
        wn2, hn2, sn = scale(inew, wn, hn, F)
        tiles.append((wo2, ho2, so, wn2, hn2, sn))

    W = sum(t[0] + t[3] for t in tiles) + GAP * (len(tiles)+1)
    H = max(t[1] for t in tiles) + 2*GAP
    canvas = bytearray([0x20] * (W*H*3))
    x = GAP
    for wo2, ho2, so, wn2, hn2, sn in tiles:
        for y in range(ho2):
            d = ((y+GAP)*W + x)*3
            canvas[d:d+wo2*3] = so[y*wo2*3:(y+1)*wo2*3]
        x += wo2 + GAP
        for y in range(hn2):
            d = ((y+GAP)*W + x)*3
            canvas[d:d+wn2*3] = sn[y*wn2*3:(y+1)*wn2*3]
        x += wn2 + GAP
    out = os.path.join(ROOT, ".tmp", "ab_compare_settings.png")
    write_png(out, W, H, canvas)
    print("saved", out, W, H)


if __name__ == "__main__":
    main()
