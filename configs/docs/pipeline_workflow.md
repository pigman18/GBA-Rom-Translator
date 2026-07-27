# AXVJ 完整流水线流程

## 入口命令

```powershell
cd "C:\code\gba\tools\Meowth-GBA-Translator-JP"
meowth full "C:\code\gba\roms\origin\POKEMON_RUBY_AXVJ00.gba" --seed-only --target zh-Hans -o "C:\code\gba\roms\outputs"
```

- `--seed-only`：不调用 LLM API，只用离线种子翻译
- `-o`：成品 ROM 输出目录

## 流水线阶段

### Phase 1: 扫描配置

1. 扫描 `configs/` 目录，找到 `POKEMON_RUBY_AXVJ00/game.json`
2. 加载 `game.json`（含 ROM 地址、模块配置、自定义翻译路径）

### Phase 2: 加载翻译数据

1. 加载 `custom_translations/` 下 6 个 JSON 文件（图鉴、地点、招式、道具、特性、其他）
2. 合并 prior work cache 中的已有翻译
3. 应用离线种子翻译（985 条 seed），清除失败的 ja→zh stubs
4. `--seed-only` 跳过剩余 4065 条未翻译文本

### Phase 3: 生成字库 + 短语表

1. 同步默认字库 `graphic/fonts/` 到工作目录
2. 生成 `phrase_data.asm`（4659 条短语 → F9 01 表）
3. 生成 `graphic/fonts.s`（incbin 字库数据）
4. 生成 `include/axvj_addrs.asm`（从 `game.json.addrs` 自动导出）

### Phase 4: 字体补丁（armips 汇编）

1. 复制 ROM 到工作目录 `baserom.gba`
2. 调用 `armips.exe main.asm` 汇编
   - `game_addrs.asm`：静态地址常量（config 根目录，管道不覆盖）
   - `include/axvj_addrs.asm`：管道自动生成（`main.asm` 不引用）
   - `HookInOrigin/ProcessCurrentChar.s`：F9 dispatch 钩子 @ 0x0800336E
   - `HookInOrigin/GetWindowAttribute.s`：窗口宽度修正钩子 @ 0x0800414C
   - `HackFunction/ChineseGlyphDispatch.s`：F9 00/F9 01 分发
   - `HackFunction/DrawChineseGlyph4bpp.s`：中文瓦片渲染（Menu 2D / 战斗线性，见 [`CHS_TILE_LAYOUT.md`](CHS_TILE_LAYOUT.md)）
   - `HackFunction/GetWindowAttributeHook.s`：ARM 模式宽度 ×2 修正
   - `HackFunction/GetStringWidthChinese.s`：F9 宽度累加（暂无人调用）
   - `graphic/fonts.s`：汉字节库数据（Normal + Small）
   - `phrase_data.asm`：F9 01 短语表（管道自动生成）

### Phase 5: 文本注入

1. 扫描 ROM 中 LZ bands
2. 将 1266 条翻译文本注入 ROM（含 F9 00/F9 01 中文序列）
3. 展开名字表（species_names 58/67, move_names 43/43, item_data 1/1）
4. 输出成品 ROM → `POKEMON_RUBY_AXVJ00_translated.gba`

## 代码架构

```
configs/POKEMON_RUBY_AXVJ00/
├── game.json                    # 游戏配置（含 font_patch.addrs）
├── game_addrs.asm              # 📌 静态地址常量（管道不覆盖）
├── main.asm                    # armips 入口
├── src/
│   ├── HookInOrigin/           # 原址 hook（替换 ROM 指令）
│   │   ├── ProcessCurrentChar.s    # → ChineseGlyphDispatch
│   │   └── GetWindowAttribute.s    # → GetWindowAttributeHook
│   └── HackFunction/           # 扩展 ROM 代码 (0x08800000+)
│       ├── ChineseGlyphDispatch.s      # F9 00/F9 01 分发
│       ├── DrawChineseGlyph4bpp.s      # 16x16 瓦片渲染
│       ├── GetWindowAttributeHook.s    # ARM 宽度 ×2
│       └── GetStringWidthChinese.s     # 宽度累加（备用）
├── graphic/
│   ├── fonts/                  # 字库 bin 文件
│   └── fonts.s                 # incbin 定义
├── custom_translations/        # 自定义翻译 JSON
└── include/
    └── axvj_addrs.asm          # 管道自动生成（main.asm 不引用）
```

## 关键文件说明

| 文件 | 来源 | 作用 |
|------|------|------|
| `game_addrs.asm` | 手动维护 | 所有 JP 地址 + 常量（管道不覆盖） |
| `include/axvj_addrs.asm` | 管道生成 | 从 `game.json.addrs` 自动导出，会被覆盖 |
| `phrase_data.asm` | 管道生成 | F9 01 短语偏移表 + 数据表 |
| `graphic/fonts.s` | 管道生成 | incbin 字库数据到扩展 ROM |

## Hook 激活状态

| Hook | 地址 | 状态 | 说明 |
|------|------|------|------|
| `ProcessCurrentChar` | 0x0800336E | ✅ 激活 | F9 00/F9 01 分发 |
| `DrawChineseGlyph4bpp` | (扩展区) | ✅ 激活 | Menu: charBase2+font3→2D；战斗→线性。见 [`CHS_TILE_LAYOUT.md`](CHS_TILE_LAYOUT.md) |
| `GetWindowAttribute` | 0x0800414C | ✅ 激活 | font 相关 width×2（清窗辅助） |
| `GetStringWidth` | 0x08004CCC | ❌ 禁用 | BL 超范围未解决；F9 测宽未挂 |
| `UpdateNickInHealthbox` | 0x08045138 | ❌ 禁用 | 地址待 GDB 确认 |
| `UpdateSafariBallsTextInHealthbox` | 0x08045848 | ❌ 禁用 | 地址待 GDB 确认 |
| `UpdateLeftNoOfBallsTextOnHealthbox` | 0x08045930 | ❌ 禁用 | 地址待 GDB 确认 |
| `PrintDisplayMonInfo` | 0x08098188 | ❌ 禁用 | 地址待 GDB 确认 |
| `sub_8097F58` | 0x08097EF0 | ❌ 禁用 | 地址待 GDB 确认 |

## 构建验证快捷命令

```powershell
# armips 直接汇编验证（不依赖 Meowth）
Copy-Item "C:\code\gba\roms\origin\POKEMON_RUBY_AXVJ00.gba" -Destination "C:\code\gba\tools\Meowth-GBA-Translator-JP\configs\POKEMON_RUBY_AXVJ00\baserom.gba"
cd "C:\code\gba\tools\Meowth-GBA-Translator-JP\configs\POKEMON_RUBY_AXVJ00"
.\tools\armips.exe main.asm

# Meowth 完整流水线
cd "C:\code\gba\tools\Meowth-GBA-Translator-JP"
meowth full "C:\code\gba\roms\origin\POKEMON_RUBY_AXVJ00.gba" --seed-only --target zh-Hans -o "C:\code\gba\roms\outputs"
```
