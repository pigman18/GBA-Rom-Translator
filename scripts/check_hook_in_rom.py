"""自检：ROM 里内嵌的钩子（@0x08000000 起）是否与 hook/out/game.bin 逐字节一致。

用法：
    python scripts/check_hook_in_rom.py [rom]
默认 rom = roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK_BIN = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "hook" / "out" / "game.bin"
DEFAULT_ROM = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"
ROM_BASE = 0x08000000
FILE_OFF = 0x00000000          # GBA ROM 头，0x08000000 映射到文件偏移 0


def main() -> int:
    rom_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ROM
    if not HOOK_BIN.exists():
        print("FAIL: 找不到", HOOK_BIN)
        return 2
    if not rom_path.exists():
        print("FAIL: 找不到", rom_path)
        return 2

    hook = HOOK_BIN.read_bytes()
    rom = rom_path.read_bytes()

    # 钩子被 armips 打到 ROM 注入区 0x08800000；也兼容 0x08000000（覆盖官方头）
    for base in (0x08800000, 0x08000000):
        off = base - ROM_BASE + FILE_OFF
        seg = rom[off:off + len(hook)]
        ok = seg == hook
        print("base=0x%08X off=0x%08X len=%d  %s" %
              (base, off, len(hook), "一致" if ok else "不一致"))
        if ok:
            print("hook sha1 =", hashlib.sha1(hook).hexdigest())
            print("rom  sha1 =", hashlib.sha1(rom).hexdigest())
            print("RESULT: PASS —— ROM 内嵌钩子与 out/game.bin 逐字节一致")
            return 0
        # 打印首个差异，便于定位
        for i in range(len(hook)):
            if seg[i] != hook[i]:
                print("   首个差异 @+0x%X  文件 %02X  rom %02X" %
                      (i, hook[i], seg[i]))
                break

    print("RESULT: FAIL —— 两个候选基址都对不上")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
