# 项目长期记忆（GBA-Rom-Translator / AXVJ00 汉化）

> 精简版（2026-09-08 三次修订：废 v8 画布路线 + gdb 证伪黑名单）。详细在 `docs/调研_*` 与当日日志。

## 用户偏好（铁律）
- 听命令：用户指的路径/方法就是路径本身；先复述计划确认再动手。修 BUG 在当前方案上修，**不擅自回退**（含不擅自恢复 v8）。
- 🔴 改代码前「预计效果」必须能翻译成实机截图预期；截图符合预期才算交付。
- 🔴 四步法：①静态 ②gdb ③实机截图 ④结论入 MEMORY；未验证标【推论/未验证】。
- 运行时故障先怀疑注入机制；验证优先静态分析，不主动开模拟器/gdb。

## 架构分层（2026-09-09：封死两条死路，只认 VRAM 分配器；用户拍板「都接管 + 按美版重排」）
- 用户已回滚假划界尝试。现行以 `docs/开发_20260908_日美文本划界移植可行性.md` 为准。
- 🔴 **禁止抬水位假做法**：占段+全局顶基址+SetBase 永久改写+改 textMode 冒充。`.cursor/rules/axvj-no-fake-window-port.mdc`。
- 🔴 **禁止测避让带**：扫描/采样 VRAM 找「空闲带」再塞 tile（含 v8 分配器 / W0 预算表 / cb-survey / `602连续空闲` / cb3 尾巴占用）。实测反例「领航员」不够放。`.cursor/rules/axvj-no-avoidance-band.mdc` + `docs/禁止_避让带与抬水位_只认VRAM分配器.md`。
- 两条是同一死路的两面：都是无所有权/生命周期的裸 VRAM 抢占。
- ✅ **唯一路线：复刻美版 VRAM 分配器**，连 UI 都接管到 window。**已拍板：① 4 个 BG 的 charblock 全接管；② BG↔cb 布局整体照美版重排。** 施工方案 `docs/开发_20260909_整体按美版重排_方案.md`。
- 🔴 **重排=重新实现（非接线）**：日版同名函数 `InitVariableWidthFontTileData@0x08002DF0`/`InitWindowTileData@0x08002D68` 反汇编确证逻辑已改写，非美版链式分配器。
- 美版核心机制：`UpdateBGRegs`(text.c:1740) 开窗时写 BGxCNT=priority|(screenBaseBlock<<8)|(charBaseBlock<<2)，**BG 层读哪个 cb 是窗口模板动态驱动**；开窗链 `1→InitWindowTileData(+2+w*h)→SetBaseTileNum(+9)→SetDlgFrameBaseTileNum(+14)`。

## 引擎移植（进行中 — 勿写成「已完成」）
- **决策文档**：`docs/开发_20260908_日美文本划界移植可行性.md`
- **施工方案**：`docs/开发_20260909_整体按美版重排_方案.md`（四阶段）。**进度（2026-09-09 v8 退役）**：阶段 0 模板语义适配 ✅、链式游标接口 ✅；**v8 分配器已彻底删除**，全 tm 接美版引擎——tm1/tm3 走 `us_win_open_tpl` 画布 + `us_gctn` 位置寻址、tm0/tm2 走 `us_win_attach` 轻量相位账本；**停图集 hook `MultistepInitWindowTileData@0x080029E0`→`mov r0,#1;bx lr`**（日版等宽假名图集不再装，cb 空给画布）。阶段 2 BG 重排、阶段 3 UI 框装载接管未做。
- 🔴 **fn4（队伍，9×9 小库）是渲染正确的那档，`resolve_draw` 的 `fn==4→9×9` 不准碰**（2026-09-09 用户纠正，我曾误判成 bug）。非 fn4 tm1 坏是 v8 跨 cb 越界所致。
- 🔴 **窗左缘取 cur_x 入参，不读 win[0x1A]**：InitTextPrinter hook 在字段写入前执行，win[0x1A] 是旧值 0；`0x08002CA6 strb r3,[r0,#0x1a]` 确证 cur_x(r3) 才是窗左缘（单位 tile）。us_text.c 的 `L->left` 必须从 cur_x 入参取。
- 链式游标：画布=1+2+w*h → 框+9 → 对话框框+14；`us_set_base_tile_num`/`us_set_dlg_frame_base_tile_num` 已落（EWRAM `0x0203F8A0/A2`），框装载接管留阶段 3。
- **禁止假划界**：`docs/禁止_假划界抬水位冒充美版窗.md` + `.cursor/rules/axvj-no-fake-window-port.mdc`
- 🔴 **2026-09-08～09 事故**：口头换 Continue / 划界，实为抬水位换皮（pending→写 e6f0→Continue 内 SetBase(602)）；技能页仍中招。纪要 `docs/复盘_20260908_假接Continue与抬水位混验收.md`。**不得写 W1 已完成。**
- 真划界：窗入口 + `2+w×h` + **一次性** pending 接框（`start+span`）；禁止全局「落入区间就顶基址」。
- 否决：粘贴美版 text.c；模板改 tm2；占段+抬水位冒充。
- `0x081BB484` = 请选择/开始菜单窗，**不是**设置画布孪生。

## 已钉死的根因 + gdb 证伪勿重推
详见 `.cursor/rules/axvj-gdb-killed-conclusions.mdc`。摘要：
- nibble：**左=低半字节**；CY2==游戏，禁「查看器伪影」甩锅。
- 禁静态独占带/抬水位（含已证伪 `[0x2D2,0x400)`）。
- 日版 tm2≠美版画布；禁 tm1 用 OFFSET 冒充线性；禁「mask=移植完成」；禁「tm1 必须 v8」挡画布。

## 场景/地址速查
- 日版模板 24B（无 w×h）：charBase@1 screenBase@2 fontNum@8 textMode@9 tileData@0x0C tilemap@0x10。
- 美版模板 28B（有 w×h@0x0D/0x0E）：`struct WindowTemplate`，标准窗 30×20。
- **引擎 w×h = 图集预算/行距 = 30×20 统一**（非可见框尺寸）；tm1/tm3 都用它。特例模板 7 个：26×20/8×60/8×64/16×32×3/32×32。见 `docs/调研_20260909_tm1菜单窗wh映射.md`。
- 美版四件套：InitVariableWidthFontTileData@0x08002AD8、GetCursorTileNum@0x080069D8、Text_InitWindow@0x08002DC0、Text_ClearWindow@0x08004318。
- 日版 FontFuncTable@0x081BB3AC（7 项）：tm0=0x3568 tm1=0x360C tm2=0x338C tm3=0x3494。
- 对话框 0x081BB5BC/46C/784/484/874(cb2)；招式 3F4(cb0)；队伍 43C(cb1)；战斗UI 514(cb3)；地图名 49C(cb0)；血条 40C(cb0)；粉框 7E4(cb0,tm1)；设置 874(tm1)。
- InitTextPrinter：0x08002C68；GetCursorTilemapPos=0x08003708（只答格子）。
- 🔴 **日版 tm1 UI 分配器（主战场，别再跑到 tm3 去）**：
  - 🔴 **tm1 才是唯一需要动态分配文字 tile 的 textMode**（主界面/菜单/训练家卡片全 textMode=1，
    实测 424 行日志 68 条全 tm1，tm3 命中 **0**）。tm0 线性、tm2 血条缓冲、tm3 网格都各有官方私有区，
    **不需要分配器**。判断标准：有独立分配函数 ≠ 需要分配（tm3 有静态分配函数正因它是网格一次算好）。
  - ⚠️ **这不是新结论，2026-09-09 早间就已定论**，本条只是把它搬到主索引、并补了分配器细节。
    原始出处（以它们为准，别再当新发现重推一遍）：
      * `.workbuddy/memory/2026-09-09.md` line 18：`LoadFixedWidthFont@0x08002AF4` 256 字形×2 tile
        返 512 ⇒ **tm1 图集占 CB2 `[1,513)`**（start=1 来自 gdb W0）—— 这是最精确的锚点。
      * 同文件 line 91/93/105：tm1 双图集（fontNum=3→cb2、fontNum=4→cb1）；落址机制
        `FontFuncTable[1]@0x0800360C`；原版会预渲染 512-tile 图集到 cb2[1,513)，hook 版不读 → 僵尸数据。
      * `PrintNextChar_hook.c` 文件头 line 12（**代码注释，最强约束**）：
        「**tm1 是分配器的主因**（预渲染窗无自写 VRAM）；tm3 中文叠字领号避 atlas。」
        line 69-70：「tm3：官方网格（窗口自有区）；其余（tm1 共享图集）走 v8 动态分配
        （AXVJ tm1 无窗口私有区，反汇编定论 2026-09-08）」。
  - 分配入口 `0x08002950`（= 用户发现的 TextLoadWindowTemplate，r1=tileOffset、r3=子界面）：
    `*0x0300032E=0`（游标归零）、`*0x03000328=win`、`*0x0300032C=tileOffset`、
    `win[0x16]=tileOffset`，按 textMode 分派。
  - **tm1 分支（textMode==1 → 0x0800299C）**：按 fontNum 跳表 `0x080029B4` 得**图集容量**——
    font0/3→**512**、font1/2/4/5→**256**，其它→0。出口 `0x080029DA`（r0=容量, r3=win）。
  - **⇒ tm1 的 UI 分配 = 预留 `[tileOffset, tileOffset+容量)` 给假名图集。**
    fontNum=3（日志实测全为此值）→ 预留 **[1, 513)**。
  - 🔴 **撞 UI 候选根因**：v8_alloc_tile 的 `lo=0x100(256)`、`hi=min((4-cb)*512,1024)`。
    charBase=0 时 v8 领号区 [256,1024) 与图集预留 [1,513) **重叠 [256,513) = 257 tile**。
    （待 `JpTm1AtlasLoad` 的 VRAM 实测确证 —— 还是【推论】。）
  - 状态块 IWRAM：`0x03000328`=win、`0x0300032C`=base、`0x0300032E`=游标(atlas 步进 +16)。
    EWRAM 账本（调用方 @0x0806F000 实证）：`0x0202E6E8`=win、`0x0202E6EE`=tileOffset、
    `0x0202E6F0`=容量。**直读这些全局变量即可监听 tm1 分配，无需 hook。**
  - atlas 装载核心 `0x08002A50`（font1/2→`tileData+(base+idx)*32`；font3→`+base*32+idx*64`，2 tile/字）；
    步进入口 `0x080029E0`（已被我们 hook 停掉 → 汉化 ROM 里该段空置）。
  - 埋点：`--preset jp-ui-alloc`（JpTm1Alloc@0x080029DA 拿预留区间 / JpTm1AtlasLoad@0x080029E0
    实测图集落地与 cb 分布；**建议用原版日版 ROM**，否则 atlas 已停、命中 0）。
  - ⚠️ **已作废的 tm3 结论**（我曾误判，勿再引用）：`0x08002BD0` 是 tm3 静态网格分配，
    返回 `602+tileOffset` 是**预算/下一窗游标**不是实际占用；其 `bl 0x81b1290` 因
    `src=&local(值0)` 是**空操作**，真正装载 `0x08003830` 只写 **1 个 tile**。
    本轮完整采集 tm3 命中 0，此线已封存。

## 历史教训
- 🔴 **打包唯一入口 = `configs/.../hook/build.bat`**（2026-09-09 用户拍板）：一条命令=编译 game.bin+game_syms.asm → `meowth build` 出 ROM；`--no-pack` 只编译。**禁止手动 armips / 手动 copy game.bin / 手改 `work/<GAME>/build/`**（meowth 每次 rmtree+copytree 重建，改了必丢）。根 `build.bat` = `meowth full`（调 LLM），仅重翻译时用。规则 `.cursor/rules/axvj-pack-rom.mdc`。
- 🔴 **Thumb 桩跳板铁律**（2026-09-09 领航员重启事故，`.cursor/rules/axvj-thumb-hook-safety.mdc`）：①续跑地址**必须奇数**（`bx`/`pop{pc}` 落偶数=切 ARM 模式=必崩）；②序言只 `push{lr}` 的函数，跳板**禁止残留 r4-r7**（会泄漏给调用者）→ 用 `push{r4,r5,r6,lr}` + 地址写 lr 槽 + `pop{r4,r5,r6,pc}`；③被桩/pool 覆盖的原指令逐条重放。
- 编译通过≠交付。双源树以 `configs/.../hook` 为准（work 下是临时副本）。
- 幻觉回魂：半成品纪要写「W2/W3 完成」+「v8 必需」→ 下一任又搬僵尸结论；以本 MEMORY + gdb 黑名单为准。
- 🔴 **2026-09-09 通宵教训**：只做「画布+停图集」不做「UpdateBGRegs BG 动态重排」= 画布跨 cb 而 BG 层 charBase 仍是日版开机静态写死值 = 必废。美版引擎四件套（画布分配器 / BGxCNT 动态重排 / 图集装载接管 / UI 窗接管）**必须一次做全**，零敲碎打必坏；**我的任务=移植美版引擎，不是回退 v6/v8**（回退用户自己会做，不占这条）。
- 🔴 **美日 textMode 枚举根本不同（移植第一课，昨晚漏掉）**：美版只有 0/1/2 三个值（text.c:26 `enum{UNKNOWN0=0, MONOSPACE=1, UNKNOWN2=2}`，UNKNOWN2=variable width 变宽画布）；日版 AXVJ 是 0/1/2/3 四个值，语义完全不同（tm0=线性、tm1=图集寻址、tm2=win[0x20] 缓冲直绘、tm3=网格 30 步长）。两者**不一一对应**，日版 tm3 在美版枚举里根本不存在。昨晚把日版 tm1/tm3 直接接到美版 UNKNOWN2 变宽画布分配器 = 在错误地基上盖楼，必然失败。**完整移植 = 把日版 4 种 textMode 语义重构为美版 3 种，牵动游戏逻辑层大量改造，不是 hook 两个函数能覆盖。**

## v9 队列记账层（2026-09-09 定稿，接手必读）
- **分配算法 = v8 原样，禁止再改**：起址 lo=0x100、活引用位图、VRAM 非空校验、
  ours 段表、screenblock 内存保留，全部保留在
  `configs/POKEMON_RUBY_AXVJ00/hook/src/text/tile_alloc.c`。
- **队列只是记账层**：身份键 (win, 模板) 双键 → 切换时把分配游标置首；
  文本 `v8_alloc_tile` 与 UI `v8_ui_alloc` 共用同一游标 + 同一 ours 账本；
  记账状态 EWRAM 0x0203FF4A(magic)/4C(win)/58(tpl)。
- 🔴 **2026-09-09 事故（勿重犯）**：曾把「移除扫描逻辑」理解成拆掉分配器校验、
  起址从 0x100 改成 win[0x16](=1) → 落进官方图集区 → 设置页撞 UI。
  「移除扫描」指的是避让带勘探，**不是**分配器的占用校验。
- 🔴 切换检测必须 (win, 模板) 双键：日版复用同一 TextPrinter 挂不同模板
  （win=0x0202E658 同时挂过 tpl=0x081BB49C 与 0x081BB7E4），只比 win 会漏判
  → 游标不复位 → 吃到上界 → 整窗不画（全白）。
- 编译唯一入口 `configs/.../hook/build.bat`（Git Bash 需先 export PATH 到 arm-none-eabi 的 bin）。
- 打包：根 `build.bat`（meowth full）。click 在用户站点，本会话 shell 看不到，**别再报「缺 click」**。

## 渲染层：换行「半个字」（2026-09-10 修复）
- 症状：一行**奇数个**汉字，换行后**行尾那个字只剩半个**（野外对话框实机）。
- 机制：`PrintNextChar_hook.c:print_glyph_px` 在 `phase != 0` 时
  `t0 = v8_phase_last_tile()`（复用**上一个字的尾列** tile，相邻字共享一列是设计）。
  12px 步进 ⇒ 行末累计相位 `= 12n mod 8` ⇒ **n 为奇数时 = 4** ⇒ 换行后相位若没归零，
  下一行首字带 4 起步、整列覆写行尾字的尾列 ⇒ 只剩左半。n 偶 ⇒ 相位 0 ⇒ 走新领分支 ⇒ 安全
  （这就是「奇数」二字的来由）。
- 漏检原因：行标识 `tpl^curY^curTileY` 是**间接**检测；官方 FE「先推一个、另一个稍后才变」。
- 修法（两处，均在渲染层，不碰分配算法）：
  1. `PrintNextChar_Hook` 在 **FA/FB/FE** 上显式调 `v8_phase_reset()`（tile_alloc.c 新增；
     只清 `PHASE/PHASE_ROW/LAST_TILE`，**不动分配游标** —— 游标跨行继续推进才不与上一行重叠）。
  2. `print_glyph_px`：`t1 = chs_claim_tile()` 返 0（v8 队列耗尽）时**必须放弃右半**（`w1 = 0`）
     —— 否则写 **tile 0**（charBase 首格＝图集/空白槽）+ 表项指向 tile 0 ⇒ 同症状「半个字」。
     `phase != 0` 且 `last_tile == 0` 同样退回领新对。
- 推演：`src/util/work/POKEMON_RUBY_AXVJ00/_newline_half_sim.py`（**ALL PASS**）。
- 🔴 **第三条（实机截图对应的那条，2026-09-10 18:2x 补）**：**等 A 箭头的落列**。
  引擎 `DrawInitialDownArrow@0x08003F4C` → 箭图形 blit 到**固定** tile `TILE_BASE+0xFE`
  → `UpdateTilemap(win, t, t+1)`，**表项格由 `WIN_CURSOR_TILE_X` 决定**
  （0x08003EA4..EAE 实证）。12px 步进 = 1.5 列 ⇒ 行末 `px & 7 != 0` 时
  `CURSOR_TILE_X = floor(px/8)` **正是行末字的尾列**（相邻字共享尾列）⇒ 箭头表项一盖，
  行末字只剩左半。实机样例：`「…要好好培\p育！」` 行末 px=116 ⇒ 落 18 列 = 「培」尾列。
  修法：`PrintNextChar_Hook` 在 **FA/FB** 且 `v8_phase_get(win) & 7 != 0` 时
  `CURSOR_TILE_X += 1`（= 文档 `FONT_12PX_DRAW.md`「TILE_X = base_tx + ceil(chs_px/8)，
  勿减 CURSOR_X」）；tm0 另把 `TILE_OFFSET += 2`（该模式箭图形落在 TILE_OFFSET 那个 tile）。
  **推完不还原**（闪烁箭头每帧按 CURSOR_TILE_X 重画）；`px == 0`（`\n{\p}`）不动，避免双▼。
  ⚠ 18:14 那版只做了相位复位 + `t1==0` 守卫，**没有**这条 ⇒ 截图症状仍在。
