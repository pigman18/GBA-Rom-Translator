# Rules

## 核心守则
- **单任务原则**：做一件事时，不动任何已跑通的东西。新增/修改只针对目标文件，不影响其他逻辑。
- **听命令（最高优先级）**：用户明确要求的必须照做。**用户指出的路径/方法就是路径本身，不是"可选项"**。
  - 用户说「直接搜字节/搜 ROM」→ 第一动作就是字节级搜索/比对，符号表与反汇编是补充不是替代。
  - 用户说「先读源码」→ 第一动作就是读 `hook/src` + `tools/pokeruby/src`，禁止先翻符号表。
  - 用户给出指引后，先复述计划让用户确认，再动手；不要自己觉得"够了"就擅自简化或改方案。
- **模式纪律**：用户通过 Plan 模式让我提前规划的，可以自由发挥；通过 Build 模式直接让我修复某个 BUG 时，**只专注该 BUG，不得擅自扩展到无关内容**（尤其不要深究"不影响运行、不在验收范围"的内部实现）。确有关联的发现，最多在完成后一句话提及，不主动展开。
- **验证纪律**：除非用户明确要求，否则**禁止主动启动模拟器（mGBA 等）或 GDB/stub 抓现场**。验证一律优先静态分析（反汇编、字节比对、构造推演）；ROM 打完后由用户实测验收，按台账约定等用户说「正常」再 commit。
- **定位纪律（只适用于"改游戏内常量/函数地址"）**：找函数/常量地址，**先查权威符号表再动手**，禁止凭空猜测地址或靠截图纯像素去反向前后函数。权威符号表在 `tools/Pokemon_GBA_Font_Patch/symbols/pokeruby/pokeruby.sym`（美版红宝石符号，含函数地址与大小）；先 `grep` 出目标函数/常量的美版地址，再用**同一代码段的已知日版锚点**求偏移。跨文件/跨分段的偏移**不是常数**，必须用同文件内的共同函数做锚点。日美两版只在低地址基础库（约 0x0803xxxx 及以下）对齐，高地址代码区因文本长度差异会重排。切忌：不查符号表就凭反汇编「猜」函数；用错偏移却继续在原错误上加码；一次失败不返工根因。
  - ⚠️ **此纪律不得套用到"数据被写坏/图形异常"类任务**。这类问题符号表帮不上忙（它告诉你函数在哪，不告诉你哪块数据被写坏），**第一动作永远是 origin-vs-output 逐字节比对 + 特征字节搜索**，见 `docs/START_HERE.md`。
- **启动必读**：每次会话开始，先读 `docs/START_HERE.md`（判断树 + 自检），再进入任务。
- **反过度分析护栏（强制）**：目标是产出可验证结果，不是把正确性推演当产出。三选一，违反即停：
  - **三连卡死即停**：同一个问题若连续 3 次工具调用（或一段长推理）仍原地打转、无产出，必须立刻改为「执行一个最小可验证步骤」或「向用户提问」，禁止第 4 次自我辩论。
  - **能推进就先推进，歧义记账**：遇到不阻塞执行的歧义，先记入 `docs/` 待办文档并用默认值继续；只有真正阻塞决策的点才停下问。禁止让 1 个歧义卡死整批工作。
  - **面向输出，不面向正确**：优先跑流水线/编译等真实结果，用输出验证替代脑内推演。多数"矛盾"在真实数据面前自动消失，先看真实数据（如直接读 `translate.build.json` 的 `original_hex`）再纠结字节边界。

# Build Rules

## ROM 路径
- 输入: `roms\origin\POKEMON_RUBY_AXVJ00.gba`
- 输出: `roms\outputs`

## 标准打包（用户验收用）
见 [`PACK_ROM.md`](docs/PACK_ROM.md)。  
用户说打 rom / 打包 / 给出该命令时，代理必须代跑；勿擅自加回姓名输入等高风险跳过模块。

> ⚠ **打包命令一律执行仓库根 [`build.bat`](build.bat)，不要在文档或对话里手写/复制 `meowth full` 命令。**
> 根 `build.bat` 是**唯一权威**的模块清单与参数来源，文档里手抄的清单会过时
> （实测教训：2026-08-30 前各文档抄的清单漏了 `图鉴分类名`，导致图鉴页
> 「たね宝可梦」翻不出「种子宝可梦」，被误判成 hook 渲染回归）。

## Armips 汇编验证（不依赖翻译文本）
```powershell
# 编译 C 源码 → configs/<ROM>\hook\out\game.bin + game_syms.asm（需 arm-none-eabi-gcc 在 PATH）
cd "configs\POKEMON_RUBY_AXVJ00\hook"
.\build.bat
# 再用 armips 打补丁（验证汇编 hook 层）
Copy-Item "..\..\roms\origin\POKEMON_RUBY_AXVJ00.gba" -Destination "baserom.gba"
..\..\..\tools\armips.exe main.asm
```

## Meowth 完整流水线（用户验收用 ROM）
**直接执行仓库根 [`build.bat`](build.bat)** —— 它内含权威模块清单与全部参数：

```bat
cd /d C:\code\GBA-Rom-Translator
build.bat
```
```powershell
# PowerShell 下（中文模块名须走 PowerShell 原生调用，Git Bash/MSYS 会转换非 ASCII 参数）
Set-Location C:\code\GBA-Rom-Translator
& cmd.exe /c "build.bat" *>&1 | Tee-Object -FilePath pack_log.txt
```

- 默认流：extract → translate → build（内含 armips 汇编 + 字体生成）
- 根 `build.bat` **未加 `--seed-only`** ⇒ 会调 LLM 补译（耗时、产生费用）。
  只想离线快速验证 hook 时，复制该命令并追加 `--seed-only`（其余参数照抄，不要手改模块清单）。
- 打完必跑自检：`C:\Python314\python.exe scripts\check_rom_hook.py`
  （验证 `configs\POKEMON_RUBY_AXVJ00\hook\out\game.bin` 与 ROM @0x800000 逐字节一致）

> 🔒 **禁止把 API key 写进仓库**：根 `build.bat` 当前**硬编码了 `--api-key=sk-...`，且已被 git 跟踪**
> （`git log -- build.bat` 可见）。这是 P0 安全问题 —— 该 key 视为已泄露，应尽快轮换，
> 并改为从环境变量读取（如 `--api-key=%QWEN_API_KEY%`）。
