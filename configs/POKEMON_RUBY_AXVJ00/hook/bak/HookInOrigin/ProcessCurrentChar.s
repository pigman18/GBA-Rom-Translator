; Hook regular-glyph dispatch inside ProcessCurrentChar.
; Replaces the font-dispatch instruction at ProcessCurrentChar_RegularGlyph.
.org ProcessCurrentChar_RegularGlyph
    ldr r0, =(ChineseGlyphDispatch | 1)
    bx r0
.pool
