set confirm off
set pagination off
set height 0
set width 0
set remotetimeout 8
target remote 127.0.0.1:2345
set {unsigned int}0x08000468 = 0x08900000
set {unsigned short}0x08900000 = 0x3FF
python
exec(compile(open(r"C:/code/GBA-Rom-Translator/.tmp/gdb_drive_exp.py", encoding="utf-8").read()), "gdb_drive_exp.py", "exec")
end
continue
