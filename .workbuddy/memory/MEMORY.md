# 项目长期记忆（GBA-Rom-Translator / AXVJ00 汉化）

## 用户偏好（铁律）
- 听命令：用户指的路径/方法就是路径本身；先复述计划确认再动手。
- 修 BUG 在当前方案上定位修掉，不擅自回退；确要回退先说明等确认。
- 🔴 代码改动前「预计效果」必须能翻译成实机截图预期；改动完截图符合预期才算交付。
- 🔴 四步法禁止跳过：①静态分析 ②gdb 动态结合 ③实机截图验证 ④结论才可写 MEMORY。未验证结论必须标注，不得当真理推进。
- 运行时故障先怀疑注入机制（relocate/hook 写坏字节），配置开关二分定位。

## v8 架构（当前方案：动态避让，2026-09-07 定稿）
- **静态表已全废弃（用户拍板「要动态获取，不要补丁」）**：kV8AvoidScenes（14签名/37段）与 kV8LinearScenes（线性落址，实测同场景多窗口并发叠印→设置菜单错乱回归）均已删除，scene_cfg 只剩字号配置 kV6Scenes。
- tile 号=顺序分配器 v8_alloc_tile，**动态三层探测**（src/text/tile_alloc.c）：
  ①活引用层：v8_alloc_begin 清零重建位图=win tilemap + DISPCNT 全启用 BG 中同 charBase 的 screenblock（BGxCNT.size 位定 1024/2048/4096 表项；affine/位图 BG 跳过）——多窗口并发互斥、防泄漏靠清零重建。
  ②VRAM 非空层：alloc 逐候选 tile 实时校验 32B 全空——atlas 区（0x208~0x2D1 场景差异自动适配）、begin 后才绘制的官方 UI（关闭按钮/状态图标）自动避开，取代全部静态带。
  ③ours 段表：EWRAM 0x0203FF80（80B=magic 0xA5C3+19 段×4B），非空 tile 仅属 ours 可回收重写；冷启动 EWRAM 残留防御=magic 一次校验。lo=0x100，hi=(4-cb)*512 clamp 1024 不变。
- **✅ 动态避让实机验收通过（2026-09-07 用户确认 OK）**。
- **🔴 性能优化踩坑实录（2026-09-07）**：begin 节流（同帧同签名+VCOUNT 跳过重建）**实测证伪**——继续菜单一帧内关旧窗开新窗，签名/VCOUNT 全不变 → 位图过期，新窗 tile 引用不在位图且图形未写（官方先写 tilemap 后画图，非空层拦不住）→ 中文压新窗疯狂撞（用户截图）。**已删除，恢复每会话全量重建，无任何跳过路径**。教训：活引用重建是权威层，任何「跳过」都在赌官方时序。保留的安全优化：②扫描 u32 化（VRAM 32-bit 总线一次取 2 表项）；③alloc 负缓存（非空非 ours → bit_set，会话内每 tile 最多一次 32B 读，方向保守只多避让）。性能优化只能往「降单次成本」做，不能往「跳过重建」做。
- **坑：ADDR_V6/V7/V8_* 宏曾只手工写在 game.h GEN_ADDR 块内，重生成即丢**（2026-09-07 编译失败实证）。已全部收编进 game_addrs.asm（`; C:` 标记）作唯一权威来源。
- 字号钩子 getFontSize：font4/tm2→8px；设置菜单 curX<8→16 否则 12；其余 12。
- 12px：相位 0/4 行隔离（ADDR_V8_PHASE_ROW=tpl^curY^tileY）；2 字占 3 tile 列、相邻字共享 tile 是数学必然。**换行复位=FE 确定性拦截（2026-09-07 定稿）**：PrintNextChar_Hook 对 FA..FF 普通调用 PrintNextChar_Origin（entry.s 实证其以 push{r4,lr} 重放序言、官方尾声弹回 hook，尾调用非硬件强制），返回后比对 (tileY,tileX) 快照，官方换行 → v8_phase_newline_reset（清相位/last_tile/行标识 + tm0/1 TILE_OFFSET+=2）。NL_MARK 跨字启发式已删除（EWRAM FF4A 释放）；保留 3 字 PHASE/PHASE_ROW/LAST_TILE，各司其职零启发式；相位像素游标本身不可约（官方 0x1A=窗左缘常量，无像素光标可推导）。行键须含 CURSOR_TILE_Y。
- 分层：text_translater=翻译 / PrintNextChar_hook=渲染 / blend_glyph=像素原语 / tile_alloc=分配 / InitTextPrinter_hook=会话边界（复位游标/相位/last_tile，治残留 BUG 的根本）/ scene_cfg=字号配置。
- EWRAM：位图 0x0203FEC0(→FF40)/游标FF42/相位FF44/行标识FF46/last_tile FF48/ours 段表 FF80(→FFCF)；FF4A~FF7F 已释放零占用。⚠ 0x0203FFD2 起游戏数据区严禁占用（背包/队伍死机根因）。
- 翻译链路：非 FA..FF 一律 TranslateHandleChar；slot 表以日文 PCS 查 f900；GetGlyph 只走中文字库；禁止把 code∈[0x36,0x3E] 当 SYM。tm2/fn4 血条名 tpl 0x081BB40C 强制 8px/FontChsSmall。

## 2026-09-07 实测定论（勿再怀疑）
- **官方 IWTD 落址公式（反汇编+实机）**：IWTD(template r0, tileBase r1, glyphIdx r2) **逐字调用**，tm1 分支 dest = tileData + (tileBase<<5) + (glyphIdx<<6) ⇒ **tile = tileBase + 2×glyphIdx，官方无分配器无避让**。IWTD 返回 void（0x08002AEA 处 r0 恒为 thumb 返回地址 0x08002AAB）⇒ IWTD-Ret 断点作废，旧「分区链/预算取返回值」理解作废。
- **cb 回收实证**：对话框场景 cb2 非零仅 tile2；背包场景 cb2 [0x001-0x1FF] 满但 tilemap 对字库区非零引用≈0（引用皆 #201/203/204/207 窗框底色，在 [0x200,0x210)）。⇒ 接管全部文本后 cb2 [0x001,0x200) 512 tile 整块可回收（判据=非零引用，空 entry tile0 不算）。
- **OBJ 余量（OAM 实测）**：战斗场景空闲≈600+ tile；对话框 128 精灵全隐藏（OBJ VRAM 全空）；战斗 UI 场景 0x0200 OBJ 禁用。⚠ OBJ位图@0x03002450 地址错（读到指针），判据以 OAM 为准。
- **MenuDrawStdWindowFrame(bg,x,y,width) 签名实证**（底部菜单 y=28 width=7/11/15）⇒ 窗口预算可靠来源。日版 win 结构 0x40 内无 width/height 字段；战斗窗 0x021E0100 布局未知（[0] 非模板指针）。
- 实测模板频次：战斗 UI 0x081BB514 打点 1020 次（高频硬骨头）；对话框 0x081BB46C tm3(220)、0x081BB5BC(204)；新模板 0x081BB7E4/0x081BB79C（cb0 pal2）。战斗 UI 场景 BG1 cb3 sb27 (0x0600D800)。
- 静态定论（同日早些）：官方字宽上限 8、无原生 12px，但原生亚 tile 拆分（startPixel 任意/mode0+64B/mode2+32B/UpdateTilemap(win,2)）⇒ 8+4 拆分没错，错在 tile 号来源。网格落址需 128~256 连续 tile 非银弹，暂缓。pokeRS 零分配器先例在 tools/Pokemon_GBA_Font_Patch/pokeRS。
- 判读全文：docs/调研_20260907_三路线实测判读.md；检索背景：docs/调研_20260907_三路线全网检索.md。
- 下一步（待决策）：主线落②位置决定（InitTextPrinter 边界复位游标 + tile=winBase+2*idx，先对话框低风险验证）；战斗 UI 单独采集（win 0x021E0100 布局 + 战斗内 MenuFrame 命中）；③OBJ 留兜底。
- 未验证清单：BG stride=32 实际显示宽（UISURVEY 已读 size 位，数据在日志）；win width/height 偏移；商店场景；12px 推进与新落址耦合。

## tile 坐标系（实证）
- tile 号=相对 charBase 偏移 0~1023（10bit 跨 2 个 charBlock）；OBJ 恒 cb4/5（VRAM 0x06010000+）；hi=(4-cb)*512 已修正。
- 模板：对话框 0x081BB5BC/46C/784/484/874 cb2；战斗招式 0x081BB3F4 cb0；队伍窗 0x081BB43C cb1；战斗UI 0x081BB514 cb3；地图名 0x081BB49C cb0；血条 0x081BB40C cb0。模板 24B：charBase@1 screenBase@2 fontNum@8 textMode@9 tileData@0x0C tilemap@0x10。

## 历史教训（思路仍有效）
- 「只有某字被盖」⇒ tile 踩踏；游标状态必须保留归零路径，否则无界累加花屏。
- 可写 static 必须显式落 EWRAM（game.ld 无 .bss/.data 规则）；排查顺序：是否旧包→是否 RAM→逻辑。
- relocate 改指针高危默认 False；改后跑 diag_relocate_collisions.py。F980 短语引用够用。
- reader=读串改串地址随偏移；FC 颜色码打印循环逐字符执行（fc 05 09橙/0f灰白/08红）。
- 打包：一律仓库根 build.bat（勿手抄模块清单）；hook 改完走 hook build→根 build→check_rom_hook.py；编译通过≠交付。🔒P0：build.bat 硬编码 api-key 已入 git，需轮换。
- 识图：node vision.js bug/xxx.PNG（Read 直读 PNG 失败）。
