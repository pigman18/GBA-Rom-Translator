# 重写设计稿：文本渲染层「混合写入」架构

> 状态：设计稿 v1（2026-08-31），已与用户对齐方向。**步骤 1 已实施并全绿**
> （2026-08-31：blend_glyph 三层对拍通过，v4 引擎已整体移入 bak/text-v4）。
> **步骤 2 已实施**（2026-08-31：FontFuncTable 4 表项重定向 + PrintGlyph/DrawGlyph
> 新渲染路径，编译/armips/表项校验全绿；tm1/tm2/tm3 像素路径留待步骤 3）。
> 结论一句话：**放弃运行时 tile 槽位分配，回归官方「混合写入」渲染语义；
> 字号（8/12/16px）退化为自由参数；运行时零 tile 分配状态。**

---

## 1. 背景：为什么必须重写而不是继续修

当前验收被以下 BUG 反复阻塞（部分修复后复发）：

| 场景 | 症状 |
|---|---|
| 捡拾道具提示 | 修了复发 |
| 对战信息 | 乱匹配 |
| 队伍底栏 / 队伍名 | 乱码 |
| 详情页进技能选取 | 左上角 No 变乱码 |

这些没有一个是"算错数"，全部是**状态串门**（tile 踩踏、槽互相顶掉、游标漂移）。
机制诊断：现架构让字形**独占 tile**（槽位分配 + tilemap 引用改写 + 相位/pass2/行键
模拟共享），而数据本身没有"所有权"语义——所有补丁都是在给这个错误语义擦屁股。

## 2. 三条证据链（结论的依据）

### 2.1 美版官方补丁工具 `tools/Pokemon_GBA_Font_Patch/pokeRS`

全局汉化只需极少量 hook：

- **`DrawGlyphTiles+2`（0x08006876）→ DrawGlyphTilesChinese**：唯一的核心渲染 hook；
- `GetGlyphWidth+2` / `GetStringWidth`：宽度 hook（**美版才有这两个函数**）；
- 对战血条 ×3、寄放系统 ×2：**不走标准文本打印器的窗口**逐个专用 hook（美版也躲不掉）；
- 字库：**整体替换 ROM 字体数据**（Normal/Small 各 0xE0000 字节 ≈900KB，扩容 32MB），
  索引→地址是纯函数，运行时零可写字库状态。

### 2.2 D 商/历史汉化

经典 D 商版是 **8px 瘦小字体**：汉字点阵塞进半角 Latin 字库槽（单字节编码），
走官方可变宽度通道。他们没有发明任何落址系统——因为官方 blit 本来就是混合写入。
代表作：Tom_C《宝可梦金·银》韩版汉化（2021–2024 持续迭代）。

### 2.3 官方 blit 源码（`tools/pokeruby/src/text.c:3877` DrawGlyphTile_UnshadowedFont）

官方 blit 是**逐像素 RMW 混合写入**：

- `sGlyphMasks[width][startPixel]`：任意宽度 × 任意亚 tile 起点都有现成掩码；
- 先 `buffer[n] & mask` 读出 tile 已有像素，字形像素移位 OR 进去再写回，
  **mask 外像素原样保留** ⇒ 相邻字符共享 tile 天然无损；
- `startPixel + width > 8` 时原生写下一列（`buffer += 8`）⇒ 跨列共享是内置能力；
- 返回值 `(startPixel + width) / 8` = 官方游标推进列数。

**推论：tile 从不"属于"任何字形，它只是一张可多次部分混合写入的画布。
12px 字距的推进序列（列数 1,2,1,2…平均 1.5）在混合写入下完全自洽。**

## 3. 日版 AXVJ 与美版的实质差异（实施前必须知道）

以下均为已反汇编定案，登记在 `configs/POKEMON_RUBY_AXVJ00/hook/game_addrs.asm`：

1. **日版没有 GetGlyphWidth / GetStringWidth**（2026-08-22 定论，勿再订址）。
   打印步进硬编码在各 FontFuncTable 处理器里（FontFunc[0]@0x08003568
   画后 `[win+0x18]+=2`，即 16px 一档；tm1 等宽处理器 `[win+0x1B]+=1`，8px 一档）。
   ⇒ 美版"hook 宽度函数"的路在日版不存在，**改为重定向 FontFuncTable 表项**。
2. **FontFuncTable 是数据表**（@0x081BB3AC，fontNum 索引；二级表 FontSubTable@0x081BB3BC）
   ⇒ armips 把表项重定向到我们的 C 处理器，比 hook 代码更干净，且天然覆盖全部 textMode。
3. **字库 ROM 化已经存在**：FontChsNormal@0x09000000、FontChsSmall@0x09100000、
   Sym@0x091E0000（128B/字容器）。这一半迁移零成本。
4. 现架构是 **PrintNextChar（0x080032F8）整函数替换**，自研游标/槽位/相位全在这一层。

## 4. 目标架构

### 4.1 架构不变量（重写后任何代码不得违反）

1. **运行时零 tile 分配**。tile 内容只允许两种产生方式：
   - 动态文本：blend 原语混合写入窗口 tileData 缓冲（官方语义）；
   - 静态预渲染文本：构建期烘焙进 ROM 数据（translate/build 管线完成）。
2. **tilemap 位置只由官方游标驱动**。不得维护第二套游标；
   处理器推进量一律取 blend 原语的返回列数。
3. **字库常驻 ROM，索引→地址纯函数**（沿用现有 0x09xxxxxx 字库）。
4. 未登记的窗口/字体组合必须显式报错，禁止静默走默认路径。

> **例外条款（2026-08-31 拍板，tm1 静态段分配）**：官方 tm1 处理器只写
> tilemap 引用预渲染 tile 号（FontSubTable 反汇编实证：font0/3 =
> BASE+2·glyph、下半=+1），**没有任何动态 tile 落点**，中文必须有人决定
> VRAM 放哪。故对**已登记窗口**引入唯一例外：
>   - **声明式配置表**（模板地址键控，`text_render.c kTm1Windows`）登记
>     逐窗验证过的空闲 tile 段；禁止启发式猜空闲区（场景门控边界）。
>   - **行游标复用官方字段 `win[0x18]`**：官方 tm1 从不推进它、AddTextPrinter
>     每行清 0 ⇒ 行首（==0）写入段基址，行内由中文路径推进，行尾官方自动
>     复位。slot 按行位置取模（`(y&31)>>1`），重绘幂等、零自研状态。
>   - 像素仍走 blend RMW（tile 无所有权），tilemap 仍只经官方 UpdateTilemap。
>   - **未登记窗口维持「消费+推进」静默旧行为**（本条是对 §4.1.4 的让步：
>     未验证空闲区前画像素 = 写坏场景图形，静默不画比显式报错更安全）；
>     每登记一个窗口须在配置表旁注验证依据（谁在何时用什么手段验证）。

### 4.2 与现状的对比

| | 现状（作废） | 新架构 |
|---|---|---|
| hook 点 | PrintNextChar 整函数替换 | FontFuncTable 表项重定向（+少量专用窗口 hook） |
| tile 语义 | 槽位分配/独占 + tilemap 引用改写 | 混合写入（RMW），无所有权 |
| 状态 | 7+ 个 EWRAM 地址互相耦合 | **零**（无 LRU、无槽表、无页游标） |
| 机制文件 | zones/kOptRows/chs_slots/相位/pass2/行键/last_off | 全部删除（git 保留） |
| 字号 | 12px（相位机制根源） | 8/12/16 自由参数，默认待定 |

**删除清单**（EWRAM 一并释放）：ChsPitchCtrl@0x0203FF80、ChsPitchSlots@0xFF90、
GlyphPageCurTab@0xFFD2、ChineseTileState@0xFFF8、SlotTableVMA@0x09EA0000、
kOptRows/kOptZones/chs_slots*.inc、gen_tm1_slots.py 链。

**保留清单**：F9 协议/PhraseTable/SLT2（文本编码层，与落址正交）、
打包链路（根 build.bat 权威清单）、relocate 体系、字库生成、
血条/寄放系统等专用窗口 hook（美版同样需要，逐个收敛，不做通用机制）。

### 4.3 blend 原语规格（新渲染层唯一的新函数）

```c
/* 把字形像素混合写入窗口 tileData。语义照抄官方 DrawGlyphTile_UnshadowedFont：
 * - colors: 值→色号 LUT（1bpp 用 [2]={bg,fg}，2bpp 用 [4] 直通），RMW：
 *   首 tile 跨度 [startPixel, startPixel+width) 内整段重写（0 号色=bg），
 *   跨度外像素逐位保留；
 * - startPixel+width>8 时溢出段 OR 进 spillTile（纯 OR，不清底）；
 * - 返回推进列数 = (startPixel + width) / 8 —— 游标推进唯一依据。 */
uint32_t blend_glyph_1bpp(uint32_t *destTile, uint32_t *spillTile,
                          const uint8_t *rows /*8B, bit7=最左像素*/,
                          uint32_t width, uint32_t startPixel,
                          const uint8_t colors[2]);
uint32_t blend_glyph_2bpp(uint32_t *destTile, uint32_t *spillTile,
                          const uint8_t *rows /*16B, GBA 2bpp 序*/,
                          uint32_t width, uint32_t startPixel,
                          const uint8_t colors[4]);
/* 中文 4bpp 字库入口（2026-08-31 步骤 2 修正时新增，方案 A）：
 * rows = 32B GBA 4bpp tile（每 u32 一行 8 像素，低 nibble=最左）；
 * colors[16] 值→色号 LUT 直通（字库索引 0=底色/14=阴影/15=前景）。 */
uint32_t blend_glyph_4bpp(uint32_t *destTile, uint32_t *spillTile,
                          const uint8_t *rows /*32B, GBA 4bpp tile*/,
                          uint32_t width, uint32_t startPixel,
                          const uint8_t colors[16]);
```

- 纯函数、无全局状态 ⇒ 可离线单测（Python 参考实现 + C 实现对拍）。
- 官方 `sGlyphMasks` 掩码表直接引用（vendored 副本同表）。
- **spillTile 显式传参（2026-08-31 定案，修正本稿初版签名）**：官方
  mode0 窗口 tileData 物理右邻 = +64B（+16 u32），mode2 血条缓冲右邻 =
  +32B（+8 u32）——右邻距离随布局不同，不能硬编码在原语里（初版
  "destTile 单指针 +8 续写"的假设与官方 mode0 不符）。无溢出传 0。
- 上游怪癖（照抄保逐位等价，已实证）：官方 Width3 特化函数实际展开
  4 个像素（pret 源码 "XXX: why 4?"）；顺序文本下被下一字形跨度重写
  即时覆盖，死代码。2bpp 路径不复制该怪癖。
- 实施状态：`src/text/blend_glyph.c` + `include/blend_glyph.h` 已落地；
  对拍 `tests/test_blend_glyph.py` 三层全绿（C↔官方 vendored 2000 例
  逐位一致；Python↔C 1016 例一致；掩码表直接从 vendored 源码解析）。

### 4.4 两条渲染路径

- **动态文本**：FontFuncTable 处理器（C 实现）→ F9 解码后的流里遇中文
  → ROM 字库取字形 → blend_glyph 写窗 → 推进 = 返回列数。
  非中文 tail call 官方原处理器，行为不变。
- **静态预渲染窗口**：tm1 处理器同样重定向到 blend 路径（官方
  PrintGlyph_TextMode1_Origin@0x0800360C 本身就是运行时 blit，等宽步进而已）；
  真正烤死在 ROM 图形里的文字走构建期烘焙（D 商重绘思路），运行时无感知。

## 5. 实施计划（每步独立打包实测，可单步回退）

1. **blend_glyph + 离线单测**：C 实现与 Python 参考实现对拍（随机 width/startPixel/底图）。
2. **FontFuncTable 重定向 + 16px 主字体先行**（✅ 已实施）：
   - `src/text/hooks_origin.s`（P25）：.org FontFuncTable 写 4 个表项
     → FontFuncTm0..Tm3_Hook（恰 0x10 字节止于 FontSubTable，二级表不触碰）；
   - `src/text/fontfunc_hook.c`：4 thunk = `TranslateHandleChar(win,c) ‖
     FontFunc_NativeDispatch(tm,win,c)`（直调 Origin 地址，防经表递归）；
   - `src/text/text_render.c`：PrintGlyph mode0 = 16px 整格（解压 4 tile →
     **blend_glyph_4bpp 混合写入 VRAM**（colors[16] 值→色号 LUT 直通，
     0→底色/14→阴影/15→前景；tile 无所有权、跨度外像素保留）→ 每列
     UpdateTilemap + cursorTileX++ → TILE_OFFSET+=4）；tm1/tm3 = cursorTileX+=cols、
     tm2 = win[0x20]+=cols*0x40 的消费推进；DrawGlyph = SYM mode0 自绘（8px
     单列）/ ≥0xF7 消费 / 其余原生分发。P01/P05/P24 随新架构废止。
     （2026-08-31 修正：初版误用 CopyGlyph2bppTo4bpp 整块覆盖，违背 §4.4
     blend 架构不变量，已改回 blend_glyph_4bpp 混合写入。）
   - 已知留白：tm1/tm2/tm3 像素路径未实现（消费+推进），中文在这些窗口
     暂不可见——步骤 3 逐窗收敛；SYM 标点在非 mode0 走 JP 同码回退。
3. **逐窗口收敛**：血条、寄放系统、捡拾提示等专用 hook 补齐（对照美版清单）。
4. **删除旧机制**：zones/槽表/相位/EWRAM 变量/SlotTableVMA 一次性摘除，重跑等价性验证。
5. **（可选）12px 主字体**：字号此时只是参数，若需要再开；PTR/槽位脚本链不再存在。

## 6. 验收清单（底线）

五 BUG 场景：捡拾道具提示（含复发路径）、对战信息、队伍底栏、队伍名、
详情页→技能选取（左上 No 完好）。
回归场景：设置菜单、战斗、图鉴（含分类名）、对话、商店/背包菜单 ▶。

## 7. 风险与开放问题

- **宽度单位**：美版 GetGlyphWidthChinese 返回值单位（4/2）与日版处理器硬编码
  步进的换算关系，实施期对照日版引擎实测定死（歧义记账，不阻塞架构）。
- F9 协议与官方状态机的接缝：F9 解码层保留，但其在打印状态机中的插入点
  需在新处理器里重新对齐（现状 PrintNextChar 整替换承担了这部分）。
- 静态烘焙窗口的清单需枚举确认（少数；优先级最低）。

## 8. 参考索引

- 美版工具源码：`tools/Pokemon_GBA_Font_Patch/pokeRS/`（main_R.asm 为 hook 总清单）
- 官方 blit：`tools/pokeruby/src/text.c:3877`（DrawGlyphTile_UnshadowedFont）
- 日版地址唯一权威：`configs/POKEMON_RUBY_AXVJ00/hook/game_addrs.asm`
- 本轮调研工作日志：`.workbuddy/memory/2026-08-31.md`
