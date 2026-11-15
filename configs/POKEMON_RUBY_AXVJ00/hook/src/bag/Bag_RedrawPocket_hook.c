/* RETIRED 2026-11-15：P37 口袋 scrub 已撤。
 *
 * 实测：scrub [TB+2,0x1F0) 与背包精灵图同 charBase → 切页左上角撞 UI、
 * 列表空窗。撞字根因改在 PrintNextChar_hook.c：
 * grid_tile_is_other_col_natural 全 band 本征保留（方案 B）。
 */
