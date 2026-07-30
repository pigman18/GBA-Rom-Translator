# src/util — 脚本工具

按职责分两级：

- **一级**：`src/util/` 下的独立脚本
- **二级**：`tools/G3宝可梦解包/` 下流水线配套脚本

---

## 一级脚本（`src/util/`）

### row_patcher.py

GBA ROM 图形导出导入工具。将 ROM 中的 tile 数据导出为 PNG 图片，编辑后再导入回 ROM。

#### 依赖

```
pip install Pillow
```

#### 用法

##### 导出 (export)

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
| `--pointers` | 指针源地址 (可多个) |
| `--no-scan` | 禁用自动指针扫描 |
| `-o` | 输出目录 |

**示例:**

```bash
python row_patcher.py export ROMS/POKEMON_RUBY_AXVJ00.gba 0x087EE9C8 \
  --format 4bpp --sprite-size 32x16 --count 23 \
  --compression lz77_swap --palette 0x087EF450

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

##### 导入 (import)

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
python row_patcher.py import ROMS/POKEMON_RUBY_AXVJ00.gba \
  works/POKEMON_RUBY_AXVJ00/tiles/ -o ROMS/POKEMON_RUBY_patched.gba
```

**行为:**

- 如果新压缩数据 ≤ 原始大小 → 原地写入
- 如果新压缩数据 > 原始大小 → 写入空闲区 (0x09000000+)，自动更新指针

##### 探测 (probe)

```bash
python row_patcher.py probe <ROM> --bin <bin文件> | --hex <hex字符串>
```

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
python row_patcher.py probe ROMS/POKEMON_RUBY_AXVJ00.gba --bin 06010A00-06010AE0.bin
python row_patcher.py probe ROMS/POKEMON_RUBY_AXVJ00.gba --hex "10001700000000000090999999128988"
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

#### 支持的压缩格式

| 格式 | 说明 |
|------|------|
| `none` | 无压缩 |
| `lz77` | 标准 GBA LZ77 |
| `lz77_swap` | Ruby JP 交换版 LZ77 (clen/coff 字节序互换) |
| `auto` | 自动检测 |

#### 文件结构

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

#### meta.json 格式

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

### text_patcher.py

从日版 Gen3 GBA ROM 导出文本 addr_bands，并按 `configs/{ROM_ID}.json` 归类 modules。

#### 用法

```bash
python text_patcher.py <rom.gba>
```

#### 配置

`configs/{ROM_ID}.json` ← 按 ROM id 命名的 module_map

#### 输出

```
works/{ROM_ID}/
  addr_bands.json   # ROM 内文本体区间列表
  modules.json      # 按模块挂上的 addr_bands + geo_ranges
```

#### 支持游戏

| Game Code | ROM id |
|-----------|--------|
| AXVJ | POKEMON_RUBY_AXVJ00 |
| AXPJ | POKEMON_SAPP_AXPJ00 |
| BPRJ | POKEMON_FIRE_BPRJ00 |
| BPGJ | POKEMON_LEAF_BPGJ00 |
| BPEJ | POKEMON_EMERALD_BPEJ00 |

---

## 二级脚本（`tools/G3宝可梦解包/`）

### 流水线总览

从日版 Gen3 ROM 导出文本区间，按模块归类，再拷进 Meowth 做 extract 戳模块 / 注入勾选。

```
measure_module_spans.py     # 测准：写 configs 的 start/end/ranges
text_patcher.py             # 扫 ROM → addr_bands → 归类 modules.json
assign_modules.py           # 匹配规则；写出 geo_ranges
configs/
  _template.json
  POKEMON_RUBY_AXVJ00.json  # module_map（ROM id 命名）
  POKEMON_SAPP_AXPJ00.json  # RS 族可与红同布局
  …
works/{ROM_ID}/
  measured_spans.json       # measure 中间结果
  addr_bands.json           # dump：ROM 内文本体区间列表
  modules.json              # dump：按模块挂上的 addr_bands + geo_ranges
```

Meowth 消费副本：`configs/{ROM_ID}/translate/modules.json`

### 端到端补全流程

#### Step A — 复现与定位（文本 only）

1. 记下屏上日文原文（或截图转录）。
2. 在 `roms/work/texts_translated.json` 或原盘 ROM 里用 PCS 编码搜偏移。
3. 判断：
   - **已在 texts、模块错/空** → 改 dump 带 / 关键词（本流水线）。
   - **texts 里没有短选项** → 同时扩 Meowth `MENU_LABEL_SEEDS` / `lexicon/短语.json`，下次 extract 才能扫到。
   - **乱码 / 定宽槽 / 疑图块** → 先写 `PENDING_TEXT_JP.md`，本流程不动图。

#### Step B — 测准模块带（`measure_module_spans.py`）

```powershell
cd C:\code\gba\tools\G3宝可梦解包
python measure_module_spans.py
```

脚本会：

| 来源 | 用途 |
|------|------|
| `FIXED_BANDS` | 名表、战斗 UI、开始菜单、存档与电源等固定池 |
| `SCRIPT_KEYWORDS` | 剧情/设施：关键词 → 模块，再聚成簇 |
| 商店 / PC / 中心 | 多段 `ranges`（对话紧簇 + 高位 UI 池） |
| `ROAD_CATCHALL` | 道路与洞窟大兜底；小带优先吃掉内部 |

写出并回写：

- `works/{ROM_ID}/measured_spans.json`
- `configs/{ROM_ID}.json`（及同布局的蓝宝石配置）

> 「缩小范围」= 收窄 `start`/`end`/`ranges`，禁止关整域剧本冒充。

#### Step C — dump 归类

```powershell
python text_patcher.py "C:\code\gba\tools\roms\origin\POKEMON_RUBY_AXVJ00.gba"
```

- 扫 ROM → `addr_bands.json`（每段文本体 `[lo,hi]`）
- 读 `configs/{ROM_ID}.json` → 匹配进模块 → `modules.json`

匹配规则（`assign_modules.py`）：

1. 模块可配 **`ranges` 多段**；无则用单一 `start`/`end`。
2. dump 带须**完全落入**某段；多段命中时取**跨度最小**者。
3. 产物里除 `addr_bands`（实际扫到的串）外，写入 **`geo_ranges`**（配置里的多段），供 Meowth 戳模块时用紧带，避免「只有 envelope、被邻居大包络抢走」。

#### Step D — 拷进 Meowth

```powershell
Copy-Item `
  "C:\code\gba\tools\G3宝可梦解包\works\{ROM_ID}\modules.json" `
  "C:\code\gba\configs\{ROM_ID}\translate\modules.json" `
  -Force
```

Meowth `modules.assign_module`：优先 `geo_ranges`，否则 `addr_bands`，再否则 `offset`/`end`。

#### Step E — 用户侧验收

重启 GUI → **重新 extract**（新短标种子）→ 翻译 / `start_gui.bat` 构建 → 自测。

### 补漏经验

| 现象 | 原因 | 做法 |
|------|------|------|
| 商店欢迎被标成宝可梦中心 | 同 bank 大包络 + 小区间未拆 | 商店用紧簇 `ranges`；`おかいもの` 关键词优先于中心 |
| 买/卖/没事 不在 texts | UI 池 `0x3E9Fxx` 未进短标 extract | `MENU_LABEL_SEEDS` + lexicon；商店加 `SHOP_UI_RANGES` |
| PC 菜单漏 | `0x3EBxxx` 超出原「开始菜单」上沿 | 扩 `PC_UI_RANGES` / 开始菜单上沿；模块归「电脑与仓库」 |
| 护士送客归 PC | dump 合并长带，整段分给 PC | 中心只用护士切片 `CENTER_EXTRA_RANGES`，勿吃 `0x1805xx` 整段 |
| 戳点仍错模块 | Meowth 只用 `addr_bands`，空则退回大 envelope | dump 写 `geo_ranges`；Meowth 优先读它 |
| 弹窗是/否仍日文 | `skip_zh` FC 前缀毒窗 | 见 PENDING；**不要**为补中文删 skip |
| `やめる` 仍日文 | 选宠取消同形黑屏史 | 不进种子/lexicon，先登记 |
| 存档/电池提示全日文 | 存档与电源 `start/end=0`；dump 合并大带无法整段落带 | `FIXED_BANDS` 多段紧带 + `geo_ranges`；`assign_modules` 对合并带按交集裁切 |

### 支持版本

| Game Code | ROM id |
|-----------|--------|
| AXVJ | POKEMON_RUBY_AXVJ00 |
| AXPJ | POKEMON_SAPP_AXPJ00 |
| BPRJ | POKEMON_FIRE_BPRJ00 |
| BPGJ | POKEMON_LEAF_BPGJ00 |
| BPEJ | POKEMON_EMERALD_BPEJ00 |

---

## 文本模块分类

### 地址族硬约束

| 地址族 | 美版码 | 日版码 | 说明 |
|--------|--------|--------|------|
| **RS** | AXVE / AXPE | AXVJ / AXPJ | 红宝石与蓝宝石**同布局** |
| **FRLG** | BPRE / BPGE | BPRJ / BPGJ | 火红与叶绿**同布局** |
| **Emerald** | BPEE | BPEJ | **单独**一作 |

- `module_map`：按 **ROM id** 各一份，放在 `configs/`。红/蓝可内容相同（RS 族），火/叶可内容相同（FRLG 族），Emerald 单独。
- 无实测地址的模块保留 `start`/`end`=`0x0`（不会匹配到 dump 带）。
- 日版相对美版会整体平移；同族内也须用 `text_patcher.py` + 指针槽实测填写 `start` / `end`。

### 公开锚点

#### FRLG 族

| 角色 | EN 参考（file offset） | 出处 |
|------|------------------------|------|
| 地图脚本主簇起 | ~`0x160458` | PokeCommunity LeafGreen Script Area |
| 宝中心 / 共享一带 | ~`0x1A4E8B`–`0x1BC2ED` | 同上 |
| 物种名表 | ~`0x245EE0` | Data Crystal Gen3 |
| 招式名表 | ~`0x247094` | 同上 |

#### RS 族

| 角色 | EN-Ruby 参考 | 出处 |
|------|--------------|------|
| 物种名表 | ~`0x1F7184` | Data Crystal Gen3 |
| 招式名表 | ~`0x1F8320` | 同上 |

#### Emerald 族

- **不要**套用 RS 或 FRLG 的绝对表基址。
- 只用 Emerald 专用表 / pokeemerald 反编译。

### 推荐分组与模块

#### 名表（`group`: `名表`）

| id | label | default | description |
|----|-------|---------|-------------|
| 物种名 | 名表·物种 | false | 物种名固定表 |
| 招式名 | 名表·招式 | true | 招式名固定表 |
| 特性名 | 名表·特性 | true | 特性名固定表 |
| 属性名 | 名表·属性 | true | 属性名短表（单字注入需谨慎） |
| 性格名 | 名表·性格 | false | 性格名表/指针体 |
| 道具名 | 名表·道具 | true | 道具结构内名称字段 |
| 训练家类名 | 名表·训练家类 | false | Trainer class 名表 |
| 地点名 | 名表·地点 | false | 地图/地区名表 |

#### 说明（`group`: `说明`）

| id | label | default | description |
|----|-------|---------|-------------|
| 道具说明 | 说明·道具 | true | 道具描述指针目标 |
| 招式说明 | 说明·招式 | false | 招式说明 |
| 特性说明 | 说明·特性 | false | 特性说明 |
| 图鉴条目 | 说明·图鉴条目 | false | 图鉴正文 |

#### 剧情（`group`: `剧情`）

| id | label | default | description |
|----|-------|---------|-------------|
| 开场家园 | 剧情·开场家园 | false | 家园镇、选角、博士开场 |
| 早期城镇 | 剧情·早期城镇 | false | 前期城镇/道馆主线 |
| 中期城镇 | 剧情·中期城镇 | false | 中期城镇主线 |
| 后期与联盟 | 剧情·后期联盟 | false | 后期城镇、联盟、冠军 |
| 岛屿或通关后 | 剧情·通关后 | false | 七岛/开拓区等 |
| 道路与洞窟 | 剧情·道路洞窟 | false | 路线、迷宫、洞窟类地图串 |

#### 设施（`group`: `设施`）

| id | label | default | description |
|----|-------|---------|-------------|
| 宝可梦中心 | 设施·宝可梦中心 | false | 护士、治疗、标准对白 |
| 商店 | 设施·商店 | false | 买卖与商店提示 |
| 电脑与仓库 | 设施·电脑 | false | PC/仓库菜单与提示 |
| 缆线与通信 | 设施·通信 | false | 联机/Wifi/神秘礼物 |
| 标准脚本串 | 设施·标准脚本 | false | obtain / yes-no / 告示牌等模板串 |

#### 界面（`group`: `界面`）

| id | label | default | description |
|----|-------|---------|-------------|
| 标题与主菜单 | 界面·标题主菜单 | false | 标题、继续/新游戏等 |
| 存档与电源 | 界面·存档 | false | 存档损坏、电池等系统提示 |
| 设置选项 | 界面·设置 | false | 选项菜单 |
| 背包界面 | 界面·背包 | false | 口袋标签、关闭等短 UI |
| 状态界面 | 界面·状态 | false | 宝可梦详情页标签 |
| 开始菜单 | 界面·开始菜单 | false | 图鉴/宝可梦/背包/保存/退出等 |

#### 战斗（`group`: `战斗`）

| id | label | default | description |
|----|-------|---------|-------------|
| 战斗菜单 | 战斗·菜单 | false | たたかう / バッグ 等 |
| 战斗提示 | 战斗·提示 | false | どうする？等短提示 |
| 战斗报文 | 战斗·报文 | false | 战斗字符串大表 |
| 对战设施 | 战斗·对战设施 | false | 对战塔等 |

#### 训练家（`group`: `训练家`）

| id | label | default | description |
|----|-------|---------|-------------|
| 登场与胜负白 | 训练家·对白 | false | 登场/胜/负文本池 |
| 训练家名 | 训练家·名称 | false | 训练家个体名 |

#### 其它

| id | label | default | description |
|----|-------|---------|-------------|
| 图鉴界面 | 图鉴·界面 | false | 搜索/模式/未知宝可梦等 UI |
| 姓名输入 | 起名·输入 | false | 五十音/键盘 |
| 默认名字 | 起名·默认名 | false | 男/女默认名列表 |
| 赛事娱乐 | 其它·赛事 | false | 华丽大赛/地下等 |
| 未归类 | 其它·未归类 | false | 未落入任何模糊带 |
| 高风险混杂 | 其它·高风险 | false | 与图形/选宠同页等易黑屏宽带 |

### 管理原则

1. **小表优先**：名表/短 UI 的 `end-start` 必须小于剧情大带；`assign_modules` 按跨度升序匹配。
2. **剧情按地理/进度命名**，不按 ROM 页号。
3. **设施共享与地图独有分开**，避免开一整块剧情时误伤全图宝中心。
4. **说明与名称分模块**，便于默认只开名表或只开说明。
5. **战斗报文 / 战斗菜单 / 地图剧情** 三分离。
6. **起名整类政策**，不按单字特例。
7. **绝对地址严禁跨族复制**；同族日版仍须实测。

### 配置字段

```json
{
  "id": "模块名",
  "label": "短标题",
  "group": "分组名",
  "default": true/false,
  "description": "简介",
  "start": 0x0,
  "end": 0x0,
  "ranges": [{"start": 0x0, "end": 0x0}, ...]
}
```

| 字段 | 说明 |
|------|------|
| `id` | 模块名（与 Meowth 勾选一致） |
| `label` / `group` / `default` / `description` | 展示与默认勾选 |
| `start` / `end` | 模糊包络（file offset；无实测可 `0x0`） |
| `ranges` | **可选**多段 `[{start,end}, …]`；散落商店、战斗双池、护士切片用这个 |

### 一键命令（红宝石日版）

```powershell
cd C:\code\gba\tools\G3宝可梦解包
python measure_module_spans.py
python text_patcher.py "C:\code\gba\tools\roms\origin\POKEMON_RUBY_AXVJ00.gba"
Copy-Item ".\works\POKEMON_RUBY_AXVJ00\modules.json" `
  "C:\code\gba\configs\POKEMON_RUBY_AXVJ00\translate\modules.json" -Force
```
