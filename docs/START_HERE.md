# START HERE

> 文档按「通用 / 游戏 / 归档」三层。**必读 10 篇，归档 3 篇不必读。**

---

## 导航

| 层 | 文档 | 内容 |
|---|---|---|
| 入口 | 本页 | 导航 + 铁律 + 自检 |
| 通用 | `通用/00-工程手册.md` | 铁律、环境与依赖、构建/打包/验收流程、调试工具、通用坑 |
| 通用 | `通用/10-GBA文本渲染原理.md` | 三层结构、原版 vs 汉化模型、12px 占 4 tile、为什么不能换 char block |
| AXVJ | `POKEMON_RUBY_AXVJ00/00-总览.md` | 现状、产物基线 SHA、未修项、路径 |
| AXVJ | `POKEMON_RUBY_AXVJ00/10-文本与数据.md` | 协议、注入模型、27 模块表、表算法、物种名、背包 |
| AXVJ | `POKEMON_RUBY_AXVJ00/20-渲染与钩子.md` | textMode 分派、字段、常量、补丁站点、已证伪 |
| AXVJ | `POKEMON_RUBY_AXVJ00/30-问题与验证.md` | BUG 状态、BUG-9/BUG-10 定案、bot 流程、判据 |
| AXVJ | `POKEMON_RUBY_AXVJ00/40-BUG根因台账.md` | **各 BUG 的根因 + 证据等级 + 已证伪的假根因** |
| AXVJ | `POKEMON_RUBY_AXVJ00/90-历史与已证伪.md` | 历史阶段、不再维护的概念、踩坑 |
| 火红 | `FIRERED_BPRE00/00-12px与昵称参照.md` | 12px 实测、昵称槽解耦、不要照抄的部分 |
| 归档 | `归档/*.md`（3 篇） | 窗口系统静态分析、11-11 渲染探索史、火红昵称槽解剖 —— 原始证据，非必读 |

---

## 判断树

```
改代码？
├─ 是 → 取证(static/gdb/bot) → build.bat → 打包 → bot 采集 → 逐字读图
│        渲染类先读 通用/10 + AXVJ/20 §6；数据类先读 AXVJ/10
└─ 否 → 按上表定位；涉及地址先 objdump 复核符号表
```

任何显示/行为问题，第一步是看 origin 同屏怎么显示，回答四问：
「谁打的、打在哪、宽度怎么算、占位符/后缀从哪来」。

---

## 三条铁律

1. 协议只加不改（`F7 00`、写入模型、hook 返回契约）。
2. 验收逐字读图（墨量/像素统计不算）。
3. 产物绑 SHA256，旧截图作废。

---

## 自检

```powershell
$env:PATH="C:\Windows\System32;C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\14.2 rel1\bin;$env:PATH"
$env:PYTHONPATH="$PWD\src;$PWD\work\_pylibs"
C:\Python314\python.exe -c "import yaml,click,PIL;print('deps ok')"
python scripts/build/evidence_gate.py --status   # 可选：查看取证记录
```
