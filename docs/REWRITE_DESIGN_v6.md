# V6 重写设计稿：单层拦截 + 官方落址

> 状态：设计稿 v1 + **部分落地（2026-09-01）**：P01 唯一拦截 `PrintNextChar`；FontFuncTable 已还原；
> tm3 落点改调官方 `0x080034E0`。EmitGlyph 表驱动 / 删 text_render 自研公式 / tm1 预扫仍待后续步骤。
> 前序：`REWRITE_DESIGN_混合写入架构.md`（v5）——v5 已实施步骤 1/2/3，但**架构上仍是 v4
> 的延伸**，本稿将其作废。
> 一句话结论：**hook 点收敛到 `PrintNextChar` 一个，落址 100% 交还官方函数，
> 我方只剩「读编码 → 选字库 → blend 写」这一件事。**

---

## 1. 为什么 v5 不算重构

v5 把 v4 的「槽位独占」换成了「blend 混合写入」，但**它仍然在自己算落址**：
`text_render.c` 里 `tm3_tile_no()` 手抄 2D 公式 `x+2+base+y*30`，`blit_column_mode0()`
手抄线性公式 `base+off`。冲突的根子——**我方维护了第二套游标语义**——一行没动。

本轮反汇编证实：这两个公式是**官方已实现函数的重复实现**：

| v5 自己写的 | 官方已有（本轮实证） |
|---|---|
| `tm3_tile_no` | `0x080034E0` → `0x08003500`（2D，`y*30` 由 `(y<<4-y)<<1` 实现） |
| `blit_column_mode0` 线性式 | `0x08003520`（线性，`(win[0x16]+win[0x18])<<5`） |

不是「算错了」，是**根本不该算**。

## 2. 关键修正：hook 点回到 `PrintNextChar`（用户纠偏）

我上一版提议 hook blit 层（`0x08003630` / `0x080033B4`），理由是官方已算好 `dest`
直接传参。**这个提议漏了最关键的一点**：

- blit 层只被 tm0 / tm2 / tm3 调用，**tm1 官方根本不调 blit**（它只写 tilemap）；
- 也就是说 hook blit 层会**恰好漏掉最难的那个 mode**，等于把问题留到最后。

而 `PrintNextChar` 是**唯一的全覆盖入口**：

```
080032F8  PrintNextChar(TextPrinter *win /*r0*/) -> int
              c = win->text /*[0x10]*/ [ win[0x14]++ ]
              if (c - 0xFA <= 5)  → 6 支跳转表（控制码 0xFA..0xFF）
              else                → CallViaR2: FontFuncTable[ win[0x0A] ](win, c)
                                    return 1
```

- 调用点仅 4 处：`0x08002E24`（RunTextPrinter 主循环）/ `0x08002E6E` /
  `0x08002FAE` / `0x08003100`；
- **`0xF9` 不在 `0xFA–0xFF` 控制码表内** ⇒ 原生把它当可印字符分发。拦截 `0xF9`
  最自然的位置就是这一层；
- tm0/tm1/tm2/tm3 **无一例外**都从这里分派 ⇒ 一个 hook 覆盖全部场景。

> **v4 失败的教训要拆开看**：v4 失败的不是「hook `PrintNextChar`」这个选择，而是它
> **整函数替换后自己管了游标/槽位/相位**。hook 点与落址责任是两件事，本稿只保留
> 前者、把后者交还官方。

## 3. 官方三层分派（本轮 capstone 逐条钉死）

| 层 | 实体 | 职责 | tm 是否都经过 |
|---|---|---|---|
| 消费层 | `PrintNextChar@0x080032F8` | 取字符、处理 `0xFA–0xFF` 控制码、可印字符分发 | ✅ 全部 |
| 落址层 | `FontFuncTable[textMode]@0x081BB3AC` | 算落点 + 推进官方游标 | ✅ 全部 |
| 字库层 | `FontSubTable[fontNum]@0x081BB3BC` | 字形索引 → tile 号（7 项仅 4 变体） | ⚠ 仅 tm1 直接调用 |
| blit 层 | `0x08003630`（tm0/tm2）/ `0x080033B4`（tm3） | 取字形 → CopyGlyph 混合写入 | ❌ tm1 不经过 |

### 3.1 落址层（tm 分派）

| tm | 处理器 | 官方落点 | 推进 |
|---|---|---|---|
| 0 | `0x08003568` | `0x08003520`：`tpl->tileData + (win[0x16]+win[0x18])<<5` | `win[0x18]+=2`、`win[0x1B]+=1` |
| 1 | `0x0800360C` | `FontSubTable[fontNum]` → `0x080036DC`（**只写 tilemap**） | `win[0x1B]+=1` |
| 2 | `0x0800338C` | `win[0x20]`（OBJ 缓冲**指针**直给） | `win[0x20]+=0x40` |
| 3 | `0x08003494` | `0x080034E0` → `0x08003500`：2D `(x+2+base) + y*30` | `win[0x1B]+=1` |

### 3.2 字库层（font 分派）

`FontSubTable@0x081BB3BC` 7 项仅 4 个变体：

| font | 处理器 | 字形 → tile 号 |
|---|---|---|
| 0 / 3 | `0x08003584` | 等宽：`t1 = base + glyph*2`、`t2 = t1+1` |
| 1 / 4 | `0x080035A0` | 变宽：查表 `0x081B34A8`（4 B/项，取 byte[0]/byte[1]） |
| 2 / 5 | `0x080035C8` | `t1 = base+0xD4`（空格）、`t2 = base+glyph` |
| 6 | `0x080035E4` | 变宽：查表 `0x081B3884` |

blit 内 fontNum 跳转表 `@0x08003678`（7 项）决定位深：
`font0/1/2/6 → 1bpp`（`0x08003830`），`font3/4/5 → 2bpp`（`0x080038A0`，多一个阴影色参数）。

### 3.3 🔑 tm 差异的本质：两个 stride（本轮最关键的发现）

blit 内「字形下半个 tile 在哪」是**唯一**的 tm 差异，且可从官方推进量直接反推：

| tm | blit 内 lower tile | rowStride | colStride | 官方推进 |
|---|---|---|---|---|
| tm0 | `r8 + 0x20` (+32 B) | **1** | **2** | `win[0x18]+=2` |
| tm1 | 不画（atlas 预渲染） | **1** | **2** | `win[0x1B]+=1` |
| tm2 | `r8 + 0x20` (+32 B) | **1** | **2** | `win[0x20]+=0x40` |
| tm3 | `r8 + (0xF0<<2)` = **+0x3C0** (+960 B = 30 tile) | **30** | **1** | `win[0x1B]+=1` |

- tm3 的 `rowStride=30` 与其落址公式 `tile = y*30 + x + base` 完全自洽（2D 布局行宽 30）；
- tm0 线性布局下上下半 tile 号差 1 ⇒ +32 B；
- tm0 的 `colStride=2` 是因为上下半**连续占 2 tile**，下一字从 `n+2` 起（与 `win[0x18]+=2` 一致）；
  tm3 上下半跨行，同行下一列就是 `+1`（与 `win[0x1B]+=1` 一致）。

⇒ **16 px 汉字 4 个 tile 的落点 = `n`、`n+rowStride`、`n+colStride`、`n+colStride+rowStride`**。
一张 4 项常量表覆盖全部 tm，**不需要任何自研落址公式**。

## 4. V6 架构不变量（任何代码不得违反）

1. **唯一拦截点**：只有 `PrintNextChar`。禁止再 hook `FontFuncTable` / blit 层
   （v5 的 4 表项重定向须**还原**）。
2. **落址交还官方**：除 tm1 外，落点一律由调用官方函数取得（`0x08003520` /
   `0x080034E0` / `win[0x20]`）。**我方不得出现任何 `*30`、`<<5`、`+0x3C0` 形式的
   自研落址表达式**——出现即视为架构回退。
3. **唯一消费方法**：`EmitGlyph(dest, glyphId, fontNum)`，内部只做
   「选字库 → blend 写入」，不碰游标。
4. **游标推进只用官方字段**，推进量取 blend 返回列数。
5. **字库常驻 ROM**，索引 → 地址纯函数，运行时零可写字库状态。
6. 未登记的 `tm` / `font` 组合必须显式回落官方，**禁止静默走默认路径**。

## 5. 架构：1 个 hook + 1 个消费方法 + 2 张表

```c
/* ---- 表 1：tm → 瓦片分配（唯一差异点） ---- */
typedef struct {
    u32  rowStride;    /* 字形上下半的 tile 间隔：tm0/1/2 = 1，tm3 = 30 */
    u32  colStride;    /* 右半列的 tile 间隔：tm0/1/2 = 2，tm3 = 1      */
    void *(*alloc)(struct TextPrinter *win);   /* 落点取得函数 */
    void (*advance)(struct TextPrinter *win, u32 cols);
} TileLayout;

static const TileLayout kLayout[4] = {
    [0] = { 1,  2, TileAlloc_Tm0_Origin, Advance_Tm0 },   /* 官方 0x08003520 线性 */
    [1] = { 1,  2, TileAlloc_Tm1_Atlas,  Advance_Tm1 },   /* 唯一需要分配器      */
    [2] = { 1,  2, TileAlloc_Tm2_Ptr,    Advance_Tm2 },   /* win[0x20] 指针      */
    [3] = { 30, 1, TileAlloc_Tm3_Origin, Advance_Tm3 },   /* 官方 0x080034E0 2D  */
};

/* ---- 表 2：font → 字库 + 字号 ---- */
typedef struct {
    const u8 *glyphRom;   /* 中文字库基址（0x09xxxxxx） */
    u32  width;           /* 8 / 12 / 16 */
    u32  indentPx;        /* 缩进策略，见 §6 */
} FontDesc;

static const FontDesc kFont[7] = {
    [0] = { FontChsNormal, 16, 0 },  /* 等宽 16px */
    [1] = { FontChsNormal, 12, 0 },  /* 变宽 12px */
    [2] = { FontChsSmall,  8,  0 },  /* 小字 8px  */
    [3] = { FontChsNormal, 16, 0 },
    [4] = { FontChsSmall,  8,  0 },  /* 🔒 强制 8px，禁止缩进 */
    [5] = { FontChsSmall,  8,  0 },
    [6] = { FontChsNormal, 12, 0 },
};
```

```c
/* ---- 唯一 hook ---- */
int PrintNextChar_Hook(struct TextPrinter *win)
{
    u8 c = win->text[win[0x14]];
    if (c != 0xF9)                       /* 非中文协议 → 原样回落 */
        return PrintNextChar_Origin(win);

    u32 glyphId;                          /* F9 解码：单汉字 / PhraseTable / SLT2 slot */
    if (!TranslateHandleChar(win, &glyphId))
        return PrintNextChar_Origin(win);

    const TileLayout *L = &kLayout[win[0x0A]];          /* textMode */
    const FontDesc   *F = &kFont[win[0x0B]];            /* fontNum  */
    u8 *dest = L->alloc(win);
    u32 cols = EmitGlyph(dest, glyphId, F, L);
    L->advance(win, cols);
    return 1;                             /* 已消费，等价于官方「打印了一个字符」 */
}

/* ---- 唯一消费方法 ---- */
u32 EmitGlyph(u8 *dest, u32 glyphId, const FontDesc *F, const TileLayout *L)
{
    /* 读字形（ROM 纯函数） → blend_glyph_4bpp 混合写入 4 个 tile → 返回推进列数 */
}
```

### 5.1 hook 装机形态（`hooks_origin.s`）

```asm
.org 0x080032F8
    ldr  r3, =PrintNextChar_Hook
    bx   r3
.pool
```

- 前 4 字节正好容纳两条 thumb 指令（原生为 `push {r4,lr}` + `adds r4,r0,#0`）；
- 用 `bx r3` **不改 lr** ⇒ C 函数 `bx lr` 直接回到 `RunTextPrinter`，无需额外跳板；
- 签名 `int (TextPrinter*)`、参数在 r0，与 AAPCS 完全兼容 ⇒ **C 直接实现，不写汇编胶水**。

## 6. 缩进策略（用户拍板）

| font | 字号 | 缩进 |
|---|---|---|
| **4** | **强制 8px 小字** | **禁止**（1 tile 一字，天然对齐，无缩进需求） |
| 0 / 3 | 16px（等宽容器） | 可选开启 |
| 1 / 6 | 12px | 可选开启 |
| 2 / 5 | 8px | 不适用 |

**「缩进」的定义**：16 px 汉字占 2×2 tile，若当前游标处于 tile 内奇数像素相位，
会横跨 3 列 tile（会污染更多相邻 tile）。**缩进 = 先把游标对齐到下一个 tile 边界
再写**，最多浪费 7 px，换取落点整齐、不跨 3 列。12 px 以亚 tile 混合写入为常态，
不需要对齐（blend 原语原生支持任意 `startPixel`）。

配置项：`FontDesc.indentPx` —— `0` = 不缩进（直接写），`1` = 对齐到 tile 边界。
**font4 该项恒为 0，运行时若检测到 font4 带缩进请求应断言失败。**

> ⚠ 待实测：`FontChsSmall` 容器尺寸。若它实为 8×16 = 64 B 容器，则
> `decompress_chs_glyph` 固定拷 128 B（4×32 B）会越界读进下一个字形
> ——v4 记忆中的「8px 小字库字形有误」旧坑疑似同一根因。实施步骤 1 先行验证。

## 7. tm1：唯一需要分配器的 mode

tm1 官方从不写 tileData，整个 charblock 被 `InitWindowTileData` 预渲染的
**256 字形 × 2 tile 写满 tile [1, 513)**（= 整个 charblock 512 tile），
tile 号是**字形索引**而非游标。

- 🔴 **抬水位已证伪**：低于 513 写进 atlas 改坏假名（v4 的 257+ 正是这么炸的）；
  高于 513 越出 charblock 静默丢失。**两者之间不存在合法静态水位。**
- ✅ **本稿采用（用户选定方案 A）**：**预扫推导空闲槽**，而非扫描内容判空。
  atlas 里「空」不能靠内容扫描（空格字形本来就是全 0，会被误判）；
  正确做法是 `InitTextPrinter` 时预扫整条文本流（含 F9 转义、短语递归展开），
  建「已用 glyph 位图」，**位图外的槽即可分配**。

三个必须处理的点（实施期逐条实测）：

1. **FD 占位符预扫拿不到**（道具名/宝可梦名运行时才解析）→ 保守预留一段，
   或给 FD 内容单独开小池；
2. **多窗口共享 atlas** —— 同 `tpl` 的 tm1 窗口共用 charblock，A 窗口分配的 tile
   会被 B 窗口当字形引用 → 分配器须**按 tpl 分池**且可回收；
3. 分配器状态**必须显式落 EWRAM**（`game.ld` 无 `.bss` 规则这条血泪教训照旧）。

> tm1 的 stride 与 tm0/tm2 一致（rowStride=1、colStride=2），
> 故 `EmitGlyph` **完全复用**，tm1 的差异只剩 `alloc` 一项。

## 8. 文件结构（用户指定）

```
configs/POKEMON_RUBY_AXVJ00/hook/src/text/
├── entry.s                    # ROM 进入点（如需）
├── hooks_origin.s             # .org 订址桩：PrintNextChar 4 字节覆写
├── PrintNextChar_hook.c       # 唯一 hook + TileLayout[4] + FontDesc[7] + EmitGlyph
├── text_translater.c          # 库：F9 协议 / PhraseTable / SLT2（非 hook，保留）
└── blend_glyph.c              # 库：绘制原语，纯函数，有离线对拍（非 hook，保留）
```

命名规范：**`{方法名}_hook.c`** 只放 hook 逻辑；纯库文件不加 `_hook` 后缀。

**删除清单**：`text_render.c`（自研落址公式全部作废）、`fontfunc_hook.c`
（FontFuncTable 重定向作废，表项须还原）、`include/text.h` 中的 tm 公式相关声明。

## 9. 实施步骤（每步独立编译 + armips，可单步回退）

1. **验字库容器尺寸**：确认 `FontChsSmall` 是 64 B 还是 128 B 容器，
   修正 `decompress_chs_glyph` 拷贝长度（先解掉 v4 遗留坑）。
2. **装机 hook**：`hooks_origin.s` 覆写 `0x080032F8`；`PrintNextChar_hook.c` 先只做
   「非 0xF9 原样回落」，验证**零行为变化**（编译 + armips + `check_rom_hook.py`）。
3. **接入 tm0**：`TileAlloc_Tm0_Origin` = 直调官方 `0x08003520`，接 `EmitGlyph`，
   16 px 整格。与 v5 已跑通的 tm0 效果对齐。
4. **接入 tm3**：`TileAlloc_Tm3_Origin` = 直调官方 `0x080034E0`，复用同一 `EmitGlyph`，
   验证 rowStride=30 下 4 tile 落点正确。
5. **接入 tm2**：`win[0x20]` 指针直给，8 px 槽。
6. **接入 tm1**：预扫分配器（§7）。**这一步是唯一新增运行时状态的地方。**
7. **删旧**：`text_render.c` / `fontfunc_hook.c` / v5 表项重定向，重跑等价性验证。

## 10. 验收清单

- **五 BUG 场景**：捡拾道具提示（含复发路径）、对战信息、队伍底栏、队伍名、
  详情页 → 技能选取（左上 No 完好）。
- **回归场景**：设置菜单、战斗、图鉴（含分类名）、对话、商店/背包菜单 ▶。
- **架构自检（新增，防回退）**：`grep -nE '\* *30|<< *5|\+ *0x3C0' src/text/*.c`
  在步骤 7 后必须**零命中**（除了对官方函数的调用注释）。

## 11. 风险与开放问题

- tm1 分配器的**回收策略**未定（按 tpl 分池 + LRU？还是窗口关闭即回收？），
  步骤 6 实施期实测决定（歧义记账，不阻塞前 5 步）。
- `PrintNextChar` 第二/第三/第四调用点（`0x08002E6E` / `0x08002FAE` / `0x08003100`）
  的宿主函数未标定，需确认其返回值语义与主控循环一致。
- 🔒 P0 未处理：根 `build.bat` 硬编码 API key 且已被 git 跟踪。

## 12. 参考索引

- 本轮反汇编脚本：`_tmp_dis_v6.py`（tm 处理器 + font 二级表）、
  `_tmp_dis_v6b.py`（落址函数 + blit 变体 + stride）、
  `_tmp_dis_v6c.py`（tm3 落址 + 跳转表）、`_tmp_dis_pnc.py`（PrintNextChar + 调用点）
- 美版参照：`tools/Pokemon_GBA_Font_Patch/pokeRS/src/HackFunction/DrawGlyphTilesChinese.s`
- 官方 blit 源码：`tools/pokeruby/src/text.c:3877`
- 日版地址权威：`configs/POKEMON_RUBY_AXVJ00/hook/game_addrs.asm`
- 本轮工作日志：`.workbuddy/memory/2026-08-31.md`
