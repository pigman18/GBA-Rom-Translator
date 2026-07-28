# AXVJ 打包（代打 ROM）

用户验收靠成品 ROM。代理**不得**以「默认交给用户 `start_gui.bat`」为由跳过打包。

## 何时必须打 ROM

出现任一情况即执行下文命令（工作目录：仓库根 `C:\code\gba`）：

- 用户说「打 rom / 打包 / build / 出 ROM」
- 用户粘贴或引用本文件中的打包命令
- 用户说「改完后流水线 build」一类明确授权

禁止手改成品 `_zh.gba` / `*_translated.gba` 字节；只允许流水线写出。

## 标准命令（模块清单以本文件为准）

默认**不勾**（`modules.json` 里已 `default: false`）：`物种名`、`姓名输入`、`默认名字`、`赛事娱乐`、`高风险混杂`、`未归类`。  
下方 `--modules` 已排除它们；不要擅自加回。

```bat
cd /d C:\code\gba
set PYTHONPATH=%cd%\src
C:\Python314\python.exe -m meowth full C:/code/gba/tools/roms/origin/POKEMON_RUBY_AXVJ00.gba -o C:/code/gba/roms/outputs --work-dir work --source ja --target zh-Hans --modules 属性名,性格名,特性名,招式名,训练家类名,地点名,道具名,道具说明,招式说明,特性说明,图鉴条目,开场家园,早期城镇,中期城镇,后期与联盟,岛屿或通关后,道路与洞窟,宝可梦中心,商店,电脑与仓库,缆线与通信,标准脚本串,标题与主菜单,存档与电源,设置选项,背包界面,状态界面,队伍底栏,队伍选项,开始菜单,战斗菜单,战斗提示,战斗报文,对战设施,登场与胜负白,训练家名,图鉴界面 --provider deepseek --model deepseek-v4-flash --api-key-env DEEPSEEK_API_KEY
```

- 输入 ROM：`tools/roms/origin/POKEMON_RUBY_AXVJ00.gba`
- API Key：只用当轮用户提供的 `--api-key=…`，或临时环境变量 / `.env`；**禁止写入仓库文档或规则文件**。
- 模块名 `道路与洞窟` 中间无空格（勿写成 `道路与 洞窟`）。
- 输出：`C:\code\gba\roms\outputs\POKEMON_RUBY_AXVJ00_translated.gba`（及 `.build.json`）。

## 与「禁止代打」的关系

「禁止」指：**未请示**就代打、或手改 ROM。  
用户当轮授权或给出本命令后，**必须代打**，不要再推回 GUI。
