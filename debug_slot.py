import struct, json

def fnv1a(data):
    h = 0x811C9DC5
    for b in data:
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h

# Find the entry
data = json.load(open('work/POKEMON_RUBY_AXVJ00/translate.build.json', encoding='utf-8'))
for e in data['entries']:
    if e.get('id') == 'axvj_4add8bb93548':
        orig = e['original_hex'].replace(' ', '')
        jp_bytes = bytes.fromhex(orig)
        while jp_bytes and jp_bytes[-1] == 0xFF:
            jp_bytes = jp_bytes[:-1]
        h = fnv1a(jp_bytes)
        print(f"original_hex: {orig}")
        print(f"jp_bytes (after strip): {jp_bytes.hex()}")
        print(f"hash: 0x{h:08X}")
        break

# Now check the generated ASM for this hash
asm = open('work/POKEMON_RUBY_AXVJ00/build/gen/translated_slot.asm', encoding='utf-8').read()
hash_hex = struct.pack('<I', h).hex()
print(f"\nLooking for hash {hash_hex} in ASM...")

found = False
for line in asm.split('\n'):
    clean = line.replace('0x', '').replace(',', '').replace(' ', '').replace(';', ':').lower()
    if hash_hex.lower() in clean:
        print(f"FOUND: {line.strip()}")
        found = True
        break

if not found:
    print("NOT FOUND in ASM!")
    # Show first few entries
    lines = [l.strip() for l in asm.split('\n') if l.strip().startswith('.byte')]
    print(f"\nTotal .byte entries: {len(lines)}")
    if lines:
        print(f"First entry: {lines[0][:120]}")
        print(f"Second entry: {lines[1][:120] if len(lines) > 1 else 'N/A'}")
