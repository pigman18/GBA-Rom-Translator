# 项目长期记忆（GBA-Rom-Translator / AXVJ00 汉化）

## 用户偏好（最高优先级）
- **听命令**：用户指出的路径/方法就是路径本身。先复述计划确认再动手。
- **修 BUG 不擅自回退旧版本**：在当前方案上定位修掉；确要回退先说明等确认。
- **场景门控边界**：✅ 按窗口模板地址键控的声明式静态配置表；❌ 启发式 scene 猜测（tileBase 区间/光标值）。裸字面量最糟。
- **运行时故障先怀疑注入机制**（relocate 改指针/hook 写坏字节），用配置开关二分定位，别纠结文本内容。

## 日版函数地址定位（2026-08-30 实证）
- pokeruby_jp.sym 的 UNVERIFIED 符号偏移不一（带 literal pool），还会张冠李戴（RunAnimScriptCommand 实为 0x08077C20，seg 标错）。
- 最硬验证：扫全 ROM 的 BL 调用点；0 处可能只是函数指针调用（thunk 表，本例 0x081B12D8）。
- gBattleAnims_Moves=0x081D997C；DoMoveAnim 0x08071D98 / LaunchBattleAnimation 0x08071DCC。
- gdb 采集前先 grep -c 验埋点计数，别录完 2034 行才发现 0 命中。

## gdb_patcher 坑
- HANDLERS 同名后注册者覆盖（文件末尾有循环注册），增强埋点要包在所有注册之后；同一地址只能一个埋点（别名转发）。

## 🔴 hook 可写 static 必须显式落 RAM（2026-08-30 实证）
- game.ld 无 .bss/.data 规则 ⇒ 文件级可写 static 被静默塞进 ROM（恒 0、零报错）。
- 查法：`grep -nE "^\.bss|^\.data" out/game.map`。修法：EWRAM 显式放置 `0x0203FFxx`。
- EWRAM 分配表：FF80 CHS_PITCH_CTRL(12B,含FF82 CHS_LAST_OFF) / FF8C LAST_ROW_KEY / FF8E SCENE_PTR_BASE / FF90 PITCH_SLOTS(8×8B→FFCF) / FFD0 OPT_PALETTE_OVERRIDE / FFD1 OPT_FG_COLOR / FFD2 ⚠游戏数据区严禁占用 / FFF8 GLYPH_ALLOC_NEXT。FF80–FF8F 已占满。
- 排查顺序：①打的是不是旧包(check_rom_hook.py) ②可写变量是否在 RAM ③才是逻辑。

## tm1 落址结论（⚠v4 专属，已随引擎入 bak/text-v4，勿再引用）
- 唯一布局：PTR 固定槽（curX<8，16px 步进幂等）+ DYN 动态 12px（kOptZones 多段，末条兜底）。旧 PARTITION/GRID/MODE 开关已删（git ≤7af3b08）。
- 容量：12px n 字占 4n tile（off 最大 4n-2），span 给 4n。
- PTR 16px 字距是固有限制非 BUG；16px 不额外耗 tile。选中槽必须 per-glyph（chs_slots_sel.inc 与主表同序；标签列不吃高亮 ⇒ 当前空表）。
- PTR 落址公式：`ptr_base + 2*xOff + yOff`，与 win[0x16]/[0x18] 无关；pass2 必须显式 `xOff = ptr_mode ? 1 : 0`（别用 delta 蹭 off+=2，会互相抵消）。
- **PTR 不得推进 win[0x18]**：off 是 DYN 区游标，PTR 推进会让 off 漂进下一区 ⇒ 越界覆盖。linear 分支两处 off 推进都要 `if (ptr_mode==0u)` 门控。
- 译文变更后必须重跑 `scripts/gen_tm1_slots.py`（自动读 kOptRows/kOptZones 当禁区）。

## 四个坑（⚠v4 专属教训，机制已删；诊断思路仍有效）
- 8px 小字库(font=4)字形有误，设置菜单一律 font=0。
- kOptRowSpans=0 是危险开关：span=0 不复位 win[0x18]，有中文会越界写 charblock 外。行内有无中文必须识图/实测确认。
- 混排=多个独立文本块，每个 InitTextPrinter 清零 win[0x18] ⇒ 数字块落回 off 0 踩掉前块的字。修法：pitch 槽键用 zone_id（跨块共享）+ CHS_LAST_ROW_KEY 行键未变不复位。
  - "只有某个字被盖"⇒怀疑 tile 踩踏非步进；"是否同一文本块"看 InitTextPrinter 的 cur_x。
- 游标类状态（chs_px）任何分支必须保留归零路径，否则无界累加越界写 VRAM 花屏。

## text v5 重写（2026-08-31 开工，混合写入架构）
- v4 引擎整体入 bak/text-v4（configs+work 双份核验一致）；src/text 只留 text_translater.c（F9 层，include 已改 blend_glyph.h）+ 新文件。
- blend_glyph（src/text/blend_glyph.c）= 唯一绘制原语：1bpp/2bpp，纯函数零状态，spillTile 显式传参（官方 mode0 右邻+64B / mode2 +32B，不能硬编码）；官方 Width3 展开 4 像素的怪癖在 1bpp 路径照抄保逐位等价。对拍 tests/test_blend_glyph.py 三层全绿。
- reference/ 不再参与构建，仅测试对拍引用（vendored 官方语义 = 对拍基准）。
- 🔴 hook 链接当前故意红：缺 PrintGlyph/DrawGlyph（步骤 2 = FontFuncTable 重定向 + 新渲染路径），打 ROM 前必须完成。
- 设计稿唯一权威：docs/REWRITE_DESIGN_混合写入架构.md（§4.3 已按 spillTile 定案修订）。
- 增删 src/text/*.c 后 build.bat（configs 与 work 两份同步改）编译段+链接段都要改；REM 保持全 ASCII。

## relocate / F980（2026-08-30 定案）
- relocate 改指针是高危：rom_writer 无对齐无区域过滤滑窗，巧合字节也改 ⇒ 黑屏。诊断脚本 scripts/diag_relocate_collisions.py；改 relocate 配置后必跑。**relocate 已改 opt-in（默认 False）**，改动点 translate_plan.py/assign_modules.py/texts_patcher.py；改默认值必须重跑 translate 才生效。
- F980 短语引用（5 字节，不改指针）基本够用：phrase 上限 16384、表体 6%。仅 62 条槽位<5B 走 SLT2 通路；1 条 650B 超 MAX_PHRASE_STREAM=512 会静默截断。🔴 护栏待补：phrase_stream_lookup 不判 code 上界；build_rom_data 无数量上限检查。

## 打包约定
- 🔴 每次改完 hook 源码走完整流水线：hook build.bat → 根 build.bat → check_rom_hook.py。编译通过≠交付。
- 🔴 打包一律执行仓库根 build.bat（唯一权威模块清单，勿手抄 meowth full；手抄清单漏「图鉴分类名」出过事故）。验 hook 用复制命令+--seed-only，--modules 照抄。
- 打包用 PowerShell 原生跑（中文参数）；`*>&1 | Out-File log` 再读日志，别只看退出码。bash 下 PYTHONPATH 用 C:\ 路径。
- check_rom_hook.py 的 MODES 表是 v3 遗留，"GRID"读数实为 use_linear，别当真。
- 🔒 P0：根 build.bat 硬编码 --api-key 已被 git 跟踪 ⇒ 视为泄露，需轮换+改环境变量+清历史。

## 重构等价性验证（可复用）
改前存 out/game.bin 快照；判据：①bin 大小相同 ②nm -S 符号块在快照中 in 搜索（纯数据块必须全命中）③地址常量逐条核对。别比 elf vs bin 反汇编行数。

## 识图
直接 Read PNG 失败，走仓库根 `node vision.js bug/<目录>/10.PNG "..."`（.env 配 VISION_API_KEY/VAISION_MODEL）。

## 相关文档
docs/START_HERE.md（判断树）/ 复盘_20260830_混排文本块踩踏 / 复盘_20260829_设置菜单tm1落址BUG链 / FONT_12PX_DRAW.md / HOOK_RELOCATE_PLAN.md
