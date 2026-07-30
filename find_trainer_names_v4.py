#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v4: Systematic scan for trainer name tables with clean UTF-8 output + hex fallback."""
import struct, sys, json
from pathlib import Path

BASE = 0x08000000

HIRAGANA = (
    "あいうえおかきくけこさしすせそたちつてと"
    "なにぬねのはひふへほまみむめもやゆよらりるれろ"
    "わをんぁぃぅぇぉゃゅょ"
    "がぎぐげござじずぜぞ"
    "だぢづでどばびぶべぼ"
    "ぱぴぷぺぽっ"
)
KATAKANA = (
    "アイウエオカキクケコサシスセソタチツテト"
    "ナニヌネノハヒフヘホマミムメモヤユヨラリルレロ"
    "ワヲンァィゥェォャュョ"
    "ガギグゲゴザジズゼゾ"
    "ダヂヅデドバビブベボ"
    "パピプペポッ"
)

def decode_pcs(raw):
    out = []
    i = 0
    while i < len(raw):
        b = raw[i]
        if b == 0xFF: break
        if b in (0xFA,0xFB,0xFC,0xFD,0xFE): i+=1; continue
        if b in (0xF7,0xF8):
            if i+2<len(raw):
                try: out.append(bytes([raw[i+1],raw[i+2]]).decode('shift_jis')); i+=3; continue
                except: pass
            i+=1; continue
        if 0x01<=b<=0x50:
            idx=b-0x01
            out.append(HIRAGANA[idx] if idx<len(HIRAGANA) else f'[H{b:02X}]')
        elif 0x51<=b<=0xA0:
            idx=b-0x51
            out.append(KATAKANA[idx] if idx<len(KATAKANA) else f'[K{b:02X}]')
        elif 0xA1<=b<=0xAA: out.append(chr(ord('0')+b-0xA1))
        elif b==0xAB: out.append('!')
        elif b==0xAC: out.append('?')
        elif b==0xAD: out.append('.')
        elif b==0xAE: out.append('-')
        elif b==0xB0: out.append('...')
        elif b==0x00: out.append(' ')
        elif 0xBB<=b<=0xD4: out.append(chr(ord('A')+b-0xBB))
        elif 0xD5<=b<=0xEE: out.append(chr(ord('a')+b-0xD5))
        elif 0x81<=b<=0x9F or 0xE0<=b<=0xEF:
            if i+1<len(raw) and 0x40<=raw[i+1]<=0xFC:
                try: out.append(bytes([b,raw[i+1]]).decode('shift_jis')); i+=2; continue
                except: pass
            out.append(f'[{b:02X}]')
        else: out.append(f'[{b:02X}]')
        i+=1
    return ''.join(out)

def encode_name(s):
    out = bytearray()
    for c in s:
        if c in KATAKANA: out.append(0x51 + KATAKANA.index(c))
        elif c in HIRAGANA: out.append(0x01 + HIRAGANA.index(c))
        elif c == '-': out.append(0xAE)
        elif c == ' ': out.append(0x00)
        else:
            try:
                sjis = c.encode('shift_jis')
                if len(sjis)==2: out.extend([0xF7, sjis[0], sjis[1]])
                else: return None
            except: return None
    out.append(0xFF)
    return bytes(out)

# Trainer names for each game
FRLG_TRAINERS = ["タケシ","カスミ","マチス","エリカ","サカキ","カツラ","ナツメ","シゲル","オーキド","カンナ","シバ","ワタル"]
RSE_TRAINERS = ["ダイゴ","ミツル","マツブサ","アオギリ","ユウキ","ハルカ","オダマキ","アスナ","センリ","ナギ","ツツジ","ムロ","トウキ","テッセン","フウ","ラン","ビート","カゲツ","プリム","ユウ","エニシダ","コゴミ","ソウタロウ"]
RSE_CLASSES = ["たくみ","たんパンこぞう","ミニスカート","かいパンやろう","ヤマッパー","さんぽう","おじさん","おばさん","カラテおう","バトルガール","パラソルおねえさん","でんきや","イカサマ","ジムリーダー","れんたい","サイキッカー","かくとう","むしとりしょうねん","とりつかい","あまのじゃく","のうぎょう","チアガール","エリート","ちゅうかじん","アロマなおねえさん","うきわボーイ","マグマだん","アクアだん","オカルトマニア","ビキニのおねえさん","ピンクぬこ","りかけ","まりん","スター","エスパー","ナース","ふなのり","ボーイ","なみのり","オーキド","ふたごちゃん","おつかい","ダイゴ","ミツル","マツブサ","アオギリ"]

def report(report_lines, s):
    report_lines.append(s)

def find_all(rom, pattern):
    res=[]
    pos=0
    while True:
        pos=rom.find(pattern, pos)
        if pos==-1: break
        res.append(pos)
        pos+=1
    return res

def find_ptr_tables(rom, data_offsets_set, stride=4, min_run=5):
    """Find runs of consecutive pointers at given stride pointing to data_offsets_set."""
    # Map each data offset to list of pointer locations
    ptr_counts={} # ptr_location -> list of data offsets it points to
    for d_off in data_offsets_set:
        ptr_bytes=struct.pack('<I', BASE+d_off)
        pos=0
        while True:
            pos=rom.find(ptr_bytes, pos)
            if pos==-1: break
            if pos not in ptr_counts:
                ptr_counts[pos]=[]
            ptr_counts[pos].append(d_off)
            pos+=4
    
    ptr_locs=sorted(ptr_counts.keys())
    
    # Find runs
    tables=[]
    i=0
    while i < len(ptr_locs):
        start=ptr_locs[i]
        run_locs=[start]
        j=i+1
        while j < len(ptr_locs):
            expected=run_locs[-1]+stride
            if ptr_locs[j]==expected:
                run_locs.append(ptr_locs[j])
                j+=1
            elif ptr_locs[j]<expected+stride*4:
                # Maybe gaps - check intervening bytes
                gap_count=(ptr_locs[j]-expected)//stride
                all_valid=True
                for k in range(1,gap_count+1):
                    test_ptr=struct.unpack('<I', rom[expected+(k-1)*stride:expected+(k-1)*stride+4])[0]
                    if not (BASE <= test_ptr < BASE+len(rom)):
                        all_valid=False
                        break
                    doff=test_ptr-BASE
                    if rom[doff]!=0xFF and rom.find(b'\xff',doff)!=-1:
                        pass
                    else:
                        pass  # might still be valid
                if all_valid:
                    run_locs.append(ptr_locs[j])
                    j+=1
                else:
                    break
            else:
                break
        if len(run_locs)>=min_run:
            end=run_locs[-1]+stride
            tables.append((start,end,len(run_locs),stride))
        i=j
    return tables

def scan_rom(rom_path, game_name, search_names, known_frlg_table=None):
    rom = rom_path.read_bytes()
    rom_size = len(rom)
    r = []
    report(r, f"\n{'='*70}")
    report(r, f"ROM: {game_name} ({rom_path.name})  size=0x{rom_size:X}")
    report(r, f"{'='*70}")

    # Step 1: encode names and search
    encoded={}
    for name in search_names:
        pcs=encode_name(name)
        if pcs: encoded[name]=pcs
    
    report(r, "\nSearching for trainer name strings in PCS encoding:")
    all_offsets=set()
    name_info={}
    for name,pcs in encoded.items():
        offs=find_all(rom, pcs)
        if offs:
            name_info[name]=offs
            all_offsets.update(offs)
            report(r, f"  {name}: PCS={pcs.hex()} -> {len(offs)} hits: {','.join(f'0x{o:X}' for o in offs[:3])}{'...' if len(offs)>3 else ''}")
    
    report(r, f"\nTotal unique name string locations: {len(all_offsets)}")

    # If known FRLG table provided, verify it
    if known_frlg_table:
        tbl_off, count = known_frlg_table
        report(r, f"\n--- Known table at 0x{tbl_off:X} ({count} entries) ---")
        ptrs_valid=0
        data_offs=[]
        samples=[]
        for i in range(count):
            off=tbl_off+i*4
            ptr=struct.unpack('<I',rom[off:off+4])[0]
            if BASE<=ptr<BASE+rom_size:
                ptrs_valid+=1
                d_off=ptr-BASE
                data_offs.append(d_off)
                if i<20 or i>=count-5:
                    txt=decode_pcs(rom[d_off:d_off+64])
                    if txt: samples.append((i,d_off,txt))
        
        report(r, f"  Valid pointers: {ptrs_valid}/{count}")
        if ptrs_valid>0:
            data_start=min(data_offs)
            data_end=max(data_offs)
            # Find last string terminator
            last_end=data_end
            for d in data_offs:
                end=rom.find(b'\xff', d)
                if end!=-1 and end>last_end: last_end=end
            report(r, f"  String range: 0x{data_start:X}..0x{last_end+1:X}")
            for idx,d_off,txt in samples[:20]:
                report(r, f"  [{idx:3d}] 0x{d_off:X} = {txt}")
            for idx,d_off,txt in samples[-5:]:
                report(r, f"  [{idx:3d}] 0x{d_off:X} = {txt}")
            return "\n".join(r)

    # Step 2: Find pointer tables pointing to these strings
    report(r, "\nSearching for pointer tables (stride=4, min 10 entries)...")
    tables=find_ptr_tables(rom, all_offsets, stride=4, min_run=10)
    if not tables:
        # Try stride=8
        report(r, "  None found with stride=4. Trying stride=8...")
        tables=find_ptr_tables(rom, all_offsets, stride=8, min_run=5)
    
    if tables:
        tbl_report={}
        for start,end,count,stride in tables:
            data_offs=[]
            for k in range(count):
                ptr=struct.unpack('<I', rom[start+k*stride:start+k*stride+4])[0]
                if BASE<=ptr<BASE+rom_size:
                    data_offs.append(ptr-BASE)
            
            if data_offs:
                data_start=min(data_offs)
                data_end=max(data_offs)
                last_end=data_end
                for d in data_offs:
                    e=rom.find(b'\xff', d)
                    if e!=-1 and e>last_end: last_end=e
                
                report(r, f"\n  Table at 0x{start:X}..0x{end:X}: {count} entries (stride={stride})")
                report(r, f"    String range: 0x{data_start:X}..0x{last_end+1:X}")
                
                for k in range(min(6, count)):
                    ptr=struct.unpack('<I', rom[start+k*stride:start+k*stride+4])[0]
                    d_off=ptr-BASE
                    txt=decode_pcs(rom[d_off:d_off+64])
                    report(r, f"    [{k:3d}] 0x{start+k*stride:X} -> 0x{d_off:X} = {txt}")
                
                if count>6:
                    for k in [count-3, count-2, count-1]:
                        ptr=struct.unpack('<I', rom[start+k*stride:start+k*stride+4])[0]
                        d_off=ptr-BASE
                        txt=decode_pcs(rom[d_off:d_off+64])
                        report(r, f"    [{k:3d}] 0x{start+k*stride:X} -> 0x{d_off:X} = {txt}")
                
                tbl_entry={
                    "table_offset_hex": f"0x{start:X}",
                    "table_end_hex": f"0x{end:X}",
                    "entries": count,
                    "stride": stride,
                    "string_start_hex": f"0x{data_start:X}",
                    "string_end_hex": f"0x{last_end+1:X}",
                }
                tbl_report[f"0x{start:X}"]=tbl_entry
        report(r, f"\nJSON: {json.dumps(tbl_report, ensure_ascii=False, indent=2)}")
    else:
        report(r, "  No pointer tables found.")
    
    # Step 3: Show string clusters as fallback
    sorted_offs=sorted(all_offsets)
    clusters=[]
    if sorted_offs:
        cs=sorted_offs[0]
        prev=sorted_offs[0]
        cc=1
        for o in sorted_offs[1:]:
            if o-prev<=2:
                prev=o
                continue
            if o-prev<64:
                cc+=1
                prev=o
            else:
                if cc>=5:
                    clusters.append((cs,prev,cc))
                cs=o
                prev=o
                cc=1
        if cc>=5:
            clusters.append((cs,prev,cc))
    
    if clusters:
        report(r, f"\nString data clusters ({len(clusters)}):")
        for cs,ce,cc in clusters:
            # Find string boundaries
            report(r, f"  0x{cs:X}..0x{ce:X}: {cc} name hits")
            # Show strings
            pos=cs
            shown=0
            while pos<=ce+32 and shown<12:
                if rom[pos]==0xFF:
                    pos+=1
                    continue
                e=rom.find(b'\xff', pos)
                if e==-1 or e-pos>128:
                    pos+=1
                    continue
                if e-pos>=1:
                    txt=decode_pcs(rom[pos:e+1])
                    if txt:
                        report(r, f"    0x{pos:X}: {txt}")
                        shown+=1
                pos=e+1
    
    return "\n".join(r)

# ======== MAIN ========
rom_dir = Path("C:/code/GBA-Rom-Translator/roms/origin")
output_lines = []

# FRLG
for fname, table_info in [
    ("POKEMON_FIRE_BPRJ00.gba", None),
    ("POKEMON_LEAF_BPGJ00.gba", None),
]:
    p=rom_dir/fname
    if p.exists():
        output_lines.append(scan_rom(p, fname.replace(".gba",""), FRLG_TRAINERS, table_info))

# RSE - might be a different table structure
for fname in ["POKEMON_RUBY_AXVJ00.gba","POKEMON_SAPP_AXPJ00.gba","Pokemon Emerald Version(JP).gba"]:
    p=rom_dir/fname
    if p.exists():
        output_lines.append(scan_rom(p, fname.replace(".gba",""), RSE_TRAINERS, None))

# Additional: check known Meowth configs for trainer name ranges
print("\n\n=== Checking Meowth config files for trainer name ranges ===")
config_dir = Path("C:/code/GBA-Rom-Translator/configs")
if config_dir.exists():
    for cfg_file in sorted(config_dir.glob("*/game.json")):
        try:
            cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
            rom_id = cfg.get("rom_id", cfg_file.parent.name)
            for mod in cfg.get("modules", []):
                if mod.get("id") == "训练家名":
                    print(f"  {rom_id}: 训练家名 = {mod.get('start','?')}..{mod.get('end','?')}")
        except:
            pass

result = "\n".join(output_lines)

# Write to UTF-8 file
out_path = Path("trainer_names_findings.txt")
out_path.write_text(result, encoding="utf-8")
print(result)
