## text 二次重构方案(只动落址层,一处文件重写+一处删死码)

### 0. 目标
把「一个字形如何按 (textMode, fontNum) 走官方协议落址」收敛为**唯一一份代码**,
FontFunc_hook.c 从 787 行降到 ≤450 行;不再有第二套重复绘制、不再有死代码、
不再在错位处打补丁。hook 面保持现状:entry.s EngineEntry → PrintNextChar_Hook
(官方通道入口),翻译链路与布局层全部不动。

### 1. 不变量契约(写进新文件头,重构不得违反)
1. 官方协议公式逐 mode 不变:tm0 tile=win[0x16]+win[0x18]、off+=2/字、
   UpdateTilemap(tile,tile+1);tm1 原生表项=tileBase+glyph*2(FontSub 查表,
   不消耗 off 链——图鉴列表数字行间不互覆);tm2 dst=win[0x20]、+=0x40;
   tm3 grid=tileData+(col+2+row*30)。
2. 中文 12px 两趟:pass1 宽 8 + pass2 宽 4;off 推进 pass1+2、pass2 sp==0?0:2。
3. curTX 同步式与 phase 校验式**严格同一公式**(含超前量——FC 移列码依赖,
   勿"修正"为真实列,2026-08-30 继续游戏回归已证)。
4. SYM 标点带 0x36-0x3E → 专用字库 0x091E0000(tm1 原生查表里是糊图)。
5. tm1 未登记窗口:中文=tile_alloc 行分配(tile_alloc.c 不动);原生=FontSub_Origin。
6. tm1+font4 → Origin 委托(PrintNextChar_hook 入口已有);tm2 中文 → FontChsSmall。
7. 尾随格清白只对 tile_alloc 白名单模板启用(灼影缓解);FC 移列码场景禁用。
8. FD 内联展开、菜单光标、arrow 前置同步、地图名/战斗/血条/选项菜单各模块接口不变。

### 2. 文件改动
**A. FontFunc_hook.c 重写(787 → ≤450 行)**,分节:
- §0 契约注释(~40)
- §1 相位槽(唯一一份,u16 px + u8 btx + u16 key + u8 char_base + u8 adv,
  8 槽 @0x0203FF84;bind+advance 合一,~50)
- §2 官方协议落址:每 mode 一组「算 tile + 写表项 + 推进」小函数,
  tm0/tm1/tm2/tm3 各 ~15 行(~70)
- §3 字形绘制(唯一一份):12px 两趟 spill(~~85)复用于中文与 SYM;
  8px 移位单趟(~~35)用于 tm0/tm3 原生(半列对齐必需,bak 同理)
- §4 分派:Chs_FontFunc_hook 按 textMode 桥接;中文入口 chs_blit
  (font 选择/tm2 小字/分配器调用/尾随清白,~60)
- §5 tm1 胶水:tm1_cfg/row_base(接 text_layout,~15)
- §6 Origin 包装(外部模块引用面不变,~25)

删除:native_via_phase 整段(90 行,与两趟绘制合并为一份)、chs_advance、
双套 pitch、我历次补丁的叙事注释(契约收进 §0)。

**B. text_render.c 删死代码(307 → ~200)**:ChineseTileState/pitch 系统
(~90 行,零调用者)、text_render.h 的死声明(DrawGlyphTiles/
refpr_draw_tile_shadowed/refpr_colors_init/GetGlyphWidthChinese 中无定义/
无调用者者)。保留:DrawGlyphTile_refpr、copy_tile32、vram_tile、
DecompressGlyph_Chinese、arrow 两件。

**C. 不动**:PrintNextChar_hook.c、text_translater.c、text_layout.c、
text_scene.c、tile_alloc.c(已导出 tile_alloc_lookup)、entry.s、build.bat、
map_name_popup/battle/option/pokedex 各模块、main.asm。

### 3. 行为保持矩阵(重构后逐项过一遍)
图鉴列表数字+名字 | 图鉴说明(标点/句号/灼影) | 凯西混排 | 继续游戏 16:28/55只 |
开始菜单/新游戏 | 对话框+FD 词条 | 选项菜单 PTR/DYN | 战斗(tm2 血条/消息) |
队伍(font4) | 地图名弹窗 | ニックネーム机体名

### 4. 验证
1. build.bat 零新警告;grep 确认被删符号无残留引用;
2. game.map 核对 Chs_FontFunc_hook/PrintGlyph 等入口地址写回 yaml 断点(如漂移);
3. 全流水线(meowth full --seed-only)出 ROM;
4. 交你按行为保持矩阵实测。

### 5. 回滚
单独 commit(不动其他在途改动),可整体 revert。
