; BUG-13 窄范围实验：只替换 species 288 的名字
.org 0x0806B288
    .dh 0x4B00
    .dh 0x4718
.org 0x0806B28C
    .dh (PartyMenuDoPrint_Hook | 1) & 0xFFFF
    .dh ((PartyMenuDoPrint_Hook | 1) >> 16) & 0xFFFF
