# 项目长期记忆（GBA-Rom-Translator / AXVJ00 汉化）

## 用户偏好（铁律）
- 听命令：用户指的路径/方法就是路径本身；先复述计划确认再动手。修 BUG 在当前方案上修，不擅自回退。
- 🔴 改代码前「预计效果」必须能翻译成实机截图预期；截图符合预期才算交付。
- 🔴 四步法：①静态分析 ②gdb 动态 ③实机截图 ④结论才入 MEMORY；未验证结论标注【推论/未验证】。
- 运行时故障先怀疑注入机制；验证优先静态分析，不主动开模拟器/gdb。

## v9 分配器（方案 A 首版，2026-09-08 实现【未实机验证】）
- 用户否掉止血类方案，拍板重构两指标：①尽量无上限 ②尽量不撞 UI。调研文档 docs/调研_20260908_tile分配器重构方案.md（方案A 独占块+按需载入主推 / B OBJ 精灵层 / C atlas 搬迁）。
- tile_alloc.c v9 已实现（安全子集，未做 BGxCNT/模板重定向）：
  ①cb0 两级区间：优先独占带 [0x2D2,0x400)（官方 tm1 字库固定止于 0x2D1，其上=物理 cb1 块上部，无官方固定产出=可声明所有权），耗尽回落 [0x100,0x2D2)；其他 cb 单区间 [0x100,hi) 原行为。
  ②ours-GC：begin 末尾把「本 cb 段表 ∧ 不在活引用位图」的历史 glyph 段 32B 清零释放+段目清空。治「负缓存只避让不回收→非空 tile 随会话单调累积→空间越用越少」机制性根源。
  ③段表 v9：段带 cb 标签（len_raw bit10~14），修跨 cb 相对号错回收；magic 0xA5C4。
- 三层探测降级 tripwire（发现声明失效自动绕开），渲染路径/场景表零改动（保持「屏蔽」提交 ea7507b 后状态：kPokeNav/kMapInfo/kTrainerInfo 规则已注释停用，仅 kOptionScene）。
- 交付 roms/outputs/POKEMON_RUBY_AXVJ00_translated_new.gba（旧名被 mGBA 锁定），check_rom_hook=True，game.bin 9384B。
- 遗留：cb2/cb3 天花板需「场景→空闲块分级表」+ 模板重定向（需 gdb 逐场景实测）；半角同块化仅重定向路线才需要。

## v8 架构（动态避让，2026-09-07 实机验收通过；v9 在其上叠加）
- 静态表全废弃（用户拍板「要动态不要补丁」）：kV8AvoidScenes/kV8LinearScenes 已删，scene_cfg 只剩字号。
- tile 号=顺序分配器 v8_alloc_tile（src/text/tile_alloc.c）三层探测：
  ①活引用（权威）：begin 清零重建位图 = win tilemap + DISPCNT 启用 BG 中**同 charBase** 的 screenblock（size 位定表项数，affine/位图跳过）。任何「跳过重建」已实测证伪（继续菜单同帧关旧开新窗→疯狂撞）；性能只能降单次成本。
  ②VRAM 非空：逐候选 32B 全空校验 + 负缓存（非空非 ours→bit_set，每 tile 最多一次读）。
  ③ours 段表 EWRAM FF80（magic 0xA5C3+19 段），仅 ours 可回收。lo=0x100，hi=(4-cb)*512 clamp 1024。
- ✅ **回卷回收踩自己已修（2026-09-07，粉框「道/路」重叠团根因）**：会话内领号不标位图 → 游标触顶回卷重扫用过期位图 → 本串刚写的 tile（ours+非空）判可回收 → blend 叠加成团。修复=v8_alloc_tile 领号成功即 v8_bit_set（会话内不回收自己，begin 全量重建不泄漏）。⚠ 字形占位=竖直 tile 对（t0=上半8行/t0+1=下半8行，UpdateTilemap(win,upper,lower) 竖排），8px/12px 都必须占 2，「省 tile」先查 upper/lower 语义。粉框模板 0x081BB7E4：charBase=0 textMode=1（走 v8）。
- ✅ **④层 screenblock 保留已实施并实机验收通过（2026-09-07 用户确认正常，自动提交 1e259cc）**：v8_alloc_begin 对 DISPCNT 全启用 text BG（含 affine，跳过位图模式 BG2/BG3）按 BGxCNT.screenBase 把 tilemap 内存区整段 bit_set（v8_reserve_mem，折算本窗 cb 相对号、超 hi 自动裁掉）；win 自身 tilemap 内存同保留（2KB）。game.bin 8784B，check_rom_hook=True。
- 分层：text_translater=翻译/PrintNextChar_hook=渲染/blend_glyph=像素原语/tile_alloc=分配/InitTextPrinter_hook=会话边界（复位游标相位，治残留）/scene_cfg=字号。
- EWRAM：位图 FEC0(→FF40)/游标FF42/相位FF44/行标识FF46/last_tile FF48/ours FF80(→FFCF)；FF4A~FF7F 已释放。⚠0x0203FFD2 起游戏数据区严禁占用。
- 翻译链路：非 FA..FF 一律 TranslateHandleChar；slot 以日文 PCS 查 f900；GetGlyph 只走中文字库，禁止把 code∈[0x36,0x3E] 当 SYM；tm2/fn4 血条名 tpl 0x081BB40C 强制 8px。
- ⚠ ADDR_V6/V7/V8_* 宏唯一来源=game_addrs.asm（`; C:` 标记），手工写 game.h 重生成即丢。

## 2026-09-07 第二轮 gdb 实测定论（导航窗端到端验收）
- 采集（win 0x0202E658/tpl 49C，14 会话）：180 领号全顺序无重叠、相位全 8 倍数→每字 phase0 全宽覆写新领 tile 对；13 次重绘复用 tile 但全覆写；写前现值全 84f2。**v8 分配器/blend/相位/场景表实机逐像素验收通过**：「墨团=blend 叠旧墨」假设证伪（此前会话内回轮踩踏已由领号即标位图修复）。
- 像素比对：16px 字符==Normal 库槽位、Middle 字符==Middle 库槽位（ROM 0x1000000/0x1400000+code*128，TL/BL/TR/BR；VRAM nibble ink!=0xF，ROM nibble 0xF=墨）。工具在 work/POKEMON_RUBY_AXVJ00/（parse_gdb_log/decode_vram/cmp_font_slot.py）。
- 🔴 **真根因分层（2026-09-07→09-08）**：①Normal.bdf em=12 塞 16×16 槽→16px 场景缩水（字源/规格，另案）；②Middle 8px 密度极限≠本次「号」错乱主因；③**2026-09-08**：「号」类错乱=packer **nibble 端序**写反（见上节），非 tile 象限序、非 CY2 伪影。
- 粉框 tpl 7E4 两轮 gdb 均零触发（banner 只在走出/走进道路时重绘）；若用户坚持粉框仍有花屏需专门补采。

## 12px（2026-09-07 定稿）
- 官方无原生 12px（sGlyphMasks 上限 8）但有亚 tile 拆分（mode0+64B/mode2+32B）；8+4 拆分没错，错在 tile 号来源。相位 0/4 行隔离（PHASE_ROW=tpl^curY^tileY），2 字占 3 tile 列数学必然。
- 换行复位=FE 确定性拦截：PrintNextChar_Hook 普通调用 Origin（entry.s 重放序言弹回），返回比对 (tileY,tileX)，官方换行→v8_phase_newline_reset（清相位/last_tile/行标识+tm0/1 TILE_OFFSET+=2）。NL_MARK 已删；行键须含 CURSOR_TILE_Y。
- ✅ **Middle 8×12 第三字库已接入（2026-09-07 实施并定稿字源）**：链路 build_chinese_font.py --narrow-8x12（墨迹→slot 左列 TR/BR 全零，禁 fallback）；engine._build_font_from_bdf 主构建 labels 排除 Middle + 独立 narrow 构建；punct patch 跳过 Middle；font.config.json slot Middle@0x09400000。hook：ADDR_FONT_CHS_MIDDLE@0x09400000、GetGlyph 第 5 参 font_lib（CHS_FONT_LIB_MIDDLE=2）、resolve_draw 输出 lib、chs_print 传 lib；scene_cfg kPokeNavScene（tpl 0x081BB49C+win 0x0202E658，cur_x==4→16px 其余 Middle）。
- **Middle 字源终版（2026-09-07 用户拍板）＝Normal 分组 OR 派生**：src/util/fonts_patcher.py 从 Normal.bdf 派生 Middle.bdf（输出列 X=源 [3X/2,3(X+1)/2) 列 OR，12→8 列不丢笔画，行不缩=满 12px 高瘦长观感；16px spec 同 Normal/Small，DWIDTH 10 同 Small 约定——DWIDTH 全链无人消费已实证）。寒蝉 7×8 方块观感被用户否决；隔列抽稀/最近邻断笔均否决；Normal 压瘦唯有分组 OR 可行。缺字回退 --fallback-bdf=fonts/default/Middle_fallback.bdf（寒蝉版，44 个 Normal 没有的符号字 §※「」《》・ー—）。数据验证：ROM 内嵌==新 bin 逐字节 True、44 符号槽与旧版一致、check_rom_hook=True。
- ✅ **场景表扩 2 条（2026-09-07，粉框花屏修复）**：kMapInfoScene tpl 0x081BB7E4（地图信息粉框「119号道路」，r3=13 居中）、kTrainerInfoScene tpl 0x081BB7B4（训练家信息），均 win=0 整模板 Middle。根因：粉框不在场景表→12px 回退，游戏按 8px/字算居中起点→12px 字形溢出窄框踩踏花屏。game.bin 8948B 四键齐；验证法=ROM 内扫描场景键字面量（check_rom_hook 字节一致会漏判两边都旧）。
- **Middle 数据链比对记录（2026-09-07 深夜，比对本身有效）**：Middle.bdf→打包算法重算 ↔ ROM 0x1400000 实字节 6807/6807 逐字节一致（工具 work/POKEMON_RUBY_AXVJ00/cmp_bdf_rom.py）；ROM==实机 VRAM 逐像素一致（宝可导航窗场景）。⚠ 注意：这些只证明「字节链路没断」，不证明「渲染语义正确」。
- 🔴🔴 **【错误结论①·永久留档】「CY2 发虚 = tile 摆法伪影」**（GLM-5.3-Flash，2026-09-07 深夜）：称 CY2 行优先 TL,TR,BL,BR 是查看器问题、让用户改 8px 宽看。证据图自画，非实测。**用户 2026-09-08 钉死：CY2 显示 == 游戏实机，一模一样 → 不是查看器伪影。**
- 🔴🔴 **【错误结论②·永久留档】「根因= tile 顺序 TL,TR vs TL,BL」**（同日凌晨跟风纠正）：把 CY2==游戏误推成「渲染按行优先读 128B」。静态核对：`pack_slot16_4bpp` 与 GetGlyph/`chs_rasterize` **同为 TL,BL,TR,BR**；按该序+「高 nibble=左」解包，「号」与 BDF 一致——**不是象限顺序错位。**
- ✅ **【真根因·2026-09-08 钉死】4bpp nibble 端序写反**：`build_chinese_font.pack_slot16_4bpp` 长期写 **左像素=高半字节**（注释还自称对齐 Font_Patch）；GBA / CrystalTile2 / `blend_row_4bpp` / `extract_cols` 均为 **左像素=低半字节（GBATEK）**。BDF 正确 → 打包把相邻像素对调 → CY2 与游戏同错；用「高=左」自洽解包的 cmp 脚本会报「BDF↔bin 全等」假闭环。2026-08-31 已记「注释 left=high 过时、字库应 GBA 低=左」，**packer 代码直到本次才改**。
- ✅ **已修**：`pack_slot16_4bpp` → `(right<<4)|left`；engine/`sim_gba_font_blit`/font_panel/font_tools 解压预览同步；已重生成 `work/.../PokeRSFontChs{Middle,Normal,Small}(_unshadow)*.bin`。tile 容器约定仍是 **TL@0 / BL@0x20 / TR@0x40 / BR@0x60**（未改）。待打 ROM 后 CY2+实机验收「号」等。
- 🔴 **方法论**：①用户「CY2==游戏」优先于任何自画伪影说；②「字节一致」必须与 **GBA 解包语义**一致，不能用错误 nibble 约定自证；③未验证布局/端序结论标【推论】；④旧 MEMORY 二次纠正仍可能错——以字节级对照+用户截图为准。
- ⚠ hook 构建坑：本环境 cmd 被拦需 bash 手复刻 gcc 序列；超长 && 链会静默断链（无报错），链接前 ls out/obj 清点 15 个 obj、链接后扫描键验证。
- 🔑 关键认识：8px 墨在 print_glyph_px 相位路径下恒 phase=0（8%8=0）/w1=0/1 列 2 tile——chs_emit 零改动，Middle 自动走 12px 已验证的推进/换行/游标链路。game.bin 8908B，check_rom_hook=True，ROM@0x09400000 抽查 1000 字形与 bin 一致。
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
