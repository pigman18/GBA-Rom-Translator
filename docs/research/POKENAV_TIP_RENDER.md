# 领航员 tip 重印残留：渲染链路调研（未改引擎）

日期：2026-11-13  
范围：研究 only；`PrintNextChar_hook.c` 已回到 `b64723d`（无 clear_cols WIP）。  
bot：`work/POKEMON_RUBY_AXVJ00/bot/navigator/20261113T223409_139965/`  
ROM sha256：`346cb44129c5024e1668bd241f013cb8233b19359df8fe806b1d5ce6df5aa6e1`

---

## 1. 现象（bot 实证）

| 侧 | 换到更短 tip | 底部说明条 |
|----|--------------|------------|
| origin | 干净 | 日文垫空格，无尾字垃圾 |
| translated | **FAIL** | 上一句末字残留：`图`（←地图）、`带`（←缎带） |

证明帧（translated）：`033`（item2+图）、`042`（item3）、`060`（item5+带）。  
最长句 `024`/`061`（地图）与同长/更长的缎带句 `044–051` 干净 → **短盖长才爆**。

---

## 2. 日美差异（pret + AXVJ 反汇编）

### 美版（pokeruby `sub_80EF428`）

```c
AlignStringInMenuWindow(&tileBuffer[0x800], pcText, 0xC0, 2);
Menu_PrintText(&tileBuffer[0x800], 3, 17);
```

tip 字符串带 `{CLEAR 0}`（`FC 10`）→ `ExtCtrlCode_ClearWindowTextLines` → `Text_ClearWindow`。

### 日版 AXVJ（`0x080EA6C8`，caller `0x080E82A8` / `0x080E9E54`）

```
ldr  string from table @ 0x083B8F24[index]
movs r1, #4          ; left
movs r2, #0x11       ; top = 17
bl   Menu_PrintText  ; 0x0806F16C
```

- **无** `AlignStringInMenuWindow`
- **无** `Menu_ClearWindowText` / `Menu_EraseWindowRect` / `FC10`
- 清旧字完全靠 ROM 里 **定长 23B + 前后 `0x00` 空格垫齐**，再整行重打覆盖

指针表（主菜单 tip 段）：

| 表项 | 字符串 |
|------|--------|
| `083B8F24` → `083EB53B` | `  ホウエンちほうの マップを みます   ` |
| `083B8F28` → `083EB552` | `   ポケモンを くわしく しらべます   ` |
| `083B8F2C` → `083EB569` | `  トレーナーの じょうほうを みます   ` |
| … | … |

`original_hex` 实证：全是 `00 … ff`，**没有** `FC 10`。

---

## 3. 官方清窗到底清什么

`Text_ClearWindow`（JP `0x08003BA8`，与 pret 同构）：

| textMode | 行为 |
|----------|------|
| 0 / 1（monospace） | tilemap 整行改写为 blank tile 号（`GetBlankTileNum`），**不**擦 VRAM 字模像素 |
| 2 | `CpuFastFill` 窗口 tile 缓冲 |

`Text_SetWindowText` 只重置 `textIndex/state`，更不擦像素。  
日版 tip **从不调用**上述清窗；靠「空格字模整 tile 覆盖」。

---

## 4. 汉化为何撕开这条契约

### 4.1 译文丢尾空格

| original | translated |
|----------|------------|
| `  ホウエンちほうの マップを みます   `（尾 3×`00`） | `  查看丰缘地区的地图`（**无尾空格**） |
| `  トレーナーの じょうほうを みます   ` | `  查看训练家的信息` |

短句覆盖不到上一句右端槽位。

### 4.2 网格引擎对 `0x00`「只推进不重绘」

`PrintNextChar_hook.c`（现行）：

```c
/* 只有 0x00（空格）保持「只推进不重绘」… 禁止对 0x00 整格铺背景 */
if (glyph == 0x00u) {
    cursorTileX += 1;
    return;   /* 不写 VRAM */
}
```

即便补回尾空格，**中文路径也不会用空格擦掉旧汉字 ink**（为保 12px 共享列不被削）。  
日文固定宽一字一列覆盖契约在中文 12px 下不成立。

### 4.3 中文落点

汉字写在 `TILE_BASE + (row&7)*62 + col*2` 网格 arena；tilemap 改指这些 tile。  
无清窗时，未再被改写的右端 tilemap 项仍指向上一句汉字 → 屏上残留「图」「带」。

---

## 5. 渲染链路（领航员 tip）

```
光标换项
  → 0x080E82A8 / 0x080E9E54
  → 0x080EA6C8 取 gTipTable[b]
  → Menu_PrintText(str, 4, 17)          // gMenuWindowPtr
  → Text_InitWindowAndPrintText
  → PrintNextChar / 网格引擎逐字
       日文：00 空格 = 空白字模覆盖旧 tile
       中文：F7 汉字写 arena；00 = 只推进
  → （日版此处从不清 Text_ClearWindow）
```

美版多一步 `{CLEAR 0}` / Align；**不能拿美版 CLEAR 当「日版已经在清」**。

---

## 6. 为何 clear_cols 曾翻车（约束）

`cbc5ce5` 的重印清尾在 tip 有效，但开始菜单与 tip **同 `gMenuWindowPtr`、同 seg** 时，三条件误触发会清菜单行（乱码）并误伤备忘录 L2。  
§9.4.7 三条件仍是方向，但必须再加 **场景/几何隔离**（例如仅 tip 的 top=17 行、或仅该 printer 在 tip 矩形内），禁止裸全局重开。

---

## 7. 动手条件（未满足前禁止改引擎）

要修必须先选定并论证一条路径，且 bot 覆盖至少：

1. `navigator` tip 长短切换（本 run 帧集）
2. `start_menu` 全项（防同 printer 误清）
3. 背包说明 / 商店价列（§9.4.7 历史误伤面）
4. 训练家备忘录两行

候选方向：

| 方案 | 层 | 状态 |
|------|----|------|
| **A. tip 换项前 `Menu_BlankWindowRect`** | 场景钩 P30 | **已实施**（2026-11-13） |
| B. 译文/注入前缀 `FC10` | 数据 | 未采用 |
| C. 受限 `clear_cols` | 引擎 | 未采用（曾伤开始菜单） |
| D. 改 `0x00` 为铺背景 | 引擎 | 禁止作默认 |

**禁止**：改短语凑长度；未隔离就恢复全局 clear_cols；手改成品 ROM。

---

## 8. 方案 A 实施（P30）

- 挂点：`0x080EA6C8` → `PokeNav_PrintMenuTip_Hook`
- 逻辑：`Menu_BlankWindowRect(3, 17, 26, 18)` → `Menu_PrintText(str, 4, 17)`
  （right 曾用 28：空白字模奶油色铺过 tip 右框，黄条溢出；origin 框内止于 ~px216/tile26）
- 源：`hook/src/pokenav/PokeNav_PrintMenuTip_{hook.c,entry.s,hooks_origin.s}`
- bot（ROM `088801978443d491…`）：
  - `navigator/20261113T224412_516318`：tip 长短切换 **PASS**（无「图」「带」）
  - `start_menu/20261113T224432_729066`：**PASS**（无抹行）

## 9. 结论

日版 tip **没有**美版那种 CLEAR；靠定长空格覆盖。中文拆掉该契约后残留可复现。  
P30 仅在 tip 打印点 blank 说明条矩形，不动 `PrintNextChar`，已过 navigator + start_menu。
