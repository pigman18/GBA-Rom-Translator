# AXVJ UI / 文本 BUG 台账（逐项修）

原则：**一次只修一类**；出 ROM → 你测 → 说「正常」后本地 commit → 再开下一项。

## 当前进度（2026-08-09）

| ID | 现象 | 状态 |
|----|------|------|
| B01 | 存档信息框花屏 | **已验收** |
| B02 | 遇敌等 A / 内联续父串 | 基线可用 |
| B02g | 路名白边、双▼（拼接已 OK） | **已验收** |
| B02h | 出招后无限打印 / 卡死 | **已验收** |
| B02i | 战斗倒下/反作用力仍日文 | **已验收** |
| B03 | 商店 / 背包光标 | **已验收** |
| B04 | 对话等 A（▼/♥）位置偏左 | 进行中 |
| B05 | 地名细项 / 血条名 | 未修 |
| B06 | 开场选初始宝可梦：宝可梦名重复打印 | **已验收** |
| B07 | PSS 宝可梦详情页 B 按钮图标被中文乱码覆盖 | 已修（lower 溢出段） |
| B08 | 队伍画面宝可梦昵称显示为错误字符 | 待修 |

## B02g — 已验收

1. **双▼**：钩 `DrawInitialDownArrow@0x3F4C` / `WaitArrow_Prepare_C`（`chs_px` 对齐 TILE_X，必要时 `TILE_OFFSET+=2`）。
2. **路名白边**：跳过 `GetMapName(fill=10)` pad，直跳 `MenuPrint`。
3. 遇敌拼接：中串 F9 内联续父串；短语 `啊！野生的\\03…` 同行。

## B02h — 出招后无限打印（已验收）

含 `FD`/`\XX` 的战斗模板禁止整串 `F9 80`；`ROM[addr-1]==FD`（extract 裁串首）亦禁。可 F900 / relocate / hook / keep。

## B02i — 战斗倒下 / 反作用力仍日文（已验收）

根因：`scan_addr_bands` 把 `0xFD`（StringExpand）当控制码跳过 → 条目从 `addr+1` 起、无指针、禁 F980 后 keep 留日；倒下模板甚至缺条。  
修复：允许 FD 起串；战斗带重扫合并；短语补 `やせいの` / `\0C倒下了` / 反作用力。

## B03 — 商店 / 背包光标（已验收）

`DrawMenuCursorEF` → `0x1E0/0x1E1`；CHS 避让到 `0x168`；列表 Linear。

## B04 — 对话等 A 符号位置（进行中）

1. 同句 `\\p`：`TILE_X = base_tx + ceil(chs_px/8)`（勿减 `CURSOR_X`）→ 商店 OK。  
2. `\n{\p}`：FE 后保持下一行光标，**禁止**按上行 `chs_px` 回画到行末（会双▼：行末静态 + 角上跳动）。只抬 `TILE_OFFSET` 防踩墨水。  
3. **译文格式**：中文把 `\n{\p}` 收成 `{\p}`（同句等 A，箭头跟在末字后）。`text_wrap.wrap_text` 对 `zh*` 做同样归一；缓存 `texts_translated.json` 已批量改过。

## B06 — 开场选初始宝可梦：宝可梦名重复打印（已验收）

**现象**（bug/20260815/5.png、6.png、7.png 为初始，11~13.png 为第一版修复后仍复现，14~16.png 为第二版修复后更乱）：

开场「救博士选宝可梦」画面，精灵球上方的两行 label 中，宝可梦名（木守宫/火稚鸡/水跃鱼）在第一行末尾与第二行**重复出现**，位置错开；第一行本应只显示「分类 + 宝可梦」。

**诊断（静态反汇编，未改 ROM 字节）**：

- 相关函数 `CreateStarterPokemonLabel` @ `0x081053A8`（对应 pokeruby `tools/pokeruby/src/starter_choose.c` 的 `CreateStarterPokemonLabel`）。
- 栈帧 `sub sp, #0x20`：`sp[0..15]` = 第一行 buffer，`sp[16..31]`（`sb = sp+0x10`）= 第二行 buffer。
- 第一行 = 颜色码(5) + 分类假名(≤6，未翻译) + 「ポケモン」 + FF。日文「ポケモン」=5B，合计 ≤16B，恰好不溢出。
- 汉化把「ポケモン」→「宝可梦」= 12B（`f9 00 ×3` 侧载字形，relocate 到 `0x0923B760`），第一行膨胀到 21~23B，**溢出 5~7B 写进第二行 buffer**，两行污染 → 名字重复。
- 分类字段（pokedex categoryName，`0x0838474C` 表）实测未翻译，仍为日文假名（ひよこ/ぬまうお/もりトカゲ）。

**根因（静态分析确认）**：

- 拷贝循环 `0x0810544C` 是**固定拷 5B**（`cmp r7,#4 / bls`），而翻译后的字符串是 13B（`f9 00 ×3 + FF`，指针 `0x08105534` 被 pointer_redirect 重定向到扩展区）。固定 5B 只拷进 `f9 00 01 63 f9` 半组序列 → 悬空 F9 把缓冲后字节当短语码查表 → 乱码（14~16.png）。
- 旧第一版只改「拷到 0xFF」、没扩 buffer → 第一行 24B 溢出进第二行，打印第一行时吃掉第二行颜色码后带出名字 → 重复（5~13.png）。
- 旧第二版只扩 frame/移 buffer、没改拷贝 → 悬空 F9 读脏栈 → 字符乱飞（14~16.png）。
- 结论：**扩 buffer 与整串拷贝必须同时做**，缺一不可。

**最终修复**（`configs/POKEMON_RUBY_AXVJ00/hook/main.asm`，B06 注释块）：

1. 栈帧 `0x20→0x60`（`.org 0x081053B2` `sub sp,0x60`）；第二行 buffer `sp+0x10→sp+0x30`（`.org 0x08105416`）；尾声 `.org 0x0810551C` `add sp,0x60`。两行各 48B，彻底隔离。
2. 拷贝循环 `.org 0x0810544C`：固定 5B → **拷到 0xFF（上限 0x11）**，字节数与原循环相同（0x1A）。整串 `f9 00 ×3 + FF` 完整落入第一行 buffer，打印在第一行的 FF 处干净收尾，无悬空 F9、无溢出。

静态验证：字节比对 + 反汇编确认 0x081053B2/0x08105416/0x0810544C/0x0810551C 四处补丁编码正确；全流水线（--seed-only）重打 ROM 成功。



## B07 — PSS B 按钮图标被中文乱码覆盖（2026-08-27 日志定案）

**现象**：PSS 右上角 B 图标左侧/上方出现汉字碎块。

**根因（gdb 2026-08-27）**：
- AXVJ `PlaceTextTile(tile)` → VRAM 字模号 **`0x200+tile*2`**（无美版 `+0x80`）→ B 用 **0x20A..0x20D**。
- 旧文档误写「tile 5/6」为字模号；5/6 只是 PlaceTextTile 形参。
- 正文 `curY=16` Mode2：`upper∈[0x1E8,0x1FF]` 已映到 `0x3E8+`，但 **`lower=idx+30`∈[0x206,0x21D]` 未映** → 实测 `u=0x3EE l=0x20C` 仍写 B 字模。

**修复**：PSS 下仅映 `0x20A..0x20D` → `CHS_PSS_B_VRAM_ALT`（0x3E0+）。  
曾误全局映 `0x206..0x21D`→`0x406`，开始菜单/队伍「携带物品」等误伤（2026-08-27）。

**证据**：`gdb_patcher_log` UTM `(11,16) u=0x3EE l=0x20C`；`PlaceTextTile` @0x0809C310。


## B08 — 队伍画面宝可梦昵称显示错误（待修）

**现象**（bug/20260819/11.PNG CN、12.PNG JP 对照）：

宝可梦队伍画面中，所有宝可梦的昵称显示为错误字符。
- JP 版正确显示玩家昵称（MEW、TYRAN、EXPLO、BUTTE、ZAPDO、ジグザグマ）
- CN 版显示为 /ウサ、/グサグマ 等完全不同的字符
- HP 值完全一致，确认是同一份存档数据

**诊断（静态分析 + GDB 日志）：**

1. 队伍名字通过 Text_InitWindow8004E3C(win=0x03004170) 渲染到 OBJ VRAM
2. 使用 fontNum=4（shadowed 4bpp），textMode=1
3. 昵称数据是 JP PCS 编码（如 c7 bf d1 = "MEW"）
4. CN hook 在 ProcessCurrentChar_RegularGlyph 拦截所有字符渲染
5. JP PCS 字符走 PrintNextChar_C -> draw_chs_pcs -> draw_jp_via_chs -> DrawGlyph_Chinese_Adv(adv_px=8)
6. draw_jp_via_chs 通过 chs_get_glyph_tile_pointers(font=4, glyph) 读取 JP glyph 数据

**根因假设**（需 GDB 验证）：

- 可能 A：DrawGlyph_Chinese_Adv 对临时 OBJ 窗口的 tile 写入地址计算错误
- 可能 B：chs_bind_pitch_slot 对临时窗口状态绑定有误
- 可能 C：font 4 的 glyph 数据在 CN 运行时被覆盖
- 名字前的 "/" 斜杠可能是渲染 bug 产生的伪影

**证据：**
- 截图：bug/20260819/11.PNG（CN）、bug/20260819/12.PNG（JP）
- GDB 日志：work/gdb_patcher_log.log
- 关键：同样字节 c7 bf d1，JP 版渲染为 "MEW"，CN 版渲染为 "/ウサ"

## 约定

你说「正常」→ 本地 `git commit`。