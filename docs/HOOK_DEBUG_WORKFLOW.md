# Hook 调试工作流 — 静态分析 → GDB 实测 → 收敛

> 目的：把 2026-08-22 地名弹窗居中（P04）从「三代同枪的隐藏 BUG」到「实测收敛」的
> 完整过程固化成可套用的流程。下次遇到任何需要改游戏内逻辑/算参数的任务，
> 按这四步走，不要跳步。
>
> 案例：`configs/POKEMON_RUBY_AXVJ00/hook/src/text/MapNamePopup_hook.c`（v1→v7）。

## 总览

```
① 静态分析（穷尽再停）
      ↓ 卡死或需实证
② gdb_patcher.py 加监听点（yaml 点 + 可选 handler）
      ↓ 抓到硬数据
③ 基于日志推算算法（指纹比对 / 单步跟踪 / 双校准点反推）
      ↓ 公式落地
④ 实际应用（改 C → build.bat → 用户打包实测 → 验收后 commit）
      ↓ 不符
   回 ③，每轮只改一个变量
```

---

## ① 静态分析 —— 先穷尽静态手段

顺序（由廉价到昂贵）：

1. **权威符号表**：`tools/Pokemon_GBA_Font_Patch/symbols/pokeruby/pokeruby.sym`
   （美版红宝石，含函数地址与大小）。先 grep 函数名/地址，再用日版同段锚点求偏移。
2. **pokeruby 源码**：`tools/pokeruby/src/*.c`。**能读 C 就别读汇编**——本次
   「MenuPrint 的 left 是格数」就是源码一行 `win->left = 8 * left;` 一锤定音的。
3. **日版反汇编**：capstone THUMB 模式。注意：
   - BL 目标符号位是 high halfword 的 **bit10**；
   - 字面量池会让线性反汇编跑飞 → 用递归下降/分段扫；
   - 早退出口（如 `pop {r0}; bx r0`）之后还有主路径代码，扫描范围要覆盖全函数。

产出：调用链、寄存器约定、**参数单位**、缓冲区大小与生命周期、候选 hook 位点。

⚠️ 护栏：同一问题静态推演连续卡死 3 次（工具调用或长推理无产出），立即转 ②，
禁止第 4 次自我辩论。静态分析给「假设」，②③ 给「实证」。

## ② gdb_patcher.py 增加监听点

### 加监听点（yaml）

`src/util/configs/{game}.yaml` 的 `gdb:` 列表追加：

```yaml
  - name: MyProbe                    # 唯一名
    address: '0x0809F6D0'            # 断点地址（命中时停在指令前）
    description: 'r0/r1/r2 含义…'    # 会话头会显示
    default: false                   # true=不加 --functions 也启用
    cfg:
      charmap: configs/POKEMON_RUBY_AXVJ00/charmap.txt   # 需要解码文本时
```

通用日志已含 PC/LR/r0-r3；要 dump 内存/比对指纹/单步，再加 handler：

```python
# src/util/gdb_patcher.py，按 name 注册
@handler("MyProbe")
def _on_my_probe(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    data = _read_ff_text(gdb, regs.get("r0", 0))     # 读到 FF 为止的文本缓冲区
    ctx.log(f"  缓冲区: {data[:24].hex(' ')} 内容={ctx.text_of(data)[:40]!r}")
```

可用原语：`_read_mem/_read_ff_text/_read_win`、`gdb.read_mem(addr,n)`、
**`gdb.cmd("s") + gdb.read_regs()` 单步**（指令级跟踪整个函数，见
`PopupStepTrace` handler——根因级 BUG 的杀手锏）、模块级计数器限次。

### 跑法

```
:: Windows Python 3.14（WSL python3 版本旧，f-string 反斜杠限制会 SyntaxError）
set PYTHONPATH=C:\code\GBA-Rom-Translator\src
C:\Python314\python.exe src\util\gdb_patcher.py log --functions A,B --no-dedup
```

mGBA 侧：加载 ROM → Tools → Start GDB stub (2345) → Pause。日志追加在
`work/gdb_patcher_log.log`，`grep "===== gdb_patcher log"` 定位会话边界。

## ③ 基于日志推算算法

三个实战手法（按威力排序）：

1. **单步跟踪还原执行流**：断点只给「某时刻寄存器快照」，单步给「全过程」。
   本次 r1=5 之谜靠它一击定案（入口 r0=0x08800145 = 跳板自身地址）。
2. **运行中 ROM 指纹比对**：handler 里 read_mem 关键字节 vs 磁盘构建逐字节比，
   排除「模拟器加载的不是这份 ROM」类环境干扰。
3. **双校准点反推物理布局**：两次实测的渲染边界联立解出未知量。本次文字区
   80px 就是 left=9 格/7 格两个出框边界（框右缘均 ≈88px）联立的产物。

纪律：**每轮只改一个变量**；每版给用户一张「预期值表」（注入值/预期现象）对照；
推算出的公式必须能同时解释此前所有观测（解释不了 = 模型还有错，别急着改码）。

## ④ 实际应用与验收

```
改 hook C/汇编 → build.bat 重编 → （大改动时 armips 全汇编验证）→ 用户打包实测
```

- **写完 hook 尽量立刻跑一遍 build.bat**：
  - `entry.s` 有 `.incbin "./baserom.gba"`——文件缺失立刻暴露，不用等打包阶段；
  - 重新生成 `out/game_syms.asm` 供 main.asm 订址；
  - 确认 game.bin 尺寸/布局变化在预期内。
- armips 全汇编验证（借文件流程见 AGENTS.md）：验证完清理
  `output.gba / charmap.txt / graphic/ / gen/`；**保留 `baserom.gba`**（构建常驻依赖）。
- 验收通过前不 commit；commit 信息记台账（已知边界、上游地雷一并写入）。

---

## 实战教训清单（2026-08-22 P04 七版收敛）

| # | 教训 | 代价 |
|---|---|---|
| 1 | **ROM 补丁严禁占用 r0**：native `mov r0,sp` 的指针必须原样进钩子；转跳用 r3 | v1~v3 三代全错（C 把自己机器码当名字量宽，恒 152px） |
| 2 | **参数单位必须实证**：MenuPrint 的 left 是格数(8px)非像素；源码+出界实测双确认 | v4 出界 wrap |
| 3 | **字段宽度别按字符数换算**：textMode=3 弹窗每字符步进 8px，10 字符字段=80px 非 160px | v5 再出界 |
| 4 | build.bat/Makefile 是 GBK+CRLF：补丁必须按字节处理，禁 UTF-8 全文重写、禁 LF-only | 编码损坏一轮 |
| 5 | 清理验证残留保留 `hook/baserom.gba`（incbin 常驻依赖） | 用户侧 build 失败两次 |
| 6 | gdb_patcher 用 `/mnt/c/Python314/python.exe` 跑 | WSL python SyntaxError |
| 7 | 静态推演与实测矛盾且三轮无解时，直接上单步跟踪，不要继续脑内模拟器 | 自写 Thumb 解释器耗数轮仍绕 |

> 相关文档：`docs/复盘_20260818_红框调试过程与问题.md`（数据坏写类任务另一套路：
> origin-vs-output 字节比对）、`AGENTS.md`（定位纪律/验证纪律）、
> `docs/PATCHES_INVENTORY.md`（P04 台账）。
