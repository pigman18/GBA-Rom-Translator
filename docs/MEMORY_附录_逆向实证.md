# AXVJ00 汉化 · 项目长期记忆
> 只留铁律 / 已证事实 / 死路。细节见 `docs/*`、`rules/*.mdc`、`memory/YYYY-MM-DD.md`。

## 🎯🔴🔴🔴 唯一验收标准 = **方案 4**（2026-09-20 用户拍板，**不可再改**）
**判据原文**：中文字形必须以 **11×11 完整像素**落到屏幕 —— 任何字、任何场景、任何行位置。
不允许：缺右列 / 缺下行 / 错位 / 散架 / 被邻字覆盖 / 被 UI 覆盖。
⇒ 一切「为省 tile 而压字」「借道官方画布而裁列」的做法**永久否决**
（方案 3 每行 2 字节、方案 5 / B2 的 8×16 压列、方案 2 的 16×16 —— 全部出局）。
⇒ 遇到「做不到」时的正确反应是**改实现**，**不是降低判据**。
✅ **用户已决策：8 列不够，必须 11 列** —— B2 的「待决策：8 列够不够」已关闭。

**方案 4 = 自写渲染链**（现状架构已符合，见 `docs/方案4_验收标准.md`）：
| 环节 | 官方（8 列定宽，装不下） | 方案 4 自写 |
|---|---|---|
| 解位流 | `CopyGlyph1bppTo4bpp` 每行 1 字节 | `chs_cell_from_1bpp` 按 11 位/行 |
| blit | `0x08003830` `cmp r2,#7` 8 列 | `extract_cols` + `blend_glyph_4bpp` 任意列 |
| 列步进 | `win[+0x1B] += 1` 硬编码 1 列 | `+adv` 列（按实宽算） |
| tilemap | `UpdateTilemap` 只写 2 个纵向项 | 两次调用 → 2 个横向格 × 上下 = 4 格 |

**目的三条**（手段层，服从上面判据）：① 不撞 UI ② 最大利用 cb 区空间 ③ 无容量限制。
🔴 接 UI 分配器只是**手段**之一，不是目的 —— 别钻牛角尖非碰 UI 不可。
❌ 已废判据：①「满池后文字与 UI 一起空白」（v20 灾难根源：奖励「把 UI 搞空」）
②「中文正常显示 + 不撞 UI」（含糊，默许裁字妥协）。

✅ **L1 可执行判据落地（2026-09-20）**：`scripts/verify_plan4.py`
（BDF 真值 → `pack_1bpp` → `chs_cell_from_1bpp` → `print_glyph_px` → `blend/extract_cols`
→ tiles+tilemap → 重建屏幕 → 逐像素比；掩码表从 `blend_glyph.c` 正则提取，**零手抄**）。
**实测：tm0 与 tm1 双路径差异均 = 0 像素**，且 **tm0 == tm1**（tm1 用 64/65/73/74… 完全不连续
的 tile 号，画面逐像素相同）⇒ **现状实现已达成方案 4，且与 tile 号无关**。
未覆盖：换行 / 行末箭头 / tm3 网格(dlow=30) / 9×9 两档 / 分配器耗尽。详见 `docs/方案4_验收标准.md`。

## ✅ 方案 = Wokann（2026-09-12 定案）
字库常驻 ROM、按需把当前字混写进 VRAM ⇒ 无容量限制。
🔴 我们**早已是** Wokann 结构：`GetGlyph()` 直接从 ROM 取字；charmap 是 Wokann
`PMRSEFRLG_charmap.txt` 的**严格超集且零冲突**（6931 项逐字节相同 + 多 44 项）。
⇒ **容量从来不是瓶颈**（8192 槽）。瓶颈是我们自造的 `v8/v9` 分配器 + 12px 相位层。

### 🔴 日版地址表（逐指令反汇编实证；`symbols/pokeruby_jp.sym` 是错的）
`DrawGlyphTiles` **0x08003630**（跳转表 @0x08003678）｜`GGTP` **0x08003730**（表 @0x08003750）｜
`GetCursorTilemapPointer` **0x08003708**（5 行小函数，出 tilemap 项地址；**不是 GGTP**）｜
`UpdateTilemap` **0x080036DC**｜blit 非阴影 `0x08003830`｜blit 阴影 `0x080038A0`。
- ❌ 曾把 `0x08003708` 当 GGTP 入口（差 0x28）。**地址必须逐指令反汇编核，不得按「锚点+偏移」推算。**
- 🔴 **日版 Window 布局 ≠ 美版**（`+0x0F=pal/+0x16=tileDataStart/+0x18=tileDataOff/+0x1A=cursorX/+0x1B=cursorTileX`；
  `+0x0B=fontNum/+0x0C/+0x0D/+0x0E` = `DrawGlyphTiles` 的 a3/a4/a5）⇒ **Wokann 汇编不能照抄**。
- 蹦床区 `0x081B1290..A7` = `svc 0x0C/0x0B/0x12/0x11/0x0F/0x15`（含 CpuFastSet/CpuSet）—— **不要吃**。
- 🛠 反汇编：`arm-none-eabi-objdump -D -b binary -m armv4t -M force-thumb --adjust-vma=0x08000000`；
  `scripts/jp_dis.py` 的 start 参数被忽略（有 bug，慎用）。

### 🔴🔴 `InitWindowTileData 0x08002A50` = font 分派器（表 @0x08002A74）
| font | 分支体 | 怎么画 | 字模源 |
|---|---|---|---|
| 1 / 4 | 0x08002A8C | `bl DrawGlyphTiles` | 经 GGTP |
| **2 / 3** | 0x08002AAC | 直调 `bl 0x08003830` | 硬编码 `0x081B49AC + idx*8` |
| **5 / 6** | 0x08002ACC | 直调 `bl 0x080038A0` | 硬编码 `0x081B51AC + idx*32` |
⇒ font 2/3/5/6 **不经 GGTP**。`DrawGlyphTiles` 表：`[1..3]=0x08003694`(4参)/`[4..6]=0x080036B0`(5参)。

### 🔴 官方链的三个硬约束（= 方案 4 的来源，别再回头试「借道官方」）
1. **官方字模画布 = 8 宽 × 16 高（纵向 2 tile）**：`blit(out0,tileBase)` + `blit(out1,tileBase+0x20)`；
   `UpdateTilemap` 首项后 `adds r0,#64`（=一行）再写次项；`FontFunc[0]`：`win[+0x18]+=2` + `win[+0x1B]+=1`。
   🔴 `GGTP` font0 分支 `0x08003770: adds r0,#8` ⇒ **`out1 = out0 + 8`**（上/下 8 行）；
   `+0x20` 是 **blit 的 VRAM 落点**偏移，曾被误当成字模偏移。原生印证：font0 idx=1「あ」= 8×16、1bpp、16 B/字。
2. **`CopyGlyph1bppTo4bpp 0x08003830` 每行取 1 字节（8 位）**：`cmp r1,#7` 8 行 / `cmp r2,#7` 8 像素 /
   `str r4,[r0,#0]` 整 u32 覆盖写。而中文 `Big1Bpp` 打的是**行间无填充连续位流**（`bits[r*11+c]`）
   ⇒ **每行累积错位 3 位 ⇒ 齐整散架**。这才是「失真」的真机理，**不是宽度裁切**。
   （`CopyGlyph2bppTo4bpp 0x080038A0`：`cmp r4,#31` = 固定 32 B = 1 个 8×8 tile，经 IWRAM `0x03000330`。）
3. 🔴 **日版 `UpdateTilemap` 只写 2 项**，无美版 `if(tilesWidth==2)` 写右列分支 ⇒ 结构性不支持「一字占 2 列」。
   **这才是「必须 8 宽」的真正来源**（不是 blit 的 `cmp #7`）。日版亦无相位、无掩码表（美版 `sGlyphMasks` 搜不到）。

### tm1 链路
`FontFuncTable @0x081BB3AC`（4 项）= tm0 `0x08003569`/tm1 `0x0800360D`/tm2 `0x0800338D`/tm3 `0x08003495`。
🔴 `FontSubTable @0x081BB3BC`（7 项）是 tm1 的**逐字落砖函数表**（不是字体表）。
tm1 处理器：`r2 = FontSubTable[win[0x0B]]; sub_081B12DC(win,r2); win[0x1B] += 1;`
**四个子处理器全部只调 `bl UpdateTilemap`，自身不碰 VRAM、不推进游标。**
⇒ 🎯 **官方只给「格子位置」，不给「tile 号」**。
### 字库（`font.config.json` + `hook/graphic/fonts.s`）—— 🔴 两套 Middle，别混
| 名 | 地址 | 步进 | 文件 | 谁在用 |
|---|---|---|---|---|
| `Middle1Bpp`（extra_bins） | **0x09700000** | **13 B/字** 1bpp 连续流 | `PokeRSFontChsMiddle1Bpp_unshadow(0x16C00).bin` | **`chs_cell_from_1bpp`**（领航员等 9×11 场景） |
| `Middle`（font_slots） | 0x09400000 | 128 B/字 4bpp 独占槽 | `PokeRSFontChsMiddle_unshadow(0xE0000).bin` | 槽表路径，**非** 1bpp 读取 |

Big1Bpp `0x09500000` 16B/字｜Small1Bpp `0x09600000` 11B｜Middle1Bpp **0x09700000** 13B；均 7168 槽。
编码 `(lead<<8)|trail`；每块末 9 槽 `0x?F7..0x?FF` = escape 保留位。
🔴 **槽位不是 `code & 0x1FFF`** —— 字库 bin 只按**有效 lead 页**压实存放，缺页不占空间：
`slot = code - 0x100 × (小于 lead 的无效 lead 个数)`，有效 lead = `chinese_leads` = [1..5][7..26][28..30]
⇒ 缺 0 / 6 / 27。实测 25 字（lead 0x03..0x1E）全中，判据脚本 `scripts/verify_middle_e2e.py`。
（C 侧代码只管 `code & 0x1FFF`，压实由打包/编码侧完成 —— 两边必须一起改。）
🔴 `game.h` 宏名：`ADDR_FONT_1BPP_BIG`(0x09500000) / `ADDR_FONT_1BPP_SMALL`(0x09600000) /
**`ADDR_FONT_1BPP_MIDDLE`(0x09700000)** / `ADDR_FONT_CHS_MIDDLE`(**0x09400000 = 4bpp 槽版**)。
🔴🔴 **`chs_cell_from_1bpp` 必须用 `ADDR_FONT_1BPP_MIDDLE`。** 2026-09-20 事故：误信本文件旧记录
「Middle1Bpp = 0x09400000」把代码改成 `ADDR_FONT_CHS_MIDDLE` ⇒ 拿 13B 步进读 128B 步进数据
⇒ 领航员全屏乱码（用户实机）。**地址一律以 `graphic/fonts.s` 的 `.org` + `.incbin` 文件名为准，
不以任何文档/记忆为准。**

## 铁律
1. 听命令；修 BUG 在现方案上修，不擅自回退。改码前「预计效果」须能译成截图预期。
   🔴 别自作聪明加防御 —— 「防御」恰好就是让系统不按要求工作的东西。
2. 验证分层：L1 静态 → L2 画面（施工期默认验收）→ L3 gdb（仅 L2 判不了才开）。
   🔴 **判据「能自证」≠ 判据「对」** —— 静态复核只能证明「实现了想实现的」（v19 教训）。
3. 🔴 禁抬水位 = 禁设不可用区：cb 全区在分配器里都必须可用。UI 和文本没有任何区别。
   🔴🔴「同一个函数」≠「同一条路径」：判「是否同池」看**走到的入口 + 传进去的 lo**。
4. 🔴 Thumb 桩型先看被钩函数有没有 push：桩 push ⊆ 原体 pop ⇒ 12B 尾跳；叶函数 ⇒ 16B 自带返回。
   🔴🔴 8B 纯跳转 + 要续跑原体 ⇒ **跳板栈净额必须 == 被覆盖指令的栈净额**（v17.1 血案）。
   判据：**跳板内 `push` 只准 1 次**。
5. 🔴🔴 跳转 Thumb 目标地址必须 `|1`。
6. 🔴🔴🔴 绝不 `mov lr, pc` 模拟 bl（bit0 恒 0 ⇒ 切 ARM ⇒ UNDEF `0x00000004`）。
7. 🔴🔴 桩=armips（`;` 注释）、跳板=GNU as（`@` 注释）——**两套汇编器别混**。
   改完必须 `build_sh_equiv.sh` → `pack_no_llm.py`（只 pack ≠ 生效）。
8. 先读源码再动手（`tools/pokeruby` 权威；`pokeemerald-jp` 是**别的游戏**）。
   YAML 地址有错，打桩前必须反汇编核对。未验证标【推论】。
9. Edit 有坑（报成功可能没落盘 / 并行编辑＝写覆盖 / CRLF）。批量改动用一次性 python。
10. 🔴 判死先 grep 调用点；**「没找到调用点」≠「不在路径上」**。
11. 自研扫描器先自证。Thumb BL(T1) `imm11 = hw2 & 0x7FF`；Python `&` 优先级低于 `+`。
12. ROM 指纹查注入区 `0x08800000`。gdb 采集不许依赖 Ctrl-C。
13. 🔴 Python 必须用 `C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe`
    （裸 `python` 不存在）；Git Bash 先
    `export PATH="/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:.../bin:$PATH"`
    （本机 `bash.exe` 找不到 `ls/dirname`，不设则**每条命令都报错**）。
14. 🔴 **手算 Thumb 指令边界必错** —— 必须用 `scripts/jp_dis.py`（objdump 逐指令）。本轮已手算错两次。

## 🔴 屏上的「UI」是两套体系（v20 定案 / 2026-09-12）
**A. 窗口体系（走分配器）**：文字 `v8_alloc_tile`｜框 A/B/C/⑧ + tilemap ⑨b/dlg｜内容区底色 `GetBlankTileNum`。
**B. 静态 BG 层（不走分配器）**：队伍 / 信息页 / 领航员 / PC 箱子 / 简易聊天。
美术 = BIOS `LZ77UnCompVram`@`0x081B1298`（`12df 7047`）解到**固定 VRAM 地址**；
原盘 `bl 0x081B1298` **118 处** / `bl 0x081B129C`(Wram) **42 处**。**从不申请号** ⇒ 池子满对它无效。
- ✅ **v20 已接管 B 类**：桩架在 `0x081B1298`，判据 = **调用点 `lr`**（桩用 `bx` 不改 lr）。
  白名单 **104 处**，**按函数归属**核过（`hook/include/lz_ui_sites.h` + `scripts/gen_lz_ui_sites.py`）；
  排除 **14 处** = 野外 tileset 4 组 + **包装函数 `0x0800A770`**（`LZDecompressVram`，其 lr 被**所有**
  转发调用共享 ⇒ 列白名单＝门控全部）+ 1 个孤立者。
- 🔴 **不能按 dst**：`0811E28A`(野外 tileset) 与 `080791BA`(信息页美术) 落点**字节级同址** `0x06000000`
  ⇒ v19 按 dst 做总闸、24 项静态复核全过、**但判据本身错**，已撤。
- 🔴 **不能按 src**：运行时 src = `tileset->tiles`（动态）⇒ 只能按**函数**归组。
- 🔴 桩的 8 字节必然吃掉 `0x081B129C`(Wram 蹦床) ⇒ 跳板**三分支**，按 dst 还原写粒度。
- 门控**只清图形**，**不动 tilemap**。字体图集**不走 LZ77** ⇒ 与门控完全隔离。

## 🔴🔴 Step B 判决（2026-09-20 实机 A/B）—— 两条「借道官方」路线**全否决**
1. **钩 `GetGlyphTilePointers`**：① GGTP 只覆盖 2 条路径（调用点仅 `0x080033B4`/`0x080035E4`），
   全路径终审出口是 `DrawGlyphTile_Unshadowed 0x08003830`(10 处) + `Shadowed 0x080038A0`(6 处)；
   ② font 2/3/5/6 硬编码常量源，**不经 GGTP**；③ 官方 tm 只给 2 tile，**装不下 11×11**。
2. **tm1 改用 `TILE_BASE + TILE_OFFSET`**：严格 A/B（同存档同脚本）—— 旧版（v8 分配器）设置菜单
   6 行**内容全对**；新版 5 行**堆叠成「普通声」「式」**，越往后被字形碎片污染。
   ⇒ **9-08 结论「AXVJ tm1 无窗口私有区」是对的**：该区**被官方图集预先 LZ77 解入占用**。
   🔴 **「tm1 子处理器只调 UpdateTilemap、不推进游标」≠「TILE_BASE 区空闲」。**
3. `GGTP` 公式（仅供查证，勿再借道）：`font0 = 0x081B3AAC+idx*16`（out1=out0+8）；表 `tbl1 = 0x081B34A8`；
   `idx` = **「字符号 << 4 | 字内子砖号」**，官方上界 `0x0F0`。
   🔴 `chs_cell_from_1bpp` 的 128B 单元（TL@0/BL@0x20/TR@0x40/BR@0x60，墨15/阴影14/空0）
   与 `DrawGlyphTile_Shadowed` 期望格式 **100% 一致**。

### 现状权威 + 旧版病灶
**v6：唯一文本 hook = `PrintNextChar@0x080032F8`(P01)，`FontFuncTable` 不再重定向**（`main.asm:9-11`）
⇒ `REWRITE_DESIGN_混合写入架构.md` §5 是**计划不是现状**。
旧版病灶（8 月 ss5/ss6 实证）：**中文渲染本身成功**（底部描述、`PP21/24`、`ぶんぷ` 全对），
**乱码只在「仍在用日文字形」的短词上**（`かみつき`/`あく` → `+ィあく` 类碎片）⇒
hook **无差别拦所有字符**，把官方日文小字库索引也当成中文 idx。
**对症药：只对中文槽位介入（SlotTable 命中 / idx ≥ 阈值），官方日文 idx 放行走官方路径。**

## 🔴 GBA 输入注入 + 画面采集（实证 / 2026-09-20）
- 注入点 = `0x0800043E`（`ReadKeys` 内 `bics` 之前）：`P3=<key>`+`P2=0` ⇒ `newKeys = key`。
  🔴 `0x0800047E` 太晚。写完**必须摘断点再 `cont`**。I/O 寄存器不可靠 ⇒ 「读 I/O 渲染 PNG」作废。
- ✅ 画面采集 = `PrintWindow` + `PW_RENDERFULLCONTENT` 截 mGBA 窗口（240×183，有效区 160px）。
- 🔴 读档法：把 `.sav` 拷成 `<rom同名>.sav`。`_translated.sav` = 后期存档（55 图鉴/5 徽章）。
  mGBA 起不来 ⇒ **脚本内全程持有 `Popen`**；`config.ini` `logToFile` 已改 0（曾涨到 5.5 GB）。
- 工具：`.tmp/b2_verify.py`（读档版主采集器，23 点）｜`.tmp/b2_capture.py`（13 点）｜`.tmp/b2_nav.py`（18 点）。

## 框链 / 底色（已证）
| 截 | 函数（日版） | 写什么 |
|---|---|---|
| 图形 | A `0x08062094`｜B `0x080620C8`｜C `0x08062100`｜⑧ `0x08062684` | `tileData + 32*框号`，拷 9/14 tile |
| tilemap | ⑨b `0x0806212C`（内层 `0x080621D8`）｜dlg `0x0806266C` | 把 `框号+0..8` 写进 `template->tilemap` |
- 槽引用：`0x03000514` 5 个 = ⑤`0x08062084` 写 A/B/C/⑨b；`0x03000516` 4 个 = ⑥`0x0806236C` 写 ⑧。回看窗口取 `0x100`。
- `GetBlankTileNum`@`0x080041BC`：号=硬编码 `win[0x16]`，从不经池子；`bl` 调用者 **3** 个。
- `DrawStandardFrame` 的 l/t/r/b 是**绝对含端点坐标**；门控语义 = 「框号==0 ⇒ 擦成 0 号砖」，**B/C 必须一起门控**。
- 🔴 v16 `v8_frame_room` 已全删（前提错）：`MultistepInitMenuWindowContinue()` case 3 调⑤ case 4 调⑦，
  pokenav 步进器正调它 ⇒ ⑤/⑦ 一直在领航员路径上。

## 官方机制（pokeruby 源码 + 反汇编实证）
- `TextWindow_SetBaseTileNum`＝`{0x03000514=base; return base+9;}`；dlg 版 +14。**官方没有分配器，全是常量拼号。**
- ① `0x08002950`（叶，不写 VRAM）：清图集游标、`gTplSlot(328)=win[0]`、`gTplBase(32C)=win[0x16]`、按 fontNum 返 512/256。
- ③ `0x080029E0` `MultistepLoadFont` = 唯一 cb 图集写入者（每帧 `bl` ④ `0x08002A50`×16、满 256 返 1）⇒ 封③即封图集。
- 模板 24B：`bgNum@0 charBase@1 screenBase@2 priority@3 fontNum@8 textMode@9 tileData@0x0C tilemap@0x10`。
  日版 textMode 0线性/1图集/2缓冲/3网格。fn4 队伍 9×9 不准碰。
- 号游标 EWRAM `0202E6E8/6EC/6F0`；① 只对窗口步进器调用（`0x0806F006` 菜单链 / `0x080685CA` 领航员链）。
- `LZDecompressVram`=`0x0800A770`、`LZDecompressWram`=`0x0800A764`。
- `0x08070A4C` 实为 `LoadCompressedPalette`（不是 YAML 写的 `DecompressAndLoadBgGfxUsingHeap`，该名 pokeruby 里不存在）。
- 领航员每次进入都重画框（`sub_80EF874` case 10 = `Menu_DrawStdWindowFrame(13,3,29,17)`），开始菜单不重画。
- 逐字渲染包装 `sub_0800338C`：`a->[0x20] += 64`；**无直连 `bl` 调用者** ⇒ 经函数指针表调。
- 窗口 `TILE_BASE`（`game.h:283-292`，互不重叠）：战斗对话/招式台词 `0x90`｜战斗命令 `0x190`/`0x1B8`｜
  tm2 Mode2 `0x254`｜战斗固定 `0x280`（`CHS_BATTLE_FIXED_BASE`）｜PSS 能力/详情 tm1+font3+cb2，
  tilemap `0x0600F000`（模板 `0x081BB5BC`）。

## 已判死（别再走）
- v8 算法、v9.x、v12 纯计数器 UI、`v8_ui_alloc` 零调用期、v16 `v8_frame_room`、**v19 一次 LZ 总闸**、
  **B2 钩 GGTP**、**B2 tm1 借道 `TILE_BASE`**。
- ①`0x08002950` 绝对不 hook 改号（入参同时写 `win[0x16]`＝tm0 线性基址）。
- ⑨`0806F16C/F224`＝绘制热函数；`v11_pool_reset_C` 绝不复位池子游标（＝假回收）。
- 抬水位 / 不可用区 / 登记表 / ours 位图 / 场景签名 / 静态避让带 / 防御式判断 —— 一律不要。

## 交付物 / L1 判据 / 工具 / 地址
- **当前成品**：`roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba`（32 MB）sha1 **`07479112…`**
  （2026-09-20 17:15），内嵌 `hook/out/game.bin` **9060 B** sha1 `b934a886…`。
  `_translated_new.gba` / `_ab.gba` 与主 ROM **同 sha1**（同内容副本）；`*.b2new_keep` sha1 `3b474fba…`（已废）。
- 🔴 **L1 判据（改完必跑，全绿才算完）**：`verify_plan4.py`（差异 0 像素）｜`verify_middle_e2e.py`（25/25 逐位）｜
  `check_font_addrs.py`（字库基址守门）｜`check_hook_in_rom.py`（钩子入 ROM 逐字节一致）。
- ⚠ 本机 `cmd.exe` 被安全策略拦 ⇒ hook 编译用 `hook/build_sh_equiv.sh`（PATH 加
  `C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\14.2 rel1\bin`）；
  打 ROM 用 `src/util/work/POKEMON_RUBY_AXVJ00/pack_no_llm.py`（离线、不调 LLM）。
  权威全量打包仍是根 `build.bat`（由用户侧跑）。`WinError 1224` = mGBA 占着 `_translated.gba`。
- `V18_UI_ON`（`tile_alloc.h`）= UI 总开关（0 关 / 1 开）；v18 管 A 类两出口，v20 补 B 类
  （`v20_lz_ui_C` + 白名单）。`V20LzUi_Hook = 0x088001BC`、跳板 34 B / 三条出口。
- 工具：`scripts/jp_dis.py`（日版反汇编）｜`scan_bl_sites.py`｜`lz77_args.py`｜`gen_lz_ui_sites.py`｜`apply_v20.py`。
  采集：`.tmp/b2_verify.py`（主力）/ `b2_capture.py` / `b2_nav.py`。
- 地址：IWRAM `03000328`=gTplSlot `32C`=gTplBase `32E`=图集游标 `03000514/16`；
  EWRAM `0203FF42`=v8 游标、`0203FFD0/D1`=选项菜单调色板（**不可占**）。
  **hook 地址每次重编都变**，采前查 `hook/out/game.map`。`gMain = 0x030016E0`（`+0x04`=callback1）。
- 字号：Big 11×11@row2 / Small 9×9@row5 / Middle **9×11**@row2（`*outWidth` 报 8，步进 10）。
  `print_glyph`：`t0 == 0` 或 `w1 == 0` ⇒ 降级 ⇒ **违反方案 4，待修**（根因分配器池耗尽）。
