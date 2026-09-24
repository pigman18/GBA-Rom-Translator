/* out/game.bin：VMA = GameBinAddresses（v5：无入口跳板，FontFuncTable
 * 表项重定向是唯一文本 hook，符号经 out/game_syms.asm 回填 armips）。 */
MEMORY
{
    ROM (rx) : ORIGIN = 0x08800000, LENGTH = 0x10000
}

SECTIONS
{
    .text :
    {
        KEEP(*entry.o(.text*))
        KEEP(*entry.o(.text.*))
        KEEP(*fixed_string_entry.o(.text*))
        *(.text*)
        *(.rodata*)
        *(.rodata.*)
        . = ALIGN(4);
    } > ROM

    /DISCARD/ :
    {
        *(.comment)
        *(.note*)
        *(.ARM.exidx*)
        *(.ARM.attributes*)
    }
}
