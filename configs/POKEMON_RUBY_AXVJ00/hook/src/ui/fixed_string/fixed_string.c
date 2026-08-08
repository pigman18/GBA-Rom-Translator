/*
 * Fixed UI strings (C). Continue-menu ひき → empty via FixedString_Write.
 * Badge こ is skipped in-place in hook_origin.s (no far call).
 */
#include <stdint.h>

#include "fixed_string.h"

const uint8_t FixedString_Empty_PCS[] = { 0xFF };
const uint8_t FixedString_ContinueBadgeUnit_PCS[] = { 0xFF, 0xFF };

const uint8_t *FixedString_Get(uint32_t id)
{
    switch (id) {
    case FIXED_STR_CONTINUE_BADGE_UNIT:
        return FixedString_ContinueBadgeUnit_PCS;
    case FIXED_STR_CONTINUE_POKEDEX_UNIT:
    case FIXED_STR_EMPTY:
    default:
        return FixedString_Empty_PCS;
    }
}

uint8_t *FixedString_Write(uint32_t id, uint8_t *dest)
{
    const uint8_t *src = FixedString_Get(id);
    uint8_t *d = dest;

    for (;;) {
        uint8_t c = *src++;
        *d++ = c;
        if (c == 0xFF)
            break;
    }
    return dest;
}
