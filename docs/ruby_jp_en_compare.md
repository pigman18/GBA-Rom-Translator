# 美日 Ruby 文本系统对照研究（US AXVE 1.0 vs JP AXVJ）

> 日期：2026-08-24
> 方法：同一套 gdb_patcher 埋点（按游戏分配置/分日志目录），美版 `Pokemon Ruby Version(US).gba`（1.0，地址与 pokeruby.sym 一致）与日版 `AXVJ00` 原盘分别采集队伍页/详情页/战斗/菜单。
> 美版日志：`src/util/work/POKEMON_RUBY_AXVE/`（4.3MB，334 ITP / 3108 GGTP / 4301 UTM / 87 RenderBold）
> 日版日志：`work/gdb_patcher_log.log` 早期 8.5MB 原生采集 + `src/util/work/POKEMON_RUBY_AXVJ00/`（新）
> 目的：为 text_jp2chs 全面接管定案——哪些语义可参考美版，哪些必须以日版反汇编为准。

---

## 一、核心结论（先看这个）

**日美 textMode 语义表完全不同，不可互套。** 美版证据（模板指纹实测）：

| tm | 美版 pokeruby 语义 | 美版实测（模板→用途） | 日版 AXVJ 语义（反汇编定案） |
|----|--------------------|----------------------|------------------------------|
| 0 | 变宽像素直绘 | font3 对话主窗（81E6C58）；**RenderTextHandleBold font4 → 直绘调用方 EWRAM 缓冲**（81E6C74, tilemap=NULL） | FontFunc[0] 无阴影像素直绘 |
| 1 | MONOSPACE：预载 256 tile + map 查表写表项 | **本次采集 0 命中**（美版 Ruby 主流程未见 tm=1） | FontFunc[1] 等宽（SubTable[fontNum] 静态块写表项）——队伍名列表主力 |
| 2 | UNKNOWN2：连续变宽（tileDataOffset 连续推进） | **主力**：font3 五套菜单/列表窗（tileData=0x06008000 charblock2）+ font4（tileData=**gTileBuffer 0x02039360 EWRAM**，HP 数字） | **FontFunc[2] 指针缓冲（win[0x20]，步进 0x40）**——日版特有 |
| 3 | （pokeruby 无此模式） | — | FontFunc[3] 带阴影网格（对话主窗） |

推论：**text_jp2chs 的分发表必须按日版语义**（我们接管的就是日版 ROM）；美版的价值在于「渲染分层思想」（取址/组色/写表项分离、窗口携带输出目标）而非具体模式号。

## 二、美版关键路径实测

### 2.1 RenderTextHandleBold（= Text_InitWindow8004E3C @0x08004E3C）

签名（r0=winTemplate, r1=**tileData/dest**, r2=text）。87 次命中，dest 分布：

| dest | 次数 | 内容（解码） | 用途 |
|------|------|--------------|------|
| 0x02039360 | 60 | `FC 12 08 A2 A1 A1 FF`（FC12=定位、数字码） | **HP 数字 → gTileBuffer**（模板 81E6CAC, font4/tm2/tilemap=NULL） |
| 0x02000000 | 19 | `ＭＥＷ` `ＴＹＲＡＮＩＴＡＬ` `ＥＸＰＬＯＵＤ`… | 详情页/队伍：宝可梦名 → EWRAM 缓冲 |
| 0x02000520 / 0x020006A0 | 8 | `ル` `ファイア` 等技能名片段 | 技能名 → EWRAM 缓冲 |

要点：
- **美版没有 win[0x20] 指针缓冲概念**——dest 是 RenderTextHandleBold 的显式参数，模板仅提供字体/颜色。
- 模板 81E6C74：font=4、**textMode=0（变宽直绘）**、tilemap=NULL——靠 UpdateTilemap 的 `tilemap!=NULL` 守卫跳过表项。
- 渲染完成后由调用方 CpuSet 缓冲→VRAM（与日版 0x02CC0 包装的 win[0x20] 缓冲**同构不同形**：日版把 dest 塞进窗口字段，美版走参数）。

### 2.2 UpdateTilemap（@0x08006954）

签名 **(win, tilesWidth)**——与日版 (win, upper, lower) 完全不同：
- pokeruby：写 cursor 处 1~2 列，列内容从窗口 tileData 区的连续分配推算（tileDataOffset 模型）；tilesWidth=0 → 空操作（实测 1009 次 w=0 占位调用）。
- cell 跨度 0..1851：美版存在 **>32 行的 tilemap**（64x32 大地图 BG），cursor 直接以格为单位推进。
- 日版：成对 upper/lower 直写，cursor 字段就是格坐标（无 >>3）。

### 2.3 字库预加载

InitWindowTileData @0x02A50 本次未命中（美版主流程的 tm=1 窗口为 0）——**美版 Ruby 的 MONOSPACE 预载块在主流程中不存在**，进一步证明日版 tm=1/SubTable 静态块是日版特有布局。

### 2.4 控制码

美版流内实测：`FC 12 xx`（SetCursorX）、`FC 08 xx`（Pause）、`FC 13 xx`、`FC 0B`——与 pokeruby sExtCtrlCodeFuncs 1..16 一族一致；日版 FC 子处理器（sub_8003110，类型 1-16）与之同构（已在 docs/ruby_jp_text.md §六A 定案）。

## 三、日版侧对照数据（引用既有定案）

| 日版路径 | 模板/窗口 | 语义 |
|----------|-----------|------|
| 对话主窗 | win=03004170 + tm=3 font3 | FontFunc[3] 网格（x+y*30，无 origin） |
| 队伍名列表 | win=03004170 + tm=1 font4（模板 0x081BB43C, charBase=1, tileData=0x06004000, tilemap=0x0600F000） | SubTable[4] 静态块写表项 |
| 开始菜单 | win=0202E658 + tm=3 font3（0x081BB46C, charBase=2, tileData=0x06008000, tilemap=0x0600F800） | FontFunc[3] 网格 |
| 请选择框 | win=0202E658 + tm=1 font3（0x081BB484, tilemap=0x06007800） | SubTable[3] 静态块 |
| 槽位 Lv/HP/昵称 | win=020231CC + tm=2 font4（0x081BB40C, tilemap=NULL, **tileData=0x06010000 OBJ**） | **幻影：win[0x20] 恒 0**（实测 13/13），原生写 0=无操作 |
| 详情页字段 | 0x02CC0 包装强制 tm=2 + win[0x20]=dest | 真缓冲渲染 |

## 四、对 text_jp2chs 的指导意义

1. **分发表按日版语义**（已正确）：美版 tm 号不可参考。
2. **TextMode2 缓冲方向正确**：日版详情页 = 「画到调用方给的 RAM 缓冲」，与美版 RenderTextHandleBold 同构；差异仅在 dest 传递方式（日版塞窗口字段）。**dst==0 守卫保留**（幻影打印原生即无操作）。
3. **【未解】槽位可见数字的真实通道**：日版 020231CC 幻影打印 dst=0，但 JP 截图数字可见 → 存在未接管的可见通道。候选：a) [0x20] 在打印后被原生改写（需对 0x020231E8 挂写观察点）；b) 另一窗口/系统的数字渲染。**这是血条乱码的最终谜题**。
4. **【未解】详情页乱序**：需在详情页打开时抓 Buf2（dst 值）+ UTM，验证每个字段的 dest 是否与 0x02CC0 传入一致、有无后续覆盖。
5. **汉字尺寸**：美 font4 与日 font4 同为 8×8 单 tile 小字；我们 12px 汉库在小字窗（tm=1/tm=2）需要小号变体或缩放策略——美版无解可抄（美版没有汉字），需自制点阵。
6. **UpdateTilemap 模型差异**：日版成对直写模型已正确复刻；美版 tilesWidth 模型仅用于理解 pokeruby 源码，不落地。

## 五、工具变更记录（本轮）

- gdb_patcher：日志按游戏分目录 `src/util/work/{gameId}/gdb_patcher_log.log`；美版布局支持（`layout: us`，pokeruby struct Window 0x30 字节段）；新 handler：RenderTextHandleBold / GetGlyphTilePointers / Text_UpdateWindow；UpdateTilemap 双签名分支（JP 成对 / US tilesWidth）；非日版游戏不做假名解码。
- 新配置：`src/util/configs/POKEMON_RUBY_AXVE.yaml`（12 点，pokeruby.sym 地址，1.0 ROM）。
- 修复：UTM JP 分支 `cur`→`curv` NameError。
- JP 引擎回滚至「大突破」版（TextMode2 桩 / 单游标无上界 / origin 非门控），game.bin 8848B；roms/outputs 成品如需同步需重跑打包。

## 六、待办

- [ ] 定位日版槽位数字可见通道（0x020231E8 写观察点 / 排查 UpdateNickInHealthbox 域）
- [ ] 详情页打开时抓 Buf2+UTM（dst 值与字段 dest 对照）→ 修详情页乱序
- [ ] mode1/tm2 小号汉字点阵（8px 高变体）——美日皆无现成解，需自制
- [ ] TextMode2 重实现（读完 battle_interface 渲染链后，按日版 0x02CC0/FontFunc[2] 语义）

---

## 七、JP 原生详情页模型定案（2026-08-24 成品ROM采集）

采集：成品 ROM 队伍→详情页（ITP 240 / UTM 573）。关键发现：

**详情页字段渲染模型（JP 原生）**：
- win=03004170、tm=0、fn=3（FontFunc[0] Linear 语义）
- **每个字段一次独立打印，调用方传专属 TILE_BASE**：实测 0x290/0x2A2/0x2C0/
  0x300/0x310/0x320/0x330（656~816，远超 512——BG 4bpp 索引 10bit 跨双 charblock，
  详情页 BG 的字库区在高段）
- **cursorY = 字面 tilemap 行**（55/57——详情页 BG 为大 tilemap，视口滚动到高行区）
- u = TILE_BASE + TILE_OFF（TILE_OFF 由调用方给非零初值 6~0x10），cell=(CY+TY)*32+(CX+TX)
  例：TILE_BASE=0x310+6=0x316=790 @ cell 1762=(55,2) ✓

**我们乱序的根因**：详情页 tm=0 被场景门控判进 Mode2 网格
（idx=CY*30+CX+TILE_BASE+origin → 55*30+... ≈ 2400+，远超表项合法域）→
上传/表项全错位。用户看到的"非12px"= 落错 tile 后显示的 font3 原生字形残留。

**修正方案（下一轮，待确认后实施）**——恢复 pokeruby 的模式语义分工：
1. sPrintGlyphFuncs[3] 独立成行 = 原生 FontFunc[3] 语义：网格公式
   idx=(CX+TX+TILE_BASE)+(CY+TY)*30，逐字形上传+UpdateTilemap
   （开始菜单/HP 区等原 tm=3 场景归它，origin/band 调校随行）
2. PrintGlyph_TextMode0 回归纯 Linear（u=TILE_BASE+TILE_OFF+floor，
   cell=原生 GetCursorTilemapPointer 公式）——详情页 tm=0 归它
3. 场景门控（shop/party-footer/menu-band）随 tm=3 行走，tm=0 不再做二次分发
4. 槽位 tm=2 缓冲 + dst==0 守卫维持（幻影打印已定案）

这样 tm0/tm1/tm2/tm3 四行 = 四种原生语义一一对应，场景特判收敛到 tm3 行内。
