import hashlib
for p in [r'C:\code\GBA-Rom-Translator\work\POKEMON_RUBY_AXVJ00\build\out\game.bin',
          r'C:\code\GBA-Rom-Translator\configs\POKEMON_RUBY_AXVJ00\hook\out\game.bin']:
    import os
    print(p)
    print('  exists', os.path.exists(p), 'size', os.path.getsize(p) if os.path.exists(p) else None)
    if os.path.exists(p):
        print('  sha', hashlib.sha1(open(p,'rb').read()).hexdigest()[:12])
