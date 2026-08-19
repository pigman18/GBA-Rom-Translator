# tiles_patcher.py

GBA ROM 图形导出导入工具。将 ROM 中的 tile 数据导出为 PNG 图片，编辑后再导入回 ROM。

## 依赖

```
pip install Pillow PyYAML regex
```

## 用法

### 导出 (export)

```bash
python tiles_patcher.py export <ROM> <地址> [选项]
python tiles_patcher.py export <ROM> --preset <id> [-o 目录]
python tiles_patcher.py export <ROM> --all [-o 目录]
```

默认输出到 `work/{ROM文件名}/tiles/`，可用 `-o` 指定其他目录。

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
work/POKEMON_RUBY_AXVJ00/tiles/
  0x087EE9C8_00.png      # sprite 图片
  0x087EE9C8_01.png
  ...
  meta/
    0x087EE9C8_meta.json   # 元数据 (import 需要)
    0x087EE9C8_palette.png # 调色板可视化
```

Meowth 流水线 tile 阶段从 `configs/<game_id>/tiles/`（PNG + `meta/*_meta.json`）调用 `tiles_patcher import`（兼容旧目录名 `tile/`）。在 **build/字库之后** 执行，避免与 `0x09000000` 字库冲突。

### 导入 (import)

```bash
python tiles_patcher.py import <ROM> <tiles目录> [-o 输出ROM] [-a 新调色板地址]
```

读取 `*_meta.json` 和对应的 `.png` 文件，编码后写入 ROM。优先从 `tiles/meta/` 查找 meta 文件，回退到 `tiles/` 根目录。

**参数:**

| 参数 | 说明 |
|------|------|
| `ROM` | 原始 ROM 路径 |
| `tiles目录` | 包含 `*_meta.json` 和 `.png` 的目录 |
| `-o` | 输出 ROM 路径 (默认: `xxx_patched.gba`) |
| `-a` / `--new-palette` | **新调色板**写入地址。PNG 缺色写入该副本并改指针；**不改**原共享板（如 `0x0836D148`），防止标题背景乱码。指定后关闭颜色吸附 |
| `--only` | 只导入指定图块数据地址（可重复/逗号分隔） |
| `--reloc-base` | 超槽重定位搜索起点（默认 `0x09200000`；写入地址 **4 字节对齐**） |
| `--no-snap-palette` | 关闭「吸附到旧板」 |

**示例:**

```bash
# 导入修改后的 sprites
python tiles_patcher.py import ROMS/POKEMON_RUBY_AXVJ00.gba \
  work/POKEMON_RUBY_AXVJ00/tiles/ -o ROMS/POKEMON_RUBY_patched.gba

# 标题图：缺色进新调色板（指定空闲地址，勿与字库/图块冲突）
python tiles_patcher.py import roms/origin/POKEMON_RUBY_AXVJ00.gba \
  configs/POKEMON_RUBY_AXVJ00/tiles \
  --only 0x0836D268,0x0836EC6C \
  -a 0x09200000 \
  -o roms/work/title_tiles_check.gba
```

**行为:**

- 如果新压缩数据 ≤ 原地槽 → 原地写入（槽长 = min(原 LZ 长, 距下一 meta 地址)，防 Logo/横幅仅隔 2B 时互相踩踏）
- 如果新压缩数据 > 原地槽 → 写入空闲区（默认自 `0x09200000`，**4 字节对齐**），自动更新指针
- Logo：仍按原 tilemap 逐格 scatter 写 tile（**不改 map / 不重映射**）
- `--new-palette`：原板只读复制 → 空闲色槽填缺色 → 写到指定地址 → 扫描并改写指向原板的指针（绘制算法不变，只补板）

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
7. 用户删掉 test.gba/work 让重新生成 → 开发者还在写运行时检查脚本，没先重新生成
8. 用户说"谁让你跳过写入了" → 开发者又理解错方向，想用跳过写入回避问题

**核心错误：**

- 开发环境无法查看图片（模型不支持图像输入），却反复用截图/图片分析路线，浪费 6-7 轮
- 用户两次明示"直接校验 ROM"，都没听，直到用户删文件逼着重跑才做文件级 diff
- 反复用"解压后数据一致所以没问题"否定用户，却忽略用户指出的关键事实：**ROM 文件本身变了**
- 最终修复极简单：统计 dist 分布发现原版 dist=1 回引为 0、新压缩数据有 logo 37 个 + banner 22 个
  → 压缩器排除 dist=1，一次数据分析就解决。**本应第一轮就做完。**

## 文件结构

```
work/
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

# debug_patcher.py（原 gdb_patcher.py）

连 mGBA GDB stub，或对成品 ROM 做静态反查，定位「坏地址」从哪来。

**依赖：** 仅 Python 标准库（不改 ROM、不代开模拟器）。

## 用法

### A. 崩后还能停在坏 PC

```bash
python src/util/debug_patcher.py 0xD8004286
```

### B. SoftReset / 进 BIOS → 优先 `romscan`（不必开 GDB）

动画完重启、CallVia trap 一直「非目标」时：坏值往往是 **ROM 里指针表被 in_place 盖成 F9 流**，不经 `CallViaR*`。

```bash
python src/util/debug_patcher.py romscan 0x5F0A00F9
```

对照原盘字 → 成品字，并反查 `translate.build.json` 的误扫条目，再写入 `rejects`。

### C. `trap`（CallVia + SoftReset 运行时拦）

```bash
python src/util/debug_patcher.py trap 0x5F0A00F9
python src/util/debug_patcher.py trap 0x5F0A00F9 --any-f9
```

---

# gdb_patcher.py

基于 mGBA GDB stub 的运行时追踪工具（`log` 命令）。每个函数 = 断点地址 + 独立
handler，`--functions` 按函数名选择要监听的函数，未注册的名字跳过并警告。
缺省（不带 `--functions`）监听**全部已注册函数**（文本 + 图像），仅排除
`ProcessCurrentChar`（逐字符输出与 `InitTextPrinter` 块级解码冗余，需显式指定）。

已注册函数（图像加载器全部在日版 AXVJ 上反汇编行为核实）：
`InitTextPrinter`、`ProcessCurrentChar`、`LZDecompressWram/Vram`、
`LoadSpriteSheet`、`LoadSpritePalette`、`LoadCompressedObjectPic/Palette`、
`LoadCompressedPalette`、`LoadPalette`。sheet 类打印 data/size/tag + 数据区域；
ROM 源额外给出原盘偏移与头字节（LZ77 头标注）。

```bash
# 缺省：监听全部函数（文本+图像），并用字库解码文本
python src/util/gdb_patcher.py log --charmap configs/POKEMON_RUBY_AXVJ00/charmap.txt
# 只追图像加载器（按函数名）
python src/util/gdb_patcher.py log --functions LoadSpriteSheet,LoadPalette \
    --charmap configs/POKEMON_RUBY_AXVJ00/charmap.txt
# 显式逐字符（仅排查单字符问题时用）
python src/util/gdb_patcher.py log --functions InitTextPrinter,ProcessCurrentChar \
    --charmap configs/POKEMON_RUBY_AXVJ00/charmap.txt
```

未指定 `--charmap` 时按原始字节 hex + 可读转义输出。缺省日志 `work/gdb_patcher_log.log`，
`--log` 可换路径。新增函数只需 `@register(name, bp, desc)` 注册新 handler。

---

# addr_patcher.py

ROM 地址交叉引用（Thumb）。默认 ROM：`roms/origin/POKEMON_RUBY_AXVJ00.gba`。

```bash
# 谁 bl/blx 到该函数（默认 depth=1）
python src/util/addr_patcher.py callers 0x08061CF4
# 向上展开调用链：调用点 → 归属函数 → 再查谁调该函数
python src/util/addr_patcher.py callers 0x08061CF4 --depth 3
python src/util/addr_patcher.py callers 0x08061CF4 --depth 3 -o callers.json

# 谁以 LE 指针引用该地址（默认含非对齐；只要对齐加 --aligned-only）
python src/util/addr_patcher.py refs 0x0814BA38
python src/util/addr_patcher.py refs 0x0814BA38 --aligned-only
```

跳过标题 LZ 带；`callers` 先建全盘调用索引（一次反汇编），再按 `--depth` 查链。归属函数启发式：最近 bl 目标 / `push {…,lr}`。

---

# texts_patcher.py

按 `src/util/configs/<game_id>.yaml` 的模块地址带导出 / 搜索 PCS 文本；坏句写入全局 `texts.omit_ranges`，模块 `ranges` 保持粗带。

在仓库根目录运行（或把 `src/util` 加入 `PYTHONPATH`）。

**依赖：**

```
pip install PyYAML regex
```

## `texts:` 配置要点

```yaml
texts:
  omit_ranges:                 # 全局跳过（闭区间）；所有模块 export/scan 共用
    - { start: '0x100C0E', end: '0x100C22' }
  filters:                     # 扁平 id 列表；type 须以 _filter 结尾
    - id: global_character_filter
      type: character_filter
      # 踢全角拉丁碎屑；保留 Ａ/Ｂ；ＤＮＡ 用 regex (*SKIP)(*FAIL) 放行
      value: 'ＤＮＡ(*SKIP)(*FAIL)|[üÜ►♂♀ÖÄß：Ｃ-Ｚａ-ｚ]'
      # 包含写法: value: '^(?=.*ＤＮＡ)(?!.*test).*' 且 filter: false
    - id: global_dialogue_shape_filter
      type: dialogue_shape_filter
      value: true
    - id: global_min_byte_length_filter
      type: min_byte_length_filter
      value: 8
    - id: global_garbage_heuristic_filter
      type: garbage_heuristic_filter
      value: true
    - id: global_anim_cmd_filter
      type: anim_cmd_filter
      value: true
    - id: global_ime_keyboard_filter
      type: ime_keyboard_filter
      value: true
    - id: global_naming_screen_filter
      type: address_filter
      value:
        start: '0x083A32D0'
        end: '0x083A34FF'
  modules:
    - id: 剧情
      start: '0x100000'        # 粗带；洞写 omit，不要切碎 ranges
      end: '0xFFFFFF'          # 全 ROM（export 按模块顺序 seen_addr 去重）
      type: scan
    - id: 宝可梦名
      type: stride             # filters 对 scan/stride/struct/stride_ptr 一律生效
      read: { stride: 6 }
      filters:
        - { id: pm_character_filter, type: character_filter, value: '？？？？？', filter: true }
    - id: 地点名
      type: scan
      filters:                 # 同 id 覆盖全局；新 id 追加
        - { id: global_dialogue_shape_filter, type: dialogue_shape_filter, value: false }
        - { id: global_min_byte_length_filter, type: min_byte_length_filter, value: 5 }
        - { id: place_max_byte_length_filter, type: max_byte_length_filter, value: 20 }
        - { id: global_garbage_heuristic_filter, type: garbage_heuristic_filter, value: false }
    - id: UI界面
      filters:
        - { id: ui_require_pointer_filter, type: require_pointer_filter, value: true }
        - id: ui_original_text_filter
          type: original_text_filter
          filter: false          # 包含：只留名单正文
          value:
            - さいしょからはじめる
            - つづきからはじめる
            # 短危词必须绑地址（禁止裸写「こ」「ひき」）：
            # - { original: "こ", address: "0x08XXXXXX" }
```

| 属性 | 层级 | 含义 |
|------|------|------|
| `texts.omit_ranges` | 全局 | 跳过地址带；`export`/`scan` = 模块带 − omit |
| `texts.filters` | 全局 | 带 `id` 的 `*_filter` 列表（层层过滤） |
| `modules[].ranges` / `start`+`end` | 模块 | 粗扫描母带（相邻模块勿互相覆盖） |
| `modules[].filters` | 模块 | 同 `id` 覆盖全局整条；新 `id` 追加 |
| `require_pointer` / `min_byte_length` | 模块 | 旧字段；无同名 `*_filter` 时仍生效 |
| `modules[].looks_like_jp_text` | 模块 | bool；默认 `false`。`true` 时才在 `type: scan` 的 FF 扫描路径调 `jp_pcs.looks_like_jp_text` 做形态预校验。**误判率很高，后续尽量不要用这个函数**——优先用地址带 / 语料白名单（msg_filter、original_text_filter、execute_filter）/ 结构定址（stride、struct），而不是形态启发式。 |

### `texts.filters` / `FilterContext`

**无 module.type 限制**：`scan` / `stride` / `struct` / `stride_ptr` 读出正文后都走同一套 `apply_filters`。

合并策略（与「能否过滤」无关）：全局列表为基线 → 模块 `filters` 按 **`id`** 覆盖/追加（保序）。`type` 必须以 `_filter` 结尾；缺 `id` 时回退用 `type` 当 id。

- `type: scan`：始终吃全局基线。
- 非 `scan` 且模块**未写** `filters` 键：基线为空（避免全局对白/长度闸误杀短表名）。
- 非 `scan` 且写了 `filters`：基线 = 全局，再按 id 覆盖/追加。
- **例外：** 模块含 `original_text_filter` 且 `filter: false` → **不合并全局**，只跑模块自己的 `filters`。

每条候选构造 `FilterContext`（`NamedTuple`）后再跑闸：

| 字段 | 含义 |
|------|------|
| `address` / `address_vma` | 文件偏移 / `0x08……` VMA |
| `raw` / `byte_length` | PCS 字节与长度 |
| `original` / `original_plain` | 解码原文；plain 已剥 `\CC` / `\n\l\p` / `\xx` |
| `is_pointer_based` / `pointer_offs` | 是否有指针命中 |
| `module_id` / `module_type` | 当前模块 |

每条 filter 可写 **`filter` 极性**（默认 **`true`**，与旧行为一致）：

| `filter` | 含义 |
|----------|------|
| `true`（默认） | **过滤**：命中条件则丢 |
| `false` | **包含**：命中条件则留，未命中则丢 |

| filter `type` | `value` | 命中条件（再经 `filter` 极性） |
|---------------|---------|--------------------------------|
| `character_filter` | 正则 | **plain** 上第三方 [`regex`](https://pypi.org/project/regex/) `search`（`(*SKIP)(*FAIL)` / lookahead 等）。缺包：`pip install regex` |
| `dialogue_shape_filter` | bool | `value: true`：不像对白则命中；`value: false`：整闸跳过 |
| `min_byte_length_filter` / `max_byte_length_filter` | int | 字节长度越界 |
| `require_pointer_filter` | bool | `value: true`：无指针则命中 |
| `story_pointer_filter` | bool | `value: true`：无指针命中（同 `require_pointer`）；有指针但目标 raw 像原始数据（顺号计数器段如 `15 16 17 18 19 FF`、anim/指针表流、五十音键盘表、垃圾假名解码）也命中——只留「真是剧情指针」的条目 |
| `garbage_heuristic_filter` | bool | `value: true`：垃圾假名/拉丁混扫则命中（不计 `Ａボタン`） |
| `anim_cmd_filter` | bool | `value: true`：`raw` 像 Gen3 精灵 anim（连续 ≥2 个 `0x08/09` ROM 指针，或连续 ≥2 个帧字 `xx 0{0,1} 10 00`，或帧字 + `FFFF` / 后随指针）则命中 |
| `ime_keyboard_filter` | bool | `value: true`：`raw` 像 Gen3 姓名五十音键盘表（RS/FRLG 日版共有页头/`5` 递增假名行；勿 `in_place`）则命中 |
| `address_filter` | 正则或 `{start,end}` | 地址命中禁止规则（正则同样用 `regex`） |
| `original_text_filter` | 列表 | 原文精确/去空白命中。元素可以是字符串，或 `{original, address}` / `{original, start, end}`（绑地址后才放行）。常配 `filter: false` 做白名单 |
| `execute_filter` | `[{name, address, depth?}]` | 候选地址被 value 指定函数的消费链消费（BL 闭包，见下文）。常配 `filter: false` 做「被消费才留」 |

**短危词**（单字/极短如 `こ`、`ひき`）：**禁止**在包含名单里裸写字符串——会全 ROM 命中假名表或错指针，`relocate` 易炸菜单。必须写成 `{ original: "こ", address: "0x08…" }`；若 ROM 根本没有独立 PCS 串（继续画面「只/个」常为绘制拼接），不要进白名单，改查绘制/hook。

AXVJ 继续画面：`ひき`/`こ` 由 hook `ui/fixed_string` 置空（非 texts 白名单）。

**勿**把 `character_filter` 写成 `[Ａ-Ｚａ-ｚ]`：会误杀 `Ａボタンで…`。要踢全角拉丁碎屑时用 `[Ｃ-Ｚａ-ｚ]`（可加 `üÜ►♂♀`），单独留下 `Ａ`/`Ｂ`。图鉴 `ＤＮＡ` 是 JP PCS **全角**（落在 `Ｃ-Ｚ`），用 `ＤＮＡ(*SKIP)(*FAIL)|…` 写进 `value`，不要在 `.py` 里白名单。

## 导出 (export)

```bash
python src/util/texts_patcher.py export <rom.gba> [--config yaml] [--module 模块名] [-o texts.json]
```

默认按 yaml 全部模块扫 PCS（已减 `omit_ranges`），写出 `src/util/work/<game_id>/texts.json`。  
单模块：`--module 道具名` → `src/util/work/<game_id>/texts_道具名.json`。  
**禁止**默认写到流水线 `configs/<game_id>/translate/`（见 `.cursor/rules/util-no-pipeline-output.mdc`）。

含 `msg_filter`（`filter: false`）的模块：**不再指针优先**——落入全盘 FF 针扫，逐条交 `msg_filter` 白名单判定；无指针的定址文本表（如偏移索引的随机词表 `0x083B29C0` 的「ドラゴン」）也会被收录。若模块未写 `looks_like_jp_text: true`，扫出的候选不做形态预校验，直接由白名单收紧。

含 `callers_filter`（`filter: false`）的模块：只验收预计算「可达汇点」的正文（∩ 模块地址带）；剧情/UI 归属靠地址带等其它 filter，不靠 callers 再分域。

含 `execute_filter`（`filter: false`）的模块：同理，只验收预计算「被消费链消费」正文（∩ 模块地址带）。

### `execute_filter`（判定：类文本是否被指定函数的消费链消费）

**定义**：自 value 指定的消费函数地址（如 `PrintNextChar` `0x080032F8`）沿 **Thumb/ARM BL 逆调用图自下而上** BFS（`depth` 默认 8）：`BL→sink 的调用点 → 归属函数（最近的上方 push {…, lr}）→ 该函数的调用者 → …`。每个新收函数的区间（到下一 push 起点，含末尾字面量池）内、值指向 ROM 的 4 对齐 LE word 目标计入「被消费」集合；候选地址命中 = 被消费。即 `C(t) ⇒ B(t) ⇒ PrintNextChar(t)` 形态可判定。

**代码指针不算文本**（防回调误判）：目标是函数起点 / BL 调用目标 / 落在任一 visited 函数区间内（含 `地址|1` 的 Thumb 指针形态）→ 排除。例：AXVJ `0x081050B5`、`0x08105208|1` 是回调函数指针，不作正文收录。

```yaml
- id: ui_execute
  type: execute_filter
  filter: false
  value:
    - name: PrintNextChar
      address: '0x080032F8'
      # depth: 8   # 可选，BFS 层数上限
```

边界：只追**代码调用链**。脚本数据（`message` op 等）里的文本指针不经 BL 传参，不在覆盖内（剧情 op 走 `callers_filter` 的 script_ops 路径）。残余非文本引用（绘制缓冲等）靠 `garbage_heuristic_filter` 等形态闸兜底。

### `callers_filter`（判定：候选地址是否可达汇点）

**定义**：`type: scan` 负责产出「类文本」候选（含垃圾）；本 filter 对每个候选**判定**它是否「可达」某个汇点地址——从候选地址正向爬升，看调用链是否经过 `value` 里的任一 `address`。**不负责识别文本**，也不叠任何「这是文本」的含义：它只是通用的「地址可达性」判定，换一种数据（如图片）把 `value` 换成对应消费点即可复用。

正向爬升链路：

```
候选地址 A ──(ldr rN,=A)──> 加载进寄存器 ──(bl F)──> F ──(被调方闭包)──> 汇点(如 PrintNextChar)
```

实现要点：

1. 全盘找 `ldr rN, [pc, #imm]`（含 Thumb-2 `ldr.w`），定位「谁加载了候选 A」。
2. 自加载点正向走到下一条 `bl`，得到接收函数 F；值被解引用（`ldr rM,[rN,…]`）则当作**表基**，按 stride 展开整表再逐项判定。
3. 从 F 沿**被调方闭包** BFS（以函数返回指令 `bx lr` / `pop {…,pc}` 为界，不再扫进后续无关代码），看是否到达任一汇点 `address`。

`value` 推荐写成列表，两种项：

```yaml
# 剧情 / 训练家：{name} = 内建 op 类别（程序自动 walk 脚本找调用点）
- id: story_callers
  type: callers_filter
  filter: false
  value:
    - name: message
    - name: messageautoscroll
    - name: loadword_callstd

- id: trainer_callers
  type: callers_filter
  filter: false
  value:
    - name: trainerbattle

# UI：{name, address} = 正向爬升（汇点）
- id: ui_callers
  type: callers_filter
  filter: false
  value:
    - name: PrintNextChar
      address: '0x080032F8'
```

- `{name, address}`：`address` 是汇点，走正向爬升（不区分注入叶/消费叶，不内置任何映射）。
- `{name}`（name ∈ `message` / `messageautoscroll` / `loadword_callstd` / `trainerbattle`）：内建 op 类别，程序 `walk_script_ops` 正向找脚本调用点，判定候选是否被该 op 引用。

不再需要 `script_ops` / `bind_leaf` / `sinks` / `text_arg` / `wrapper_depth`。

预计算（一次性反汇编，可慢）：

1. **`{name, address}`（UI）**：全盘 `ldr [pc,#imm]` 建字面量索引 → 正向找 `bl` → 被调方闭包到汇点；表基展开。
2. **`{name}`（剧情/训练家）**：自 `texts.script_roots` 入口 walk，抽 `message` / `loadword_callstd` / `trainerbattle`。
3. 只收录 ROM 正文指针；剧情 vs UI 用模块顺序 + 地址带等其它 filter（story 先认领脚本池，UI 收剩余）。

说明：AXVJ 字段本正文几乎都在 `0x1xxxxx`；训练家模块须排在剧情之前，并用 `trainerbattle` 单独认领。

AXVJ `texts.script_roots`（util yaml 钉址）：

| 字段 | 地址 / 值 | 说明 |
|------|-----------|------|
| `map_header_ptrs` | `0x082E03CC` | 各组 `MapHeader*` 表拼接（393） |
| `map_header_count` | `393` | |
| `gMapGroups` | `0x082E09F4` | 组索引表（33） |
| `gStdScripts` | `0x08145A48` | `gotostd`/`callstd` 目标（×8） |

叶与闭包（对照 pokeruby）：`InitTextPrinter@0x08002C68` ← `Text_InitWindow` ← `Text_InitWindowAndPrintText` ← `Menu_PrintText` / 字段 `ShowFieldMessage*` 等。表形例：Start Menu `MenuAction`（stride 8）、口袋名指针表。

**不要**当叶：`Text_InitWindowWithTemplate`（只建窗）、`StringExpandPlaceholders` / `BattleStringExpandPlaceholders*`（只展开）、`BufferStringBattle`（string ID）、`Text_PrintWindow*` / `Text_UpdateWindow*`（读已绑 `win->text`）。

## 搜索 (scan)

```bash
python src/util/texts_patcher.py scan <rom.gba> <关键字> [--module 模块名] [--start ADDR] [--end ADDR]
```

在区间内按解码后原文子串命中，打印地址与句子。

## 标记无意义 404 (mark-404)

对 `texts_translated.json` 中 `status=200`：

- 译文含「这是一段乱码 / 明显乱码」→ 无可用汉字或原文垃圾则 **404**；否则清洗译文保持 200
- 无乱码标记但原文像垃圾假名/代码误扫（性别符+全角拉丁、高重复片假名等）→ **404**

```bash
python src/util/texts_patcher.py mark-404
```

## 邻近合并碎 ranges (migrate-omit)

把模块内间距 ≤ `--max-gap`（默认 32）的碎 `ranges` 合并；**大缝保留为多段**，不写入 omit。并确保存在 `texts.omit_ranges`。

```bash
python src/util/texts_patcher.py migrate-omit roms/origin/POKEMON_RUBY_AXVJ00.gba
python src/util/texts_patcher.py migrate-omit --max-gap 64
```

## 挖洞预览 / 执行 (remove-preview / remove)

对坏句：**整句字节区间**写入全局 `texts.omit_ranges`（merge），**不**再把模块 `ranges` 切碎。

地址来源（至少一种）：

| 参数 | 说明 |
|------|------|
| `--addrs` | 逗号分隔**句起点**；PowerShell 请加引号 |
| `--from-translated [PATH]` | 读 `status=404` 的 `original`，经 `texts.json` 反查起点 |

| 子命令 | 写盘 | 行为 |
|--------|------|------|
| `remove-preview` | 否 | 预览将 merge 的 omit、命中模块、将删 entries |
| `remove` | 是 | 写 `texts.omit_ranges`；同步 `texts.json`（删本次洞内条目） |

```bash
python src/util/texts_patcher.py remove-preview roms/origin/POKEMON_RUBY_AXVJ00.gba \
  --addrs "0x08376A3C,0x086F0B14"

python src/util/texts_patcher.py remove-preview roms/origin/POKEMON_RUBY_AXVJ00.gba \
  --from-translated
python src/util/texts_patcher.py remove roms/origin/POKEMON_RUBY_AXVJ00.gba \
  --from-translated
```

| 参数 | 说明 |
|------|------|
| `rom` | 原盘 ROM（只读解码 / 测长度） |
| `--addrs` | 逗号分隔句起点 |
| `--from-translated` | 可选 PATH；从 404 原文反查起点 |
| `--config` | yaml；默认按 ROM stem / game_code 解析 |
