# 项目长期记忆（GBA-Rom-Translator / AXVJ00 汉化）

## 用户偏好（最高优先级，铁律）
- **听命令**：用户指出的路径/方法就是路径本身。先复述计划确认再动手。
- **修 BUG 不擅自回退旧版本**：在当前方案上定位修掉；确要回退先说明等确认。
- **🔴 铁律：任何代码改动前，「预计效果」必须能翻译成一张实机截图的预期样子**。看不到这个预期不写代码。改动完**看到截图符合预期**才算交付，看不到就是没做完（2026-09-03）。
- **🔴 铁律：执行流程固定四步，禁止跳过**——①静态分析（反汇编/查表）②动态结合（gdb_patcher 采集/字段追踪）③实操验证（写代码+实机截图，**只有截图符合预期才算**）④总结结论（这时才能写进 MEMORY）。禁止用未经验证的静态结论当真理推进下一步。
- **运行时故障先怀疑注入机制**（relocate 改指针/hook 写坏字节），用配置开关二分定位，别纠结文本内容。

## v8 架构（2026-09-04 定稿，当前方案）
- **tile 号 = 唯一顺序分配器 `v8_alloc_tile(win,font_px,glyph_len)`**（`src/text/tile_alloc.c`）：运行时扫 tilemap 活引用得避让带，顺序放入、跳过占用、领连续 glyph_len 空闲。屏幕位置继续交官方光标（UpdateTilemap）。**一字一个 tile 来源，16/12/8 统一走同一条路径，无静态表/off 分区/行带表分裂**。
- **字号 = `getFontSize(win)` 钩子**：font4/tm2→8px；设置菜单(模板 0x081BB874) curX<8→16 否则12；其余12。
- **12px 相位 = 按行隔离单变量**（`ADDR_V8_PHASE` + 行标识 `ADDR_V8_PHASE_ROW=tpl^curY^tileY`），非全局 8 槽表。**tile 号分配 与 相位 px 正交**：前者顺序分配器，后者行内像素游标。
- **渲染分层（src/text/）**：text_translater.c=翻译层；PrintNextChar_hook.c=渲染层（解压→栅格化→落址三段）；blend_glyph.c=像素原语（1bpp/2bpp 纯函数零状态）；tile_alloc.c=分配器；InitTextPrinter_hook.c=会话边界（v8_alloc_begin 快照位图+复位游标/相位）。scene_cfg.c=纯字号配置数据。
- **根治来回切换残留 BUG 的根本** = 所有跨窗口状态（游标/相位/last_tile/行标识）在 InitTextPrinter 边界复位，不依赖任何「行指纹 key 续接」启发式。
- **RAM（EWRAM）**：位图 0x0203FEC0(128B→FF40) / 游标 0x0203FF42 / 相位 0x0203FF44 / 行标识 0x0203FF46 / last_tile 0x0203FF48 / **NL_MARK 0x0203FF4A**（上次绘字 tileY<<8|tileX）。⚠ **0x0203FFD2 起为游戏数据区严禁占用**（背包/队伍死机根因）。
- **翻译链路统一**：非 `FA..FF` 一律 `TranslateHandleChar` → 否则 `DrawGlyph`；slot 表以日文 PCS 为 bucket 查 f900；**不要用 F9 判断决定翻译**。
- **GetGlyph 只走中文字库**：ADDR_FONT_CHS_NORMAL/SMALL。**禁止**把 `code∈[0x36,0x3E]` 当 SYM——F9 打包索引也会落此带（「白」=0x0036 → 曾画成「；」）。PCS 标点由 `DrawHalfWidth` 直接读 `ADDR_FONT_CHS_SYM`。
- **tm2/fn4 血条名**：tpl `0x081BB40C`，dest=`win[0x20]`，每列 `+=0x40`，强制 8px/`FontChsSmall`；落在现有 `chs_place_col` 分支，不开平行方法。

## 🔴 经常犯：12px 奇数位换行（「壤」切半 / 句首冒号鬼影）
- **症状**：行末奇数个汉字后 `FE` 换行 → 上行尾半截 + 下行首「：」状碎片（图鉴说明「土壤」经典）。
- **机制**：12px → phase 只在 0/4；奇数个字收尾 phase=4，半列挂在 last_tile。
- **致命陷阱**：`PrintNextChar_Origin` 是**尾调用进 ROM**（`bx` 不回到 hook）。在 `if (c==FE) { Origin(); 清相位; }` 里写的清理**永远跑不到**——以为修了其实没修。
- **定案（对齐 FONT_12PX_DRAW.md）**：在**下一字绘制前** `v8_phase_before_glyph`：TY 变或 TX 回落 → 清相位/last_tile；tm0/1 **恒** `TILE_OFFSET+=2`。行键须含 `CURSOR_TILE_Y`（FE 有时先推 tileY）。
- **作者标注（2026-09-04）**：Auto（Cursor Agent Router）/ Composer。

## v8 已知边界（2026-09-04 实机实证，下一轮任务）
1. **队伍页 HP 条上方 Pokemon 状态图标被中文覆盖（稳定撞血条）** —— 根因=队伍窗 charBase=1 占用段 [0x0EE-0x11A] 罩住 lo=0x100，中文压在状态图标上。已接 kV8AvoidScenes 避让（kPartyScene），**待实机验证**。
2. **设置界面关闭按钮为橙色**（关闭按钮 tile 被中文覆盖、调色板串色）—— 根因=该 tile 不在 tilemap 活引用里、未被避让带覆盖。已接消费方（kOptionAvoidScene 的 [0x001,0x208]），**待实机验证**。
3. 设置菜单偶发缺角（相位共享+动态领号在「字符短+边界 tile 紧邻」下溢出，治本=glyph_len 加安全余量）。
- **根因方向（用户 2026-09-04 判断「缺避让区配置」）**：当前避让带**只来自 tilemap 活引用扫描 + lo=0x100 + OBJ charBlock 上界截断**，漏掉「关闭按钮/血条/状态图标」等不在文本 tilemap 扫描范围的 UI 元素（OBJ 精灵 / 其它 BG 层 / 扫描后才绘制）。
  ✅ **避让带数据已于 2026-09-04 补齐并接入消费方**（`scene_cfg.c:kV8AvoidScenes` → `tile_alloc.c:v8_alloc_begin`/`v8_lookup_avoid`，14 签名全录，见「tile 分配器坐标系」节）。硬件验证待用户实机确认。
  - 已对上的根因：队伍窗 charBase=1，占用段 [0x0EE-0x11A] 正好罩住 `lo=0x100` ⇒ 中文压在状态图标上（与 BUG ① 完全吻合）。

## tile 分配器坐标系（实证，仍有效）
- tile 号 = 相对当前 BG charBase 的偏移，合法范围 **0~1023**（tilemap 10bit + 4 charBlock），**非 0~511**。
- atlas = 官方字库区 = [BASE, BASE+512)，不可标满 [BASE,512)。
- ✅ **OBJ 起始 charBlock 恒为 4**（OBJ tile 固定占 VRAM 0x06010000 起，即 charBlock 4/5）。GBA 的 DISPCNT 没有 OBJ charBlock 字段（bits[4]=Display Frame Select、bits[5]=HBlank Interval Free）。`v8_alloc_hi()` 已改正确公式 `hi=(4-char_base)*512 clamp 1024`（2026-09-04 修复）：char_base=0/1/2→1024；**char_base=3→512（正确拦住相对 512+ = cb4 = OBJ 区）**。旧 `v8_obj_charblock()`（误读 DISPCNT bits[5:4]）已删除。
- ✅ **避让带已全量落盘并已接消费方**（2026-09-04 下午）：`kV8AvoidScenes`（14 签名/7 模板/37 段，从 gdb `[CBAVOID]` 录入，每条带注释）。`tile_alloc.c` 已 `#include "scene_cfg.h"`，`v8_alloc_begin()` 在扫完 tilemap 后调 `v8_lookup_avoid()`：按硬件签名（DISPCNT+BGxCNT，掩码 0x1F8C 归一）查表，命中即把 bands 标进位图；签名未命中按 tpl 兜底。消费策略=**全量避让带（含 atlas 段）**，中文整体挪到 atlas 之上（设置菜单 0x209 起）；14 场景 bands 上限均 ≤0x3FF，仍在各自 cb 相对 0~1023 内，不跨 OBJ 区。待用户实机验证。
- 战斗窗(charBase=0)动态区高段相对号 513+ = 物理 charBlock1 = OBJ 精灵区 ⇒ 花屏；charBase=2 主力窗安全。
- gdb 模板分布（AXVJ00）：主力对话框 0x081BB5BC/46C/784/484/874 charBase=2 base=0x0001；战斗招式 0x081BB3F4 charBase=0；队伍窗 0x081BB43C charBase=1 font4；**战斗 UI 0x081BB514 charBase=3；地图名弹窗 0x081BB49C charBase=0；战斗血条 0x081BB40C charBase=0 font4/tm2**。
- gdb_patcher `--cb-survey` 采集端扫 **cb0~cb5 全 6 块**（`for cb in range(6)`，标签 cb4(OBJ)/cb5(OBJ)），cb4 数据一直有，不是"没开放"。

## 历史教训（诊断思路仍有效；v4/v5/v6 实现细节已删）
- 8px 小字库(font=4)字形有误（v4 曾令设置菜单一律 font=0）。
- 「只有某个字被盖」⇒ 怀疑 tile 踩踏非步进；「是否同一文本块」看 InitTextPrinter 的 cur_x。
- 游标类状态（相位 px）任何分支必须保留归零路径，否则无界累加越界写 VRAM 花屏。
- blend_glyph（src/text/blend_glyph.c）仍是当前唯一像素原语：spillTile 显式传参（官方 mode0 右邻+64B / mode2 +32B，不硬编码）；官方 Width3 展开 4 像素怪癖在 1bpp 路径照抄保逐位等价；对拍 tests/test_blend_glyph.py。

## 日版函数地址定位（实证）
- pokeruby_jp.sym 的 UNVERIFIED 符号偏移不一（带 literal pool），会张冠李戴。最硬验证=扫全 ROM 的 BL 调用点（0 处可能只是函数指针 thunk 调用）。
- gBattleAnims_Moves=0x081D997C；DoMoveAnim 0x08071D98 / LaunchBattleAnimation 0x08071DCC。
- gdb 采集前先 grep -c 验埋点计数，别录完才发现 0 命中。

## hook 关键坑
- **可写 static 必须显式落 RAM**：game.ld 无 .bss/.data 规则 ⇒ 文件级可写 static 被静默塞进 ROM（恒 0 零报错）。查法 `grep -nE "^\.bss|^\.data" out/game.map`；修法 EWRAM 显式放置。
- gdb_patcher：HANDLERS 同名后注册者覆盖（增强埋点要包在所有注册之后）；同一地址只能一个埋点（别名转发）。
- 排查顺序：①打的是不是旧包(check_rom_hook.py) ②可写变量是否在 RAM ③才是逻辑。

## relocate / F980
- relocate 改指针高危（无对齐无区域过滤滑窗，巧合字节也改⇒黑屏），已改 opt-in 默认 False；改后必跑 scripts/diag_relocate_collisions.py。
- F980 短语引用(5B 不改指针)基本够用；🔴 护栏待补：phrase_stream_lookup 不判 code 上界、build_rom_data 无数量上限检查。

## 打包约定
- 🔴 每次改完 hook 源码走完整流水线：hook build.bat → 根 build.bat → check_rom_hook.py。**编译通过≠交付**。
- 🔴 打包一律执行仓库根 build.bat（唯一权威模块清单，勿手抄 meowth full；手抄清单漏「图鉴分类名」出过事故）。验 hook 用复制命令+--seed-only，--modules 照抄。
- 打包用 PowerShell 原生跑（中文参数）；但 `*>&1 | Out-File` 会静默吞输出且**不真正重编**（log 0 行、bin 时间戳不更新）。稳妥：**bash 直跑** gcc/meowth，PYTHONPATH 用 C:\ 路径。判定真编了：`stat -c %y out/game.bin src/*.c` 对比时间戳。
- check_rom_hook.py 的 MODES 表是 v3 遗留，"GRID"读数实为 use_linear，别当真。
- 🔒 **P0**：根 build.bat 硬编码 --api-key 已被 git 跟踪 ⇒ 视为泄露，需轮换+改环境变量+清历史。

## 重构等价性验证（可复用）
改前存 out/game.bin 快照；判据：①bin 大小相同 ②nm -S 符号块在快照中 in 搜索（纯数据块必须全命中）③地址常量逐条核对。别比 elf vs bin 反汇编行数。

## 识图
直接 Read PNG 失败，走仓库根 `node vision.js bug/<目录>/10.PNG "..."`（.env 配 VISION_API_KEY/VAISION_MODEL）。

## 相关文档
docs/START_HERE.md（判断树）/ docs/V8_顺序tile分配器_设计.md（v8 权威设计）/ FONT_12PX_DRAW.md / HOOK_RELOCATE_PLAN.md
