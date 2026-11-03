# bot 场景覆盖表（POKEMON_RUBY_AXVJ00）

> 目的：**重写 text 引擎之前，先把「回归验证面」立起来。**
> 没有这一层，重写之后只能靠肉眼翻截图，无法判断是变好了还是换了个坏法。

跑法（两侧共用同一份 .sav，自动读 `saves/scene_saves.json`）：

```bash
python bot/run.py POKEMON_RUBY_AXVJ00 <scene>          # 采集
python bot/run.py POKEMON_RUBY_AXVJ00 <scene> --verify  # 采集 + 判据
```

`verify.py` 需要 numpy + Pillow，系统 python 里没有。用隔离环境里的解释器：

```
C:\Users\pigman\.workbuddy\binaries\python\envs\default\Scripts\python.exe
```

（`--verify` 走的是 `sys.executable`，所以用上面这个解释器启动 `run.py` 才会自动带上）

---

## 0. 导出规格（schema 3，2026-10-22 修正）

每帧产出：

| 文件 | 区间 | 大小 |
|---|---|---|
| `NNN.vram.bin` | `0x06000000 + 0x18000`（全部 VRAM） | 96 KB |
| `NNN.pal.bin` | `0x05000000 + 0x400` | 1 KB |
| `NNN.io.bin` | `0x04000000 + 0x60`（DISPCNT…BLDCNT） | 96 B |
| `NNN.oam.bin` | `0x07000000 + 0x400` | 1 KB |
| `NNN.ram.bin` | **`0x02000000 + 0x40000`（全 EWRAM）** + **`0x03000000 + 0x8000`（全 IWRAM）** | 288 KB |

**schema 2 → 3 的改动**：`ram.bin` 原来是 `EWRAM 0x02020000+0x20000 | IWRAM+0x800`（130 KB），
缺 EWRAM 低 128 KB、IWRAM 只剩 2 KB。两个缺口都实际卡过分析：
低半 EWRAM 里的结构看不见；IWRAM 2 KB 之外的状态（例如将来字形槽表的候选放置区）看不见。

布局现在写进 `manifest.json` 的 `dumps` 字段，**离线读取方不要再按文件长度猜**。
schema 2 的旧批次仍是旧布局，靠 `manifest.schema` 区分。

### 这套导出够不够用（实测判据）

用 `scripts/font/match_vram_glyphs.py` 把每个采集帧的 VRAM tile 按「nibble 去调色板化」归一化，
再和 ROM 里的 256 个字形图样比对：

| 场景 | 帧数 | 命中字模 tile |
|---|---|---|
| bag_sweep | 34 | 15631 |
| bag | 24 | 10641 |
| options_sweep | 22 | 9567 |
| options | 19 | 8082 |
| pokemon_menu | 17 | 7470 |
| dex | 13 | 5722 |
| font_capture | 9 | 2514 |
| start_menu | 11 | 896 |
| font_talk | 8 | 128 |

→ **字模在 VRAM 里可稳定定位**，导出可用于字形级验收，不必为了「看一眼字」再跑 bot。

---

## 1. 框架能力（2026-10-18 这一轮加固）

| 能力 | 解决什么 | 位置 |
|---|---|---|
| **窗口真实性校验** | 裸扫 win 结构假阳性 7/7。现在要求 `tpl` 页的 `charBase/tileData/tilemap` 与**已开启 BG 图层的寄存器**逐项相等 | `bot/bot.lua` `win_is_real()` |
| **`talk` 对话闸门** | 场景按 A 打空也照样产出「合法对照」。现在必须观察到**文本真的在推进**（新窗口 / 文本指针变化 / 打印下标变化 / 窗口关闭），否则整场景硬失败 | `bot.lua` `PHASE=talk_*` |
| **`walk` 持续按住** | 旧版「按固定帧数再松手」把时长和格数绑死，换方向就漂。现在每帧读坐标，**一到位当帧松手**；按住 40 帧没挪格判 BLOCKED | `bot.lua` `settle_step` pos 分支 |
| **`[POS]` 站位日志** | 写场景不必靠截图数格子，跑完直接看日志里角色在哪一格 | `bot.lua` `snapshot()` |
| **场景默认存档** | 不同场景对地图有硬要求（室内/野外），不必每次手写 `--save` | `saves/scene_saves.json` + `run.py` |

**已验证效果**：bag 场景 24 张截图 = 24 条窗口记录（校验前是 140 条），对话场景两次 `talk` 均命中、
两侧帧号差 ≤ 2 帧。

---

## 2. 场景清单

| 场景 | 默认存档 | 目标界面 | 覆盖的已知问题 | 闸门 |
|---|---|---|---|---|
| `selfcheck` | Route118 | 野外 / 开始菜单 | 框架健康度（prove + settle + 按键响应） | await(title) + prove |
| `start_menu` | Route118 | 开始菜单 8 项逐项 | 菜单项短词 | settle |
| `pokemon_menu` | Route118 | 队伍列表 + 查看能力 4 页 | **B08（六行同名）**、摘要页长句 | settle |
| `bag` | Route118 | 背包 → 道具子菜单 → **「使用」说明框（2 页）** → 四口袋 → 滚到底 | **BUG 1 撞 UI**（说明框横穿列表）、**BUG 2 残留**（翻页后第 1 页字模不清） | settle |
| `dialogue` | MauvilleCity_Mart | 柜台对话 → 商店主菜单 → 购买列表 → 告别 → 重开 | **BUG 2 残留**（同窗反复重写）、多窗口同屏 | `talk`（硬） |
| `navigator` | Route118 | ポケナビ主菜单 5 项 + トレーナーアイ 列表 | **BUG 3 左侧背景被涂**、说明句整句重画 | settle |
| `dex` | Route118 | 图鉴列表翻页 | 宝可梦名 + 分类名（最长文本之一） | settle |
| `trainer_card` | Route118 | 训练家卡片正反面 | 标签 + 徽章图形混排（撞图形） | settle |
| `options` | Route118 | 设置菜单 | 大量文字（相似度天然 ~0.77） | await |
| `battle` | Route118 | 遇敌 → 战斗（单帧） | 战斗文本 | walk(soft) |
| **`battle_full`** | Route118 | **遇敌 → 转场 → 开场台词 → 战斗主菜单四项 → 招式列表 → 队伍 → 逃跑** | **Small(8×8) 主战场**：我方/敌方名+等级、HP「77/115」、招式名+PP「31/35」、属性名 | `poke`(钉RNG) + `hunt` + `await` |
| `_probe_talk` | MauvilleCity_Mart | 四方向各按一次 A | **诊断**：找哪一面有可对话 NPC | 无（故意打空） |
| `_probe_use` | Route118 | 背包「学习装置 → 使用 → A/B 各推几下」 | **诊断**：确认说明框几页、退回到哪一层 | 无 |
| `_probe_hunt` `_probe_hunt2` | Route118 | 遇敌搜捕可行性 | **诊断**：验证 hunt / 钉RNG | 无 |
| **`gym_mauville`** | Route118 | **Mauville 道馆 `10:0`**：进馆 → 训练家对话 | 道馆训练家台词、室内多 NPC | `poke`+`warp`+`talk` |
| **`contest_hall`** | Route118 | **华丽大赛大厅 `5:1`**（Fallarbor） | 大赛报名/柜台文本、会场 NPC | `poke`+`warp` |

---

## 2.2 ★ 精确跳图（2026-11-03 跑通）—— 跳场景就用它

```lua
api.warp{ map = "10:0", x = 5, y = 8, mon = 1 }
```

原理：写 `SaveBlock1.lastHealLocation`（`+0x1C`）+ 用传送术，
走 `Overworld_ResetStateAfterTeleport → WarpIntoMap` 那条路。
实测 `(23,17) map=0:2` → `(68,7) map=0:33`，**坐标一字不差**。

**前置**：存档里要有会传送术的宝可梦，用
`python scripts/warp_tool.py --apply --out work/teleport.sav` 植入一次。

### 已验证可直达的地图 ID

日版 group 顺序与美版**在 0 / 2 / 10 / 5 组上完全一致**（用实测点校准过，
见 `scripts/map_ids.py`）：

| 地图 | ID | 用途 | 实测 |
|---|---|---|---|
| MauvilleCity_Gym | **10:0** | 道馆 | ✅ `warp` 命中，截图确认是道馆内部 |
| MauvilleCity_Mart | 10:7 | 商店（原存档点） | ✅ 读档即在此 |
| FallarborTown_ContestLobby | **5:1** | 华丽大赛大厅 | ✅ `warp` 命中，截图见到柜台/接待 |
| FallarborTown_ContestHall | 5:2 | 大赛会场 | 未试 |
| SlateportCity_ContestLobby | 9:2 | 大赛大厅（另一城） | 未试 |
| LilycoveCity_ContestLobby | 13:4 | 大赛大厅（最大会场） | 未试 |
| MauvilleCity | 0:2 | 该市户外 | ✅ |
| Route118 / Route119 | 0:33 / 0:34 | 野外 | ✅ |

### ⚠ 两个使用注意

1. **一个场景只做一次 warp**。连续第二次会 TIMEOUT（菜单状态未归位）。
   要多次跳图请拆成多个 scene —— 这也正是用户建议的做法。
2. **落点要选地图内可走区域**。华丽大赛 Lobby 用 `(10,10)` 会落在地图外的黑屏里，
   改 `(8,5)` 才正常。落点不对时看 `ct_lobby` 截图再调。

### 朝向错了会白按 A

道馆场景一开始从 `(5,3)` 朝 UP 按 A，`talk` 闸门直接报「没打到对话」。
换成 **LEFT** 才成功——这个方向是**实测出来的**：四方向逐点试 A，
事后按 VRAM tilemap 差异排序，差异最大那帧（diff=102562 vs 其他 <98000）
对应的动作就是 `gn2_a_LEFT`，画面确实是训练家对话。

---

## 2.3 ★ 用生成器铺场景（2026-11-03）

窗口覆盖要采十几张室内地图，手写会大量重复且容易漏掉「连帧」「闸门」。
`scripts/gen_scenes.py` 把套路固化，改一处全部更新。

```powershell
python scripts/gen_scenes.py                  # 列出全部场景定义
python scripts/gen_scenes.py --emit           # 全部生成
python scripts/gen_scenes.py --emit --only gym_dewford
```

三种套路：

| 模式 | 适用 | 做法 |
|---|---|---|
| `counter` | 柜台/店员（商店、PC、自行车店） | 走到柜台 → **四方向各试 talk（soft）** → 逐句推进 → 试菜单列表 |
| `gym` | 道馆 | **两段扫**：先竖扫 6 格，再蛇形；每格四方向试 A |
| `interior` | 普通室内（大赛会场） | 蛇形走位 + 每格四方向试 A |

### 生成器踩过的两个坑

1. **模板花括号**：`HEADER` 走 `.format()` 后 `{{` 变 `{`，但 BODY 若直接拼接
   会留下未替换的 `{prefix}` 和 `{{` ⇒ mGBA 报 `scene load failed: nil`。
   BODY 也必须走 `.format()`。
2. **漏 `return api.S`**：dofile 返回 nil，bot.lua 判 `type(STEPS) ~= "table"`
   直接失败，症状同样是 `scene load failed: nil`。

### 覆盖实测（25 个场景）

```
合计：约 2800 帧，其中 2160+ 帧含真实窗口（经 win_is_real 校验）
去重后的 window template 地址：17 个
```

| 场景 | 帧 | 有窗口帧 | 说明 |
|---|---|---|---|
| center_mauville / center_oldale / center_slateport | 181 | **164** | PC 柜台对话 + 菜单 |
| mart_oldale / mart_slateport | 181 | **164** | 商店买卖列表 |
| bikeshop_mauville | 181 | **139** | 四方向试 talk 后从 1 → 139 |
| bag | 144 | 144 | |
| battle_full | 127 | 107 | 含 fontNum=4 的 Small 帧 |
| gym_mauville | 125 | **109** | |
| gym_rustboro | 123 | **86** | 两段扫后 30 → 86 |
| gym_lavaridge | 123 | **57** | 两段扫后 31 → 57 |
| contest_slateport | 103 | **86** | |
| navigator / options / pokemon_menu / start_menu / dex | 56–115 | 全覆盖 | |
| contest_hall | 78 | 59 | |
| **gym_dewford** | 123 | **1** | ⚠ 见下 |
| **contest_lilycove** | 103 | 1 | ⚠ 见下 |
| **gamecorner_mauville** | 181 | 1 | ⚠ 见下 |

### 补齐两个缺口（2026-11-03 第二轮）

**`gamecorner_mauville`：1 → 81 帧有窗口**

原因是主角落点 `(8,10)` **紧贴老虎机台**，直接 UP 被挡。改成
**先 RIGHT 绕 2 格再 UP**（`counter_left` 模式）后解决。

**`bikeshop_mauville`：先改坏了，又改回来**

我一度把侧移加到所有 counter 场景，结果 bikeshop 从 139 掉到 1。
对比两次日志才看清：

| 路径 | 站位 | 结果 |
|---|---|---|
| 先 UP 4 格 | **(6,5)** | **137/139 帧** ✅ |
| 先 RIGHT 2 格 → UP | **(9,2)** | 1 帧（墙边，全超时）❌ |

⇒ 侧移会把 bikeshop 带到墙边。**按场景分开**：bikeshop 用普通 `counter`，
gamecorner 用 `counter_left`。

**最终两种 counter 模式**

| 模式 | 适用 | 做法 |
|---|---|---|
| `counter` | 商店 / 宝可梦中心 / 自行车店 | 先 UP 4 格 → 四方向试 talk（soft） |
| `counter_left` | 游戏厅（紧贴老虎机） | 先 RIGHT 2 格 → UP 4 格 → 四方向试 talk |

### 最终覆盖（14 个室内场景）

| 场景 | 有窗口帧 | 场景 | 有窗口帧 |
|---|---|---|---|
| center_mauville | **311** | gym_mauville | **109** |
| center_oldale | **311** | gym_rustboro | **86** |
| center_slateport | **311** | contest_slateport | **86** |
| mart_oldale | **164** | gamecorner_mauville | **81** |
| mart_slateport | **164** | contest_hall | **59** |
| bikeshop_mauville | **111** | gym_lavaridge | **57** |
| **gym_dewford** | **1** ⚠ | **contest_lilycove** | **1** ⚠ |

### 剩下两个缺口的根因（已查明，非路径问题）

**`gym_dewford`（123 帧仅 1 窗口）**

这是**溜冰迷宫道馆**。实测：
- 落点 `(8,15)` 能走到 `(2,7)`（左上角），一路 21 步没问题
- 但 `(2,7)` 左侧是大片虚空，NPC 在**墙的另一侧**
- 逐格四方向试 A 共 40+ 次，全部超时
- 试过用 object 表坐标定位：解出 4 个固定坐标
  `(8,17)(9,24)(12,31)(19,31)`，但**都不是可对话 NPC**（是门/箱子/楼梯）

⇒ 要进道馆深处必须用**溜冰推箱机制**，不是走位能到。

**`contest_lilycove`（103 帧仅 1 窗口）**

放大截图后确认：会场里那两个“人形”其实是**盆栽装饰**，
右上角深色物体是**家具/展台**。这个大厅里**没有可对话 NPC**——
报名要走到特定柜台触发脚本，而柜台位置未知。

⇒ 它不是“没走到”，是**这张图本身没有走动触发的对话点**。

> 这两处要补齐，正确做法是**读地图事件表**（`ObjectEventTemplate` 的
> script 字段）拿到真正带脚本的对象坐标。但 object 表在日版的偏移
> 与符号表不符（本项目已多次验证），需要先花一轮把结构定死。

---

## 2.1 2026-11-03 新增的三个 bot 动作

| 动作 | 作用 | 用法 | 关键约束 |
|---|---|---|---|
| `burst(prefix, n, every)` | **多帧连续采集** | `api.burst("bt_menu", 20, 8)` | 只出 PNG（全量 dump 每帧 385KB），落名 `<prefix>_01..NN` |
| `poke(writes)` | **金手指：写实时内存** | `api.poke{ {addr=0x03004818, width=4, value=0xAAAA} }` | **必须在 prove 之后**（顺序铁律）；写后自动复核读回值 |
| `hunt{dir,x,y,steps}` | **遇敌搜捕**：逐格走，`DISPCNT≠0x7F60` 立刻停 | `api.hunt{ dir="DOWN", steps=40 }` | 撞墙自动掉头；走满没遇到会记 `gave-up`，由后续 `await` 判定 |

**`poke` 的两道硬门槛**（用户口径「先加载 .sav 再用金手指」）：
1. 运行时：`SB2_RUNTIME == nil` ⇒ 拒绝（等价于「存档没进内存」）
2. 运行时：`DISPCNT == 0x1741`（标题）或 `0x3140`（继续游戏菜单）⇒ 拒绝
3. 准备期：`_lib.poke()` 断言此前已有 `prove` 步骤，顺序写错在开跑前就炸

**确定性遇敌的最终方案**（实测 6 轮定下来，勿再改）：

```
prove → poke 钉 gRngValue(0x03004818)=0x0000AAAA → hunt → await{any_of={0x0000,0xBF40}}
```

| 试过 | 结果 |
|---|---|
| 只钉 RNG（逐格递增） | 两侧遇敌格差 1（origin 第7 / translated 第6） |
| 只 hunt | translated 侧 30 格没遇到，纯随机 |
| 只钉一次 RNG + hunt | **两侧都在第 5 / 第 7 格遇敌，完全一致** ✅ |

> 为什么「差 1 格」治不掉：两侧写入的 RNG 序列**逐值相同**、走位坐标**逐格相同**，
> 说明还有帧号相关判定参与遇敌。`hunt` 把这点差异吸收在内部（一遇敌就停），
> 后面全部从战斗画面对齐。


---

## 3. 已知陷阱（都踩过，写下来省下一轮）

1. **带 RNG 的场景不能当对照。**
   野外草丛按 A 会触发野生遭遇；两侧文字打印耗时不同 ⇒ settle 时长不同 ⇒
   按键落在不同游戏帧 ⇒ 遭遇判定分岔。实测 translated 拍到战斗转场、origin 还在
   野外，却被记成 11 对「合法对照」。**对话类场景必须换室内存档。**
2. **AXVJ 的文本窗口在野外也「一直存在」。**
   `tpl=0x081BB46C` / `BG0` 的窗口在野外 HUD 上常驻（`index=11`、text 指针固定）。
   所以「有合法窗口」≠「对话开了」，必须看**文本指针/打印下标有没有变**。
3. **`OldaleTown_PokemonCenter_1F_5-5.sav` 是废的。**
   载入后 `prove` 报 `loc=2:2 / pos=(5,5)`，但画面仍是 Route118 地形 —— warp 没生效。
   室内场景统一用 `MauvilleCity_Mart_3-3.sav`。
4. **B 在商店里是逐层退出**：购买列表 → 商店主菜单 → 告别语 → 野外，一共四下。
   少按一下，下一次 `talk` 会去推告别语，看起来像「A 打空」。
5. **`walk` 的 BLOCKED 不一定是错**：贴到 NPC/柜台面前本来就该停住，
   真正的到位由后续 `talk` 验证，所以走位用 `soft=true`。
6. **「使用」装备类道具只播说明，不改存档**：学习装置按「使用」出的是
   `おとうさんの ことば‥‥` 两页说明（译文 `爸爸的话……\p用！`），退回列表后仍是
   ×2，所以可以放心采；「携带 / 丢弃」才会动宝可梦持物，绝不能按。
7. **打印动画不用手动等**：settle 会一直等画面稳定，截到的都是「这一页打完、
   停在 ▼」的定型帧 —— 正好是要验收的那一帧，不必为打字动画加 `wait`。

---

## 4. 重写 text 引擎后的回归流程

1. 打包 → `roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba`
2. 逐场景采集：`python bot/run.py POKEMON_RUBY_AXVJ00 <scene> --verify`
3. 看 `verdict.md`：`fail` 帧 + 可疑块 bbox 直接定位到像素
4. 回归重点（按 bug 反查场景）：
   - 撞 UI ⇒ `bag`（**「使用」说明框**，横穿列表）、`dialogue`（购买列表）、`trainer_card`
   - 文字残留 ⇒ `bag`（说明框翻第 2 页）、`dialogue`（告别/重开）、`navigator`（说明句重画）
   - 背景被涂 ⇒ `navigator`（トレーナーアイ 左栏）
   - 六行同名类 ⇒ `pokemon_menu`（队伍列表）
