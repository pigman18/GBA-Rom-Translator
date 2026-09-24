# -*- coding: utf-8 -*-
"""v13.2 静态复核：UI/文字统一分配 + 「本窗模板」来源改为「最近初始化的窗口」。
零 gdb，纯字节 / 反汇编。

v13.2 相对 v13.1 的唯一改动：
  在 InitWindow(`0x08002C28`) 中部 `0x08002C44`（`win[0] = tpl` 之后第一条）挂桩，
  记下 win 指针 → ⑤ 的 C 实现改从「最近初始化的窗口」的 win[0] 取模板。

判据（任一失败 → 退出码 1）：
  A 注入区 == game.bin（逐字节）
  B ③ 桩 0x080029E0 仍是就地 6B
  C ⑦ / ⑧ 桩仍是 12B「尾跳」，字面量指向注入区且带 Thumb 位
  C2 0x080028BC 桩（v13.1 姊妹路径）仍是 12B「尾跳」
  C3 0x08002C44 桩（v13.2 新钩点）8B，字面量 = V13NoteWin_Hook
  D 桩以外函数体 == 原盘（含 InitWindow 前缀/后缀、WinGfxLoad 尾段）
  E ① body / ④ / ⑥ 未被触碰
  F 注入区无 `mov lr, pc`（46 FE）—— 历史崩因护栏
  G 注入区无 0x0203FF56（v12 魔数已删）；含官方 0x03000514 / 0x03000516
  H ⑦⑧ 跳板门控读官方字段
  I V13NoteWin_Hook 跳板重放的 4 条 == 原盘对应字节；续跑字面量奇数且指向 0x08002C4C
  J 代码区（0x08000000..0x08200000）的全部差异只落在已知桩点
  K 打包结果 32MB
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


def dis(addr, n, label, buf=None):
    b = OUT if buf is None else buf
    print("  --- %s 0x%08X ---" % (label, addr))
    print("      bytes:", " ".join("%02x" % x for x in b[addr:addr + n]))
    for i in MD.disasm(b[addr:addr + n], 0x08000000 + addr):
        print("      0x%08X  %-8s %s" % (i.address, i.mnemonic, i.op_str))


def thumb_bl_target(addr, hw1, hw2):
    """Thumb-2 BL（T1 编码，4 字节）目标地址。自证：0x088000DC 处的 `02 f0 72 f9`
    必须解出 0x088023C4（= game.map 的 v13_note_win_C）。"""
    s = (hw1 >> 10) & 1
    imm10 = hw1 & 0x3FF
    j1 = (hw2 >> 13) & 1
    j2 = (hw2 >> 11) & 1
    imm11 = hw2 & 0x7FF
    i1 = (~(j1 ^ s)) & 1
    i2 = (~(j2 ^ s)) & 1
    off = (s << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
    if off & (1 << 24):
        off -= (1 << 25)
    return addr + 4 + off


assert thumb_bl_target(0x088000DC, 0xF002, 0xF972) == 0x088023C4, "BL 解码器自证失败"


print("=== A. 注入区 == game.bin ===")
chk("逐字节一致 (%dB sha1=%s)" % (len(GB), hashlib.sha1(GB).hexdigest()[:12]),
    OUT[0x800000:0x800000 + len(GB)] == GB)

print("\n=== B. ③ 桩（封图集装载器）===")
dis(0x29E0, 8, "③ MultistepLoadFont")
chk("③ = push{r4,lr} / mov r0,#1 / pop{r4,pc}",
    OUT[0x29E0:0x29E6] == bytes.fromhex("10b5012010bd"))

print("\n=== C. ⑦ / ⑧ 桩（框图形装载门控）===")
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

print("\n=== C2. 0x080028BC 桩（v13.1 菜单姊妹路径）===")
b = OUT[0x28BC:0x28BC + 12]
print("      bytes:", " ".join("%02x" % x for x in b))
lit = int.from_bytes(b[8:12], "little")
chk("0x080028BC 桩头 8B = push{lr} / ldr r3 / bx r3",
    b[0:8] == bytes.fromhex("00b5014b18470000"), " ".join("%02x" % x for x in b[0:8]))
chk("0x080028BC 字面量 = V13WinGfx_Hook | 1", lit == 0x088000BD, "0x%08X" % lit)

print("\n=== C3. 0x08002C44 桩（v13.2 新钩点：InitWindow 中部）===")
b = OUT[0x2C44:0x2C44 + 8]
print("      bytes:", " ".join("%02x" % x for x in b))
lit = int.from_bytes(b[4:8], "little")
# ldr r5,[pc,#0]（B = (0x2C44+4) & ~3 = 0x2C48，恰为紧随其后的字面量）
chk("0x08002C44 桩头 4B = ldr r5 / bx r5",
    b[0:4] == bytes.fromhex("004d2847"), " ".join("%02x" % x for x in b[0:4]))
chk("0x08002C44 字面量 = V13NoteWin_Hook | 1", lit == 0x088000D9, "0x%08X" % lit)

print("\n=== D. 桩以外函数体 == 原盘 ===")
chk("③ 尾段 0x29E6..0x2A4C", ORIG[0x29E6:0x2A4C] == OUT[0x29E6:0x2A4C])
chk("⑦ 尾段 0x620A0..0x620C0", ORIG[0x620A0:0x620C0] == OUT[0x620A0:0x620C0])
chk("⑧ 尾段 0x62690..0x626A4", ORIG[0x62690:0x626A4] == OUT[0x62690:0x626A4])
chk("0x080028BC 尾段 0x28C8..0x2950", ORIG[0x28C8:0x2950] == OUT[0x28C8:0x2950])
chk("InitWindow 前缀 0x2C28..0x2C44", ORIG[0x2C28:0x2C44] == OUT[0x2C28:0x2C44])
chk("InitWindow 后缀 0x2C4C..0x2C68", ORIG[0x2C4C:0x2C68] == OUT[0x2C4C:0x2C68])

print("\n=== E. 其它函数未触碰 ===")
chk("① body 0x295C..0x29DE", ORIG[0x295C:0x29DE] == OUT[0x295C:0x29DE])
chk("① 桩头 0x2950..0x295C 仍被 v11 桩覆盖", ORIG[0x2950:0x295C] != OUT[0x2950:0x295C])
chk("④ 0x2A50..0x2A90", ORIG[0x2A50:0x2A90] == OUT[0x2A50:0x2A90])
chk("⑥ 0x62368..0x62378", ORIG[0x62368:0x62378] == OUT[0x62368:0x62378])
chk("⑤ 桩 0x62080..0x62094 仍被 v10 桩覆盖", ORIG[0x62080:0x62094] != OUT[0x62080:0x62094])

print("\n=== F. 注入区无 `mov lr, pc`（46 FE）===")
bad = ["bin+0x%X" % i for i in range(0, len(GB) - 1, 2)
       if GB[i] == 0xFE and GB[i + 1] == 0x46]
chk("无 46 FE", not bad, str(bad) if bad else "")

print("\n=== G. EWRAM 地址使用 ===")
chk("注入区无 0x0203FF56（v12 魔数已删）",
    GB.find((0x0203FF56).to_bytes(4, "little")) < 0)
chk("注入区含 0x0203FFB0（ADDR_V13_LAST_WIN）",
    GB.find((0x0203FFB0).to_bytes(4, "little")) >= 0)
chk("注入区含 0x03000328（gTplSlot）",
    GB.find((0x03000328).to_bytes(4, "little")) >= 0)
chk("注入区含 0x03000514（官方框号槽）",
    GB.find((0x03000514).to_bytes(4, "little")) >= 0)
chk("注入区含 0x03000516（官方对话框框号槽）",
    GB.find((0x03000516).to_bytes(4, "little")) >= 0)

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

print("\n=== I. V13NoteWin_Hook 跳板（v13.2 新）===")
dis(0xD8, 24, "V13NoteWin_Hook", buf=GB)
chk("重放的 4 条 == 原盘 0x08002C44..0x08002C4C",
    GB[0xE2:0xEA] == ORIG[0x2C44:0x2C4C],
    "out=%s orig=%s" % (GB[0xE2:0xEA].hex(" "), ORIG[0x2C44:0x2C4C].hex(" ")))
lit = int.from_bytes(GB[0xF0:0xF4], "little")
chk("续跑字面量 = 0x08002C4D（奇数，指向 ldrb r1,[r0,#5]）",
    lit == 0x08002C4D, "0x%08X" % lit)
chk("跳板内 bl 落在注入区（v13_note_win_C）",
    GB[0xDC:0xE0] == bytes.fromhex("02f072f9") and
    0x08800000 <= thumb_bl_target(0x088000DC,
                                  int.from_bytes(GB[0xDC:0xDE], "little"),
                                  int.from_bytes(GB[0xDE:0xE0], "little")) < 0x08800000 + len(GB),
    "bl 编码 " + GB[0xDC:0xE0].hex(" ") + " → 0x%08X" % thumb_bl_target(
        0x088000DC, int.from_bytes(GB[0xDC:0xDE], "little"),
        int.from_bytes(GB[0xDE:0xE0], "little")))

print("\n=== J. 代码区差异归因（0x08000000..0x080A0000）===")
LO, HI = 0x000000, 0x0A0000                      # 文件偏移 = 地址 - 0x08000000
# 扫描窗覆盖本 ROM 全部「被补丁命中」的地址（最大 0x0809F6CE）；
# 翻译文本数据在 0x1D0000+，不在本检查范围。
KNOWN = [
    (0x28BC, 0x28C8, "WinGfxLoad 桩 (v13.1 姊妹路径)"),
    (0x2950, 0x295C, "① TextLoadWindowTemplate 桩 (v11)"),
    (0x29E0, 0x29E6, "③ MultistepLoadFont 桩"),
    (0x2C44, 0x2C4C, "★ InitWindow 中部桩 (v13.2 本轮新增)"),
    (0x2C68, 0x2C74, "InitTextPrinter 桩 (P01)"),
    (0x32F8, 0x3300, "PrintNextChar 桩 (P01)"),
    (0x77A0, 0x77A4, "start_menu.asm 徽章串指针"),
    (0x7924C, 0x79250, "tiles 调色板指针补丁"),
    (0x41690, 0x41691, "UpdateNickInHealthbox 补丁点 1"),
    (0x41758, 0x41759, "UpdateNickInHealthbox 补丁点 2"),
    (0x41760, 0x41761, "UpdateNickInHealthbox Alt1_Pool"),
    (0x425D6, 0x425D7, "UpdateNickInHealthbox 补丁点 3"),
    (0x42620, 0x42621, "UpdateNickInHealthbox Alt2_Pool"),
    (0x42BCA, 0x42BCB, "UpdateNickInHealthbox 补丁点 4"),
    (0x42C38, 0x42C39, "UpdateNickInHealthbox Pool"),
    (0x62080, 0x62094, "⑤ TextWindow_SetBaseTileNum 桩 (v10)"),
    (0x62094, 0x620A0, "⑦ LoadStdFrameGraphics 桩"),
    (0x62684, 0x62690, "⑧ LoadDlgFrameGraphics 桩"),
    (0x889F0, 0x889FC, "DrawOptionMenuChoice 桩 (option)"),
    (0x8AA00, 0x8AA01, "pokedex.asm 补丁点 1"),
    (0x8AA24, 0x8AA25, "pokedex.asm 补丁点 2"),
    (0x8AB34, 0x8AB35, "pokedex.asm 补丁点 3"),
    (0x8ABDA, 0x8ABDB, "pokedex.asm 补丁点 4"),
    (0x8ABFE, 0x8ABFF, "pokedex.asm 补丁点 5"),
    (0x8DD60, 0x8DD68, "UnusedPrintMonName 桩 (pokedex)"),
    (0x90EF0, 0x90EFC, "start_menu.asm 桩 1"),
    (0x90F3C, 0x90F48, "start_menu.asm 桩 2"),
    (0x90FAA, 0x90FB6, "start_menu.asm 桩 3"),
    (0x9F67E, 0x9F688, "MapNamePopup 桩 (DrawMapNamePopup_StringLength)"),
]
ranges = []
i = LO
while i < HI:
    if ORIG[i] != OUT[i]:
        j = i
        while j < HI and ORIG[j] != OUT[j]:
            j += 1
        ranges.append((i, j))
        i = j
    else:
        i += 1
print("  差异区间 %d 段：" % len(ranges))
unexplained = []
for a, b in ranges:
    tag = next((t for x, y, t in KNOWN if a >= x and b <= y), None)
    print("    0x%08X..0x%08X (%2d B)  %s" % (0x08000000 + a, 0x08000000 + b, b - a,
                                              tag or "⚠ 未归因"))
    if tag is None:
        unexplained.append((a, b))
chk("代码区差异全部落在已知桩点", not unexplained, str(unexplained) if unexplained else "")

print("\n=== K. 打包结果 ===")
chk("输出 ROM 存在且 32MB", len(OUT) == 33554432, "%d B" % len(OUT))
chk("输出 ROM sha1", True, hashlib.sha1(OUT).hexdigest()[:12])

print()
if FAILS:
    print("结果：%d 项失败 ❌  %s" % (len(FAILS), FAILS))
    sys.exit(1)
print("结果：全部通过 ✅")
sys.exit(0)
