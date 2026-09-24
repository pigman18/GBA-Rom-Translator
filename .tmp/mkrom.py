# -*- coding: utf-8 -*-
"""mkrom.py — 把 hook/out/game.bin + armips 的全部订址补丁打进已打包 ROM，零重建换 hook。

原理（2026-09-21 实证重写）：
  · 交付 ROM = meowth(armips(baserom))，即 armips 产物 + 注入的译文数据。
  · baserom.gba **逐字节 == 原盘 8 MB**（实测 hook 区外 0 处差异），所以
        armips 补丁集 = diff(原盘, output.gba) 且全部落在 [0, 8 MB)。
  · ⇒ 只需把「armips 对原盘的补丁」重放到交付 ROM 上，再把 game.bin 贴到
    hook 区，交付 ROM 就等价于「重跑一遍 armips + 注入同一批译文」。

🔴 为什么必须重放**全部**补丁、不能只打新增那一个桩：
   桩里的 `.word HookAddr|1` 是**绝对地址**。hook 代码一增删，其后的所有符号
   位移 ⇒ 所有旧桩都指向错地址。2026-09-21 用「只打新桩」的旧版 mkrom 生成了
   t12/t13/t14，全部开机崩，真凶就是这个（不是抬 TILE_BASE）。

用法:  python .tmp/mkrom.py <tag>
       产出 roms/outputs/_<tag>.gba 与同名 .sav（从交付 ROM 的 .sav 拷贝）
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(r"C:/code/GBA-Rom-Translator")
BASE = ROOT / "roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba"
ORIGIN = ROOT / "roms/origin/POKEMON_RUBY_AXVJ00.gba"
ARMIPS_OUT = ROOT / "configs/POKEMON_RUBY_AXVJ00/hook/output.gba"
HOOK = ROOT / "configs/POKEMON_RUBY_AXVJ00/hook/out/game.bin"
OFF = 0x800000
LIMIT = 0x810004          # armips 把 game.bin 打在 0x800000，其后到 0x810004 全零


def patch_regions():
    """(offset, bytes) 列表 —— armips 相对原盘的全部改动（hook 区除外）。"""
    a = ORIGIN.read_bytes()
    b = ARMIPS_OUT.read_bytes()
    n = min(len(a), len(b))
    out = []
    s = None
    for i in range(n):
        if OFF <= i < LIMIT:
            continue
        if a[i] != b[i]:
            if s is None:
                s = i
        elif s is not None:
            out.append((s, b[s:i]))
            s = None
    if s is not None:
        out.append((s, b[s:n]))
    return out


def main(tag):
    rom = bytearray(BASE.read_bytes())
    hook = HOOK.read_bytes()
    arm = ARMIPS_OUT.read_bytes()
    assert OFF + len(hook) < LIMIT, "hook 超出空白区：%d" % len(hook)
    assert arm[OFF:OFF + len(hook)] == hook, \
        "output.gba 里的 hook 与 out/game.bin 不一致 ⇒ 请先重跑 tools/armips.exe main.asm"

    regs = patch_regions()
    changed = 0
    for off, blob in regs:
        if rom[off:off + len(blob)] != blob:
            changed += 1
        rom[off:off + len(blob)] = blob
    rom[OFF:OFF + len(hook)] = hook

    out = BASE.with_name("_%s.gba" % tag)
    out.write_bytes(bytes(rom))
    sav = BASE.with_suffix(".sav")
    if sav.exists():
        shutil.copyfile(sav, out.with_suffix(".sav"))

    chk = out.read_bytes()
    ok = chk[OFF:OFF + len(hook)] == hook and all(
        chk[o:o + len(bl)] == bl for o, bl in regs)
    print("写出 %s (%d B)  hook %d B @0x%X  自检=%s" % (out.name, len(chk), len(hook), OFF, ok))
    print("  armips 补丁 %d 处，其中 %d 处与交付 ROM 不同（=本次重打的桩）" % (len(regs), changed))
    for off, blob in regs:
        if len(blob) <= 4:
            print("    0x%08X  %d B  → %s" % (0x08000000 + off, len(blob), blob.hex(" ")))
    assert ok, "自检失败"


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "t1")
