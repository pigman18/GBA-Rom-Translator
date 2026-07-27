# TODO(未验证) — 不参与 game.bin 链接

这里是未挂 `main.asm` 的参考骨架。

要启用某个 hook：

1. 补全对应 `.c` 实现  
2. 建议放到 `src/text/<函数名>/`，并加入 Makefile / `font_patch` 源列表  
3. 在 `main.asm` 增加 `.org` 挂载；`#include "game.h"`

未验证前不要链进 ROM。
