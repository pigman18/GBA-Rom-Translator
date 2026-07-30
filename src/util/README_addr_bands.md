# addr_bands 流水线（测准 → dump → Meowth）

从日版 Gen3 ROM 导出文本区间，按模块归类，再拷进 Meowth 做 extract 戳模块 / 注入勾选。

推荐分组见 [MODULE_TAXONOMY.md](MODULE_TAXONOMY.md)。  
截图残留日文 / 乱码登记见 Meowth [`docs/PENDING_TEXT_JP.md`](../tools/Meowth-GBA-Translator-JP/docs/PENDING_TEXT_JP.md)。

---

## 1. 目录约定

```
G3宝可梦解包/
  measure_module_spans.py     # 测准：写 configs 的 start/end/ranges
  dump_addr_bands.py          # 扫 ROM → addr_bands → 归类 modules.json
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

Meowth 消费副本：

`configs/{ROM_ID}/translate/modules.json`（仓库根下，与 `src/meowth` 同级）

ROM 路径（2026-07 起）：

- 原盘：`tools/roms/origin/`
- 成品：`tools/roms/outputs/`
- Meowth work：仓库根 `work/`（译文 JSON 等）

地址族：RS（红=蓝）、FRLG（火=叶）、Emerald 单独；**绝对地址严禁跨族复制**。

---

## 2. 端到端补全流程（日常）

漏对话 / 错模块 / 商店店员、PC 菜单未归类时，按此顺序，**不要手改成品 ROM**。

### Step A — 复现与定位（文本 only）

1. 记下屏上日文原文（或截图转录）。
2. 在 `roms/work/texts_translated.json` 或原盘 ROM 里用 PCS 编码搜偏移（file offset，非 `0x08……` 总线也可先减 `0x08000000`）。
3. 判断：
   - **已在 texts、模块错/空** → 改 dump 带 / 关键词（本流水线）。
   - **texts 里没有短选项** → 同时扩 Meowth `MENU_LABEL_SEEDS` / `lexicon/短语.json`，下次 extract 才能扫到。
   - **乱码 / 定宽槽 / 疑图块** → 先写 `PENDING_TEXT_JP.md`，本流程不动图。

### Step B — 测准模块带（`measure_module_spans.py`）

```powershell
cd C:\code\gba\tools\G3宝可梦解包
python measure_module_spans.py
```

脚本会：

| 来源 | 用途 |
|------|------|
| `FIXED_BANDS` | 名表、战斗 UI、开始菜单、**存档与电源** 等固定池 |
| `SCRIPT_KEYWORDS` | 剧情/设施：关键词 → 模块，再聚成簇 |
| 商店 / PC / 中心 | 多段 `ranges`（对话紧簇 + 高位 UI 池） |
| `ROAD_CATCHALL` | `道路与洞窟` 大兜底；**小带优先**吃掉内部 |

写出并回写：

- `works/POKEMON_RUBY_AXVJ00/measured_spans.json`
- `configs/POKEMON_RUBY_AXVJ00.json`（及同布局的蓝宝石配置）

**「缩小范围」= 收窄 `start`/`end`/`ranges`，禁止关整域剧本冒充。**

### Step C — dump 归类

```powershell
python dump_addr_bands.py "C:\code\gba\tools\roms\origin\POKEMON_RUBY_AXVJ00.gba"
```

- 扫 ROM → `addr_bands.json`（每段文本体 `[lo,hi]`）
- 读 `configs/{ROM_ID}.json` → 匹配进模块 → `modules.json`

匹配规则（`assign_modules.py`）：

1. 模块可配 **`ranges` 多段**；无则用单一 `start`/`end`。
2. dump 带须**完全落入**某段；多段命中时取**跨度最小**者。
3. 产物里除 `addr_bands`（实际扫到的串）外，写入 **`geo_ranges`**（配置里的多段），供 Meowth 戳模块时用紧带，避免「只有 envelope、被邻居大包络抢走」。

### Step D — 拷进 Meowth

```powershell
Copy-Item `
  "C:\code\gba\tools\G3宝可梦解包\works\POKEMON_RUBY_AXVJ00\modules.json" `
  "C:\code\gba\configs\POKEMON_RUBY_AXVJ00\translate\modules.json" `
  -Force
```

Meowth `modules.assign_module`：优先 `geo_ranges`，否则 `addr_bands`，再否则 `offset`/`end`；**有紧带时不要再用粗 envelope 吞中间表**。

### Step E — 用户侧验收

重启 GUI → **重新 extract**（新短标种子）→ 翻译 / `start_gui.bat` 构建 → 自测。  
代理默认不代打 ROM、不开模拟器。

---

## 3. 配置字段

### 3.1 `configs/{ROM_ID}.json`（module_map）

| 字段 | 说明 |
|------|------|
| `id` | 模块名（与 Meowth 勾选一致） |
| `label` / `group` / `default` / `description` | 展示与默认勾选 |
| `start` / `end` | 模糊包络（file offset；无实测可 `0x0`） |
| `ranges` | **可选**多段 `[{start,end}, …]`；散落商店、战斗双池、护士切片用这个 |

### 3.2 `works/.../modules.json`（dump 产物）

| 字段 | 说明 |
|------|------|
| `addr_bands` | 本模块实际分到的文本体区间（可能为空：配置有带但 ROM 扫不到串） |
| `geo_ranges` | 从配置 `ranges` 原样带出；Meowth 戳点优先用 |
| `offset` / `end` | 包络，名表等用 |

---

## 4. 补漏经验（AXVJ 已踩坑）

| 现象 | 原因 | 做法 |
|------|------|------|
| 商店欢迎被标成宝可梦中心 | 同 bank 大包络 + 小区间未拆 | 商店用紧簇 `ranges`；`おかいもの` 关键词优先于中心 |
| 买/卖/没事 不在 texts | UI 池 `0x3E9Fxx` 未进短标 extract | `MENU_LABEL_SEEDS` + lexicon；商店加 `SHOP_UI_RANGES` |
| PC 菜单漏 | `0x3EBxxx` 超出原「开始菜单」上沿 | 扩 `PC_UI_RANGES` / 开始菜单上沿；模块归「电脑与仓库」 |
| 护士送客归 PC | dump 合并长带，整段分给 PC | 中心只用护士切片 `CENTER_EXTRA_RANGES`，勿吃 `0x1805xx` 整段 |
| 戳点仍错模块 | Meowth 只用 `addr_bands`，空则退回大 envelope | dump 写 `geo_ranges`；Meowth 优先读它 |
| 弹窗是/否仍日文 | `skip_zh` FC 前缀毒窗 | 见 PENDING；**不要**为补中文删 skip |
| `やめる` 仍日文 | 选宠取消同形黑屏史 | 不进种子/lexicon，先登记 |
| 存档/电池提示全日文 | 「存档与电源」`start/end=0`；dump 合并大带无法整段落带 | `FIXED_BANDS` 多段紧带 + `geo_ranges`；`assign_modules` 对合并带按交集裁切 |

测准脚本里相关常量：`FIXED_BANDS`、`SCRIPT_KEYWORDS`、`SHOP_UI_RANGES`、`PC_UI_RANGES`、`CENTER_EXTRA_RANGES`。

---

## 5. 一键命令（红宝石日版）

```powershell
cd C:\code\gba\tools\G3宝可梦解包
python measure_module_spans.py
python dump_addr_bands.py "C:\code\gba\tools\roms\origin\POKEMON_RUBY_AXVJ00.gba"
Copy-Item ".\works\POKEMON_RUBY_AXVJ00\modules.json" `
  "C:\code\gba\configs\POKEMON_RUBY_AXVJ00\translate\modules.json" -Force
```

可选自检（模块戳点）：

```powershell
python -c "
from pathlib import Path
import sys
sys.path.insert(0, r'C:\code\gba\src')
from meowth.config_loader import set_active_game_id, _modules_cache
from meowth.modules import stamp_entry_module
_modules_cache.clear(); set_active_game_id('POKEMON_RUBY_AXVJ00')
for a in ['0x081806BA','0x083E9F28','0x083EB41C','0x08180545','0x083EBD9B']:
    print(a, stamp_entry_module({'address': a, 'original': 'x'}, game_id='POKEMON_RUBY_AXVJ00'))
"
```

期望大致：商店欢迎/买选项 → `商店`；PC 菜单 → `电脑与仓库`；护士送客 → `宝可梦中心`；存档写盘提示 → `存档与电源`。
---

## 6. 支持版本

| Game Code | ROM id |
|-----------|--------|
| AXVJ | POKEMON_RUBY_AXVJ00 |
| AXPJ | POKEMON_SAPP_AXPJ00 |
| BPRJ | POKEMON_FIRE_BPRJ00 |
| BPGJ | POKEMON_LEAF_BPGJ00 |
| BPEJ | POKEMON_EMERALD_BPEJ00 |

从旧 game.json 总结地图（少用）：

```bash
python assign_modules.py --from-gamejson path\to\game.json -o configs\POKEMON_RUBY_AXVJ00.json
```
