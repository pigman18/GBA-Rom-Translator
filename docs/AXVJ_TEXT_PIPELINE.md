# AXVJ 日版文字链路 — 反汇编取证（ROM 实证，非 hook 反推）

> 来源：`arm-none-eabi-objdump` / capstone 反汇编 `roms/origin/POKEMON_RUBY_AXVJ00.gba`。
> 仅取证，不参考任何现有 hook C 代码。Thumb 反汇编原始摘录见各节。

## 0. 引擎判定：日版 = TextPrinter（不是美版 struct Window）

`ProcessCurrentChar 0x080032F8` 前几条指令即证明布局：

```
0x080032FA: adds r4, r0, #0        ; r4 = win (r0 = TextPrinter*)
0x080032FC: ldrh r0, [r4, #0x14]   ; textIndex  @ +0x14
0x08003300: strh r1, [r4, #0x14]   ; textIndex++
0x08003306: ldr  r1, [r4, #0x10]   ; text       @ +0x10
0x0800330A: ldrb r3, [r1]          ; c = text[textIndex]
0x0800330E: subs r0, #0xfa         ; c - 0xFA
0x08003310: cmp  r0, #5
0x08003312: bhi  0x800336e         ; 普通字形 → RegularGlyph
```

→ `text@0x10`、`textIndex@0x14`、`state@0x04`、`textMode@0x0A`。
美版 pokeruby `struct Window` 是 `text@0x20 / textIndex@0x1E / textMode@0x00`，**布局不同，不能直接套用其结构体**；但**算法一一对应**。

## 1. RegularGlyph → FontFunc 分派（唯一 hook 点）

```
0x0800336E: ldr  r0, [pc,#0x18]    ; FontFuncTable = 0x081BB3AC
0x08003370: ldrb r1, [r4, #0xa]    ; textMode @ +0x0A
0x08003374: adds r1, r1, r0
0x08003376: ldr  r2, [r1]          ; r2 = FontFunc[textMode]
0x08003378: adds r0, r4, #0        ; r0 = win
0x0800337A: adds r1, r3, #0        ; r1 = cur_char
0x0800337C: bl   0x81b12dc         ; CallViaR2 → FontFunc(win, char)
0x08003380: movs r0, #1            ; 返回 1
```

**FontFuncTable 0x081BB3AC**（实测指针）：

| idx | target | 角色 |
|-----|--------|------|
| 0 | 0x08003569 | Font0_Wrapper（普通无阴影） |
| 1 | 0x0800360D | Font1（monospace） |
| 2 | 0x0800338D | 战斗/血条缓冲（dest=win[0x20]，ptr+=0x40） |
| 3 | 0x08003495 | Font3_Wrapper（带阴影 4bpp） |
| 4 | 0x08003585 | Font4 |
| 5 | 0x080035A1 | Font5 |
| 6 | 0x080035C9 | Font6 |

**hook 契约**：在 `0x0800336E` 拦截；`r4=win`、`r3=cur_char` 已就位；自处理返回非 0，交还原版则跳回 `RegularGlyph` 让 `bl CallViaR2` 跑原版 FontFunc。

## 2. 各 FontFunc 的 dest / 前进 / UTM 契约

### FontFunc[0]（Font0_Wrapper 0x08003568 → DrawGlyph_Font0 0x08003520）

```
DrawGlyph_Font0(win=r5, glyph=r1):
  dest = [template=win[0x00]]+0x0C (tileData)  + ((TILE_BASE[0x16]+TILE_OFFSET[0x18])<<5)
  BlitGlyphTiles(glyph, dest, fontNum=win[0x0B], FG=win[0x0C], BG=win[0x0D], Shadow=win[0x0E])
  UpdateTilemap(win, upper=(TILE_BASE+TILE_OFFSET)&0xFFFF, lower=upper+0x100)
Font0_Wrapper: 后 TILE_OFFSET[0x18] += 2 ; TILE_X[0x1B] += 1
```

### FontFunc[3]（Font3_Wrapper 0x08003494 → 0x08003464 区）

```
x = CX[0x1A] + 2 + TILE_BASE[0x16] + TX[0x1B]
y = CY[0x1C] + TY[0x1D]
dest   = [template+0x0C] + ((x + y*30)<<5)        ; 0x08003500
UTM    : upper = x + y*30 , lower = x + (y+1)*30  ; 0x080034A8 → UpdateTilemap
Font3_Wrapper: 后 TILE_X[0x1B] += 1
```

### FontFunc[2]（0x0800338D，战斗/血条）

```
dest = win[0x20] ; BlitGlyphTiles(...) ; win[0x20] += 0x40   ; 不写 tilemap
```

## 3. 可复用的原版函数（自写 4bpp blit + 复用 UTM）

| 函数 | 地址 | 签名（寄存器） | 用途 |
|------|------|----------------|------|
| BlitGlyphTiles | 0x08003630 | r0=glyph, r1=dest, r2=fontNum, r3=FG, [sp]=BG, [sp+4]=Shadow | 原版字库 blit（中文不走） |
| CopyGlyph1bppTo4bpp | 0x08003830 | 1bpp→4bpp | 原版 font0/1/2/6 |
| CopyGlyph2bppTo4bpp | 0x080038A0 | 4bpp 颜色重映射 | 原版 font3/4/5 |
| **UpdateTilemap** | 0x080036DC | r0=win, r1=upperTile, r2=lowerTile | **复用**：写 BG tilemap（palette=`win[0x0F]<<12`，`tilemap[0]`/`[+0x40]`） |
| **GetCursorTilemapPointer** | 0x08003708 | r0=win → r0=&tilemap[(CY+TY)*32+(CX+TX)] | **复用**（UTM 内部调它） |
| GetWindowPaletteBits | 0x08003728 | r0=win → palette<<12 | 复用 |
| GetGlyphTilePointers | 0x08003730 | r0=fontNum, r1=glyph, r2=&up, r3=&low | 原版字库寻址（中文不走） |

## 4. F9 叠加契约（最终方案）

```
hook @ 0x0800336E (RegularGlyph):
  if (win->textMode == 2)  return to_origin;          // 战斗缓冲不接管
  if (cur_char == 0xF9) {                             // F9 00 lead trail
      win->textIndex += 3;
      gidx = pack(lead, trail);
      src  = FontChsNormal + (gidx << 7);             // 128B = 8x16 4bpp TL/BL/TR/BR
      // 自写 4bpp blit（12px 跨 tile + 相位），dest 用上面的 Font0/Font3 公式
      // 复用 UpdateTilemap 写 tilemap
      // cursor_px += 12；同步 TILE_OFFSET[0x18]/TILE_X[0x1B]
      return 1;                                       // 已处理
  }
  return to_origin;                                   // 日文/数字/Sym → 原版 FontFunc
```

字库：FontChsNormal `0x09000000` + `(gidx<<7)`，每字形 128B（8×16 4bpp，TL/BL/TR/BR 四 32B 半块）。

## 5. 对应 pokeruby text.c（算法参照，布局不可照搬）

`PrintNextChar`↔`ProcessCurrentChar`、`sPrintGlyphFuncs[textMode]`↔`FontFuncTable`、
`DrawGlyphTiles`↔`BlitGlyphTiles`、`ApplyColors_ShadowedFont`↔`CopyGlyph2bppTo4bpp`、
`UpdateTilemap`↔`UpdateTilemap`、`GetCursorTilemapPointer`↔`GetCursorTilemapPointer`。
美版 `struct Window` 偏移全部不同，仅借其算法逻辑。
