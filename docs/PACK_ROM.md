# AXVJ 打包（代打 ROM）

用户验收靠成品 ROM。代理**不得**以「默认交给用户 `start_gui.bat`」为由跳过打包。

## 何时必须打 ROM

出现任一情况即执行下文命令（工作目录：仓库根 `C:\code\GBA-Rom-Translator`）：

- 用户说「打 rom / 打包 / build / 出 ROM」
- 用户粘贴或引用本文件中的打包命令
- 用户说「改完后流水线 build」一类明确授权
- 用户约定「每次修复后代打 ROM」

禁止手改成品 `_zh.gba` / `*_translated.gba` 字节；只允许流水线写出。

## 标准命令（模块清单以本文件为准）

默认用 **`--seed-only`**（词库 + 种子 + work 缓存，不调 LLM）。  
默认**不勾** `高风险混杂`（`modules.json` / texts 里 `default: false`）。  
**默认包含 `宝可梦名`（物种）与 `UI界面`**（菜单短标含「关闭背包」「取消」等）；其余跳过项不要擅自加回。

```bat
cd /d C:\code\GBA-Rom-Translator
set PYTHONPATH=%cd%\src
C:\Python314\python.exe -m meowth full roms/origin/POKEMON_RUBY_AXVJ00.gba -o roms/outputs --work-dir work --source ja --target zh-Hans --seed-only --modules 属性名,性格名,特性名,宝可梦名,招式名,训练家名,地点名,道具名,道具说明,招式说明,特性说明,图鉴说明,UI界面,剧情,训练家对白
```

- 输入 ROM：`roms/origin/POKEMON_RUBY_AXVJ00.gba`
- 需要 LLM 补译时再临时加 `--provider` / `--api-key-env`（**禁止**把 API key 写入仓库文档）。
- 默认**不勾** `高风险混杂`（及姓名输入类，若另有独立模块）。
- 输出：`roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba`（及 `.build.json`）。

## 与「禁止代打」的关系

「禁止」指：**未请示**就代打、或手改 ROM。  
用户当轮授权或给出本命令后，**必须代打**，不要再推回 GUI。
