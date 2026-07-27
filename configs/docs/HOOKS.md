# AXVJ 补丁结构

```text
patch/
  main.asm / game_addrs.asm
  out/                      # 产物：game.bin、obj/、*.map
  src/
    game.h                  # 公共头
    text/PrintNextChar/     # 活代码（仅此 hook 启用）
      entry.s
      print_next_char.c
      draw_glyph.c
      draw_scene.c
  todo/                     # 未验证，不链接
  bak/                      # 旧 asm
```

## 已启用

| 原址 | 目标 |
|------|------|
| `ProcessCurrentChar_RegularGlyph` | `PrintNextChar\|1` @ `0x08800000`（`out/game.bin`） |
