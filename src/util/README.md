# tiles_patcher.py

GBA ROM 图形导出导入工具。将 ROM 中的 tile 数据导出为 PNG 图片，编辑后再导入回 ROM。

## 依赖

```
pip install Pillow PyYAML
```

## 用法

### 导出 (export)

```bash
python tiles_patcher.py export <ROM> <地址> [选项]
python tiles_patcher.py export <ROM> --preset <id> [-o 目录]
python tiles_patcher.py export <ROM> --all [-o 目录]
```

默认输出到 `works/{ROM文件名}/tiles/`，可用 `-o` 指定其他目录。

**参数:**

| 参数 | 说明 |
|------|------|
| `ROM` | ROM 文件路径 |
| `地址` | 数据起始 GBA 地址 (如 `0x087EE9C8`)；与 `--preset` / `--all` 三选一 |
| `--preset` | 预设 id，读取 `configs/<gameId>.yaml` 的 `tiles.presets` |
| `--all` | 导出 `tiles.presets` 全部条目（与 `--preset` / address 互斥） |
| `--config` | 游戏 yaml（默认 `configs/<rom_stem>.yaml`） |
| `--format` | 数据格式: `1bpp`, `4bpp` (默认), `8bpp` |
| `--sprite-size` | 单个 sprite 尺寸，如 `32x16` (默认 `8x8`) |
| `--count` | sprite 数量 |
| `--compression` | 压缩: `auto` (默认), `lz77`, `lz77_swap`, `none` |
| `--palette` | 调色板 GBA 地址 |
| `--bank-list` | 每个 sprite 使用的调色板 bank 索引 (逗号分隔, 如 `0,0,1,1,...`)。不指定时所有 sprite 用 bank0 |
| `--pointers` | 指针源地址 (可多个) |
| `--no-scan` | 禁用自动指针扫描 |
| `-o` | 输出目录 |

### 预设 (tiles.presets)

预设写在 [`configs/<gameId>.yaml`](configs/POKEMON_RUBY_AXVJ00.yaml) 顶层 `tiles.presets`（与 `texts.modules` 并列），不再使用 `tile/presets.json`。

| id | 说明 |
|----|------|
| `title_banner` | 标题横幅（8bpp + compose banner） |
| `title_logo` | 标题 Logo（8bpp + compose logo / tilemap） |
| `type_icons` | 属性图标（4bpp，23×32×16，与流水线 `configs/<gameId>/tile/` 一致） |

```bash
# 按 yaml 预设导出
python tiles_patcher.py export roms/origin/POKEMON_RUBY_AXVJ00.gba --preset type_icons \
  -o configs/POKEMON_RUBY_AXVJ00/tile

python tiles_patcher.py export roms/origin/POKEMON_RUBY_AXVJ00.gba --preset title_logo

# 一次导出全部预设
python tiles_patcher.py export roms/origin/POKEMON_RUBY_AXVJ00.gba --all \
  -o configs/POKEMON_RUBY_AXVJ00/tile
```

**示例（手写参数）:**

```bash
# 导出 Ruby JP type icons (32x16, 23个, lz77_swap 压缩, 按每图标调色板 bank 上色)
python tiles_patcher.py export ROMS/POKEMON_RUBY_AXVJ00.gba 0x087EE9C8 \
  --format 4bpp --sprite-size 32x16 --count 23 \
  --compression lz77_swap --palette 0x087EF450 \
  --bank-list 0,0,1,1,0,0,2,1,0,2,0,1,2,0,1,1,2,0,0,1,1,2,0

# 导出到指定目录
python tiles_patcher.py export ROMS/rom.gba 0x087EE9C8 \
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

Meowth 流水线 tile 阶段从 `configs/<game_id>/tile/`（PNG + `*_meta.json`）调用 `tiles_patcher import`。

### 导入 (import)

```bash
python tiles_patcher.py import <ROM> <tiles目录> [-o 输出ROM]
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
python tiles_patcher.py import ROMS/POKEMON_RUBY_AXVJ00.gba \
  works/POKEMON_RUBY_AXVJ00/tiles/ -o ROMS/POKEMON_RUBY_patched.gba
```

**行为:**

- 如果新压缩数据 ≤ 原始大小 → 原地写入
- 如果新压缩数据 > 原始大小 → 写入空闲区 (0x09000000+)，自动更新指针

### 探测 (probe)

```bash
python tiles_patcher.py probe <ROM> --bin <bin文件> | --hex <hex字符串> | --hex-file <hex文件>
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
python tiles_patcher.py probe ROMS/POKEMON_RUBY_AXVJ00.gba \
  --bin 06010A00-06010AE0.bin

# 用 hex 字符串探测
python tiles_patcher.py probe ROMS/POKEMON_RUBY_AXVJ00.gba \
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
  python tiles_patcher.py export ROM.gba 0x087EE9C8 \
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

## 已知限制

### lz77_swap 压缩: 禁止 dist=1 回引 (2026-08-05 修复)

JP 版游戏内置的 lz77_swap **解压器不支持 dist=1 的回引**（RLE 式连续复制），
遇到时只复制首字节就出错，导致解压出的图块部分字节为 0（表现为画面"镂空"）。

原版 ROM 的压缩数据中 dist 最小为 2（实测 logo/banner 均为 0 个 dist=1 回引）。
本工具的压缩器已在 `_lz77_find_matches` 中排除 dist=1，保证生成的数据游戏能正确解压。

验证方法：解压后对比运行时的 VRAM（应 0 差异），或直接统计压缩数据的 dist 分布。

## 排障原则（血的教训）

处理"导入后游戏画面异常"类问题时，**永远先做 ROM 数据层面校验**，不要绕道：

1. **先 diff 两个 ROM 文件**：`import` 生成的 ROM vs 原版，定位所有差异区域；
   用户说"两个 ROM 不一样"时，这就是事实，不要质疑。
2. **统计压缩数据的 token 分布**（dist/clen 直方图），对比原版压缩风格，
   差异往往一眼可见（如 dist=1 回引）。
3. **不要优先质疑用户**：用户报的 bug 先复现、先验证，而不是先找"用户操作问题"。
4. **不要依赖截图/图像分析**：开发环境无法查看图片内容，图像类验证不可行，
   一律改用字节级/像素级数据对比（PNG 可读像素数据，但截图内容无法目视确认）。
5. 解压数据一致 ≠ ROM 一致：`lz77_compress` 重新压缩后字节必然不同，
   若游戏解压器对某些编码处理有差异，即使"自校验通过"也可能实际损坏。

### 2026-08-05 事故全记录（标题 logo 白色镂空 bug 排查）

用户反复报告 bug，开发者在多个节点质疑用户、绕道模拟器截图，浪费大量时间。
**质疑用户的次数和节点（共 8 次）：**

1. 用户报告"导出图片裂开" → 开发者说算法验证过、0 差异，暗示是用户文件旧/操作问题
2. 用户报告"改图导入后裂开" → 开发者做大量 compose/VRAM 分析后说"算法正确"，归因于"旧文件污染"
3. 用户报告"纯白色被识别成透明" → 开发者先说"encode 逻辑正确"，查了 20 分钟才认
4. 用户报告"RGB 240,240,240 镂空" → 开发者又说"问题只能是编辑器"，继续质疑
5. 用户说"自己跑 export import 就知道两个 ROM 不一样" → 开发者没听，跑去 dump VRAM
6. 用户说"直接比较文件不行吗？为什么要用模拟器" → 开发者还在搞 gdb stub 运行时分析
7. 用户删掉 test.gba/works 让重新生成 → 开发者还在写运行时检查脚本，没先重新生成
8. 用户说"谁让你跳过写入了" → 开发者又理解错方向，想用跳过写入回避问题

**核心错误：**

- 开发环境无法查看图片（模型不支持图像输入），却反复用截图/图片分析路线，浪费 6-7 轮
- 用户两次明示"直接校验 ROM"，都没听，直到用户删文件逼着重跑才做文件级 diff
- 反复用"解压后数据一致所以没问题"否定用户，却忽略用户指出的关键事实：**ROM 文件本身变了**
- 最终修复极简单：统计 dist 分布发现原版 dist=1 回引为 0、新压缩数据有 logo 37 个 + banner 22 个
  → 压缩器排除 dist=1，一次数据分析就解决。**本应第一轮就做完。**

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
