# -*- coding: utf-8 -*-
import re, json

ROOT = r'C:\code\GBA-Rom-Translator'
bdf = open(ROOT + r'\fonts\default\Normal.bdf', 'rb').read().decode('ascii', 'replace')
cm_txt = open(ROOT + r'\work\POKEMON_RUBY_AXVJ00\charmap.txt', 'rb').read().decode('utf-8', 'replace')

CM = {}
for line in cm_txt.splitlines():
    line = line.strip().replace('\r', '')
    if not line or line.startswith('#'):
        continue
    p = line.split('=', 1)
    if len(p) != 2:
        continue
    k, v = p
    try:
        CM[int(k, 16)] = v
    except Exception:
        pass

# 用非贪婪 + 限制长度，避免病态回溯
IDX = {}
for m in re.finditer(r'ENCODING\s+(\d+)\s*\n(?:.*?\n)*?BITMAP\s*\n((?:[0-9A-Fa-f]+\s*\n)+)ENDCHAR', bdf):
    IDX[int(m.group(1))] = [int(l, 16) for l in m.group(2).split()]

print('BDF 解析出字形数:', len(IDX))
print('charmap 槽数:', len(CM))

W, H, X0, Y0 = 11, 11, 0, 2
STRIDE = 16


def pack(rows):
    out = bytearray(STRIDE)
    bit = 0
    for r in range(H):
        y = Y0 + r
        row = rows[y] if 0 <= y < len(rows) else 0
        for c in range(W):
            if (row >> (15 - (X0 + c))) & 1:
                out[bit >> 3] |= 0x80 >> (bit & 7)
            bit += 1
    return list(out)


want = ['\u554a', '\u7684', '\u4e00', '\u4e86']
slot_of = {}
for s, v in CM.items():
    if v in want and v not in slot_of:
        slot_of[v] = s

data = {}
for ch in want:
    rows = IDX.get(ord(ch))
    if rows:
        data[ch] = {'slot': slot_of.get(ch),
                    'bdf': [f'{v:04X}' for v in rows],
                    'rom': pack(rows)}
    else:
        print('MISS', ch, hex(ord(ch)))

out = {'geom': {'W': W, 'H': H, 'X0': X0, 'Y0': Y0, 'stride': STRIDE},
       'cn': data,
       'slots': {ch: (hex(s) if s is not None else None) for ch, s in slot_of.items()}}

open(ROOT + r'\.tmp\b2_data.json', 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=1))
print('saved.')
for ch in want:
    if ch in data:
        print(ch, 'ROM:', ' '.join(f'{b:02X}' for b in data[ch]['rom']))
