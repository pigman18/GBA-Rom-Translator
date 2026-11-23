# scripts/ 索引

规则：**一个目录 = 一个小功能**，目录名说清"这脚本干什么"，不按"分析/工具"这类大词划分。
主流程（构建、打包、场景运行）只读这里，不在目录里做数据加工。

| 目录 | 做什么 | 常用入口 |
|---|---|---|
| `build/` | 静态守门 | `evidence_gate.py --status/--check`（取证记录，`hook/build.bat` 已不再调用）；`lint_lua.py`（bot 改完先跑） |
| `font/` | 中文字库生成、预览、修补 | `gen_chs_bdfs.py`（BDF，`font.config.json` 引用）；`build_chinese_font.py`（出 C 数组/头文件）；`bdf_preview.py`、`test_glyph_18.py`、`glyph_valign.py`、`bdf_fill_missing.py`、`patch_font_punct.py` |
| `verify/` | 成品与符号校验 | `verify_output_rom.py`（产物 20 项检查）；`verify_pokeruby_jp_sym.py`、`verify_jp_addrs.py`；`hexdiff.py` |
| `textdata/` | 抽取→翻译→注入链的辅助 | `run_axvj_pipeline.py`、`run_batch.py`、`run_verify_batch.py`、`build_baseline.py`、`coverage_report.py`、`merge_extract_cfg.py`、`fix_ptr_*.py`、`apply_text_cleanup.py`、`full_ref_index.py` |
| `tables/` | 表几何 / stride / 汇编数据生成 | `emit_table_data.py`、`emit_item_test.py`、`emit_ability_test.py`、`gen_item_stride.py`（`src/meowth/item_table_plan.py` 引用）、`stride_v4_verify.py`、`a2_final_plan.py` |
| `maps/` | 地图 ID、NPC、场景坐标 | `map_ids_full.py`、`map_ids.py`、`list_all_city_maps.py`、`list_interactables.py`、`list_objects.py`、`calibrate_all.py` |
| `scene/` | 场景注册与生成 | `gen_scenes.py`、`scene_gate.py`、`calibrate_scenes.py` |
| `scene_assets/` | 场景图形采集与资产回推 | `harvest_obj_assets.py`（`ui_sweep.lua` 引用）、`harvest_all_scene_assets.py`、`capture_scene_graphics.py`、`emit_scene_presets.py`、`infer_preset_palette.py` |
| `window/` | TextPrinter 窗口、排版宽度 | `dump_wins.py`、`scan_wins.py`、`probe_wins.py`、`strict_census.py`、`find_text_rows.py`、`dump_font_slots.py` |
| `tilemap/` | 图块与 BG tilemap 比对 | `cmp_tilemap.py`、`tilemap_scan.py`、`find_tile.py`、`charblock_map.py`、`audit_tiles_vs_screen.py` |
| `image/` | 截图裁切与差异图 | `png_diff.py`、`crop_png.py`、`pixel_ascii.py`、`region_ascii.py` |
| `memory/` | RAM / 存档 / 结构布局诊断 | `probe_sav_state.py`、`diff_sav_full.py`、`derive_template_layout.py`、`dump_objects.py`、`find_party_hp.py` |
| `gdb/` | GDB 探针、调用链、反汇编 | `find_callers.py`（`src/meowth/struct_trampoline.py` 引用）、`step_trace.py`、`trace_callpath.py`、`gdb_loop.py`、`emu_run.py`、`disasm_thumb.py` |
| `battle/` | 战斗 / 野生表 | `scan_wild_headers.py`、`parse_wild_headers.py`、`plan_rng_sweep.py` |
| `pokedex/` | 图鉴条目与指针 | `dump_pokedex_entry.py`、`diff_pokedex.py`、`check_dex_overlap.py` |
| `warp/` | 传送/瞬移存档工具 | `warp_tool.py`（`bot.lua` 注释引用）、`set_teleport_move.py`、`explain_warp_limit.py` |
| `firered/` | 火红参照实验（12px/昵称结论来源） | `207_dump_firered_font.py`、`278_small_deliver.py`、`310_nick_slot_gdb.py` |
| `oneoff/` | 一次性补丁（已执行完，留作操作记录） | `_add_tower_table.py`、`_patch_*.py` |

## 不能随意改路径的引用

- `configs/.../translate/font.config.json` 说明 → `scripts/font/gen_chs_bdfs.py`
- `src/meowth/item_table_plan.py` → `scripts/tables/gen_item_stride.py`
- `src/meowth/struct_trampoline.py` → `scripts/gdb/find_callers.py`

移动这些脚本必须同步改上面三处，否则构建/导入直接断。
（`hook/build.bat` 已于 2026-11-23 解除对 `evidence_gate.py` 的调用。）

## 已删除的调研脚本

2026-11-23 清掉 561 个一次性调研/诊断脚本（`research/firered` 300+、`research/ruby` 180+、`diag/` 40+ 等），
结论已并入 `docs/POKEMON_RUBY_AXVJ00/`。备份在 `work/_backup/scripts_deleted_20261123.zip`（无 git，需要时可解压）。
