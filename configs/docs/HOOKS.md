# AXVJ 补丁结构

```text
patch/
  main.asm / game_addrs.asm
  out/                      # 产物：game.bin、obj/、*.map
  src/
    game.h                  # 公共头
    text/PrintNextChar/     # hook text 引擎 PrintNextChar
      entry.s
      print_next_char.c
      draw_glyph.c
      draw_scene.c
      get_string_width.c
    battle/UpdateNickInHealthbox/   # hook 对战 HP 条昵称
      entry.s               # → game.bin
      update_nick_in_healthbox.c
      hook_origin.s         # 仅 armips：.org 改原盘池
  todo/                     # 未验证，不链接
  bak/                      # 旧 asm
```

## 目录约定（后续 hook 一律遵守）

| 规则 | 说明 |
|------|------|
| 路径 | `src/<域>/<原函数名>/` |
| 域 | 约等于原 decomp 文件族：`text`（text.c）、`battle`（battle_interface / HP 条） |
| 原函数名 | pokeruby / Font Patch 符号名（如 `PrintNextChar`、`UpdateNickInHealthbox`） |
| `*.c` + `entry.s` | 编进 `out/game.bin`，由 `Makefile` / `font_patch._build_game_bin` 列出 |
| `hook_origin.s` | **只**给 armips：`.org` 改原盘字面量/跳转；**不**进 gcc |
| 挂载 | `main.asm`：函数入口 `ldr/bx` → game.bin；池补丁 `.include` 对应 `hook_origin.s` |

## 已启用

| 原址 | 目标 |
|------|------|
| `ProcessCurrentChar_RegularGlyph` | `PrintNextChar\|1` @ `0x08800000`（`out/game.bin`） |
| `GetStringWidth` | `GetStringWidthChinese\|1`（同 bin） |
| nick 三池 `0x41760` / `0x42620` / `0x42C38` | `0x04000008` → `0x04000006`（`battle/UpdateNickInHealthbox/hook_origin.s`） |

## JP-via-CHS / 对战旁路

**产品铁律（双链路）**：`textMode==2` → 原版日文 FontFunc[2]；其余 → 统一中文（F9 + JP-via-CHS）。详见根目录 [`技术文档.md`](../../技术文档.md) BUG-02「双链路定案」。经验叠字 / 「取消取消」不在此闸上，见该节剩余表。

| 项 | 说明 |
|----|------|
| 默认 | 可印 PCS → JP-via-CHS（`GetGlyphTilePointers` → `DrawGlyph_Chinese_Adv` 8px）；F9 中文不变 |
| 例外 | `WIN_TEXTMODE`（`+0x0A`）**== 2** → 整钩子交 FontFunc（含 F9/sym）；FontFunc[2] blit healthbox |
| 落点 | `draw_scene.c` `scene_is_battle_interface_dest`；`print_next_char.c` 入口闸 |
| dest 闸 | `tileData∈eBattleInterfaceGfxBuffer` **未兑现**（详情好、对战仍坏）→ 弃作主闸 |
| 总闸结论 | 全关：对战好、详情乱 → 收窄为 textMode==2（勿再全关） |
| game.bin 嵌入校验 | `font_patch._verify_game_bin_embedded`：armips 后 ROM `@0x08800000` 必须 ≡ `out/game.bin`，否则失败 |
