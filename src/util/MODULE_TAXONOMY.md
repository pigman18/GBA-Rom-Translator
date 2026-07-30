# Gen3 文本管理：分组与模块分类

按**文本角色**划分 group / module，供 `*.module_map.json` 使用。  
三套地址族共用同一套语义名单；**绝对地址严禁跨族复制**。

相关流水线见 [README_addr_bands.md](README_addr_bands.md)。  
配置：`configs/{ROM_ID}.json`（例 `configs/POKEMON_RUBY_AXVJ00.json`）；空模板 `configs/_template.json`。  
产物：`works/{ROM_ID}/modules.json`（及同目录 `addr_bands.json`）。

---

## 1. 地址族硬约束

| 地址族 | 美版码（例） | 日版码（例） | 说明 |
|--------|--------------|--------------|------|
| **RS** | AXVE / AXPE | AXVJ / AXPJ | 红宝石与蓝宝石**同布局** |
| **FRLG** | BPRE / BPGE | BPRJ / BPGJ | 火红与叶绿**同布局** |
| **Emerald** | BPEE | BPEJ | **单独**一作，与上两套都不同 |

- `module_map`：按 **ROM id** 各一份，放在 `configs/`（如 `POKEMON_RUBY_AXVJ00.json`）。红/蓝可内容相同（RS 族），火/叶可内容相同（FRLG 族），Emerald 单独；**绝对地址仍严禁跨族复制**。
- 无实测地址的模块保留 `start`/`end`=`0x0`（不会匹配到 dump 带）。
- 社区 / Data Crystal 表里「Fire Red 列」与「Ruby 列」是两套数：只可同族内参考「表角色 / 相对疏密」，不可把 FR 绝对地址填进 Ruby（或反过来）。
- 日版相对美版还会整体平移；同族内也须用 `dump_addr_bands.py` + 指针槽实测填写 `start` / `end`。

---

## 2. 公开锚点（按族标注，美版为主）

下列为社区公开的**大区间参考**，不是日版真值。

### 2.1 FRLG 族（火红 = 叶绿）

| 角色 | EN 参考（file offset） | 出处 |
|------|------------------------|------|
| 地图脚本主簇起 | ~`0x160458` | [PokeCommunity LeafGreen Script Area](https://www.pokecommunity.com/threads/eventual-complete-map-of-the-script-area-and-beyond-of-leaf-green.241925/) |
| 早期地图字符串池 | ~`0x172231` | 同上（串在脚本后） |
| 宝中心 / 共享 / Wifi 一带 | ~`0x1A4E8B`–`0x1BC2ED` | 同上 |
| 物种名表 | ~`0x245EE0` | [Data Crystal Gen3](https://datacrystal.tcrf.net/wiki/Pok%C3%A9mon_3rd_Generation) / Offset Reference |
| 招式名表 | ~`0x247094` | 同上 |
| 道具结构 | ~`0x3DB028` | 同上 |
| 图鉴数据 | ~`0x44E850` | 同上 |

组织习惯：同一 map 的脚本成簇，**字符串跟在该图脚本后**；宝中心 / 联机等共享段另聚。

### 2.2 RS 族（红 = 蓝）

| 角色 | EN-Ruby 参考（蓝宝石同） | 出处 |
|------|--------------------------|------|
| 物种名表 | ~`0x1F7184` | Data Crystal Gen3（Ruby 列） |
| 招式名表 | ~`0x1F8320` | 同上 |
| 道具结构 | ~`0x3C5580` | 同上 |
| 图鉴数据 | ~`0x3B1874` | 同上 |

语义分类可参考 pret [pokeruby `strings.h`](https://github.com/pret/pokeruby/blob/master/include/strings.h)（系统 / 主菜单 / 博士 / 图鉴 UI）与 `data/maps/*/scripts`（每图文本）。

### 2.3 Emerald 族

- **不要**套用 RS 或 FRLG 的绝对表基址。
- 多对战开拓区等扩展文本；偏移只用 Emerald 专用表 / [pokeemerald](https://github.com/pret/pokeemerald) 反编译。

---

## 3. 推荐分组与模块

`group` = 下表分组名；`id` = 模块名（生成 `modules.json` 时作 key）。  
三族共用此名单；剧情模块按**地理/进度**命名，**不按 ROM 64KB 页号**。

### 3.1 名表（`group`: `名表`）

固定 stride / 指针表；模糊带应最小，assign 时优先吃掉。

| id | label | default 建议 | description |
|----|-------|--------------|-------------|
| 物种名 | 名表·物种 | false（出宠风险高时可关） | 物种名固定表 |
| 招式名 | 名表·招式 | true | 招式名固定表 |
| 特性名 | 名表·特性 | true | 特性名固定表 |
| 属性名 | 名表·属性 | true | 属性名短表（单字注入需谨慎） |
| 性格名 | 名表·性格 | false | 性格名表/指针体 |
| 道具名 | 名表·道具 | true | 道具结构内名称字段 |
| 训练家类名 | 名表·训练家类 | false | Trainer class 名表 |
| 地点名 | 名表·地点 | false | 地图/地区名表（若独立） |

### 3.2 说明（`group`: `说明`）

长文与名表分离。

| id | label | default 建议 | description |
|----|-------|--------------|-------------|
| 道具说明 | 说明·道具 | true | 道具描述指针目标 |
| 招式说明 | 说明·招式 | false | 招式说明 |
| 特性说明 | 说明·特性 | false | 特性说明 |
| 图鉴条目 | 说明·图鉴条目 | false | 图鉴正文 |

### 3.3 剧情（`group`: `剧情`）

按地理/进度切模糊带（FRLG 关都名；RS 换成丰缘对应进度即可）。

| id | label | default 建议 | description |
|----|-------|--------------|-------------|
| 开场家园 | 剧情·开场家园 | false | 家园镇、选角、博士开场 |
| 早期城镇 | 剧情·早期城镇 | false | 前期城镇/道馆主线 |
| 中期城镇 | 剧情·中期城镇 | false | 中期城镇主线 |
| 后期与联盟 | 剧情·后期联盟 | false | 后期城镇、联盟、冠军 |
| 岛屿或通关后 | 剧情·通关后 | false | 七岛 / 开拓区等（有则开） |
| 道路与洞窟 | 剧情·道路洞窟 | false | 路线、迷宫、洞窟类地图串 |

### 3.4 设施（`group`: `设施`）

到处复用的共享段，与地图独有剧情分开。

| id | label | default 建议 | description |
|----|-------|--------------|-------------|
| 宝可梦中心 | 设施·宝可梦中心 | false | 护士、治疗、标准对白 |
| 商店 | 设施·商店 | false | 买卖与商店提示 |
| 电脑与仓库 | 设施·电脑 | false | PC / 仓库菜单与提示 |
| 缆线与通信 | 设施·通信 | false | 联机 / Wifi / 神秘礼物 |
| 标准脚本串 | 设施·标准脚本 | false | obtain / yes-no / 告示牌等模板串 |

### 3.5 界面（`group`: `界面`）

| id | label | default 建议 | description |
|----|-------|--------------|-------------|
| 标题与主菜单 | 界面·标题主菜单 | false | 标题、继续/新游戏等 |
| 存档与电源 | 界面·存档 | false | 存档损坏、电池等系统提示 |
| 设置选项 | 界面·设置 | false | 选项菜单 |
| 背包界面 | 界面·背包 | false | 口袋标签、关闭等短 UI |
| 状态界面 | 界面·状态 | false | 宝可梦详情页标签（非图鉴条目） |
| 开始菜单 | 界面·开始菜单 | false | 图鉴/宝可梦/背包/保存/退出等 |

### 3.6 战斗（`group`: `战斗`）

| id | label | default 建议 | description |
|----|-------|--------------|-------------|
| 战斗菜单 | 战斗·菜单 | false | たたかう / バッグ 等（PCS 或图块另册） |
| 战斗提示 | 战斗·提示 | false | 「どうする？」等短提示 |
| 战斗报文 | 战斗·报文 | false | 战斗字符串大表 |
| 对战设施 | 战斗·对战设施 | false | 对战塔等（Emerald 更重） |

### 3.7 训练家（`group`: `训练家`）

| id | label | default 建议 | description |
|----|-------|--------------|-------------|
| 登场与胜负白 | 训练家·对白 | false | 登场 / 胜 / 负文本池 |
| 训练家名 | 训练家·名称 | false | 训练家个体名（若与类名分表） |

### 3.8 图鉴（`group`: `图鉴`）

| id | label | default 建议 | description |
|----|-------|--------------|-------------|
| 图鉴界面 | 图鉴·界面 | false | 搜索/模式/未知宝可梦等 UI；条目正文归「图鉴条目」 |

### 3.9 起名（`group`: `起名`）

| id | label | default 建议 | description |
|----|-------|--------------|-------------|
| 姓名输入 | 起名·输入 | false | 五十音/键盘；政策常整类留日 |
| 默认名字 | 起名·默认名 | false | 男/女默认名列表 |

### 3.10 其它（`group`: `其它`）

| id | label | default 建议 | description |
|----|-------|--------------|-------------|
| 赛事娱乐 | 其它·赛事 | false | 华丽大赛/地下等（多见于 RS/Emerald） |
| 未归类 | 其它·未归类 | false | dump 未落入任何模糊带（亦可由 assign 的 unassigned 承担） |
| 高风险混杂 | 其它·高风险 | false | 与图形/选宠同页等易黑屏宽带；默认关，不当「缩小剧情」替身 |

---

## 4. 管理原则

1. **小表优先**：名表/短 UI 的 `end-start` 必须小于剧情大带；`assign_modules` 按跨度升序匹配。
2. **剧情按地理进度命名**，不按 ROM 页号（禁止「剧情1=0x10 页」当产品语义）。
3. **设施共享与地图独有分开**，避免开一整块剧情时误伤全图宝中心。
4. **说明与名称分模块**，便于默认只开名表或只开说明。
5. **战斗报文 / 战斗菜单 / 地图剧情** 三分离。
6. **起名整类政策**，不按单字特例。
7. **绝对地址严禁跨族复制**；同族日版仍须实测。

---

## 5. 与 module_map 字段对应

| 字段 | 含义 |
|------|------|
| `id` | 上表模块 id |
| `label` | 短标题 |
| `group` | 分组名 |
| `default` | 是否默认勾选 |
| `description` | 简介 |
| `start` / `end` | 本族实测模糊带（file offset） |
| `ranges` | 可选多段；散落 UI / 设施切片（见 README） |

匹配规则：dump 出的 `addr_bands` 须**完全落入**某模块的一段 `[start,end]` 或 `ranges[]`；多个命中时取**跨度最小**者。产物另带 `geo_ranges` 供 Meowth 戳点。

**补全 addr_bands 的完整步骤（测准 → dump → 拷 Meowth）见 [README_addr_bands.md](README_addr_bands.md) §2。**