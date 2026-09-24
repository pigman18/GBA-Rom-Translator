## 已判死（别再走）
- v8 算法、v9.x、v12 纯计数器 UI、`v8_ui_alloc` 零调用期、v16 `v8_frame_room`、**v19 一次 LZ 总闸**、
  **B2 钩 GGTP**、**B2 tm1 借道 `TILE_BASE`**。
- ①`0x08002950` 绝对不 hook 改号（入参同时写 `win[0x16]`＝tm0 线性基址）。
- ⑨`0806F16C/F224`＝绘制热函数；`v11_pool_reset_C` 绝不复位池子游标（＝假回收）。
- 抬水位 / 不可用区 / 登记表 / ours 位图 / 场景签名 / 静态避让带 / 防御式判断 —— 一律不要。

## 交付物 / L1 判据 / 工具 / 地址
- **当前成品**：`roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba`（32 MB）sha1 **`07479112…`**
  （2026-09-20 17:15），内嵌 `hook/out/game.bin` **9060 B** sha1 `b934a886…`。
  `_translated_new.gba` / `_ab.gba` 与主 ROM **同 sha1**（同内容副本）；`*.b2new_keep` sha1 `3b474fba…`（已废）。
- 🔴 **L1 判据（改完必跑，全绿才算完）**：`verify_plan4.py`（差异 0 像素）｜`verify_middle_e2e.py`（25/25 逐位）｜
  `check_font_addrs.py`（字库基址守门）｜`check_hook_in_rom.py`（钩子入 ROM 逐字节一致）。
- ⚠ 本机 `cmd.exe` 被安全策略拦 ⇒ hook 编译用 `hook/build_sh_equiv.sh`（PATH 加
  `C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\14.2 rel1\bin`）；
  打 ROM 用 `src/util/work/POKEMON_RUBY_AXVJ00/pack_no_llm.py`（离线、不调 LLM）。
  权威全量打包仍是根 `build.bat`（由用户侧跑）。`WinError 1224` = mGBA 占着 `_translated.gba`。
- `V18_UI_ON`（`tile_alloc.h`）= UI 总开关（0 关 / 1 开）；v18 管 A 类两出口，v20 补 B 类
  （`v20_lz_ui_C` + 白名单）。`V20LzUi_Hook = 0x088001BC`、跳板 34 B / 三条出口。
- 工具：`scripts/jp_dis.py`（日版反汇编）｜`scan_bl_sites.py`｜`lz77_args.py`｜`gen_lz_ui_sites.py`｜`apply_v20.py`。
  采集：`.tmp/b2_verify.py`（主力）/ `b2_capture.py` / `b2_nav.py`。
- 地址：IWRAM `03000328`=gTplSlot `32C`=gTplBase `32E`=图集游标 `03000514/16`；
  EWRAM `0203FF42`=v8 游标、`0203FFD0/D1`=选项菜单调色板（**不可占**）。
  **hook 地址每次重编都变**，采前查 `hook/out/game.map`。`gMain = 0x030016E0`（`+0x04`=callback1）。
- 字号：Big 11×11@row2 / Small 9×9@row5 / Middle **9×11**@row2（`*outWidth` 报 8，步进 10）。
  `print_glyph`：`t0 == 0` 或 `w1 == 0` ⇒ 降级 ⇒ **违反方案 4，待修**（根因分配器池耗尽）。
