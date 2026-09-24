# Step B / B2 落点定案 —— tm1 官方链路全解（2026-09-20）

> 本文回答一个此前从未被正面回答的问题：**「中文的 tile 号到底该从哪来？」**
> 结论：**官方只给「格子位置」，不给「tile 号」。分配器暂时删不掉。**

---

## 1. 三张表的真实身份（此前全部误读）

```
FontFuncTable @0x081BB3AC（4 项，textMode 索引，Thumb 位已置）
  [0] = 0x08003569   tm0
  [1] = 0x0800360D   tm1
  [2] = 0x0800338D   tm2
  [3] = 0x08003495   tm3

FontSubTable  @0x081BB3BC（7 项，fontNum 索引，Thumb 位已置）
  [0] = 0x08003585  [1] = 0x080035A1  [2] = 0x080035C9  [3] = 0x08003585
  [4] = 0x080035A1  [5] = 0x080035C9  [6] = 0x080035E5
```

**`FontSubTable` 不是「字体表」，是「tm1 的逐字落砖函数表」。**

## 2. tm1 处理器 `0x0800360C` 的真实语义

```c
void PrintGlyph_TextMode1(TextPrinter *win)      /* FontFuncTable[1] */
{
    /* 0x0800360C */
    r2 = FontSubTable[win[0x0B]];                /* fontNum 索引，取子处理器 */
    sub_081B12DC(win, r2);                       /* 0x081B12DC = `bx r2` 蹦床 */
                                                 /* ⇒ 等价于 r2(win)：尾调用，r0=win */
    win[0x1B] += 1;                              /* cursorTileX += 1（唯一的推进） */
}
```
- `0x081B12DC = 4710` = `bx r2`（后接 `nop` 填充，一直到 `0x081B1302`）
  —— **`0x081B12xx` 这一带是 BIOS 蹦床区**（`LZ77UnCompVram` 在 `0x081B1298`）。

## 3. 四个 tm1 子处理器：**全部只写 tilemap，不碰 VRAM**

| 子处理器 | 落点算式 | UpdateTilemap 实参 |
|---|---|---|
| `0x08003584` | `t = TILE_BASE(0x16) + glyph*2` | `(t+1, t)` |
| `0x080035A0` | `b0 = tbl1[glyph*4]`、`b1 = tbl1[glyph*4+1]`（`tbl1 = 0x081B34A8`） | `(TILE_BASE+b0, TILE_BASE+b1)` |
| `0x080035C8` | `t = TILE_BASE + 0xD4`，`t2 = TILE_BASE + glyph` | `(t, t2)` |
| `0x080035E4` | `b0/b1 = tbl2[glyph*4(+1)]`（`tbl2 = 0x081B3884`，值是 `0x1000/0x1001/...`） | `(TILE_BASE+b0, TILE_BASE+b1)` |

**⇒ tm1 的 tile 号全部 = `TILE_BASE + 常量`，指向**预载在 VRAM 的官方图集**。
（印证的 `chs_claim_tile` 注释：「AXVJ tm1 无窗口私有区」是**正确的**。）

## 4. `UpdateTilemap 0x080036DC` 全貌

```c
void UpdateTilemap(TextPrinter *win, uint16_t upper, uint16_t lower)
{
    r0 = GetCursorTilemapPointer(win);            /* 0x080036EC */
    *(u16*)r0       = upper | (win[0x0F] << 12);  /* win[0x0F] = 调色板 */
    r0 += 0x40;                                   /* 下一 tilemap 行（+32 表项） */
    *(u16*)(r0)     = lower | (win[0x0F] << 12);
}

/* GetCursorTilemapPointer 0x08003708：
 *   &tilemap[ ((CURSOR_Y + CURSOR_TILE_Y) << 5) + (CURSOR_X + CURSOR_TILE_X) ]
 *   即「官方游标指向的那一格」 */
```

**⇒ `UpdateTilemap` 的输入是「VRAM tile 号」，位置由官方游标决定。**

## 5. 🎯 核心结论：官方只给「格子」，不给「号」

| 东西 | 谁提供 | 说明 |
|---|---|---|
| **格子位置**（tilemap 表项地址） | ✅ 官方游标 | `GetCursorTilemapPointer(win)` |
| **tile 号**（VRAM 里的图形落点） | ❌ **官方不给中文用的** | tm1 只给 `TILE_BASE + 常量`（图集） |

**⇒ 所以 v6 引擎当前的做法（`chs_claim_tile` → `v8_alloc_tile` 找一块空闲 VRAM + 自己写 tilemap 表项）
已经是「混合写入」：位置官方给、号我们给。**

**⇒ B2「把落砖从分配器换成官方落点」的前提不成立 —— 官方没有可用的号。**

## 6. 分配器为什么不能直接删

删掉分配器后，中文 tile 号只能来自：
1. `TILE_BASE + cursorTileX` —— **落在官方图集上**（tm1 图集全部驻留在 `TILE_BASE` 起）。
2. 固定写死一个号 —— **所有字共用一个 tile，只能显示一个字**。

**⇒ 要么保留「找空闲号」的能力，要么先知道「图集占了哪些号」。**

## 7. 🟢 真正的出路（三条，按推荐度）

### 甲 · 静态预载中文字库（最贴合 Wokann 精神，推荐）

把**常用中文字**在**构建期**预处理成 4bpp tile，**烘焙进 ROM，并让 ROM 地址 = VRAM 的固定约定**。
运行时中文是「预渲染 tile 号」，与 tm1 官方行为完全同构：
- 中文每个字在 VRAM 占固定号 `CHS_TILE_BASE + gidx*2`；
- 需要时用 `bl 0x081B1298`（`LZ77UnCompVram`）或 `svc 0x12`（`CpuFastSet`）把那 64 字节搬进 VRAM；
- 分配器**彻底删除**（B4 成立），12px 相位层也可删。

**代价**：VRAM 要预留 `CHS_TILE_BASE` 起的一段给中文字库（大小 = 同时上屏字数上限，不是全字库）。
**关键待定**：`CHS_TILE_BASE` 取多少？需要**枚举当前场景的官方图集占用上界**。

### 乙 · 保留分配器，但收窄职责

只保留「找空闲 tile」这一件事，删掉 12px 相位层，把 `v8_alloc_*` 的「活引用扫描」
换成「一次性的静态图集占用枚举 + 单调递增游标」——**这正是 `REWRITE_DESIGN` 的不变量 ①**。

**代价**：仍需运行时探测；跨场景复用 window 时可能误判。

### 丙 · 重定向 `FontSubTable`（接管 tm1）

把 `FontSubTable[fontNum]` 改成我们的处理器，中文走自己的落点、日文尾调原处理器。
**但这不解决「号从哪来」**，只是把落点决策点前移。
**⇒ 只有配合甲或乙才有意义。**

## 8. 本轮实证工具与中间产物

- `scripts/jp_dis.py` —— 逐指令反汇编（**禁止手算指令边界**；本轮手算错过两次）
- `.tmp/scan_glyph_sites.py` —— 全 ROM BL 站点扫描
- `.tmp/find_func_owner.py` —— 调用点 → 所属函数回溯

## 9. 附：`GetGlyphTilePointers` 7 分支公式（修正版，供将来参考）

| fontNum | `*out0` | `*out1` |
|---|---|---|
| 0 | `0x081B3AAC + idx*16` | `*out0 + 8` |
| 1 | `0x081B49AC + tbl1[idx*4]*8` | `0x081B49AC + tbl1[idx*4+1]*8` |
| 2 | **常量 `0x081B504C`** | `0x081B49AC + idx*8` |
| 3 | `0x081B6D2C + (idx&0xFFF0)*64 + (idx&0xF)*32` | `*out0 + 0x200` |
| 4 | `0x081B51AC + tbl1[idx*4]*32` | `0x081B51AC + tbl1[idx*4+1]*32` |
| 5 | **常量 `0x081B6C2C`** | `0x081B51AC + idx*32` |
| 6 | `0x081BACAC + tbl1[idx*4]*8` | `0x081BACAC + tbl1[idx*4+1]*8` |

`tbl1 = 0x081B34A8`。跳转表 @`0x0800374C`（`[0]` 是死项）。

---

## 10. 🔴🔴🔴 实机判决（2026-09-20 第三轮）—— 本文 §7「出路 1」**已被否决**

> §7 曾提出「tm1 借道官方 `TILE_BASE` 私有区」。**实机 A/B 证明这是错的。**

### 实测方法

- **读档法**：`POKEMON_RUBY_AXVJ00_translated.sav`（后期存档：玩家 祐树 / 时间 17:23 / 图鉴 55 只 / 徽章 5 个）
  拷成 `<rom同名>.sav`，mGBA 启动即识别 ⇒ 直接进游戏内，**验收素材不用从头玩**。
- **画面采集**：`PrintWindow` + `PW_RENDERFULLCONTENT` 截 mGBA 窗口位图（绕开不可靠的 I/O 寄存器读法）。
- **严格 A/B**：同一存档、同一采集脚本、同一场景序列；旧版 vs 新版各采 23 点。
  对照图：`.tmp/ab_compare_settings.png`

### 判决

| 场景 | 旧版（v8 分配器） | 新版（B2 借道 TILE_BASE） |
|---|---|---|
| 标题 / 主菜单 | ✅ 正常 | ✅ 正常 |
| **设置菜单**（对话速度/战斗动画/对战规则/声音/按键模式/窗口） | ✅ **内容全对** | ❌ **整体错乱**：6 行退化成「普通声」「式」堆叠，标题「设置」变「普 凵」 |
| 宝可梦列表 | ✅ | ❌ 同错乱 |

### 机理

**9-08 的旧结论「AXVJ tm1 无窗口私有区」是对的。**
tm1 的 `TILE_BASE` 区**确实被官方图集占用** —— 这正是 v6 当初给 tm1 上分配器的原因。

🔴 **关键教训：「tm1 子处理器只调 UpdateTilemap、不推进 tile 游标」≠「TILE_BASE 区空闲」。**
官方图集是**预先 LZ77 解到该区**的（v20 门控管的正是这个），
**不需要在 tm1 逐字路径上写** ⇒ 「路径上没人写」不能推出「这块地是空的」。

### 处置

- 回退：`PrintNextChar_hook.c` ← `.tmp/PrintNextChar_hook.c.b2bak`（md5 `307bd9a4…`）。
  B2 改动留存 `.tmp/PrintNextChar_hook.c.b2new`（md5 `b4949ba3…`）。
- 产物：`_translated_new.gba` = **旧版基线**，sha1 `8cc5e0dc…`，`game.bin` 9060 B。
  B2 新版存档 `_translated.gba.b2new_keep`，sha1 `3b474fba…`，`game.bin` 9100 B。

### 真正的病灶（下一步该干的）

8 月旧图 `.ss5` / `.ss6` 实证：**中文渲染本身成功**（底部中文描述、`PP21/24`、标签 `ぶんぷ` 全对），
**乱码只出现在「还在用日文字形」的短词上**（招式 `かみつき`、属性 `あく` → 显示成 `+ィあく` 类字形碎片）。
⇒ **hook 无差别拦截所有字符，把官方日文小字库索引也当成了中文 idx。**

**对症药（零架构改动）**：让 hook **只对中文槽位介入**（SlotTable 命中 / `idx ≥ 阈值`），
官方日文 idx 一律**放行走官方路径**。
**tm1 的落砖必须继续走「全池分配」，不能借官方号。**
若要「无容量限制」，才需重新设计 tm1 私有落点（例如**重定向 `FontSubTable[*]`** ⇒ 需另找可写落点）。
