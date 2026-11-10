# GBA 渲染 12px 字体：方案总结

> 核心判断：12px 的难点不是"能不能画出来"，而是**它和硬件 8×8 tile 网格不对齐**。选哪条路，取决于文本是静态还是每帧动态。

---

## 一、硬件约束速查

| 项目 | 参数 | 影响 |
|---|---|---|
| 屏幕 | 240×160 | 12px 下每行正好 20 字、每屏 13 行，中文 UI 尺寸很舒服 |
| Tile 尺寸 | 固定 8×8 | 12×12 汉字横跨 **2×2 = 4 个 tile**，只填空闲像素约 56% |
| 4bpp tile | 32 字节/tile | 8bpp 为 64 字节/tile |
| VRAM | 共 96KB @ `06000000-06017FFF` | mode 0/1/2 下 64KB 由 BG Map 与 Tile 共享（BG Tile 至少占 32KB），OBJ Tile 32KB |
| Mode 3 | 单帧缓冲 80KB（实占 75KB）+ OBJ 16KB | 16bpp，无页翻转余量 |
| Mode 4/5 | 双帧缓冲各 40KB（Mode 4 实占 37.5KB）+ OBJ 16KB | 8bpp，可页翻转 |
| 调色板 | 1KB Palette RAM；4bpp 下每 tile 独立选 16  palette | **tile 拼接处最容易踩调色板冲突** |
| OAM | 1KB，最多 128 个 OBJ | 限制精灵方案的字数量 |

数据来源：[GBATEK - LCD VRAM Overview](http://www.akkit.org/info/gbatek.htm)、[Tiles & Maps (stdgba)](https://felixjones.github.io/stdgba/graphics/tiles.html)

**两个必须处理的底层坑：**

1. 4bpp tile 每个字节存**两个点**，低 4 位左点、高 4 位右点；一个 12px 宽的字跨两个 tile，左右两半各自引用 palette，必须保证两半落在同一 palette 或各自不冲突。
2. ROM 字形数据是 16bit 总线、默认等待周期较慢，逐像素读 ROM 会明显拖帧（详见第四节）。

---

## 二、三条路线对比

| 方案 | 适用场景 | CPU 开销 | 主要代价 |
|---|---|---|---|
| **A. 文本层 + 4bpp tile 图集** | 剧情对话、菜单、静态 UI | 极低（只写 screen entry） | 需预栅格化 + 处理 tile 拼接 |
| **B. 8bpp 位图模式直绘（mode 4）** | 滚动、淡入淡出、彩色渐变 | 中（纯 CPU blit） | 无硬件排版，必须自己做脏矩形 |
| **C. 精灵层 OBJ** | 血量数字、伤害飘字（十几个字符） | 低 | 128 OBJ 上限，正文会吃光预算 |

---

## 三、方案 A：文本层 + 4bpp tile 图集（推荐）

把 12×12 字形预栅格化成 4bpp，塞进 8×8 tile 图集，运行时只写 screen entry —— 显示静态文本最高效的做法，CPU 几乎不参与。Tonc 的评价同样是：tilemap 方式是**静态文本最高效的路径**。[citation:3]

### 关键技巧

**1. 别按 2×2 整块存，用 BIOS `BitUnPack` 现场展开**

- 源数据保持 **1bpp**：256 个 8×8 字形仅 2KB，展开成 4bpp 后 8KB
- `BitUnPack` = **SWI `10h`**，把 1/2/4/8bit 位图提升到更高位深，官方用途举例就是"把 1bit 单色字体转成 4bit/8bit GBA tile"[citation:1]
- 调用约定：`r0` 源地址（无需对齐）、`r1` 目标地址（**必须 4 字节对齐**，可写 VRAM）、`r2` 指向 UnPack 信息结构：

```
+00h 16bit  Source 数据长度（字节）
+02h 8bit   源单位位宽（1/2/4/8）
+03h 8bit   目标单位位宽（1/2/4/8/16/32）
+04h 32bit  Data Offset（bit0-30）+ Zero Data Flag（bit31）
```

- Data Offset 会加到所有**非零**源单位上；置了 Zero Data Flag 则零值也加。利用这一点可以把 0/1 直接映射成"透明 / 前景色索引"
- 展开结果长度必须是 4 的倍数；源单位宽度（加 offset）不得超过目标宽度

**2. 用位平面（bitplane）编码绕开调色板地狱**

每个 8×8 单元只用 **2 个位平面**，即可表达背景色 / 前景色 / 阴影描边三色，9 个调色板条目搞定全屏文字。换配色只需重写 palette RAM，不用重绘一个像素。TTE 内部也采用类似思路，预定义了 `TTE_INK`(0) / `TTE_SHADOW`(1) / `TTE_PAPER`(2) / `TTE_SPECIAL`(3) 四个色槽。[citation:11]

**3. ASM 里做字形缓存**

维护"已上传 VRAM 的字形 → tile 索引"哈希表，同行对话里重复汉字只传一次。这是汉化 ROM 的常规做法；12×12 字库配合缓存后，一屏对话的**实际唯一字形通常只有 60~100 个**，远低于 20×13=260 个格子。

**4. 字库先瘦身**

只保留 GB2312 一级字 + 脚本实际出现的字符，别整库塞进 ROM（GB18030 全库 21 万字，12×12 4bpp 就是约 45MB，完全不可行）。

---

## 四、方案 B：mode 4 位图直绘

一字节一像素，字形想画哪画哪，没有 tile 边界问题，半透明 / 渐变 / 抗锯齿都自由；双缓冲可页翻转。

**代价是纯 CPU 拷贝，所以别用 `SetPixel` 逐点画** —— 那是 144 次函数调用加 144 次地址计算。正确写法：

**1. 字形按行存储，整行打包**

每行 12 位打包，用 `u32` 一次读出一行，掩码后直接写半字。业界现成格式就是这样：`gba_agb_font_renderer` 的字形数据以 `u32` 存储、每个 `u32` 装 8 个 4bpp 像素，**每行占 `(glyph_width + 7) / 8` 个 u32**，palette 索引 0 为透明。[citation:5]

**2. 常用字形拷进 IWRAM**

IWRAM 32KB 单周期访问。把 ASCII 部分或高频汉字驻留其中，实测每行像素的等待周期能少约 **8 倍**。官方 crate 文档也明确建议：printable font 放 IWRAM"每行像素等待周期少约 8×，小字体（约 3KB）才值得"。[citation:5][citation:8]

对照 ROM 侧成本：Game Pak 默认等待周期 5/5/8（8/16/32bit），且 **DMA 只有通道 3 能访问 ROM**。

**3. 只重绘脏矩形**，别整屏刷（37.5KB 全刷一帧根本来不及）。

---

## 五、方案 C：OBJ 精灵

适合血量数字、伤害飘字、弹出动画（OAM 带缩放/旋转参数）。但一行 20 字正文会迅速吃光 128 个 OBJ 预算。

agbrs 的 `ObjectTextRenderer` 走的是另一条路子：**把一串字符打成一个 group、用一个精灵承载**，并建议把排版/上传工作分摊到多帧，以避免掉帧或音频卡顿。[citation:9]

---

## 六、12px 中文字形本身：最容易翻车的一环

直接从 TTF 栅格化 12px 宋体，笔画会糊成一团。汉化作品看着舒服，是因为用了**手工调过的点阵字库**：该连的连、该断的断，横竖线锁在整像素上。

### 推荐字形来源

| 资源 | 说明 | 许可 |
|---|---|---|
| [文泉驿点阵宋体 12px](http://git-hub.com/AmusementClub/WenQuanYi-Bitmap-Song-TTF) | 12×12，覆盖 GB18030，源 `wenquanyi_9pt.pcf`，逾 21 万汉字点阵经手工优化 | GPLv2（含字体嵌入例外）[citation:16][citation:17] |
| 文泉驿 12pt 规格 | 该字号即对齐国家标准 **GB19966** 点阵 | 同上 [citation:13] |
| Unifont | 覆盖极全，但 12px 段为 8×16 结构，中文需自行裁到 12×12 | GPLv2 + 字体例外 |
| 汉化圈 12×12 HZK | 现成 GBA/掌机字库，多为 1bpp，可直接配合 `BitUnPack` | 逐库确认 |

### 取模工具

- **[BMFont (AngelCode)](https://www.angelcode.com/products/bmfont)** —— 生成位图图集 + 描述文件（text/xml/binary 三选一），支持 Unicode 13.0、kerning、描边、padding/spacing 配置、命令行批量导出，开源（zlib 许可）[citation:12]
- 流程：字体选 12px 点阵字体 → `Edit → Select chars from file` 只导入脚本用字 → 固定 cell 高度、padding 设 0~1 → 导出 png + `.fnt`，运行时按描述取贴图区域
- **[CrystalTile2](http://2006.emu618.org/forum.php?action=printable&mod=viewthread&tid=99840)** —— 汉化方向用：直接打开 ROM 定位原字库，可切换 1bpp / GBA 4bpp 等格式并调整宽高（8×8 → 12×12 逐试），抓取原版调色板[citation:15][citation:20]
- **Bits'N'Picas / pcf2bdf / fonttools** —— PCF → BDF → TTF 转换链，便于把点阵字体喂给 BMFont[citation:16]

### 可读性增强

**加 1px 右下阴影或 1px 描边**，在 240×160 小屏上提升极其明显；位平面方案下几乎零成本。BMFont 自带 outline 生成，也可像 stdgba 那样在编译期用 `with_shadow()` / `with_outline()` 生成带装饰的字体变体。[citation:4]

**行距别省**：12px 字号建议行距 2~3px，否则中文上下笔画会粘连 —— GBA 屏的实际像素间距比模拟器上看着要紧。纵向节奏可参考 12px 字 + 4~5px 行间隙 = 16~17px 行高，13 行缩到 11~12 行。

---

## 七、现成代码可直接用

| 项目 | 语言 | 要点 | 链接 |
|---|---|---|---|
| **Tonc Text Engine (TTE)** | C | 统一上下文 + 可插拔 renderer，支持 UTF-8、任意尺寸字体、tilemap / 4bpp 行列主序 / 8bpp / 16bpp / OBJ 全套后端；有 `w8h8`、`w8h16` 定长优化路径和 `b1cts`（1bpp+彩色+透明+strip）系列 | [Tonc 文档](https://documentation.help/Tonclib/group__grpTTE.htm)、[系统概览](https://deepwiki.com/gbadev-org/tonc/5.2-text-rendering-systems) |
| **Tonc 基础文本系统** | C | `m3_puts` / `m4_puts` / `se_puts` / `obj_puts`，96 glyph 的 1bpp mini-ascii 字库 + 256 项 LUT，最省事 | 同上 |
| **gba_agb_font_renderer** | Rust (agb) | 4bpp 字形、`u32` 打包按行存储；`printable_font!(..., iwram)` 一行切换驻留；自带打字机 / 多行打字机渲染器 | [crates.io](https://crates.io/crates/gba_agb_font_renderer/0.2.0)（当前 0.25.x） |
| **gba_agb_font_loader / _creation_internals** | Rust | `include_agb_font!` 宏，编译期把 Aseprite/PNG 字体表转成 CGBA 格式，支持等宽、逐字宽度覆盖、加粗、重映射灰阶 | [lib.rs](https://lib.rs/crates/gba_agb_font_creation_internals) |
| **agbrs 官方 text rendering** | Rust | `Layout` + `ObjectTextRenderer` / `RegularBackgroundTextRenderer`，支持富文本 Tag | [agbrs.dev](https://agbrs.dev/book/articles/text_rendering.html) |
| **stdgba** | C++ | `embed::bdf()` 编译期解析 BDF，行数据按 BitUnPack 友好布局（LSB 在 bit0、行主序、字节宽 `(w+7)/8`），并提供 `with_shadow` / `with_outline` | [Embedding Fonts](https://felixjones.github.io/stdgba/graphics/embed-fonts.html) |

> 注意：`gba_agb_font_renderer` 的字体网格默认是 8×8 / 8×16 单元。要用 12×12，需自备图集并用 `size(cols, rows)` 指定网格 —— 宏会拿图片尺寸除以网格数得到单元尺寸，图片必须能整除，否则直接编译报错（不会静默错位）。[citation:10]

---

## 八、选型速查表

| 场景 | 选什么 | 理由 |
|---|---|---|
| 剧情对话、菜单、静态 UI | **方案 A**：4bpp tile 图集 + `BitUnPack` + 字形缓存 | 运行时零 blit，只写 screen entry |
| 需要滚动、淡入淡出、彩色渐变 | **方案 B**：mode 4 + 行打包 blit + IWRAM 字形 | 位图模式排版自由 |
| 少量动态数字 / 提示飘字 | **方案 C**：OBJ | 可逐字做动画，预算够用 |
| 想最快跑起来 | TTE 或 `gba_agb_font_renderer` | 别从零写 blitter |

### 落地顺序建议

1. 先定字形源（文泉驿 12px 或自有 12×12 点阵），用 BMFont 导出图集 + `.fnt`
2. 按脚本统计**唯一用字**，裁字库（通常 1000~2500 字足够一款游戏）
3. 写 1bpp → 4bpp 的 `BitUnPack` 路径，验证 tile 拼接处无串色
4. 上字形缓存哈希表，测一屏最坏情况的唯一字形数
5. 最后补阴影/描边和行距，真机（或 mGBA）上校对可读性

---

## 附：外链汇总

**硬件与 BIOS 权威资料**
- GBATEK（完整版，含 VRAM / Tile / 调色板）：http://www.akkit.org/info/gbatek.htm
- GBATEK PDF 版：http://ric.san.free.fr/_donnees/gbatek.pdf
- BIOS 解压函数（`BitUnPack` SWI 10h 官方说明）：https://problemkaputt.de/gbatek-bios-decompression-functions.htm
- GBA Memory System 解析：https://deepwiki.com/mgba-emu/gbatek/2.1-gba-memory-system

**文本引擎与库**
- Tonc Text Engine API：https://documentation.help/Tonclib/group__grpTTE.htm
- Tonc 文本渲染系统概览：https://deepwiki.com/gbadev-org/tonc/5.2-text-rendering-systems
- gba_agb_font_renderer（crates.io）：https://crates.io/crates/gba_agb_font_renderer
- gba_agb_font_creation_internals（宏文档最详细）：https://lib.rs/crates/gba_agb_font_creation_internals
- agbrs 文本渲染教程：https://agbrs.dev/book/articles/text_rendering.html
- stdgba Tiles & Maps：https://felixjones.github.io/stdgba/graphics/tiles.html
- stdgba Embedding Fonts（BDF + BitUnPack）：https://felixjones.github.io/stdgba/graphics/embed-fonts.html

**字体与工具**
- 文泉驿点阵宋体 TTF 版（12px~16px）：http://git-hub.com/AmusementClub/WenQuanYi-Bitmap-Song-TTF
- 文泉驿官网（点阵宋体项目页）：http://wenq.org/wqy2/index.cgi?BitmapSong
- 文泉驿点阵标准化审核（GB19966 说明）：http://wenq.org/index.cgi?ProjectTotem
- BMFont 官网：https://www.angelcode.com/products/bmfont
- BMFont 使用流程示例：https://paratranz.com/blog?category=document
- CrystalTile2 汉化实战教程（字库定位与格式切换）：http://2006.emu618.org/forum.php?action=printable&mod=viewthread&tid=99840
- GBA Tile 格式解读（含 GBA 4bpp/8bpp 位排布）：https://blog.csdn.net/qqj_1228/article/details/5092517
