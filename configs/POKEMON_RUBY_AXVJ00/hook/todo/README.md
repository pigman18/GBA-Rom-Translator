# TODO(未验证) — 不参与 game.bin 链接

这里是未挂 `main.asm` 的参考骨架。

要启用某个 hook：

1. 补全对应 `.c` 实现  
2. 放到 `src/<域>/<原函数名>/`（例：`src/text/PrintNextChar/`、`src/battle/UpdateNickInHealthbox/`），并加入 Makefile / `font_patch` 源列表  
3. 原盘改写放同目录 `hook_origin.s`，在 `main.asm` `.include`；函数入口用 `.org` + `ldr/bx` 进 `game.bin`  
4. 约定详见 [`configs/docs/HOOKS.md`](../../docs/HOOKS.md)

未验证前不要链进 ROM。
