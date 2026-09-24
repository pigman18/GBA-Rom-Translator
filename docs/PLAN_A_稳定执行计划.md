# PLAN_A 稳定执行计划 — text.bak + 归一化重构

> 目标：`src/text` 仅保留 `engine.c + {函数}_hook.c + hooks_origin.s + entry.s`，废弃旧分配器/场景表/实验窗，走方案A（tm1归一线性私有）

## 已执行（2026-09-23）

1. **备份**：`src/text` → `src/text.bak`（15文件原样，含`tile_alloc.c/scene_cfg.c/win_canvas/softbuf/opt_pixel`）
2. **归一**：
   - `engine.c` 聚合 `blend_glyph.c:199`（`sGlyphMasks/shift` RMW + `extract_cols:235`）+ `chinese_glyph.c:19`（`chs_cell_from_1bpp`）+ PlanA桩（单相位`tpl^curY` + `v8_alloc`线性桩 + `v6_scene_font`桩）
   - 删除死码：`blend_glyph.c/chinese_glyph.c/tile_alloc.c/scene_cfg.c/win_canvas.* /softbuf.* /opt_pixel.*`
   - 保留：`entry.s:26 EngineEntry`/`hooks_origin.s:7 .org PrintNextChar/InitTextPrinter`（`main.asm:28` armips钉桩，必须`.s`）
   - 保留翻译层：`text_translater.c:404 TranslateHandleChar`（`{函数}_hook.c`外独立翻译协议，若严格4类可并入`engine.c`尾部§T1-§T4）
3. **落点归一**：`PrintNextChar_hook.c:97 chs_claim_tile` 由`tm0线性/tm3网格/其余v8` → `tm3网格 其余线性（tm0/tm1统一 `TILE_BASE+TILE_OFFSET`）`
4. **档位归一**：`resolve_draw:31` 去`scene_cfg`分支，`fn==4/tm2→10px 其余12px`（Middle暂退化为BIG，后续按tpl单窗恢复）
5. **构建**：`hook/build.bat:31` 改 `engine.o + text_translater.o`，`hook/out/game.bin 7010B` + `build.bat(Python meowth full) 9510 replaced / 32MB ROM` 双绿（仅`scene_px`未用警告已清）

## 剩余结构

```
text/
  engine.c                   // 唯一渲染真源
  PrintNextChar_hook.c       // P01分流 + chs_emit/print_glyph_px/tm2
  InitTextPrinter_hook.c     // P0x块边界 phase_reset
  text_translater.c          // F9/SLT2/Phrase（可并入engine）
  entry.s / hooks_origin.s   // 汇编钉桩（不可改为.c）
text.bak/                    // 旧实现封存
include/tile_alloc.h/scene_cfg.h  // 桩头保留，待R3清
```

## 下一步（稳定迭代，每步独立ROM验收）

- **A1** 实机回归：对话/战斗四格/设置/背包/图鉴/领航员/血条名 — 验tm1线性不撞（`TILE_OFFSET+=adv*2` 与多窗`BASE`隔离，`v8_phase`单变量`&7`）
- **A2** 按需恢复 `Middle 9×11`：`engine.c`内按`tpl==0x081BB49C/0x081BB7E4 && win==0x0202E658`单窗分支（`scene_cfg`桩内加回）
- **A3** 清理：`include/tile_alloc.h/scene_cfg.h` + `game.h:63 ADDR_V8_*` 待全窗验收后删；`text_translater.c`并入`engine.c`即达严格4类

## 回退

```bat
rmdir /s /q src\text && ren src\text.bak text
git checkout -- configs\POKEMON_RUBY_AXVJ00\hook\build.bat
```

## 验收

- `hook\build.bat` → `out/game.bin` 绿
- `build.bat` (meowth full) → `roms/outputs/*_translated.gba` 32MB 绿
- 截图：设置/领航员/队伍/图鉴四窗不撞不花，长文滚动无尾列污染
