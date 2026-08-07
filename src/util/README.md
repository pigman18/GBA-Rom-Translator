# row_patcher.py

GBA ROM 图形导出导入工具。将 ROM 中的 tile 数据导出为 PNG 图片，编辑后再导入回 ROM。

## 依赖

```
pip install Pillow
```

## 用法

### 导出 (export)

```bash
python row_patcher.py export <ROM> <地址> [选项]
```

默认输出到 `works/{ROM文件名}/tiles/`，可用 `-o` 指定其他目录。

**参数:**

| 参数 | 说明 |
|------|------|
| `ROM` | ROM 文件路径 |
| `地址` | 数据起始 GBA 地址 (如 `0x087EE9C8`) |
| `--format` | 数据格式: `1bpp`, `4bpp` (默认), `8bpp` |
| `--sprite-size` | 单个 sprite 尺寸，如 `32x16` (默认 `8x8`) |
| `--count` | sprite 数量 |
| `--compression` | 压缩: `auto` (默认), `lz77`, `lz77_swap`, `none` |
| `--palette` | 调色板 GBA 地址 |
| `--bank-list` | 每个 sprite 使用的调色板 bank 索引 (逗号分隔, 如 `0,0,1,1,...`)。不指定时所有 sprite 用 bank0 |
| `--pointers` | 指针源地址 (可多个) |
| `--no-scan` | 禁用自动指针扫描 |
| `-o` | 输出目录 |

**示例:**

```bash
# 导出 Ruby JP type icons (32x16, 23个, lz77_swap 压缩, 按每图标调色板 bank 上色)
python row_patcher.py export ROMS/POKEMON_RUBY_AXVJ00.gba 0x087EE9C8 \
  --format 4bpp --sprite-size 32x16 --count 23 \
  --compression lz77_swap --palette 0x087EF450 \
  --bank-list 0,0,1,1,0,0,2,1,0,2,0,1,2,0,1,1,2,0,0,1,1,2,0

# 导出到指定目录
python row_patcher.py export ROMS/rom.gba 0x087EE9C8 \
  --format 4bpp --sprite-size 32x16 --count 23 -o my_output/
```

**输出文件:**

```
works/POKEMON_RUBY_AXVJ00/tiles/
  0x087EE9C8_00.png      # sprite 图片
  0x087EE9C8_01.png
  ...
  meta/
    0x087EE9C8_meta.json   # 元数据 (import 需要)
    0x087EE9C8_palette.png # 调色板可视化
```

### 导入 (import)

```bash
python row_patcher.py import <ROM> <tiles目录> [-o 输出ROM]
```

读取 `*_meta.json` 和对应的 `.png` 文件，编码后写入 ROM。优先从 `tiles/meta/` 查找 meta 文件，回退到 `tiles/` 根目录。

**参数:**

| 参数 | 说明 |
|------|------|
| `ROM` | 原始 ROM 路径 |
| `tiles目录` | 包含 `*_meta.json` 和 `.png` 的目录 |
| `-o` | 输出 ROM 路径 (默认: `xxx_patched.gba`) |

**示例:**

```bash
# 导入修改后的 sprites
python row_patcher.py import ROMS/POKEMON_RUBY_AXVJ00.gba \
  works/POKEMON_RUBY_AXVJ00/tiles/ -o ROMS/POKEMON_RUBY_patched.gba
```

**行为:**

- 如果新压缩数据 ≤ 原始大小 → 原地写入
- 如果新压缩数据 > 原始大小 → 写入空闲区 (0x09000000+)，自动更新指针

### 探测 (probe)

```bash
python row_patcher.py probe <ROM> --bin <bin文件> | --hex <hex字符串> | --hex-file <hex文件>
```

自动分析匹配数据：压缩格式、bpp、sprite 尺寸/数量、调色板地址与 bank 数、指针源。
若 sprite 使用多个调色板 bank（如属性图标每图标一个 bank），probe 会自动扫描
OAM 调色板槽号表（13~15）并输出 `--bank-list`，保证建议的 export 命令颜色正确。
也可用 `--palette` 手动覆盖调色板地址。

在 ROM 中搜索数据，自动检测参数并生成 export 命令。支持两种输入：
- `--bin`: mgba 导出的 .bin 文件 (推荐)
- `--hex`: hex 字符串

**参数:**

| 参数 | 说明 |
|------|------|
| `ROM` | ROM 文件路径 |
| `--bin` | mgba 导出的 .bin 文件路径 |
| `--hex` | 要搜索的 hex 字符串 |

**示例:**

```bash
# 用 mgba 导出的 bin 文件探测 (推荐)
python row_patcher.py probe ROMS/POKEMON_RUBY_AXVJ00.gba \
  --bin 06010A00-06010AE0.bin

# 用 hex 字符串探测
python row_patcher.py probe ROMS/POKEMON_RUBY_AXVJ00.gba \
  --hex "10001700000000000090999999128988"
```

**工作流程:**
1. 在 mgba 中打开 View → Memory Viewer
2. 导航到 VRAM 地址（如 0x06010A00）
3. 选择区域 → 右键 → Export to .bin file
4. 运行 probe 命令

**输出:**

```
找到 1 个匹配

[1] 文件偏移: 0x7EE9C8
  数据位置: 0x7EE9C8 (GBA 0x087EE9C8)
  压缩: lz77_swap (2693 → 5888 bytes)
  格式: 4bpp
  Sprite: 32x16 × 23
  调色板: 0x087EF450 (3 banks, lz77_swap)
  指针源: 0x0839747C

建议命令:
  python row_patcher.py export ROM.gba 0x087EE9C8 \
    --format 4bpp --sprite-size 32x16 --count 23 \
    --compression lz77_swap --palette 0x087EF450
```

## 支持的压缩格式

| 格式 | 说明 |
|------|------|
| `none` | 无压缩 |
| `lz77` | 标准 GBA LZ77 |
| `lz77_swap` | Ruby JP 交换版 LZ77 (clen/coff 字节序互换) |
| `auto` | 自动检测 |

## 文件结构

```
works/
  POKEMON_RUBY_AXVJ00/
    tiles/
      0x087EE9C8_00.png
      0x087EE9C8_01.png
      ...
      meta/
        0x087EE9C8_meta.json
        0x087EE9C8_palette.png
```

## meta.json 格式

```json
{
  "name": "0x087EE9C8",
  "rom_address": "0x087EE9C8",
  "format": "4bpp",
  "compression": "lz77_swap",
  "raw_size": 5888,
  "sprite_size_px": [32, 16],
  "sprite_count": 23,
  "palette": {
    "rom_address": "0x087EF450",
    "format": "gbapal555",
    "bank_count": 3,
    "colors_per_bank": 16
  },
  "pointer_sources": [
    {"address": "0x0839747C", "current_value": "0x087EE9C8"}
  ]
}
```

---

# gdb_patcher.py

汉化崩溃排查：输入坏指针值，扫出 ROM 里存放该 4 字节的槽地址；可选连 mGBA GDB 对槽下写断点，回报写入方 PC。

**依赖：** 仅 Python 标准库（不改 ROM、不代开模拟器）。

## 用法

```bash
# 崩后已 Pause：读现场（识别 Thumb 近邻）
python gdb_patcher.py listen 0xF909F6A4 --gdb 127.0.0.1:2345 --now

# 强制 PC 跳到坏地址再炸一次（一般不推荐；已在异常向量时会拒绝）
python gdb_patcher.py goto 0xF909F6A4 --gdb 127.0.0.1:2345

# 坏值 -> 槽地址（可对照原盘）
python gdb_patcher.py find 0xF909F6A4 --rom path\to\zh.gba \
  --origin path\to\origin.gba
```

| 子命令 | 输入 | 输出 |
|--------|------|------|
| `listen --now` | 坏值 | 当前停机现场；识别 `F909F6A5` 等 Thumb 近邻 |
| `listen` | 坏值 | 对坏地址下访问断点后复现，再反查 |
| `goto` | 坏地址 | 写 PC 再 continue（只验证会炸） |
| `find` | 坏值 | ROM 中存放该 LE 字的槽 |
| `watch` | 槽地址 | 写断点命中时的 PC |
| `regs` | — | 寄存器 |
| `find-live` | 坏值 | RAM 命中 |

**重要：** 若 `PC≈0x00000004` 且 `r1/LR≈F909F6A5/A6`，说明已经崩过，再 `goto` 没有排查价值。

---

# texts_patcher.py

按 `src/util/configs/<game_id>.yaml` 的模块地址带导出 / 搜索 PCS 文本；对明显坏地址（LLM 404 等）从区间中挖洞剔除。

在仓库根目录运行（或把 `src/util` 加入 `PYTHONPATH`）。

## 导出 (export)

```bash
python src/util/texts_patcher.py export <rom.gba> [--config yaml] [--module 模块名] [-o texts.json]
```

默认按 yaml 全部模块扫 PCS，写出 `configs/<game_id>/translate/texts.json`。

## 搜索 (scan)

```bash
python src/util/texts_patcher.py scan <rom.gba> <关键字> [--module 模块名] [--start ADDR] [--end ADDR]
```

在区间内按解码后原文子串命中，打印地址与句子。

## 挖洞预览 / 执行 (remove-preview / remove)

对坏句：**整句字节区间**挖洞。起点 `X`、长度 `L`（来自 `texts.json` 的 `byte_length`，否则 ROM `read_pcs`）→ 从模块带中剔除 `[X, X+L-1]`，即 `[A,B]` 变成 `[A,X-1]` + `[X+L,B]`。只挖起点 1 字节会导致再扫时从句中冒出更多乱码。

地址来源（至少一种）：

| 参数 | 说明 |
|------|------|
| `--addrs` | 逗号分隔**句起点**；PowerShell 请加引号 |
| `--from-translated [PATH]` | 读 `texts_translated.json` 中 `status=404` 的 `original`，经同游戏 `texts.json` 反查起点；省略 PATH 则用 `configs/<game_id>/translate/texts_translated.json` |

二者可并用（去重并集后再按长度扩成整句）。**不**改缓存格式。

| 子命令 | 写盘 | 行为 |
|--------|------|------|
| `remove-preview` | 否 | 打印将改哪些模块、区间前后对比、ROM 整句摘要、`texts.json` 将删条目 |
| `remove` | 是 | 同上算法写 yaml；同步 `texts.json` 的 modules 区间，并删除落在剔除整句内或已出带的 entries |

**不**自动全量 `export`；需要整库重扫时再跑 `export`。

```bash
# 预览（不写盘）— PowerShell 请给 --addrs 加引号，否则 0x… 会被当成数字吃掉
python src/util/texts_patcher.py remove-preview roms/origin/POKEMON_RUBY_AXVJ00.gba \
  --addrs "0x08376A3C,0x086F0B14"

# 按翻译缓存 404 反查起点后预览 / 执行（整句挖洞）
python src/util/texts_patcher.py remove-preview roms/origin/POKEMON_RUBY_AXVJ00.gba \
  --from-translated
python src/util/texts_patcher.py remove roms/origin/POKEMON_RUBY_AXVJ00.gba \
  --from-translated

# 指定缓存路径，并可与 --addrs 并用
python src/util/texts_patcher.py remove-preview roms/origin/POKEMON_RUBY_AXVJ00.gba \
  --from-translated configs/POKEMON_RUBY_AXVJ00/translate/texts_translated.json \
  --addrs "0x08376A3C"

# 执行：改 yaml + 同步 texts.json
python src/util/texts_patcher.py remove roms/origin/POKEMON_RUBY_AXVJ00.gba \
  --addrs "0x08376A3C,0x086F0B14"

# 可选指定配置
python src/util/texts_patcher.py remove-preview roms/origin/POKEMON_RUBY_AXVJ00.gba \
  --addrs "0x08376A3C" \
  --config src/util/configs/POKEMON_RUBY_AXVJ00.yaml
```

| 参数 | 说明 |
|------|------|
| `rom` | 原盘 ROM（只读解码 / 无 texts 条目时测长度） |
| `--addrs` | 逗号分隔句起点；VMA 或文件偏移 |
| `--from-translated` | 可选 PATH；从 404 原文反查起点 |
| `--config` | yaml；默认按 ROM stem / game_code 解析 |

**示例命中（Ruby AXVJ）：**

- `0x08376A3C` → 文件 `0x376A3C` → 模块 **UI界面**（剔除整句长度）
- `0x086F0B14` → 文件 `0x6F0B14` → 模块 **高风险混杂**
