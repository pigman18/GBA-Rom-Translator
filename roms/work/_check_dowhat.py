from pathlib import Path
import struct
from meowth.jp_pcs import decode_pcs

orig = Path(r"C:/code/GBA-Rom-Translator/roms/origin/POKEMON_RUBY_AXVJ00.gba").read_bytes()
out = Path(r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba").read_bytes()

fo = 0x3EA622
end = orig.find(0xFF, fo)
print("orig", orig[fo : end + 1].hex())
print("decode", decode_pcs(orig[fo : end + 1]))

pt = struct.unpack_from("<I", out, 0x3502AC)[0]
f = pt & 0x1FFFFFF
end = out.find(0xFF, f)
print("out", hex(pt), out[f : end + 1].hex())
print("decode", decode_pcs(out[f : end + 1]))

fo = 0x3DC980
end = orig.find(0xFF, fo)
print("battle", orig[fo : end + 1].hex(), decode_pcs(orig[fo : end + 1]))

fo = 0x3E9B1E
end = orig.find(0xFF, fo)
print("naniwo", orig[fo : end + 1].hex(), decode_pcs(orig[fo : end + 1]))
