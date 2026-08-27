# 方案2：16px 委托（原生列原子渲染）

## 目标

用原生引擎的列原子 painter（col++ 步进），每个汉字占两列 = 16px 步进。  
不引入相位合成器、不引入像素光标——最简改动，看效果。

## 前提

- GGTP font3 字面量（0x080037CC）需指向 meowth 生成的字模银行
- meowth 需按 font3 公式 `(g&0xFFF0)*64 + (g&0xF)*32 + BASE` 生成字模

## 文件结构

```
configs/POKEMON_RUBY_AXVJ00/hook/src/text/
├── hooks_origin.s       # P01 JMP + GGTP font3 字面量重定向
├── entry.s             # EngineEntry 跳板
├── PrintNextChar_hook.c   # 薄入口：跳表复刻 + SlotTable + 派发
├── FontFunc_hook.c         # CHS 处理器：双列派发
└── text_render.c           # 共享渲染原语 + GetGlyph + render_native
```

## 修改的文件

- `build.bat` — 编译路径从 `src/` 改为 `src/text/`
- `main.asm` — `.include "./src/hooks_origin.s"` → `.include "./src/text/hooks_origin.s"`
- `include/text.h` — 添加 `GetGlyph` 声明

## 已知问题

1. ~~**GGTP 字面量指向空地址**~~ — font3 双布局字库已写入 `0x09000000`；**勿**改 GGTP 字面量（会破坏日文 font3）
2. ~~**render_native 误用 CopyGlyph2bppTo4bpp**~~ — 中文字模已是 4bpp，须 `remap_tile4bpp`（15/14/0→C/E/D）后直接写 VRAM

## 下一步

1. ~~跑 meowth 生成字模数据到 `0x09000000`~~
2. ~~修复 render_native 的 tile 地址计算~~
3. 测试对话窗效果（mGBA 实测）

## 旧文件

`configs/POKEMON_RUBY_AXVJ00/hook/src/` 下的旧文件（text.c、text_render.c 等）保留不删，仅作备份。
