; =============================================================================
; src/bag/hooks_origin.s — 背包场景钩（已撤）
;
; P37 口袋总绘 scrub：清 [TB+2,0x1F0) 时与背包图同 charBase → 切页撞 UI、
; 列表空窗。根因改走 PrintNextChar grid_tile_resolved 全 band 本征保留
; （方案 B，见 docs/research/BAG_LIST_TILE_COLLISION.md）。
; P38 TM left 右移：r2 双用途，暂撤。
; =============================================================================
