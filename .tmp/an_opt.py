# -*- coding: utf-8 -*-
"""分析实测 dump：UI 号 vs 文字号，以及它们占用的 tilemap 格。
关键问题 Q1: 设置页 UI 边框号 512..520 占据哪些格？是否 == 32-stride 绝对格号？
        Q2: 文字块 (a4,a5) 与 UI 格是否重叠？
        Q3: 若文字改用 32-stride 绝对格号，号域是什么？与 UI 号域是否重叠？
"""
import struct, collections, os, re, glob

ROOT = r'C:/code/GBA-Rom-Translator'
VB = 0x06000000
EB = 0x02000000


def rd(p):
    p = os.path.join(ROOT, p)
    return open(p, 'rb').read() if os.path.exists(p) else None


print('=== .tmp 下 dump 文件 ===')
for f in sorted(glob.glob(os.path.join(ROOT, '.tmp', 'drive_*'))):
    print('  %-42s %d bytes' % (os.path.basename(f), os.path.getsize(f)))


def gentries(vram, base, rows=32, cols=32):
    o = base - VB
    ent = []
    for r in range(rows):
        for c in range(cols):
            w = struct.unpack_from('<H', vram, o + (r * cols + c) * 2)[0]
            n = w & 0x3FF
            if n:
                ent.append((r, c, n, w))
    return ent


def report(vram, base, label):
    ent = gentries(vram, base)
    print('\n=== %s  BG map @0x%08X : %d 非零格 ===' % (label, base, len(ent)))
    by = collections.defaultdict(list)
    for r, c, n, w in ent:
        by[n].append((r, c))
    los = sorted(n for n in by if n < 480)
    his = sorted(n for n in by if n >= 480)
    print('  低号(<480) %d 种: %s' % (len(los), los[:40]))
    for n in los[:40]:
        print('    号 %3d (x%-2d): %s' % (n, len(by[n]), ' '.join('(%d,%d)' % p for p in by[n][:26])))
    print('  高号(>=480) %d 种: %s' % (len(his), his[:40]))
    for n in his[:40]:
        print('    号 %3d (x%-2d): %s' % (n, len(by[n]), ' '.join('(%d,%d)' % p for p in by[n][:26])))
    return by


# ---- 设置页 ----
vram = rd('.tmp/drive_opt_vram.bin')
if vram:
    report(vram, 0x06007800, '设置页 BG0 (screenBase15)')
    # 采样 a4/a5 -> map 查号
    s = rd('.tmp/itp_out.txt')
    if s:
        pairs = []
        for ln in s.decode('utf-8', 'replace').split('\n'):
            m = re.search(r'a4=(\d+)\s+a5=(\d+)', ln)
            if m:
                pairs.append((int(m.group(1)), int(m.group(2))))
        uniq = sorted(set(pairs))
        print('\n=== 采样 a4/a5 唯一对 (%d 个) ===' % len(uniq))
        print(uniq)
        o = 0x06007800 - VB
        print('\n=== 这些格在设置页 map 里的号（a5=行, a4=列）===')
        for a4, a5 in uniq:
            if 0 <= a5 < 32 and 0 <= a4 < 32:
                w = struct.unpack_from('<H', vram, o + (a5 * 32 + a4) * 2)[0]
                print('  (行%2d,列%2d) -> 号 %4d (raw 0x%04X)' % (a5, a4, w & 0x3FF, w))

# ---- START 菜单 ----
vram2 = rd('.tmp/drive_dbg1_vram.bin')
if vram2:
    report(vram2, 0x0600F800, 'START 菜单 BG0 (screenBase31)')
    report(vram2, 0x06007800, 'START 菜单 同屏 BG0 screenBase15')

# ---- 领航员 ----
vram3 = rd('.tmp/drive_nav_vram.bin')
if vram3:
    for b in (0x0600F800, 0x0600D800, 0x0600E000, 0x06007800):
        report(vram3, b, '领航员 BG')

# ---- win 周边 ----
ew = rd('.tmp/drive_opt_ewram.bin')
if ew:
    w = 0x0202E658
    o = w - EB
    print('\n=== 设置页 win @0x%08X 周边 (off 0x%X) ===' % (w, o))
    st = max(0, o - 0x40)
    for i in range(st, min(len(ew), o + 0x90), 16):
        ch = ew[i:i + 16]
        print('  %08x  %s  |%s|' % (EB + i, ' '.join('%02x' % c for c in ch),
                                    ''.join(chr(c) if 32 <= c < 127 else '.' for c in ch)))
    print('\n  win 字段值:')
    for off in (0x00, 0x02, 0x04, 0x06, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F,
                0x10, 0x14, 0x16, 0x18, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F, 0x20, 0x22, 0x24,
                0x26, 0x28, 0x2A, 0x2C, 0x2E):
        b1 = ew[o + off]
        b2 = ew[o + off + 1] if o + off + 1 < len(ew) else 0
        print('    win[0x%02X] = 0x%02X%02X (u16=%d)' % (off, b2, b1, b1 | (b2 << 8)))
