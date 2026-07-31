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
