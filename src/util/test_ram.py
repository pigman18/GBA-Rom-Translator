from unicorn import *
from unicorn.arm_const import *
mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
mu.mem_map(0x08000000, 32 * 1024 * 1024)   # ROM
mu.mem_map(0x03000000, 0x8000)         # IWRAM
mu.mem_write(0x08000000, open("C:\\code\\GBA-Rom-Translator\\roms\\outputs\\POKEMON_RUBY_AXVJ00_translated.gba", "rb").read())
# hook 写 0x030011E0
def hook_mem(uc, access, addr, size, val, data):
    if addr == 0x030011E0:
        print("write at crash site, pc=", hex(uc.reg_read(UC_ARM_REG_PC)))
mu.hook_add(UC_HOOK_MEM_WRITE, hook_mem)
mu.emu_start(0x08000000, 0x09000000)
