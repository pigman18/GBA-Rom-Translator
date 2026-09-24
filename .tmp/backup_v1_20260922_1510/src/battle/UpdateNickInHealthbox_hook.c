/* UpdateNickInHealthbox — healthbox nick chrome length (Font Patch idea).
 *
 * JP chrome (elem 0x2B/2C/2D) and column→OBJ CpuSet shared one literal pool.
 * Patching the pool alone to 0x04000006 shortens chrome AND starves OBJ of the
 * last 8B/half-column (glyph rows 6–7) — looks like a white bar over Chinese.
 * hooks_origin.s keeps pools at 06 for chrome LDRs only; OBJ LDRs retarget to
 * other ROM literals that stay 0x04000008.
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
