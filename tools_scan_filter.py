"""Parse scan_out.txt by exact fixed column layout -> icon-like candidates."""
import sys

rows = []
for ln in open('scan_out.txt', encoding='utf-16', errors='replace'):
    if len(ln) < 80:
        continue
    try:
        off = int(ln[0:8].strip())
    except ValueError:
        continue
    gba = int(ln[8:19].strip(), 16)
    csize = int(ln[19:27].strip())
    dsize = int(ln[27:36].strip())
    comp = ln[36:46].strip()
    bpp = int(ln[46:50].strip())
    w = int(ln[50:54].strip())
    h = int(ln[54:58].strip())
    cnt = int(ln[58:62].strip())
    pal_s = ln[62:73].strip()
    pal = int(pal_s, 16) if pal_s.startswith('0x') else 0
    rows.append(dict(off=off, gba=gba, dsize=dsize, comp=comp, bpp=bpp,
                     w=w, h=h, cnt=cnt, pal=pal))
print('parsed', len(rows))


def is_map(r):
    return r['w'] == 64 and r['h'] == 64


icon = [r for r in rows if not is_map(r)]
print('non-64x64 map', len(icon))
for r in sorted(icon, key=lambda r: r['off']):
    print('0x{:08X} {}bpp {}x{} x{} d={} pal=0x{:08X}'.format(
        r['gba'], r['bpp'], r['w'], r['h'], r['cnt'], r['dsize'], r['pal']))
