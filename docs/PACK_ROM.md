# AXVJ 打包（代打 ROM）

用户验收靠成品 ROM。代理**不得**以「默认交给用户 `start_gui.bat`」为由跳过打包。

## 何时必须打 ROM

出现任一情况即执行下文命令（工作目录：仓库根 `C:\code\GBA-Rom-Translator`）：

- 用户说「打 rom / 打包 / build / 出 ROM」
- 用户粘贴或引用本文件中的打包命令
- 用户说「改完后流水线 build」一类明确授权
- 用户约定「每次修复后代打 ROM」

禁止手改成品 `_zh.gba` / `*_translated.gba` 字节；只允许流水线写出。

## 标准命令

默认用 **`--seed-only`**（词库 + 种子 + work 缓存，不调 LLM）。

```bat
cd /d C:\code\GBA-Rom-Translator
set PYTHONPATH=%cd%\src
C:\Python314\python.exe -m meowth full roms/origin/POKEMON_RUBY_AXVJ00.gba -o roms/outputs --work-dir work --source ja --target zh-Hans --seed-only
```

- 输入 ROM：`roms/origin/POKEMON_RUBY_AXVJ00.gba`
- 需要 LLM 补译时再临时加 `--provider` / `--api-key-env`（**禁止**把 API key 写入仓库文档）。
- 输出：`roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba`（及 `.build.json`）。

### ⚠️ `--modules` 已废弃（2026-11-02 实测确认）

`meowth full --help` 明确标注 `--modules TEXT  Ignored (AXVJ always extracts/translates all texts)`。
旧版本文里那串 `--modules 属性名,性格名,…` 长列表**传了也不报错、但完全不生效**，
容易让人误以为「选了模块」。现行行为：AXVJ 固定抽取并翻译**全量** `translate/texts.json`
（11428 条），再由注入阶段的 `policy.py` 漏斗逐条决定 `KEEP` / `REPLACE` / `RELOCATE`。

想收窄注入范围，改 `policy.py` 的域规则或 `translate/config.json` 的 reject，
**不要**再指望 `--modules`。

> 实测基线（2026-11-02，原版 AXVJ 8MB）：`7297 replaced, 2221 relocated, 0 skipped`，
> 产物对齐 32MB。

## 打包后必做：静态验收

```bat
cd /d C:\code\GBA-Rom-Translator
C:\Python314\python.exe scripts\verify_output_rom.py
```

全部 `PASS` 才算可交付。它逐字节核对（**不启模拟器**，符合验证纪律）：

| 项 | 期望 |
|---|---|
| `game.bin` 与当前源码一致 | ROM @`0x08800000` == `hook/out/game.bin` |
| EngineEntry 跳板 | 落在 `0x0880xxxx`（当前 `0x08800165`） |
| P01/P04/P07/P08 订址桩 | `bx` 目标 == `out/game_syms.asm` 回填地址 `\|1` |
| P03 三处血条池 | `0x04000006`（原版 `0x04000008`） |
| PhraseOffsets | u32 单调递增 |
| PhraseTable | 以 `F9 00` 起的侧载流 |
| SlotTable | `SLT2` 签名 |
| 字库 Normal/Small/Sym | 非空 |

退出码 `0` = 全通过。任何 `FAIL` 都在说明「源码 / game.bin / armips 产物」三者脱节，
先跑 `build.bat` 再重新打包。

## 与「禁止代打」的关系

「禁止」指：**未请示**就代打、或手改 ROM。  
用户当轮授权或给出本命令后，**必须代打**，不要再推回 GUI。
