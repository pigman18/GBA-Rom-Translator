#ifndef AXVJ_FIXED_STRING_H
#define AXVJ_FIXED_STRING_H

#include <stdint.h>

/*
 * Fixed UI "translation" channel (C-side).
 * Short / fixed particles live here — not texts.json.
 */
enum {
    FIXED_STR_EMPTY = 0,
    FIXED_STR_CONTINUE_POKEDEX_UNIT = 1, /* was ひき after dex count */
    FIXED_STR_CONTINUE_BADGE_UNIT = 2,   /* continue menu こ @ 0x081BC164; blanked in asm */
};

extern const uint8_t FixedString_Empty_PCS[];
extern const uint8_t FixedString_ContinueBadgeUnit_PCS[];

const uint8_t *FixedString_Get(uint32_t id);
uint8_t *FixedString_Write(uint32_t id, uint8_t *dest);

#endif
