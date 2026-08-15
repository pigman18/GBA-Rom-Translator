import struct
# 英文版 DoMoveAnim @ 0x08075700，反汇编看它引用动画脚本数据的地址
rom = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()

# 但这是日版 ROM，英文版地址在日版 ROM 里不适用。
# 关键：需要找日版的 DoMoveAnim。用 game_addrs.asm 里 GetBattlerPosition=0x08075860
# 英文版 GetBattlerPosition? 让我从英文版符号表确认日英偏移。

# 英文版符号表里找 DoMoveAnim 和邻近符号，与日版 game_addrs 的已知符号对偏移
lines = open('tools/Pokemon_GBA_Font_Patch/symbols/pokeruby/pokeruby.sym', encoding='utf-8', errors='replace').read().splitlines()
for ln in lines:
    if 'DoMoveAnim' in ln or 'LaunchBattleAnimation' in ln or 'RunAnimScript' in ln or 'GetBattlerPosition' in ln:
        print(ln)
