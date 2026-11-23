import struct
# 英文版符号表里 WindowTemplate 在 0x081E6C3C 等，但这是英文版 ROM 地址。
# 我们有的是日版 ROM，地址不同。这里先分析英文版模板的 28 字节结构语义。

# 从 pokeruby.sym 看 gWindowTemplate 长度 0x1c = 28 字节。
# 参考 pokefirered window.h: WindowTemplate 是 8 字节。
# 但 pokeruby 可能扩展了。让我从英文版 symbol 找 battle 相关模板。

# 实际上，用 pokefirered 的 struct Window (window + tileData) = 8+4 = 12 字节
# 但 pokeruby 的 gWindowTemplate 是 28 字节，说明结构不同。

# 让我直接读日版 ROM 里的战斗窗口模板。先找 sub_802D798 用的 WindowTemplate。
# 反推：TextPrinter = 0x03004170，其 [0] = template 指针，运行时设置。

# 用英文版符号表帮助理解。找 battle text 相关模板名
import re
lines = open('tools/Pokemon_GBA_Font_Patch/symbols/pokeruby/pokeruby.sym', encoding='utf-8', errors='replace').read().splitlines()
for ln in lines:
    if 'atkWindow' in ln or 'BattleText' in ln or 'WindowTemplate' in ln and ('Battle' in ln or 'Text' in ln or 'Menu' in ln):
        print(ln)
