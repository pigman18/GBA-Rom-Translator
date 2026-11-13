/* RETIRED 2026-11-13：左侧透明底改由 PrintNextChar grid_bg 认 tpl@0x081BB7B4。
 * 勿再引入 .bss 锁（game.ld 无 RAM，变量落 ROM 读 0xFF → 全局 bg=0）。
 * 本文件保留作废案说明，不参与 build.bat。 */
