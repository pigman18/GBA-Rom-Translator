# 项目长期记忆（GBA-Rom-Translator / AXVJ00 汉化）

## 用户偏好（铁律）
- 听命令：用户指的路径/方法就是路径本身；先复述计划确认再动手。修 BUG 在当前方案上修，不擅自回退。
- 🔴 改代码前「预计效果」必须能翻译成实机截图预期；截图符合预期才算交付。
- 🔴 四步法：①静态分析 ②gdb 动态 ③实机截图 ④结论才入 MEMORY；未验证结论标注【推论/未验证】。
- 运行时故障先怀疑注入机制；验证优先静态分析，不主动开模拟器/gdb。

## v8 架构（动态避让，2026-09-07 实机验收通过）
- 静态表全废弃（用户拍板「要动态不要补丁」）：kV8AvoidScenes/kV8LinearScenes 已删，scene_cfg 只剩字号。
- tile 号=顺序分配器 v8_alloc_tile（src/text/tile_alloc.c）三层探测：
  ①活引用（权威）：begin 清零重建位图 = win tilemap + DISPCNT 启用 BG 中**同 charBase** 的 screenblock（size 位定表项数，affine/位图跳过）。任何「跳过重建」已实测证伪（继续菜单同帧关旧开新窗→疯狂撞）；性能只能降单次成本。
  ②VRAM 非空：逐候选 32B 全空校验 + 负缓存（非空非 ours→bit_set，每 tile 最多一次读）。
  ③ours 段表 EWRAM FF80（magic 0xA5C3+19 段），仅 ours 可回收。lo=0x100，hi=(4-cb)*512 clamp 1024。
- ✅ **④层 screenblock 保留已实施（2026-09-07 下午，待实机验收）**：v8_alloc_begin 对 DISPCNT 全启用 text BG（含 affine，跳过位图模式 BG2/BG3）按 BGxCNT.screenBase 把 tilemap 内存区整段 bit_set（v8_reserve_mem，折算本窗 cb 相对号、超 hi 自动裁掉）；win 自身 tilemap 内存同保留（2KB）。game.bin 8784B，check_rom_hook=True。
- 分层：text_translater=翻译/PrintNextChar_hook=渲染/blend_glyph=像素原语/tile_alloc=分配/InitTextPrinter_hook=会话边界（复位游标相位，治残留）/scene_cfg=字号。
- EWRAM：位图 FEC0(→FF40)/游标FF42/相位FF44/行标识FF46/last_tile FF48/ours FF80(→FFCF)；FF4A~FF7F 已释放。⚠0x0203FFD2 起游戏数据区严禁占用。
- 翻译链路：非 FA..FF 一律 TranslateHandleChar；slot 以日文 PCS 查 f900；GetGlyph 只走中文字库，禁止把 code∈[0x36,0x3E] 当 SYM；tm2/fn4 血条名 tpl 0x081BB40C 强制 8px。
- ⚠ ADDR_V6/V7/V8_* 宏唯一来源=game_addrs.asm（`; C:` 标记），手工写 game.h 重生成即丢。

## 12px（2026-09-07 定稿）
- 官方无原生 12px（sGlyphMasks 上限 8）但有亚 tile 拆分（mode0+64B/mode2+32B）；8+4 拆分没错，错在 tile 号来源。相位 0/4 行隔离（PHASE_ROW=tpl^curY^tileY），2 字占 3 tile 列数学必然。
- 换行复位=FE 确定性拦截：PrintNextChar_Hook 普通调用 Origin（entry.s 重放序言弹回），返回比对 (tileY,tileX)，官方换行→v8_phase_newline_reset（清相位/last_tile/行标识+tm0/1 TILE_OFFSET+=2）。NL_MARK 已删；行键须含 CURSOR_TILE_Y。
- 省 tile 方向：8×12 窄字形=2 tile/字+零相位态，拟引入第三字库「Middle」放 fonts\default（寒蝉点阵体 7px 源；Normal/Small.bdf 实为 16px spec）。待实施。
- GetCursorTilemapPos=0x08003708：tilemap=(0x1A+0x1B)+(0x1C+0x1D)*32（stride30 变体）。只答「往 tilemap 哪格写引用」，不答「引用指向的数据放哪」——**不能取代分配器**（官方零分配根基=tm1 字库常驻 tile=tileBase+2×glyphIdx；中文装不下；位置决定公式需每窗连续预算区，实测 2/8 场景选不出：地图名 62/战斗UI 0）。OBJ 空闲 tile 对 BG 文字物理不可用（tilemap 10bit+charBase 上限 0x0600FFF8 够不到 0x06010000），只能走路线③精灵文字层。

## 2026-09-07 实测定论
- IWTD(template,tileBase,glyphIdx) 逐字调用，tm1 dest=tileData+(tileBase<<5)+(glyphIdx<<6)，返回 void（Ret 断点作废）。
- InitTextPrinter：AddTextPrinter@0x08002CFC(win,text,r2=1,起始X列,栈:起始Y行)→0x08002C68；win+0x14 字节index/+0x16=r2/+0x18 tile游标(tm1+2/字)/+0x1A 起始X/+0x1B 当前X(活游标)/+0x1C 起始Y/+0x1D 当前Y（tile 列/行级非像素）。
- cb 回收：cb2 [0x001,0x200) 接管全部文本后整块可回收（判据=非零引用）。OBJ 余量以 OAM 为准（0x03002450 位图地址错）。
- 模板 24B：charBase@1 screenBase@2 fontNum@8 textMode@9 tileData@0x0C tilemap@0x10。对话框 0x081BB5BC/46C/784/484/874 cb2；招式 0x081BB3F4 cb0；队伍 0x081BB43C cb1；战斗UI 0x081BB514 cb3（win 0x021E0100 布局未知）；地图名 0x081BB49C cb0；血条 0x081BB40C cb0。
- 网格落址比顺序分配器更费空间（需 128~256 连续 tile），暂缓；pokeRS 零分配器先例在 tools/Pokemon_GBA_Font_Patch/pokeRS。判读：docs/调研_20260907_三路线实测判读.md。

## 历史教训
- 「只有某字被盖」⇒ tile 踩踏；游标状态必须留归零路径。可写 static 显式落 EWRAM（game.ld 无 .bss/.data）；排查：旧包→RAM→逻辑。
- relocate 改指针高危默认 False；reader=读串改串地址随偏移；FC 颜色码逐字符执行。
- 打包一律根 build.bat；hook 改完→hook build→根 build→check_rom_hook.py；编译通过≠交付。🔒P0：build.bat 硬编码 api-key 已入 git 待轮换。批量 Edit 后必须 grep 验证落盘。
- 识图：node vision.js bug/xxx.PNG（Read 直读 PNG 失败）。
