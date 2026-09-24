# -*- coding: utf-8 -*-
"""v13 静态复核：UI/文字统一分配 + 真回收。零 gdb，纯字节/反汇编。

判据（任一失败 → 退出码 1）：
  A 注入区 == game.bin（逐字节）
  B ③ 桩 0x080029E0 仍是就地 6B（push / mov r0,#1 / pop{r4,pc}）
  C ⑦ 桩 0x08062094 / ⑧ 桩 0x08062684 仍是 12B「尾跳」，且字面量指向注入区、带 Thumb 位
  D ⑦⑧ 桩以外的原体字节 == 原盘（逐字节）
  E ① body / ④ / ⑥ 未被触碰
  F 注入区无 `mov lr, pc`（46 FE）—— 历史崩因护栏
  G 注入区无 0x0203FF56 引用（v12 魔数已删）
  H ⑦⑧ 跳板里的门控字面量是 0x03000514 / 0x03000516（官方字段，不是自造魔数）
"""
import hashlib
import pathlib
import sys

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

R = pathlib.Path(r"C:\code\GBA-Rom-Translator")
ORIG = (R / "roms/origin/POKEMON_RUBY_AXVJ00.gba").read_bytes()
OUT = (R / "roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba").read_bytes()
GB = (R / "configs/POKEMON_RUBY_AXVJ00/hook/out/game.bin").read_bytes()

MD = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
FAILS = []


def chk(name, ok, detail=""):
    print(("  [OK]   " if ok else "  [FAIL] ") + name + (("  " + detail) if detail else ""))
    if not ok:
        FAILS.append(name)


def dis(addr, n, label):
    print("  --- %s 0x%08X ---" % (label, addr))
    print("      bytes:", " ".join("%02x" % b for b in OUT[addr:addr + n]))
    for i in MD.disasm(OUT[addr:addr + n], 0x08000000 + addr):
        print("      0x%08X  %-8s %s" % (i.address, i.mnemonic, i.op_str))


print("=== A. 注入区 == game.bin ===")
chk("逐字节一致 (%dB sha1=%s)" % (len(GB), hashlib.sha1(GB).hexdigest()[:12]),
    OUT[0x800000:0x800000 + len(GB)] == GB)

print("\n=== B/C. 三个桩 ===")
dis(0x29E0, 8, "③ MultistepLoadFont")
chk("③ = push{r4,lr} / mov r0,#1 / pop{r4,pc}",
    OUT[0x29E0:0x29E6] == bytes.fromhex("10b5012010bd"))

for name, addr, reg in (("⑦ StdFrame", 0x62094, "r4"), ("⑧ DlgFrame", 0x62684, "r3")):
    print("  --- %s 桩 0x%08X ---" % (name, addr))
    b = OUT[addr:addr + 12]
    print("      bytes:", " ".join("%02x" % x for x in b))
    lit = int.from_bytes(b[8:12], "little")
    expect_head = bytes.fromhex("10b5014c20470000") if reg == "r4" else bytes.fromhex("00b5014b18470000")
    chk("%s 桩头 8B 正确" % name, b[0:8] == expect_head, " ".join("%02x" % x for x in b[0:8]))
    chk("%s 桩字面量 = 注入区 | 1" % name,
        (lit & 1) == 1 and 0x08800000 <= (lit & ~1) < 0x08800000 + len(GB),
        "0x%08X" % lit)

print("\n=== D. 桩以外函数体 == 原盘 ===")
chk("③ 尾段 0x29E6..0x2A4C", ORIG[0x29E6:0x2A4C] == OUT[0x29E6:0x2A4C])
chk("⑦ 尾段 0x620A0..0x620C0", ORIG[0x620A0:0x620C0] == OUT[0x620A0:0x620C0])
chk("⑧ 尾段 0x62690..0x626A4", ORIG[0x62690:0x626A4] == OUT[0x62690:0x626A4])

print("\n=== E. 其它函数未触碰 ===")
chk("① body 0x295C..0x29DE", ORIG[0x295C:0x29DE] == OUT[0x295C:0x29DE])
chk("① 桩头 0x2950..0x295C", ORIG[0x2950:0x295C] != OUT[0x2950:0x295C])   # 仍被 v11 桩覆盖
chk("④ 0x2A50..0x2A90", ORIG[0x2A50:0x2A90] == OUT[0x2A50:0x2A90])
chk("⑥ 0x62368..0x62378", ORIG[0x62368:0x62378] == OUT[0x62368:0x62378])
chk("⑤ 0x62080..0x62094", ORIG[0x62080:0x62094] != OUT[0x62080:0x62094])   # 仍被 v10 桩覆盖

print("\n=== F. 注入区无 `mov lr, pc`（46 FE）===")
bad = ["bin+0x%X" % i for i in range(0, len(GB) - 1, 2)
       if GB[i] == 0xFE and GB[i + 1] == 0x46]
chk("无 46 FE", not bad, str(bad) if bad else "")

print("\n=== G. 注入区无 0x0203FF56（v12 魔数地址已删）===")
needle = (0x0203FF56).to_bytes(4, "little")
idx = GB.find(needle)
chk("无 0x0203FF56 字面量", idx < 0, ("bin+0x%X" % idx) if idx >= 0 else "")
# 也确认整个 ROM 里 0x03000514 仍是官方语义（被我们读写）
chk("注入区含 0x03000514（官方框号槽）", GB.find((0x03000514).to_bytes(4, "little")) >= 0)
chk("注入区含 0x03000516（官方对话框框号槽）", GB.find((0x03000516).to_bytes(4, "little")) >= 0)

print("\n=== H. ⑦⑧ 跳板反汇编（门控读官方字段）===")
for name, addr, n in (("⑦ V12StdFrame_Hook", 0x6C, 48), ("⑧ V12DlgFrame_Hook", 0x88, 44)):
    print("  --- %s (game.bin+0x%X) ---" % (name, addr))
    for i in MD.disasm(GB[addr:addr + n], 0x08800000 + addr):
        print("      0x%08X  %-8s %s" % (i.address, i.mnemonic, i.op_str))

print("\n  --- 字面量池逐字核实 ---")
POOL = [
    (0xA8, 0x03000514, "⑦ 门控 → 官方框号槽"),
    (0xAC, 0x080620A1, "⑦ 原体续跑点 |1"),
    (0xB0, 0x03000516, "⑧ 门控/重放 → 官方对话框框号槽"),
    (0xB4, 0x080626A0, "⑧ 重放字面量槽"),
    (0xB8, 0x08062691, "⑧ 原体续跑点 |1"),
]
for off, val, what in POOL:
    got = int.from_bytes(GB[off:off + 4], "little")
    chk("%-34s 0x%08X" % (what, val), got == val, "实际 0x%08X" % got)

print("\n=== I. 打包结果 ===")
chk("输出 ROM 存在且 32MB", len(OUT) == 33554432, "%d B" % len(OUT))

print()
if FAILS:
    print("结果：%d 项失败 ❌  %s" % (len(FAILS), FAILS))
    sys.exit(1)
print("结果：全部通过 ✅")
sys.exit(0)
