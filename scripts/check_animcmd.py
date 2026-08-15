import struct
orig = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()
trans = open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()

# 英文版 sAnimCmdFuncs @ 0x081e2950（动画命令函数表）。
# 日版 AnimCmd 解释器 0x1580 里 ldr r0,[pc]=0x081B33E4（0x15ec 字面量），
# 这是日版 sAnimCmdFuncs 表。但关键是"动画脚本数据"（命令流）在哪。

# 更直接：扫成品 ROM 里，原版是"动画脚本命令"、成品被改成含 F9 的区域。
# 动画脚本命令流 = 每帧命令（frame/jump/loop/end），数据集中在 gBattleAnims 区。

# 方法：找原版里 F9 前面的数据被成品改成 F9 xx 的地方，且原版该处不是文本。
# 用 build.json 的 in_place 条目，反查哪些 in_place 落到了非文本区（与动画脚本重叠）。

import json
d = json.load(open('work/POKEMON_RUBY_AXVJ00/translate.build.json', encoding='utf-8'))
entries = d.get('entries', [])

# 收集所有 in_place 注入的地址，找它们是否落在动画脚本区。
# 日版动画脚本区未知，但可以反过来：找成品里 F9 密集、原版里是"命令字节模式"的区域。

# 直接搜：原版 ROM 里 sAnimCmdFuncs（日版 0x081B33E4）附近，看动画命令表。
print("=== 日版 sAnimCmdFuncs 表（0x081B33E4 附近）===")
for i in range(8):
    off = 0x081B33E4 - 0x08000000 + i*4
    o = struct.unpack_from('<I', orig, off)[0]
    t = struct.unpack_from('<I', trans, off)[0]
    mark = ' <== 改' if o != t else ''
    print(f'  [{i}] 0x{o:08X} -> 0x{t:08X}{mark}')
