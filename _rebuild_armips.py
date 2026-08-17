import subprocess, sys, shutil, hashlib
build = r'C:\code\GBA-Rom-Translator\work\POKEMON_RUBY_AXVJ00\build'
armips = r'C:\code\GBA-Rom-Translator\tools\armips.exe'
out = subprocess.run([armips, 'main.asm'], cwd=build, capture_output=True, text=True)
print('armips rc', out.returncode)
print(out.stdout[-500:] if out.stdout else '')
print(out.stderr[-500:] if out.stderr else '')
if out.returncode != 0:
    sys.exit(1)
gb = open(build + '\\out\\game.bin','rb').read()
patched = open(build + '\\output.gba','rb').read()
emb = patched[0x80000:0x80000+len(gb)]
print('embedded == out/game.bin ?', emb == gb)
print('embedded sha', hashlib.sha1(emb).hexdigest()[:12], 'bin sha', hashlib.sha1(gb).hexdigest()[:12])
print('hook site:', patched[0x0808DD60-0x08000000:0x0808DD60-0x08000000+8].hex(' '))
if emb == gb:
    dst = r'C:\code\GBA-Rom-Translator\roms\outputs\POKEMON_RUBY_AXVJ00_translated.gba'
    shutil.copyfile(build + '\\output.gba', dst)
    print('copied to', dst)
else:
    print('EMBED MISMATCH - not copied')
