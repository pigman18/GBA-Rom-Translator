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
| `battle` | Route118 | 遇敌 → 战斗 | 战斗文本 | walk(soft) |
| `_probe_talk` | MauvilleCity_Mart | 四方向各按一次 A | **诊断**：找哪一面有可对话 NPC | 无（故意打空） |
| `_probe_use` | Route118 | 背包「学习装置 → 使用 → A/B 各推几下」 | **诊断**：确认说明框几页、退回到哪一层 | 无 |

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
