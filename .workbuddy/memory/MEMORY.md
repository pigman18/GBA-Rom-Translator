# 项目长期记忆（GBA-Rom-Translator / AXVJ00 汉化）

## 用户偏好（最高优先级）
- **听命令**：用户指出的路径/方法就是路径本身。先复述计划确认再动手。
- **修 BUG 不擅自回退旧版本**：在当前方案上定位修掉；确要回退先说明等确认。
- **场景门控边界（2026-09-01 v6 拍板）**：❌ 逐窗登记/声明式配置表(kTm1Windows)/atlas 扫描/OBJ 运行时避让——统统否掉。✅ tile 分配器 = **tile 号独立高水位分配器 v6_alloc_tile()**（唯一递增领号，不跟官方每行清零的 TILE_OFFSET 走），屏幕位置继续交官方光标(UpdateTilemap→GetCursorTilemapPointer)。区间 [0x100,0x1C8) 避开官方字库/场景映射/UI 图标带。
- **翻译链路统一（2026-09-01 用户确认）**：slot 表以日文字符(PCS 字节)为 bucket 索引，能查对应 f900 中文流。**不要用 F9 判断来决定翻译**——替换流(F9 短语/slot 替换流)内遇日文字符也应走 slot 查 f900，查不到才 DrawGlyph 画日文。
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

## 🔴 tile 分配器坐标系（2026-09-01 实证，动态区正确语义）
- `chs_emit_column` 写 `tile_data + free_tile*32`，free_tile 是**相对当前 BG charBase 的偏移**，
  合法范围 **0~1023**（tilemap 10bit + VRAM 4 charBlock），**不是 0~511**。上界封顶 512 = 错。
- atlas = 官方字库区 = `[BASE, BASE+512)`（官方 tm1 窗口创建时 InitWindowTileData 静态预渲染
  256 glyph×2 tile，v4 tile_alloc.c 实证），**不可**标满 `[BASE,512)`（会把 base 小窗口动态区
  吞空 ⇒ 字体全空，2026-09-01 回归根因）。
- 动态区 = 相对 charBase 偏移 `[BASE+512, hi)`，hi = `min(1024, OBJ 避让上界)`。
- **战斗窗花屏根因**：charBase=0 时动态区高段相对号 513+ = 物理 charBlock1 = OBJ 精灵区（精灵
  是 OBJ 非 BG，tilemap 活引用扫不到）⇒ 花屏。修法 `tm1_obj_rel_hi(win)`：OBJ 起始
  charBlock=(REG_DISPCNT>>4)&3，若 >BG charBase 则 hi=(obj-cb)*512（战斗窗=512，动态区截断）；
  否则 hi=1024。charBase=2 主力窗高段 = 物理 charBlock3+，不与 OBJ(charBlock1) 冲突 ⇒ 安全。
- tilemap 活引用(tm1_mark_one_map)须标 **0~1023 全部**（≥512 高段是官方引用，丢弃会让动态区
  领走官方已用 tile）；调用方已按 charBase 过滤，相对号一致。
- 无空闲时回落 lo=base 从 atlas 起点找（靠活引用精确避开），宁部分不显示也不写坏精灵。
- gdb 模板分布（AXVJ00）：主力对话框 0x081BB5BC/46C/784/484/874 charBase=2 base=0x0001（~2161 次）；
  战斗招式 0x081BB3F4 charBase=0 base=0x0000/0x0090/0x0190/0x01B8；队伍窗 0x081BB43C charBase=1 font4。
- ⚠ 上条「根治方向=声明式配置表 kTm1Windows 逐窗登记」**已被用户否定（2026-09-01 v6 拍板）**。
  根治方向改为：**按 textMode 分派的简单固定区间分配器**，不做任何窗口登记。见下方 v6 章节。

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

## v6 架构（2026-09-01 拍板，text_render.c 已删）
- **文件**：text_translater.c=翻译层(GetGlyph 解字 f900/slot/GetStringWidth，无渲染)；PrintNextChar_hook.c=渲染层(管线三段)；blend_glyph.c=像素原语。
- **管线三段独立**：解压(GetGlyph)→栅格化(chs_rasterize，按 fontSize 8/12/16 生成 tile 列对)→落址(chs_place，按 textMode 固定区间分配)。16+12+8 可混排，字号只影响栅格化。
- **统一入口** chs_print(win,code,fontSize)：GetGlyph→rasterize→place。translater 调它（传 f900 gidx + 16）。
- **🔴 GetGlyph 取字必须从中文字库**：ADDR_FONT_CHS_NORMAL(0x09000000)/SMALL(0x09100000)，索引=(code&0x7FFF)<<7，code&0x8000 再+64。**严禁用 GetGlyphTilePointers_Origin(官方日文字形)**——gidx 是中文索引查官方表返 null→全空。
- **🔴 落址定案（2026-09-01「第三层正确解法」，最重要认知）**：画一个字恒两步、缺一不可——①写 tile data（要 tile 号）②写 tilemap（要屏幕位置）。官方两条腿里**位置这条腿管得对**（GetCursorTilemapPointer @0x08003708 = `&tilemap[(CY+TY)*32+(CX+TX)]`，UpdateTilemap @0x080036DC 写 tilemap[0]/[+0x40]，palette=win[0x0F]<<12），保留；**tile 号这条腿是病灶**（`tile=base+TILE_OFFSET`，TILE_OFFSET 每行 AddTextPrinter 清零 ⇒ 每行复用同批 tile ⇒ 行2盖行1=替换）。治本=**tile 号从自家高水位 v6_alloc_tile() 领唯一递增号，与官方游标解耦；屏幕位置继续调 UpdateTilemap**。每字独享 tile，替换/叠加不再发生。
  · 各 mode 只决定「屏幕光标怎么推」：mode0/1 推 TILE_OFFSET+=2+cursorTileX+=1；mode3 只推 cursorTileX+=1（不推 TILE_OFFSET）；mode2 缓冲指针无分配。
  · lower_delta **恒=1**（v6_alloc_tile 每列领连续 2 tile，下半个=tile+1）；⚠ 曾误用 mode3=30（官方网格行距残留）⇒ 每字浪费 28 tile + 上界越界撞 UI。
  · 区间 [0x100,0x1C8)（cb=2 自由带；[0x1C9,0x1F7] 详情页场景映射、[0x1E0,0x1FF] UI 图标章避开）。高水位绝对地址 ADDR_V6_TILE_HW=0x0203FEB0。cb=1 自由带 [0x102,0x14B] 更窄，单全局高水位对其偏宽，可后续按 charBase 分桶。
  · chs_place_col = 统一原语（写像素+UTM+推 cursorTileX），cursorTileX 推进必须在原子里（曾漏推⇒多字变单字）。
- **🔴 12px 主字体（2026-09-01 落地，CHS_ADVANCE_12=1 默认）**：12px 步进 12 mod 8 = 4 ⇒ 相位两态 0/4，官方游标只有整列粒度 ⇒ 相位自存 struct ChsPhase @0x0203FF90（8B×8，key=行指纹 TILE_BASE^CURSOR_Y<<8^CURSOR_TILE_Y<<4^template>>2，失配即归零）。**print_glyph_px(win,g128,ink)** 两段式：w0=min(8-phase,ink)/w1=ink-w0，extract_cols 拼列+blend(startPixel=phase/0)；tile 号 phase==0 领新列 v6_alloc_tile、phase!=0 复用 cur_tile（**ChsPhase 加 cur_tile 字段**，相邻字共享半列 tile，每 2 字省 1 列）；尾像素 chs_fill_bg 补底色；返回 adv=(phase+ink)/8，TILE_OFFSET 推 adv*2。ink=8(半角)不改变 phase(8 是 8 倍数)。**回退**：game.h CHS_ADVANCE_12=0 → 16px 整格零状态。
- **🔴 统一绘制通道（2026-09-01 落地）**：日文/半角不再交官方 FontFunc（官方 base+TILE_OFFSET 每行清零=行间替换），改 `draw_jp_glyph(win,font_num,glyph)` 调官方字库取字、一起走 v6_alloc_tile + print_glyph_px(ink=8)。**jp_glyph_to_g128**：font 3/4/5=shadowed 4bpp(32B/tile,索引 0/14/15,同中文)直接 copy_tile32；font 0/1/2/6=1bpp 用 CopyGlyph1bppTo4bpp(src,dst,15,0) 转索引(巧法:fg/bg 参数传索引非色号)。tm2 缓冲仍交原生。**定位**=方案 B 完整化(治标),非方案 A(窗口独占 charBase+每帧重绘)。FontIsShadowed 判 1bpp/4bpp。chs_flush_to_col 已删(日文也走相位)。
- **slot 递归翻译**：slot_lookup_stream(win,cur_char,text,index) 接受任意流；替换流内日文字符也走 slot 查 f900，失败才 DrawGlyph。index 语义 pos=index-1；内层递归写 TEXT_INDEX 由外层 slot_draw_chinese 末尾统一覆盖。
- 打包：hook build.bat→根 build.bat→check_rom_hook。v6 game.bin 7132B（2026-09-01 统一绘制通道落地后），.data 0 / .bss 0。
