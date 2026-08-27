.loadtable "./patches/unit_charmap.txt"

.org 0x081DA780
.align 2
Brendan:
    .strn "ユウキ$"
May:
    .strn "ハルカ$"


; --- 修改初始名称为 佑树、小遥 ---
.org 0x083E9640
    .word   Brendan
.org 0x083E9658
    .word   May
