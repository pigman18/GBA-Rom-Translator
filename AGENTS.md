# Rules

## 核心守则
- **单任务原则**：做一件事时，不动任何已跑通的东西。新增/修改只针对目标文件，不影响其他逻辑。
- **听命令**：用户明确要求的必须照做。不要自己觉得"够了"就擅自简化或改方案。

# Build Rules

## ROM 路径
- 输入: `roms\origin\POKEMON_RUBY_AXVJ00.gba`
- 输出: `roms\outputs`

## 标准打包（用户验收用）
见 [`PACK_ROM.md`](docs/PACK_ROM.md)。  
用户说打 rom / 打包 / 给出该命令时，代理必须代跑；`modules.json` 里默认模块（物种名等）勿擅自加回。

## Armips 汇编验证（不依赖翻译文本）
```powershell
# 编译 C 源码 → configs/<ROM>\patch\out\game.bin + game_syms.asm（需 arm-none-eabi-gcc 在 PATH）
cd "configs\POKEMON_RUBY_AXVJ00\patch"
.\build.bat
# 再用 armips 打补丁（验证汇编 hook 层）
Copy-Item "..\..\roms\origin\POKEMON_RUBY_AXVJ00.gba" -Destination "baserom.gba"
..\..\..\tools\armips.exe main.asm
```

## Meowth 完整流水线验证（需要 BDF 字库 + 种子翻译，不需要 API Key）
```powershell
# 从仓库根运行（CLI 在 src\meowth，桥接在 src\MeowthBridge）
$env:PYTHONPATH = "$PWD\src"
C:\Python314\python.exe -m meowth full "roms\origin\POKEMON_RUBY_AXVJ00.gba" --seed-only --target zh-Hans -o "roms\outputs"
```
- `--seed-only`：不调用 LLM API，只用离线种子翻译
- 如需指定模块，追加 `--modules 招式1,道具1,...`（模块名见 game.json modules 节）
- 默认流：extract → seed-translate → build（内含 armips 汇编 + 字体生成）
