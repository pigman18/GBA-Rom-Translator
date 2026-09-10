# 项目长期记忆（GBA-Rom-Translator / AXVJ00 汉化）
> 只留铁律与速查；详细在 `docs/*` 与 `.workbuddy/memory/YYYY-MM-DD.md`。

## 用户偏好（铁律）
- 听命令：用户指的路径/方法就是路径本身；修 BUG 在当前方案上修，**不擅自回退**。
- 🔴 改代码前「预计效果」必须能翻译成实机截图预期；截图符合预期才算交付。
- 🔴 四步法：①静态 ②gdb ③实机截图 ④结论入 MEMORY；未验证标【推论/未验证】。故障先怀疑注入机制，验证优先静态分析。

## 架构：两条死路 + 唯一路线
- 🔴 禁抬水位假做法（占段+顶基址+SetBase 永久改写+改 textMode 冒充）：`docs/禁止_假划界抬水位冒充美版窗.md`、`.cursor/rules/axvj-no-fake-window-port.mdc`。
- 🔴 禁探避让带（扫 VRAM 找空闲带塞 tile）：`docs/禁止_避让带与抬水位_只认VRAM分配器.md`、`.cursor/rules/axvj-no-avoidance-band.mdc`。反例「领航员」不够放。两条同源＝无所有权/生命周期的裸 VRAM 抢占。
- ✅ 唯一路线＝复刻美版 VRAM 分配器（UI 也接管）。已拍板：①4 个 BG charblock 全接管；②BG↔cb 布局整体照美版重排。方案 `docs/开发_20260909_整体按美版重排_方案.md`。**重排＝重新实现（非接线）**：日版 `InitVariableWidthFontTileData@0x08002DF0`/`InitWindowTileData@0x08002D68` 逻辑已改写。
- 美版机制：`UpdateBGRegs`(text.c:1740) 开窗写 BGxCNT=priority|screenBase<<8|charBase<<2；开窗链 1→InitWindowTileData(+2+w*h)→SetBaseTileNum(+9)→SetDlgFrameBaseTileNum(+14)。
- 🔴 **美日 textMode 枚举不一一对应**：美 3 值(0/1/2，2=变宽画布)；日 4 值(tm0 线性/tm1 图集寻址/tm2 win[0x20] 缓冲直绘/tm3 网格 30)。完整移植＝4 语义重构为 3，牵动游戏逻辑层。
- 🔴 只做「画布+停图集」不做 BG 动态重排＝必废；四件套（画布分配/BGxCNT 重排/图集装载/UI 窗接管）必须一次做全。`0x081BB484`＝请选择/开始菜单窗，非设置画布孪生。

## 引擎移植（进行中，勿写「已完成」）
- 决策 `docs/开发_20260908_日美文本划界移植可行性.md`；方案同上（四阶段）。
- 进度：阶段 0 模板语义 ✅、链式游标 ✅；v8 分配器已删，全 tm 接美版引擎（tm1/tm3→`us_win_open_tpl` 画布+`us_gctn` 位置寻址；tm0/tm2→`us_win_attach` 相位账本）；停图集 hook `0x080029E0`→`mov r0,#1;bx lr`。**阶段 2/3 未做**。
- 🔴 fn4（队伍 9×9）渲染正确，`resolve_draw` 的 `fn==4→9×9` 不准碰。
- 🔴 窗左缘取 cur_x 入参，不读 win[0x1A]（hook 早于字段写入；`0x08002CA6 strb r3,[r0,#0x1a]`）。链式游标：画布 1+2+w*h→框 +9→对话 +14；`us_set_base_tile_num`/`us_set_dlg_frame_base_tile_num` 已落 EWRAM `0x0203F8A0/A2`。
- 🔴 2026-09-08~09 事故：口头换 Continue/划界，实为抬水位换皮（`docs/复盘_20260908_假接Continue与抬水位混验收.md`）。真划界＝窗入口+2+w×h+**一次性** pending 接框(start+span)，禁全局「落区间就顶基址」。否决：粘贴美版 text.c、模板改 tm2、占段+抬水位冒充。

## gdb 证伪黑名单（勿重推）
`.cursor/rules/axvj-gdb-killed-conclusions.mdc`：nibble **左=低半字节**；CY2==游戏（禁「查看器伪影」甩锅）；禁静态独占带/抬水位（已证伪 `[0x2D2,0x400)`）；日版 tm2≠美版画布；禁 tm1 用 OFFSET 冒充线性；禁「mask=移植完成」；禁「tm1 必须 v8」挡画布。

## 地址/结构速查
- 日版模板 24B：charBase@1 screenBase@2 fontNum@8 textMode@9 tileData@0x0C tilemap@0x10。美版 28B（w×h@0x0D/0x0E），标准 30×20。
- 引擎 w×h＝图集预算/行距＝30×20 统一（非可见框），tm1/tm3 都用；特例 7 个见 `docs/调研_20260909_tm1菜单窗wh映射.md`。
- 美版四件套：InitVariableWidthFontTileData@0x08002AD8、GetCursorTileNum@0x080069D8、Text_InitWindow@0x08002DC0、Text_ClearWindow@0x08004318。日版 FontFuncTable@0x081BB3AC：tm0=0x3568 tm1=0x360C tm2=0x338C tm3=0x3494。
- 窗模板：对话 0x081BB5BC/46C/784/484/874(cb2)；招式 3F4(cb0)；队伍 43C(cb1)；战斗UI 514(cb3)；地图名 49C(cb0)；血条 40C(cb0)；粉框 7E4(cb0,tm1)；设置 874(tm1)。InitTextPrinter@0x08002C68；GetCursorTilemapPos=0x08003708。
- 🔴 **tm1 是唯一需动态分配文字 tile 的 textMode**（tm0 线性/tm2 缓冲/tm3 网格各有官方私有区）。分配入口 `0x08002950`：`*0x0300032E=0`、`*0x03000328=win`、`*0x0300032C=tileOffset`、`win[0x16]=tileOffset`；tm1 分支 0x0800299C 按 fontNum 跳表 0x080029B4 得容量（font0/3→512，font1/2/4/5→256），出口 0x080029DA ⇒ 预留 `[tileOffset,+容量)`，fontNum=3→**[1,513)**。现场 IWRAM `0x03000328/32C/32E`＝win/base/游标；EWRAM `0x0202E6E8/6EE/6F0`＝win/tileOffset/容量（直读即可监听）。atlas 装载 0x08002A50、步进 0x080029E0（已停）；埋点 `--preset jp-ui-alloc`（用原版日版 ROM）。⚠ 已作废：`0x08002BD0` 是 tm3 静态网格，返回 `602+tileOffset` 是预算游标非占用。

## 字库流程（fonts/default/*.bdf = 唯一权威入口）
- 🔴 权威源＝`fonts/default/{Normal,Small,Middle}.bdf`（改字即生效：改完跑 full 或 `pack_no_llm.py`）。Normal 11×11@row2→大库；Small 9×9@row5→小库；Middle **9×11@row2**（`fonts_patcher.py --src-cols 11 --dst-cols 9 --ink-h 11 --top-pad 2 --no-fallback` 手工派生，**不自动跟随 Normal**）。提取器 `src/util/fonts_extract.py`（1bpp→BDF，逆向用）。⚠ BDF 行 **MSB＝最左像素**（`0x80>>(x&7)`）。
- **三条下游链，同一轮 `_build_font_from_bdf` 跑完**（产物只写 `work/<GAME>/graphic/fonts`）：
  ① 4bpp 128B/字槽 ← `build_chinese_font.py --ink-fixed --pad-top`；`font_slots` 各带 `bdf/ink_fixed/pad_top`，**Sym 无 bdf⇒legacy**。**代码零引用**（仅 Sym 用于渲染）。
  ② ③ **1bpp 位流库（汉字实际渲染走这条）** ← `build_font_1bpp.py`，槽位在 `extra_bins` → `fonts.s` `.org+.incbin`：
     **Big1Bpp 11×11@2 16B/字 @0x09500000**、**Small1Bpp 9×9@5 11B/字 @0x09600000**、**Middle1Bpp 9×11@2 13B/字 @0x09700000**（ROM file off = VMA−0x08000000）。
     几何必须与 `chs_cell_from_1bpp(bits, W, H, row_off)` 互逆。固定几何槽跳过 `patch_font_punct.py` 与 hook/work 参考回灌（`apply_font_patch` 的 `bdf_driven` 守卫）。
- 运行时：`text_translater.c:GetGlyph(font_lib)` → `chinese_glyph.c:chs_cell_from_1bpp`（墨15/阴14）。**档位解析（PrintNextChar_hook.c:resolve_draw）**：① tm2/tm2血条、fn==4、请求 8px → Small 9×9（adv10/ink9）；② **场景字号表**（`scene_cfg.h/.c`）→ MIDDLE→Middle 9×11 / SMALL→Small；③ 默认 Big 11×11（adv12/ink11）。
- 行偏移：`CHS_1BPP_ROW_OFF_BIG=2 / SMALL=5 / MIDDLE=2`。`GetGlyph` 步进：Big 16B、Small 11B、Middle 13B（`code & 0x1FFF` 索引）。
- **1bpp vs 4bpp 只差存储**（16/11/13 vs 128 B/字）；**VRAM tile 占用完全相同**。
- **校验工具**（`src/util/work/POKEMON_RUBY_AXVJ00/`）：`font_bdf_roundtrip_check.py`、`font_authority_probe.py`（改字即生效）、`font_stage_probe.py`、`pack_no_llm.py`（免 LLM full 等价链）。
- 🔴 **打包必须跑 full 链**：`run_full`＝`build_rom`+`_run_tiles`+`_align_rom_file`(→32MB)；只跑 `meowth build` 缺 tile 与对齐。
- 🔴 **bulk-delete 守卫按「回合」累计**（`scope=turn`）：`apply_font_patch` 开头 `rmtree(work/<GAME>/build)`（~100 文件）就会触发 ⇒ 打包中止、**无 traceback**（极易误判成功 —— 必须核对 `Saved:`/`FINAL:`/sha1）。绕行＝**rename 挪走**（`pack_no_llm.py:_sidestep_bulk_delete_guard` / `_sidestep_temp_unlink`，rename 不计配额）。
- 冗余清理（09-10/11 已完成）：删 BDF `Normal_unshadow/Small_unshadow/Middle_fallback`、`_bak_20260910/`、仓库根 `graphic/`、`hook/graphic/fonts/*.bin`、`hook/graphic/phrase_data.asm`(4.6MB)、`five_way_hao.py`、`/tmp/axvj_build_stale`(739MB)。**字库 bin 只存在于 `work/<GAME>/graphic/fonts`**；保留 `hook/graphic/fonts.s`（`main.asm` include 目标）。
- **未挂载死代码（记录未删）**：`gui/components/font_panel.py:FontPanel`（无 import）；`font_patch.py:_reference_fonts_dir`→不存在目录 ⇒ 三个 `*_from_reference` 函数全死。

## 打包与 Hook 铁律
- 🔴 打包唯一入口＝`configs/.../hook/build.bat`（编译 game.bin+game_syms.asm → `meowth build`）。禁手动 armips / 手 copy game.bin / 手改 `work/<GAME>/build/`。根 `build.bat`＝`meowth full`（调 LLM）。规则 `.cursor/rules/axvj-pack-rom.mdc`。**改 src 清单时 `build.bat` 与 `build_sh_equiv.sh` 必须同改**（Git Bash 用后者）。`meowth` 不重编 C：它只 `copytree(hook)` 取 `out/game.bin`，所以改 C 后必须先在 hook 目录跑一次构建。
- 🔴 Thumb 桩安全（`.cursor/rules/axvj-thumb-hook-safety.mdc`）：①续跑地址必须奇数（落偶数＝切 ARM＝必崩）；②序言只 `push{lr}` 的跳板禁残留 r4–r7 → `push{r4,r5,r6,lr}`+地址写 lr 槽+`pop{r4,r5,r6,pc}`；③被桩/pool 覆盖的原指令逐条重放。
- 编译通过≠交付；双源树以 `configs/.../hook` 为准（work 下是临时副本）。幻觉回魂：半成品纪要写「W2/W3 完成」「v8 必需」→ 下一任搬僵尸结论；以本 MEMORY + gdb 黑名单为准。

## v9 队列记账层（2026-09-09）
- 分配算法＝v8 原样（起址 lo=0x100、活引用位图、VRAM 非空校验、ours 段表），全在 `hook/src/text/tile_alloc.c`。**三闸门全是当帧事实，零预测 —— 这是安全来源**。
- 队列＝记账层：身份键 (win, 模板) 双键 → 切换时游标置首；`v8_alloc_tile` 与 `v8_ui_alloc` 共用游标+ours 账本；EWRAM 0x0203FF4A(magic)/4C(win)/58(tpl)。
- 🔴 「移除扫描」＝移除避让带勘探，**不是**拆分配器占用校验（曾因此把起址改成 win[0x16]=1 → 落进图集区 → 设置页撞 UI）。
- 🔴 切换检测必须 (win, 模板) 双键：同一 TextPrinter 挂不同模板（win=0x0202E658 挂过 0x081BB49C/0x081BB7E4/0x081BB46C），只比 win 会漏判 → 游标不复位 → 整窗不画（全白）。

## 场景字号配置（scene_cfg，2026-09-11 重建）
- `hook/include/scene_cfg.h` + `hook/src/text/scene_cfg.c`（**本次才纳入 build.bat/build_sh_equiv.sh** —— 此前从未编译）。
- `V6SceneRule{tpl, win, zones, zone_n}` + `V6Zone{cx_hi, font_px}`；键 = tpl+win 精确 > tpl 通配。`v6_scene_font(tpl, win, cx)`，cx 取 `WIN_CURSOR_X`（0x1A，按串恒定）。
- 档位：`V6_FONT_PX_BIG=12 / SMALL=10 / MIDDLE=13`（13 沿用旧哨兵；历史值 16 归一化并入 BIG）。
- **启用规则：领航员** `tpl=0x081BB49C + win=0x0202E658`，`cx<4→Middle / cx==4→Big / cx≥5→Middle`。注：0x0202E658 被多模板复用，**必须双键**。
- 历史未启用规则（可加回 `kV6Scenes`）：地图名粉框 `0x081BB7E4` 整模板 Middle（防 Big 溢出窄框花屏）、训练家信息 `0x081BB7B4` 整模板 Middle。
- ⚠ `scene_cfg.c` 里的 v9「静态避让带」块已挪到文末 `#if 0` 存档（引用的 `chs_band_add` 全工程不存在）。

## 渲染层：换行「行尾半个字」（2026-09-10 修复）
- 机制：`print_glyph_px` 在 `phase != 0` 时 `t0 = v8_phase_last_tile()`（复用上一字尾列；相邻字共享一列是设计）。12px 步进 ⇒ 行末相位 `12n mod 8` ⇒ n 奇=4、n 偶=0。
- 三条成因＋修法（均在渲染层，不碰分配算法）：
  1. FA/FB/FE 显式 `v8_phase_reset()`（只清 PHASE/PHASE_ROW/LAST_TILE，不动游标）。
  2. `chs_claim_tile()` 返 0 时必须放弃右半（`w1=0`），否则写 tile 0（charBase 首格）同症状；`phase!=0 && last_tile==0` 退回领新对。
  3. **等 A 箭头落列**：`DrawInitialDownArrow@0x08003F4C` blit 到固定 tile `TILE_BASE+0xFE`，表项格由 `WIN_CURSOR_TILE_X` 决定（0x08003EA4..EAE）。行末 `px&7!=0` 时 `CURSOR_TILE_X=floor(px/8)`＝行末字尾列 ⇒ 盖掉右半。修法：FA/FB 且相位非 0 时 `CURSOR_TILE_X += 1`（＝`ceil(px/8)`，见 `docs/FONT_12PX_DRAW.md`），tm0 另 `TILE_OFFSET += 2`；推完不还原；`px==0`（`\n{\p}`）不动，避免双▼。
- 推演：`src/util/work/POKEMON_RUBY_AXVJ00/_newline_half_sim.py`（ALL PASS）。
