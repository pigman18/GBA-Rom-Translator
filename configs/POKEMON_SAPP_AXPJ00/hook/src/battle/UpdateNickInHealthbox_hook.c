/* UpdateNickInHealthbox — healthbox nick mask tile copy size (Font Patch).
 *
 * After TextPrintBattleInterface writes the nick into eBattleInterfaceGfxBuffer,
 * JP overlays kana/blank healthbox elements (0x2B/0x2C/0x2D) via CpuSet.
 * Control word 0x04000008 = 8 words = 32B covers the upper half of 10/12px
 * glyphs; Font Patch / 增益版 use 0x04000006 = 6 words = 24B.
 *
 * Origin pools are patched in hook_origin.s (armips). This unit exports the
 * constant for map/debug and future BL helpers — not called from origin yet.
 */
#include "game.h"

/* CpuSet: bit26=32-bit, low bits = word count */
#define HEALTHBOX_NICK_CPUSET_WORDS_STOCK  8u
#define HEALTHBOX_NICK_CPUSET_WORDS_CHS    6u
#define HEALTHBOX_NICK_CPUSET_CTRL_STOCK   0x04000008u
#define HEALTHBOX_NICK_CPUSET_CTRL_CHS     0x04000006u

uint32_t HealthboxNickCpusetCtrl(void)
{
    return HEALTHBOX_NICK_CPUSET_CTRL_CHS;
}

uint32_t HealthboxNickCpusetWords(void)
{
    return HEALTHBOX_NICK_CPUSET_WORDS_CHS;
}

/* Keep stock constants referenced so link map documents both sides. */
uint32_t HealthboxNickCpusetCtrlStock(void)
{
    (void)HEALTHBOX_NICK_CPUSET_WORDS_STOCK;
    return HEALTHBOX_NICK_CPUSET_CTRL_STOCK;
}
