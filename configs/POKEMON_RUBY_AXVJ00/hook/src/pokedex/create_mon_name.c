/* AXVJ CreateMonName — dex list species label; left(px) from styles_data.asm. */
#include "game.h"

#define PCS_SPACE   0x00u
#define PCS_HYPHEN  0xAEu
#define PCS_EOS     0xFFu
#define POKEMON_NAME_LENGTH 10u

typedef uint16_t (*NationalToSpeciesFn)(uint16_t);
typedef uint8_t (*MenuPrintPixelFn)(const uint8_t *text, uint8_t left, uint16_t top, uint8_t a4);

static NationalToSpeciesFn const national_to_species =
    (NationalToSpeciesFn)(ADDR_NATIONAL_TO_SPECIES | 1u);
static MenuPrintPixelFn const menu_print_pixel =
    (MenuPrintPixelFn)(ADDR_MENU_PRINT_TEXT_PIXEL | 1u);

static const uint8_t *species_name_slot(uint16_t species)
{
    return (const uint8_t *)(ADDR_SPECIES_NAMES
                             + (uint32_t)species * SPECIES_NAME_STRIDE);
}

static uint8_t style_dex_name_left(void)
{
    return *(const uint8_t *)(uintptr_t)ADDR_STYLE_DEX_LEFT;
}

/**
 * Mirror of pokeruby CreateMonName with pixel X nudge from StyleDexNameLeft:
 *   left_px = (uint8_t)((b - 0x11) * 8 + 0xFC) - *StyleDexNameLeft
 */
uint8_t CreateMonName_Chinese(uint16_t num, uint8_t b, uint8_t row)
{
    uint8_t text[POKEMON_NAME_LENGTH + 1u];
    uint8_t i;
    uint8_t left_px;
    uint8_t nudge;
    uint16_t species;

    for (i = 0; i < POKEMON_NAME_LENGTH; i++)
        text[i] = PCS_SPACE;
    text[POKEMON_NAME_LENGTH] = PCS_EOS;

    species = national_to_species(num);
    if (species == 0u) {
        for (i = 0; i < POKEMON_NAME_LENGTH; i++)
            text[i] = PCS_HYPHEN;
    } else {
        const uint8_t *src = species_name_slot(species);
        for (i = 0; i < POKEMON_NAME_LENGTH && src[i] != PCS_EOS; i++)
            text[i] = src[i];
    }

    left_px = (uint8_t)((b - 0x11u) * 8u + 0xFCu);
    nudge = style_dex_name_left();
    if (nudge > 0 && left_px >= nudge)
        left_px = (uint8_t)(left_px - nudge);
    else if (nudge > 0)
        left_px = 0;

    menu_print_pixel(text, left_px, (uint16_t)row * 8u, 0u);
    return i;
}
