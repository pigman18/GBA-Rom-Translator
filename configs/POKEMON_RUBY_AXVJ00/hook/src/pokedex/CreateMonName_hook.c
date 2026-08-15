/* CreateMonName_hook — 图鉴列表页「NoXXX」与「宝可梦名」间距。
 *
 * pokeruby (pokedex.c) CreateMonListEntry 每行三列：
 *   CreateMonDexNum  No.编号  列 0x03
 *   CreateCaughtBall  精灵球   列 0x11
 *   CreateMonName     名字     列 0x17 (原值 23)
 *
 * 日版地址由 pokeruby.sym + PrintSavePokedexCount 偏移对齐：
 *   pokeruby CreateMonListEntry 0x0808DBE8 → 日版 0x0808A7F8（偏移 -0x33F0）。
 * 名字列 = movs r1,#0x17，日版共 5 处：0x0808AA00/AA24/AB34/ABDA/ABFE，
 * 由 main.asm 直接改立即数。
 *
 * DEX_NAME_COLUMN 是名字列的唯一来源：改这里 + 同步 main.asm 五处 mov。
 * 值越小名字越靠左（贴近 NoXXX），越大越靠右。
 */
#include "game.h"

#define DEX_NAME_COLUMN  0x16u   /* 图鉴列表页名字列（原 0x17=23，现 0x14=20，贴球右侧） */

uint8_t DexNameColumn(void)
{
    return DEX_NAME_COLUMN;
}
