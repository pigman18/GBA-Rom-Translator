/* out/game.bin：VMA = GameBinAddresses；入口 EngineEntry（jp2chs 引擎跳板） */
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

ENTRY(EngineEntry)
