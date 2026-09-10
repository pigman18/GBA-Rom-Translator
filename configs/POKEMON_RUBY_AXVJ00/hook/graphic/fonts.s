.org 0x09000000
.incbin "C:\code\GBA-Rom-Translator\work\POKEMON_RUBY_AXVJ00\graphic\fonts\PokeRSFontChsNormal_unshadow(0xE0000).bin"
; shadow=false → PokeRSFontChsNormal_unshadow(0xE0000).bin

.org 0x09100000
.incbin "C:\code\GBA-Rom-Translator\work\POKEMON_RUBY_AXVJ00\graphic\fonts\PokeRSFontChsSmall_unshadow(0xE0000).bin"
; shadow=false → PokeRSFontChsSmall_unshadow(0xE0000).bin

.org 0x091E0000
.incbin "C:\code\GBA-Rom-Translator\work\POKEMON_RUBY_AXVJ00\graphic\fonts\PokeRSFontChsSym_unshadow(0x240).bin"
; shadow=false → PokeRSFontChsSym_unshadow(0x240).bin

.org 0x09400000
.incbin "C:\code\GBA-Rom-Translator\work\POKEMON_RUBY_AXVJ00\graphic\fonts\PokeRSFontChsMiddle_unshadow(0xE0000).bin"
; shadow=false → PokeRSFontChsMiddle_unshadow(0xE0000).bin

.org 0x09500000
.incbin "C:\code\GBA-Rom-Translator\work\POKEMON_RUBY_AXVJ00\graphic\fonts\PokeRSFontChsBig1Bpp_unshadow(0x1C000).bin"
; extra_bins 1bpp → PokeRSFontChsBig1Bpp_unshadow(0x1C000).bin

.org 0x09600000
.incbin "C:\code\GBA-Rom-Translator\work\POKEMON_RUBY_AXVJ00\graphic\fonts\PokeRSFontChsSmall1Bpp_unshadow(0x13400).bin"
; extra_bins 1bpp → PokeRSFontChsSmall1Bpp_unshadow(0x13400).bin

.org 0x09700000
.incbin "C:\code\GBA-Rom-Translator\work\POKEMON_RUBY_AXVJ00\graphic\fonts\PokeRSFontChsMiddle1Bpp_unshadow(0x16C00).bin"
; extra_bins 1bpp → PokeRSFontChsMiddle1Bpp_unshadow(0x16C00).bin

.include "C:\code\GBA-Rom-Translator\work\POKEMON_RUBY_AXVJ00\build\graphic\phrase_data.asm"