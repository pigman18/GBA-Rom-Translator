# BUG 台账 · 2026-11-18（全量 bot 扫描 + GLM 审图后整理）

**产物基线**
- 分支 `refactor/drop-f980-slt2`，HEAD = `f5ab01c`
- ROM SHA256 `8be7b0fe0d3c95db3cc5bbf022a82741902d5fbc26f171236526139cf17ae513`
- `hook/out/game.bin` = 8880 B
- 审图员路线：`provider=qoder, model=gfmodel`（GLM-5.3-Flash），已验证读图准确

**审图员路线记录（2026-11-18 复验）**
| 路线 | 状态 |
|---|---|
| `qoder/gfmodel`（GLM-5.3-Flash） | ✅ **当前使用**，读图准确（正确读出「危机时火威力提升」等） |
| `dshgw/workbuddy/glm-5.3-flash` | ❌ 额度耗尽 |
| `doubao/person-glm-5-3-flash-261111` | ❌ 额度耗尽 |
| `trae/glm-5.3-flash` | ❌ 额度耗尽 |
| `opencode-free/glm-5.3-flash-free` | ❌ 返回 `vision_ok:false` |
| SiliconFlow `Qwen/Qwen3.5-4B` | ⚠️ 文本可用（82s/次），**视觉接口超时**（300s / 900s 均超时）；且 `siliconflow` provider 不允许本会话建子代理 |

**关键教训（避免重复踩坑）**
1. 比对版本前必须核对 ROM SHA256 —— 曾拿诊断构建当基线，得出「两版 95 帧完全相同」的错误结论。
2. 用图判断「内容对不对」必须读字，不能靠墨量/颜色统计（统计只能说「有没有字」）。
3. 裁图必须只框一个语义块，不能把两行框在一起。
4. `git show <commit>:file > file` 在 PowerShell 下会破坏 UTF-8 编码 → 用 `git checkout <commit> -- <path>`。

**扫描范围**
- 138 个 bot 场景全跑：125 OK / 13 FAIL（FAIL 全是场景脚本问题，见附录 A）
- 采集帧对合计 **34752** 对，全部绑定上述 ROM SHA
- 审图覆盖：核心 UI 场景已逐帧或抽检目检；其余场景做了自动初筛（整块空白 / 黑带检测，0 命中）

---

## 一、待修 BUG 清单（按影响面排序）

### BUG-1 战斗对话框整框空白 ★最高优先级
**现象**
战斗内所有文本不渲染，只剩空框 + ▼/▶ 光标：
- 开场对话「パッーモは どうする?」
- 主菜单四项：たたかう / バッグ / ポケモン / にげる
- 招式表四个招式名
- PP 标签与数值
- 逃跑阶段对话

**证据**
| 项 | 值 |
|---|---|
| 复现场景 | `battle_menu_audit` f019–105、`battle_full` f022–041/071–085/111–127、`battle_dialog` f019–044 |
| run | `battle_menu_audit/20261117T222039_177822` |
| 像素实测 | origin 对话框墨量 1360，本版 **1124** |
| 对照版 | `5d88eb72` 版为 1305（接近 origin）→ 证明可修好 |
| 是否回归 | **否**。`926d09e` 基线同为 1124，属既有缺陷 |

**根因（已定位到算术）**
```
战斗对话框窗：tpl=0x081BB3F4, tm=0, fn=3
              TB=0x01B8, cursor_ty=35
row  = 35 >> 1     = 17
band = 17 & 7      = 1
grid_tile(col=0) = TB + 2 + band*62 + 2*col
                 = 0x1B8 + 2 + 62 + 0
                 = 0x1F8   >  GRID_TILE_LIMIT (0x1F0)
```
`grid_emit` 的越界保护分支（`t0 + 2*(ncols-1) + 2 > GRID_TILE_LIMIT`）
**col=0 就成立**，于是每个字都 `return` 不画 → 整框空白。

**为什么不能简单放宽上限**
`GRID_TILE_LIMIT = 0x1F0` 是**全局绝对位置**保护线，注释明确：
- `0x1F0/0x1F1` = 菜单 ▶ 固定 tile 对
- `0x1E8..0x1FB` = Summary 提示图标
- `0x1FC..0x1FF` = 图鉴编号/精灵球图标

把上限改成 `TB + 0x1F0` 会直接写坏这些 UI 图标。

**已尝试但失败的方案**
越界时在 `[TB+2, 0x1F0)` 内找空闲 tile 兜底（`grid_tile_find_free` 内联版）。
失败原因：`TB=0x1B8` 时可用区间只剩 `[0x1BA, 0x1F0)` 共 **27 对 tile**，
`grid_tile_is_other_col_natural()` 会拒绝其中大部分，实际找不到可用对。
（验算：`0x1B8+2+1*62 = 0x1F8 > 0x1F0`；可用对 = `(0x1F0-0x1BA)/2 = 27`）

**下一步方向（未验证）**
1. 先 dump `TB=0x1B8` 窗口的完整 tilemap，看清哪些 tile 真正空闲；
2. 评估是否该给战斗窗单独分配 arena（例如 `TB=0x1B8` 时把 band 压到 0，用 `0x1BA..0x1F0`）；
3. 或改分配策略：12px 汉字在本窗改用「跨 band 借位」而非固定 `band*62`。

---

### BUG-2 训练家详情页道路名整块空白
**现象**
领航员 → 训练家之眼 → 详情页，左侧道路名框内无字。
origin 显示「118ばん どうろ」「109ばん すいどう」等，translated 框内完全空白。

**证据**
| 项 | 值 |
|---|---|
| 复现场景 | `navigator` f114–152（约 39 帧连续） |
| run | `navigator/20261118T001337_940901` |
| 文字区墨量（x10-104, y50-64） | origin **182 px**，translated **102 px**（且这 102 全在 y=57/58/69/70 的边框上） |
| 有墨行分布 | origin y=44–53（文字）+ 57/58/69/70（边框）；translated **只有** 57/58/69/70（无文字行） |
| 是否回归 | **否**。11-15 起所有历史 run 该区域墨量恒为 245（含边框），translated 一直无字 |

**相关代码**
- `pokenav/PokeNav_TrainerEye_DetailEnter_hook.c:105-108`
  ```c
  init(LEFT_WIN);
  blank(LEFT_L, LEFT_T, LEFT_R, LEFT_B);   /* 0,9,11,16 */
  ((void_fn_t)(ADDR_TE_PRINT_LOCATION | 1u))();   /* 重印道路名 */
  ```
- `ADDR_TE_PRINT_LOCATION = 0x080EB9C0`
- 框区域：`left=0, top=9, right=11, bottom=16`（11 列 = 88px）

**待查**
`blank()` 清空后 `PRINT_LOCATION` 是否真的执行、打印时 grid 引擎是否因 tile 冲突跳过。
需要 GDB 在 `0x080EB9C0` 下断点抓入参，或给 `grid_emit` 加 TB/col 诊断。

---

### BUG-3 图鉴列表名字整列丢失 / 滚动行错位
**现象**
图鉴列表右栏的名字列全部显示为 `------` 占位符，origin 是真实名字（假名）。
滚动时顶行编号也会错位（origin 顶行 No003，translated 顶行 No011）。

**证据**
| 项 | 值 |
|---|---|
| 复现场景 | `dex` f035–155（约 121 帧） |
| run | `dex/20261117T230514_012419` |
| f035 实测 | origin 顶行「No003 フラキけ」，translated 顶行「No011 ------」 |
| 整列状态 | translated 侧 **所有行**名字都是 `------`，不只是顶行 |
| 对照 | 同界面 `dex_area` 184 帧全 PASS（该场景不显示名字列） |
| 帧重复排除 | f034–f037 四帧两侧哈希均不同，GLM 所说「重复帧」是它自己的裁剪图，不是采集问题 |

**判断**
这是**图鉴名字列整体未汉化/未渲染**，比「滚动错位」更严重。
需查 `UnusedPrintMonName_hook.c` 与图鉴列表的名字打印路径。

**下一步**
1. 确认名字列数据源：是走 `UnusedPrintMonName` 还是原版 species name 表；
2. 检查 hook 是否因 tile 冲突跳过（与 BUG-1 同源可能性高，都涉及 TB 高的窗口）。
3. ⚠️ 抓窗难点：`dex` 场景的 RAM dump 只在 f001/002/003/016/025/034/043/052... 存，
   且列表窗在 dump 时刻已释放，扫到的都是未初始化残留。
   需要在 `grid_emit` 里按 `tpl` 或 `TB` 打点，或让 bot 在列表页多存几帧 RAM。

---

### BUG-4 PP / 属性框灰底
**现象** 战斗招式面板的 PP 框、属性框底色为灰（`D6D6CE`），origin 为白（`FFFFFF`）。
**证据** 像素统计：origin `FFFFFF`×1491 vs translated `D6D6CE`×1299。
**状态** 既有缺陷，已知，未修。

---

### BUG-5 HP 显示 `377/115`
**现象** 我方体力条数字异常。
**状态** 既有缺陷，已知，未修。

---

### BUG-6 敌方名牌假名错序 / 我方名牌仍日文
**现象** 敌方宝可梦名假名顺序错排；我方名牌未汉化。
**状态** 既有缺陷，已知，未修。

---

### BUG-7 `｜｜begin▁of▁sentence｜｜` 标记泄漏
**现象** 文本中出现 LLM 特殊 token 字面量。
**状态** 既有缺陷，已知，未修。

---

## 二、已验证修复的（本轮 PASS）

| 场景 | 验证项 | 结果 |
|---|---|---|
| `pokemon_menu` f050–093 | 特性说明 | ✅「危机时火威力提升」（不是地点文字） |
| `bag_blank_rows` 全 192 帧 | 列表行名字 | ✅ 0 行空白，8 行名字齐全 |
| `start_menu` 全 56 帧 | 菜单项 | ✅ PASS |
| `options` 全 91 帧 | 设置项 | ✅ PASS |
| `mart_oldale` 全 181 帧 | 商店/队伍/电脑 | ✅ PASS |
| `center_dewford` 全 181 帧 | 宝可梦中心 | ✅ PASS |
| `dex_area` 全 184 帧 | 图鉴详情 | ✅ PASS |

对应提交：
- `dac71dd` 背包列表窗排除 band 重映
- `10d6583` summary 宽度计算按缓冲容量
- `f5ab01c` 移除 band0→5 重映（修特性说明被备忘行覆盖）

---

## 三、附录 A：13 个场景脚本失败（与 ROM 无关）

| 场景 | 原因 |
|---|---|
| `font_dump` `fr_menu` `fr_pair` `fr_pair2` `fr_text` | 依赖 `BOT_OUTPUT` / `BOT_SHOT_DIR` 环境变量 |
| `images_dump` | 依赖 `IMG_OUT`，需 `images_patcher.py --mgba` 启动 |
| `ref_probe` | 依赖 `REF_OUT` |
| `font_probe` | `scene load failed: nil` |
| `page_sweep` | `api.run` 为 nil（脚本 API 失效） |
| `dialogue` `gym_dewford` `gym_mauville` `shop` | `[TALK] TIMEOUT` — 存档位置导致 NPC 不在面前 |

---

## 四、复现命令

```powershell
# 打包
cd C:\code\GBA-Rom-Translator
$env:PYTHONPATH="$PWD\src"
C:\Python314\python.exe -m meowth full "roms\origin\POKEMON_RUBY_AXVJ00.gba" `
  --seed-only --target zh-Hans -o "roms\outputs" --work-dir work

# 单场景采集
$env:PYTHONIOENCODING='utf-8'
C:\Python314\python.exe bot\run.py POKEMON_RUBY_AXVJ00 <scene> `
  --save bot\scenes\POKEMON_RUBY_AXVJ00\saves\Route118_68-7.sav

# 全量批跑
C:\Python314\python.exe work\batch_all.py
```

改 `hook/src/**` 后**必须先** `cd configs\POKEMON_RUBY_AXVJ00\hook; .\build.bat` 再打包，
流水线只嵌入现有的 `hook/out/game.bin`，不自动编译。

---

## 五、修复顺序建议

1. **BUG-1 战斗对话框** — 影响最大（整个战斗流程无字），且根因已定位到算术，只差 arena 策略
2. **BUG-2 道路名** — 单点、易验证
3. **BUG-3 图鉴错位** — 先排除采集时序
4. BUG-4/5/6/7 — 已知既有缺陷，按用户优先级排

---

## 六、2026-11-19 复查结果

### 6.1 BUG-1 战斗对话框整框空白 —— **已修复**

提交 `b9e2db8`。根因不是「上限 0x1F0 太小」，而是 **textMode 0 被套用了
tm1 的 band 网格公式**。修法：按 textMode 分派落址，tm0 用
`tile = TB + TILE_OFFSET`（每字 +2），换行不清零。

证据：帧 058 tilemap `y5` 与 origin 逐项一致
（`19:1A2 20:1A4 21:1A6 22:1A8 23:1AA 25:1AE 26:1B0 27:1B2`）。
详见 `TEXTMODE_DISPATCH_RESEARCH_20261119.md`。

### 6.2 BUG-4 PP/属性框灰底 —— **已修复（同批）**

根因：`grid_bg()` 取 `tpl[6]`，而菜单/招式窗 `tpl[6]=15` 在 pal5 下是
灰 `(213,213,205)`。GDB origin 侧实测三个战斗窗真正打印时
`C/D/E = 1/15/8(pal0)` 或 `13/14/15(pal5)`，**D 就是背景色**。
修法：tm0 改用 `win[0x0D]`。

### 6.3 BUG-5 HP `377/115` —— **既有缺陷，与本轮无关（已排除）**

验证：逐帧对比 11-15 起全部历史采集，`x168..172`（那个 `3`）**一直有墨**。
最早样本 `battle_menu_audit/20261115T220537_719421` 即存在。

关键事实（排除渲染层）：
- GDB origin 侧 `PrintNextChar` 的所有窗 `curY` 只有 `0/15/35/55/57`，
  **没有一个对应 HP 数字所在的屏幕 y≈98（ty=12）**。
- ⇒ **HP 数字不经过 PrintNextChar**，由游戏血条代码直接写 VRAM。

待查方向：游戏侧 HP 字符串构造（`ConvertIntToDecimalStringN` 等价物）
或血条 BG 缓冲的字模来源。**不能靠改渲染层解决。**

### 6.4 BUG-2 / 3 / 6 / 7 —— 未动，待逐个走静态+GDB

| BUG | 状态 | 下一步 |
|---|---|---|
| BUG-2 训练家详情页道路名空白 | 未修 | 在 `0x080EB9C0` 下断抓入参 |
| BUG-3 图鉴名字列 `------` | 未修 | 查名字列数据源与 `UnusedPrintMonName` |
| BUG-6 敌方名牌假名错序 | 未修 | 需确认是否为 font4 8px 路径 |
| BUG-7 `begin▁of▁sentence` 泄漏 | 未修 | 查 texts.json 里的脏数据 |
