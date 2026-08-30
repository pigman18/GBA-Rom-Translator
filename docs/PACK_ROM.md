# AXVJ 打包（代打 ROM）

用户验收靠成品 ROM。代理**不得**以「默认交给用户 `start_gui.bat`」为由跳过打包。

## 何时必须打 ROM

出现任一情况即执行下文命令（工作目录：仓库根 `C:\code\GBA-Rom-Translator`）：

- 用户说「打 rom / 打包 / build / 出 ROM」
- 用户说「改完后流水线 build」一类明确授权
- 用户约定「每次修复后代打 ROM」

禁止手改成品 `_zh.gba` / `*_translated.gba` 字节；只允许流水线写出。

## 标准命令：**直接执行仓库根 `build.bat`**

> ⚠ **不要在本文档或对话里手写、复制、转述 `meowth full` 命令。**
> 根 [`build.bat`](../build.bat) 是**唯一权威**的模块清单与参数来源。

```bat
cd /d C:\code\GBA-Rom-Translator
build.bat
```

PowerShell 下（**中文模块名必须走 PowerShell 原生调用**，Git Bash/MSYS 会转换非 ASCII 参数）：

```powershell
Set-Location C:\code\GBA-Rom-Translator
& cmd.exe /c "build.bat" *>&1 | Tee-Object -FilePath pack_log.txt
```

### 为什么必须走根 build.bat（2026-08-30 实测教训）

各文档里手抄的模块清单**会过时**。此前 `AGENTS.md` / 本文档抄的 15 个模块漏了
`图鉴分类名`（及 `树果名`、`秘密基地装饰名`、`训练家个人名`、`补漏剧情`、
`属性名-华丽大赛`、`招式名-华丽大赛`、`招式说明-华丽大赛`），
导致图鉴条目屏显示「たね宝可梦」而不是「种子宝可梦」——
被误判成 hook 渲染回归，实际只是**打包时没带上该模块**。

改模块清单 = 改根 `build.bat`，不要改文档。

## 参数说明

- 输入 ROM：`roms/origin/POKEMON_RUBY_AXVJ00.gba`
- 输出：`roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba`（及 `.build.json`）
- 默认流：extract → translate → build（内含 armips 汇编 + 字体生成）
- 根 `build.bat` **未加 `--seed-only`** ⇒ 会调 LLM 补译（耗时、产生费用）。
  只想离线快速验证 hook 时：**复制该命令并追加 `--seed-only`**，
  其余参数（含模块清单）**照抄，不要手改**。
- 默认**不勾** `高风险混杂`（`modules.json` / texts 里 `default: false`）；
  姓名输入类等高风险跳过模块不要擅自加回。

## 打包后自检（必做）

```bat
C:\Python314\python.exe scripts\check_rom_hook.py
```

验证 `configs\POKEMON_RUBY_AXVJ00\hook\out\game.bin` 与 ROM @0x800000 **逐字节一致**。
若旧 ROM 正被模拟器占用，产物会落到 `..._translated_new.gba` —— 关掉模拟器重跑，
或显式对 `_new` 路径自检后再 `mv -f` 覆盖。

> ⚠ 该脚本打印的 `MODES = {0:PARTITION,1:GRID,2:PTR,3:MIX}` 是 v3 遗留表，
> v4 的 `WinCfg` 没有 `mode` 字段（读到的是 `use_linear`）。
> 字节一致性判定不受影响，但别把那行读数当真。

## 🔒 API Key 安全（P0，待处理）

根 `build.bat` 当前**硬编码了 `--api-key=sk-...`，且已被 git 跟踪**
（`git log -- build.bat` 可见，历史提交里也有）。该 key **视为已泄露**：

1. 尽快到服务商后台**轮换/吊销**该 key；
2. 把 `build.bat` 改成从环境变量读：`--api-key=%QWEN_API_KEY%`；
3. 历史提交里的 key 需要从 git 历史清理（filter-repo / BFG），或整个仓库视为敏感。

**禁止把 API key 写进本仓库任何文档、脚本或消息。**

## 与「禁止代打」的关系

「禁止」指：**未请示**就代打、或手改 ROM。  
用户当轮授权后，**必须代打**，不要再推回 GUI。
