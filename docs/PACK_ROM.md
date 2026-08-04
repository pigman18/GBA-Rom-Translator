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
默认**不勾**（`modules.json` 里已 `default: false`）：`姓名输入`、`默认名字`、`赛事娱乐`、`高风险混杂`、`未归类`。  
**默认包含 `物种名`**（已写入下方 `--modules`）；其余跳过项不要擅自加回。

```bat
cd /d C:\code\GBA-Rom-Translator
set PYTHONPATH=%cd%\src
C:\Python314\python.exe -m meowth full roms/origin/POKEMON_RUBY_AXVJ00.gba -o roms/outputs --work-dir work --source ja --target zh-Hans --seed-only --modules 物种名,属性名,性格名,特性名,招式名,训练家类名,地点名,道具名,道具说明,招式说明,特性说明,图鉴条目,开场家园,早期城镇,中期城镇,后期与联盟,岛屿或通关后,道路与洞窟,宝可梦中心,商店,电脑与仓库,缆线与通信,标准脚本串,标题与主菜单,存档与电源,设置选项,背包界面,状态界面,队伍底栏,队伍选项,开始菜单,战斗菜单,战斗提示,战斗报文,对战设施,登场与胜负白,训练家名,图鉴界面
```

- 输入 ROM：`roms/origin/POKEMON_RUBY_AXVJ00.gba`
- 需要 LLM 补译时再临时加 `--provider` / `--api-key-env`（**禁止**把 API key 写入仓库文档）。
- 模块名 `道路与洞窟` 中间无空格（勿写成 `道路与 洞窟`）。
- 输出：`roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba`（及 `.build.json`）。

## 与「禁止代打」的关系

「禁止」指：**未请示**就代打、或手改 ROM。  
用户当轮授权或给出本命令后，**必须代打**，不要再推回 GUI。
