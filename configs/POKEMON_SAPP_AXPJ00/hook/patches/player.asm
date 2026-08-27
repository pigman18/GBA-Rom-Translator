.loadtable "./patches/unit_charmap.txt"

; 起名菜单 preset #1：内联 PCS（指针表 0x081BC1CC 男 / 0x081BC1F4 女 指入此处）
; 禁止 .word 外链指针；slot 运行时：ユウキ→祐树、ハルカ→小遥
; 与 0x083E944C/9450 训练家名表字节一致，便于串档
.org 0x083E9640
    .strn "ユウキ$"
    .byte   0xFF, 0xFF

.org 0x083E9658
    .strn "ハルカ$"
    .byte   0xFF, 0xFF
