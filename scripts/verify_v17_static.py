# -*- coding: utf-8 -*-
"""verify_v17_static.py —— v17 静态复核。退出码即结论。

v17 改了什么（2026-09-11）：
  ① **删掉 v16 的第二关**（`v8_frame_room`「池子还能不能给出一整框」）——
     它要求 23 个**连续**可用砖，而官方图形是碎片化的 ⇒ 池子明明还有空间也判
     「给不出」⇒ 把本来正常的菜单框一起擦掉（用户实测「继续游戏菜单 UI 直接没了」）。
     判据回退为 v14 的「框号槽 == 0 ⇒ 擦」，也就是 ⑤ 自己的判决。
     `v8_frame_room` 本体/声明/`bl` 全部删除（用户纪律：先删上一轮的产物）。
  ② **补上漏掉的第三类消费者：窗口背景砖号 `GetBlankTileNum` @0x080041BC**。
     官方「窗口」在屏上是**两类**：① 框（v12/v14/v15 已接）；② **内容区底色**。
     ② 由 `GetBlankTileNum` 的「空白砖」号填出来，全盘只有 3 个调用点
     （`Text_ClearWindow` ×2 / `Text_BlankWindowRect` / `DoScroll_TextMode0`）。
     该号是**硬编码官号** `win[0x16]`（fontNum∈{1,2,4,5} 再 +212），从不经池子
     ⇒ 池子满后文字不画、底色照画 ⇒ 「文字空、UI 不空」。
     新语义：池子连一个砖都给不出 ⇒ 返回 0 ⇒ 调用方填 0 号砖（官方 erase 约定）。

覆盖：
  A. 注入区 @0x800000 == out/game.bin
  B. 12 个桩（含新增 0x080041BC）逐字节形态（按桩型分派判据）
  C. 桩**以外**的函数体逐字节 == 原盘（含 GetBlankTileNum 桩后本体）
  D. 5 个跳板：解析全部 `ldr` 字面量与 `bl` 目标，逐个核对语义；
     **v14 两个跳板必须已无 `gTplSlot` 读取与 `bl v8_frame_room`**；
     V17 跳板只重放原体后 3 条半字（`push {lr}` 由栈上那份代替）并含续跑点 0x080041C5；
    跳板内 push 只允许 1 次（多一次 = 把垃圾压进原体返回槽 ⇒ 开菜单即重启）
  E. C 符号存在（含 v17_blank_tile_C；不得再有 v8_frame_room）
  F. 注入区不得出现 `mov lr, pc`（fe 46）
  G. 代码区 0x08000000..0x08100000 差分全部归因（含 0x41BC 新桩）
  H. 门控完整性：框号槽的**所有**引用点与预期清单逐一对应
  I. 源码级证据：v8_frame_room 全仓清除；v17 的 lo/纯扫描同源；
     entry.s 无旧门控；game_addrs / hooks_origin 都有 GetBlankTileNum

── 判据设计备忘（前几版脚本栽过，别再踩）─────────────────────────────
1. 桩型分派：头 ∈ {10 b5, 00 b5, 00 4b, 00 4d} 且区间内任一偶偏移有 4 字节 == hook|1
   且区间 != 原盘。
2. **重放段判定要比「解出的语义」**，不比编码字节（`ldr rX,[pc,#imm]` 是 PC 相对的）。
3. 区间起点别压在桩上。
4. **跳板地址一律从 game_syms.asm 读**，不写死（跳板会随 entry.s 变长而移位）。
5. Python 里 `&` 优先级低于 `+`，`((x+4) & ~3) + n` 的括号别省。
"""
import hashlib
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "configs", "POKEMON_RUBY_AXVJ00", "hook")

N = open(os.path.join(ROOT, "roms", "outputs", "POKEMON_RUBY_AXVJ00_translated.gba"), "rb").read()
O = open(os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba"), "rb").read()
GB = open(os.path.join(HOOK, "out", "game.bin"), "rb").read()
MAP = open(os.path.join(HOOK, "out", "game.map"), encoding="utf-8", errors="replace").read()
SYMS = open(os.path.join(HOOK, "out", "game_syms.asm"), encoding="utf-8", errors="replace").read()

SRC_WIN = open(os.path.join(HOOK, "src", "text", "win_alloc.c"), encoding="utf-8").read()
SRC_TILE = open(os.path.join(HOOK, "src", "text", "tile_alloc.c"), encoding="utf-8").read()
SRC_ENTRY = open(os.path.join(HOOK, "src", "text", "entry.s"), encoding="utf-8").read()
SRC_HDR = open(os.path.join(HOOK, "include", "tile_alloc.h"), encoding="utf-8").read()
SRC_ADDR = open(os.path.join(HOOK, "game_addrs.asm"), encoding="utf-8").read()
SRC_STUB = open(os.path.join(HOOK, "src", "text", "hooks_origin.s"), encoding="utf-8").read()

INJ_LO = 0x08800000
INJ_HI = INJ_LO + len(GB)
fails = []


def off(a):
    return a - 0x08000000


def u16(buf, o):
    return struct.unpack_from("<H", buf, o)[0]


def u32(buf, o):
    return struct.unpack_from("<I", buf, o)[0]


def hx(b):
    return " ".join("%02x" % x for x in b)


def chk(label, cond, detail=""):
    print("  %s %s%s" % ("OK " if cond else "FAIL", label, ("  [" + detail + "]") if detail else ""))
    if not cond:
        fails.append(label)


def bl_target(addr, hw1, hw2):
    """Thumb-2 BL(T1)。自证样本：0x088000DC 的 f002 f972 ⇒ 0x088023C4。"""
    s = (hw1 >> 10) & 1
    imm10 = hw1 & 0x3FF
    j1 = (hw2 >> 13) & 1
    j2 = (hw2 >> 11) & 1
    imm11 = hw2 & 0x7FF
    i1 = (~(j1 ^ s)) & 1
    i2 = (~(j2 ^ s)) & 1
    v = (s << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
    if v & (1 << 24):
        v -= (1 << 25)
    return addr + 4 + v


def ldr_abs(addr, hw):
    """`ldr rX,[pc,#imm8]` @addr → 它读的 4 字节的**绝对**地址。括号别省。"""
    return (((addr + 4) & ~3) + ((hw & 0xFF) * 4))


assert bl_target(0x088000DC, 0xF002, 0xF972) == 0x088023C4, "BL 解码器自证失败"
assert ldr_abs(0x08062154, 0x4906) == 0x08062170, "LDR 解码器自证失败(原盘)"

MAPSYM = {}
for line in MAP.splitlines():
    m = re.match(r"^\s+0x([0-9a-fA-F]+)\s+(\S+)\s*$", line)
    if m:
        MAPSYM[m.group(2)] = int(m.group(1), 16)

_sym = {}
for line in SYMS.splitlines():
    p = line.split()
    if len(p) == 3 and p[1] == "equ":
        _sym[p[0]] = int(p[2], 16)
_addrs = sorted(_sym.values())


def H(name):
    """跳板地址：一律从 game_syms.asm 读。"""
    return _sym[name]


def sym_span(name, cap=0x60):
    a = _sym[name]
    nxt = min([x for x in _addrs if x > a], default=a + cap)
    return min(nxt - a, cap)


def sym_addr(name):
    return MAPSYM.get(name)


print("=== A. 注入区 == game.bin ===")
chk("ROM[0x800000..] == out/game.bin  (%d B)" % len(GB), N[0x800000:0x800000 + len(GB)] == GB)

print("\n=== B. 桩形态（按桩型分派）===")
STUB_HEADS = (b"\x10\xb5", b"\x00\xb5", b"\x00\x4b", b"\x00\x4d")
STUBS = [
    (0x08002950, 12, H("V11WinInit_Hook"),      "① TextLoadWindowTemplate     12B尾跳"),
    (0x080029E0,  6, None,                      "③ MultistepLoadFont          原地6B"),
    (0x080028BC, 12, H("V13WinGfx_Hook"),       "◎ WinGfxLoad (v13.1)         12B尾跳"),
    (0x08002C44,  8, H("V13NoteWin_Hook"),      "InitWindow 中部 (v13.2)       8B不碰栈"),
    (0x08062080, 16, H("V10SetFrameBase_Hook"), "⑤ TextWindow_SetBaseTileNum  16B自带返回"),
    (0x08062094, 12, H("V12StdFrame_Hook"),     "⑦ LoadStdFrameGraphics       12B尾跳"),
    (0x08062684, 12, H("V12DlgFrame_Hook"),     "⑧ LoadDlgFrameGraphics       12B尾跳"),
    (0x080620D4,  8, H("V15LoadPal_Hook"),      "v15 OverridePal 门控点        8B不碰栈"),
    (0x0806210C,  8, H("V15LoadStyle_Hook"),    "v15 OverrideStyle 门控点      8B不碰栈"),
    (0x08062154,  8, H("V14StdFrame_Hook"),     "v14 StdFrame tilemap 写入点   8B不碰栈"),
    (0x0806266C,  8, H("V14DlgFrame_Hook"),     "v14 DlgFrame 包装入口         8B不碰栈"),
    (0x080041BC,  8, H("V17BlankTile_Hook"),    "v17 GetBlankTileNum 入口      8B不碰栈"),
]
for a, n, hook, name in STUBS:
    b = N[off(a):off(a) + n]
    if hook is None:
        chk("%-44s %s" % (name, hx(b)), b == bytes.fromhex("10b5012010bd"), hx(b))
        continue
    head_ok = bytes(b[:2]) in STUB_HEADS
    found = [p for p in range(0, n - 3, 2) if u32(b, p) == (hook | 1)]
    patched = b != O[off(a):off(a) + n]
    chk("%-44s %s" % (name, hx(b)), head_ok and bool(found) and patched,
        "head=%s pool@%s patched=%s 期望 %08X" % (head_ok, found, patched, hook | 1))

print("\n=== C. 桩以外逐字节 == 原盘 ===")
TAIL = [
    (0x080041B0, 0x080041BC, "GetBlankTileNum 桩**前**（函数头之前）"),
    (0x080041C4, 0x08004230, "GetBlankTileNum 桩**后**本体（含全部返回路径）"),
    (0x08003BA8, 0x08003C40, "Text_ClearWindow（两个调用点所在）"),
    (0x0806212C, 0x08062154, "⑨b 本体（桩前）"),
    (0x0806215C, 0x08062174, "⑨b 本体（桩后，含 epilogue）"),
    (0x08062674, 0x08062684, "dlg 包装（桩后，从桩尾起）"),
    (0x080625B8, 0x0806266C, "dlg 写入器全文"),
    (0x0800424C, 0x08004268, "0x0800424C/0x08004254（取 tilemap / tileData，未接）"),
    (0x080620A0, 0x080620D4, "⑦ 本体（重放段后）"),
    (0x080620DC, 0x0806210C, "B 本体（桩后）"),
    (0x08062114, 0x0806212C, "C 本体（桩后）"),
    (0x08062694, 0x080626C0, "⑧ 桩后本体"),
    (0x08002C4C, 0x08002C68, "InitWindow 桩后本体"),
    (0x08002C74, 0x08002CB0, "InitTextPrinter 桩后本体"),
]
for lo, hi, name in TAIL:
    chk("%-52s 0x%08X..0x%08X" % (name, lo, hi),
        N[off(lo):off(hi)] == O[off(lo):off(hi)])

def thunk_span(base):
    """从跳板机器码**自推长度**（别写死，也别靠相邻符号推）。

    `V17BlankTile_Hook` 是 `game_syms.asm` 里**最后一个**符号 ⇒ 没有相邻符号
    可推（`sym_span` 会退回 cap，更长、会读进下一个函数）。这里改走机器码：
      1. 逐条扫半字：`BL/BLX`(0xF0xx) 占 4 字节，其余占 2 字节；
         遇到 `pop {...,pc}`(0xBDxx) ⇒ 函数体结束；
      2. 向上对齐到 4；
      3. 每出现一条 `ldr rX,[pc,#imm]`(0x4Bxx) ⇒ `.pool` 里多一个 4 字节字面量。

    🔴 教训：跳板区间**写死**过一次（0x26），结果比真实长度(0x24)多读 2 字节、
       恰好读进下一个函数的 `push` ⇒ 判据误报。
    """
    k, n_pool = 0, 0
    while True:
        hw = u16(GB, base - INJ_LO + k)
        if (hw & 0xF800) == 0xF000:          # BL / BLX：4 字节
            k += 4
            continue
        if (hw & 0xFF00) == 0x4B00:          # ldr rX,[pc,#imm] ⇒ 一个 .pool 字
            n_pool += 1
        if (hw & 0xFF00) == 0xBD00:          # pop {...,pc}：函数最后一条
            k += 2
            break
        k += 2
    return ((k + 3) & ~3) + 4 * n_pool


print("\n=== D. 跳板语义（解析 ldr 字面量 + bl 目标）===")
STD, DLG = H("V14StdFrame_Hook"), H("V14DlgFrame_Hook")
PAL, STY = H("V15LoadPal_Hook"), H("V15LoadStyle_Hook")
BLK = H("V17BlankTile_Hook")
HOOKS = [
    (STD, "V14StdFrame_Hook", 0x03000514, "v14_std_frame_erase_C",
     [0x08062165, 0x0806215D], "⑨b epilogue / ⑨b 续跑点", sym_span("V14StdFrame_Hook")),
    (DLG, "V14DlgFrame_Hook", 0x03000516, "v14_dlg_frame_erase_C",
     [0x131C0E01, 0x08062675], "dlg 矩形 / 包装续跑点", sym_span("V14DlgFrame_Hook")),
    (PAL, "V15LoadPal_Hook", 0x03000514, None,
     [0x080620DD, 0x080620F1], "B 续跑点 / B epilogue", sym_span("V15LoadPal_Hook")),
    (STY, "V15LoadStyle_Hook", 0x03000514, None,
     [0x08062115, 0x08062123], "C 续跑点 / C epilogue", sym_span("V15LoadStyle_Hook")),
    (BLK, "V17BlankTile_Hook", None, None,
     [0x080041C5], "GetBlankTileNum 续跑点 0x080041C4", thunk_span(BLK)),
]
for base, name, slot, erase_sym, must_val, note, span in HOOKS:
    lits, bls = [], []
    for k in range(0, span, 2):
        hw = u16(GB, base - INJ_LO + k)
        if (hw & 0xF800) == 0x4800:
            t = ldr_abs(base + k, hw)
            if INJ_LO <= t < INJ_HI:
                lits.append(u32(GB, t - INJ_LO))
        elif (hw & 0xF800) == 0xF000 and k + 4 <= span:
            hw2 = u16(GB, base - INJ_LO + k + 2)
            if (hw2 & 0xF800) == 0xF800:
                bls.append(bl_target(base + k, hw, hw2))
    print("  --- %s 0x%08X  span=0x%X ---" % (name, base, span))
    print("      ldr 字面量: %s" % " ".join("0x%08X" % x for x in lits))
    print("      bl  目标  : %s" % (" ".join("0x%08X" % x for x in bls) or "（无）"))
    chk("%s 所有 bl 目标在注入区" % name, all(INJ_LO <= t < INJ_HI for t in bls))
    if slot is not None:
        chk("%s 读框号槽 0x%08X" % (name, slot), slot in lits)
    for v in must_val:
        chk("%s 含字面量 0x%08X（%s）" % (name, v, note), v in lits)
    if erase_sym is not None:
        ea = sym_addr(erase_sym)
        chk("%s 含擦除函数 bl %s(0x%08X)" % (name, erase_sym, ea or 0), ea in bls)
    if name.startswith("V14"):
        # v16 的第二关必须彻底消失
        chk("%s **不再**读 gTplSlot(0x03000328)" % name, 0x03000328 not in lits)
        chk("%s **不再** bl v8_frame_room 类判定口（不在符号表里了）" % name,
            sym_addr("v8_frame_room") is None)

print("\n  --- 重放段（语义比对，不比编码；偏移一律从跳板地址算）---")
want = u32(O, off(0x08062170))
got = u32(GB, ldr_abs(STD, u16(GB, STD - INJ_LO)) - INJ_LO)
chk("重放 0x08062154 `ldr r1,=0x03000514`（原盘 06 49 → %08X / 跳板 → %08X）"
    % (want, got), want == got == 0x03000514)
chk("重放 0x08062156 `ldrh r1,[r1]` == 原盘",
    GB[STD - INJ_LO + 2:STD - INJ_LO + 4] == O[off(0x08062156):off(0x08062156) + 2],
    hx(GB[STD - INJ_LO + 2:STD - INJ_LO + 4]))
resume_lits = [k for k in range(0, sym_span("V14StdFrame_Hook"), 2)
               if (u16(GB, STD - INJ_LO + k) & 0xF800) == 0x4800
               and u32(GB, ldr_abs(STD + k, u16(GB, STD - INJ_LO + k)) - INJ_LO) == 0x0806215D]
chk("std 跳板含续跑点字面量 0x0806215D", bool(resume_lits))
if resume_lits:
    rp = resume_lits[0] - 4                 # 续跑点前两条就是 str r4/r5
    chk("重放 0x08062158/5A `str r4,[sp]` / `str r5,[sp,#4]` == 原盘",
        GB[STD - INJ_LO + rp:STD - INJ_LO + rp + 4] == O[off(0x08062158):off(0x08062158) + 4],
        hx(GB[STD - INJ_LO + rp:STD - INJ_LO + rp + 4]))
# v15 跳板：内容未改，重放段固定在 +2/+8/+A（相对跳板起点）
for base, tag in ((PAL, "B 0x080620D4"), (STY, "C 0x0806210C")):
    org0 = 0x080620D4 if base == PAL else 0x0806210C
    for k, org in ((0x02, org0 + 2), (0x08, org0 + 4), (0x0A, org0 + 6)):
        chk("%-16s 重放 +%02X == 原盘 0x%08X" % (tag, k, org),
            GB[base - INJ_LO + k:base - INJ_LO + k + 2] == O[off(org):off(org) + 2],
            hx(GB[base - INJ_LO + k:base - INJ_LO + k + 2]))
seq = O[off(0x0806266C):off(0x0806266C) + 8]
chk("dlg 包装 8 字节重放序列 (%s) 出现在 dlg 跳板内" % hx(seq),
    seq in GB[DLG - INJ_LO:DLG - INJ_LO + sym_span("V14DlgFrame_Hook")])

# v17 跳板：只重放原体的**后 3 条**半字（0x080041BE / C0 / C2）。
# 🔴 第 1 条 `push {lr}` 不许重放：入口 lr 就是调用者返回地址（桩用 bx 不回写 lr），
#    它经 `push {r4,lr}` / `pop {r4}` 后留在栈顶 = 原体那条 push 的等价物。
#    v17 原版在这里多压一次，压进的是 C 调用残留在 lr 的垃圾 ⇒ 原体 pop {pc} 弹垃圾
#    ⇒ 打开开始菜单立刻重启（用户实测）。本判据把它钉死。
BLKSZ = thunk_span(BLK)          # 自推，别写死
blk_bytes = GB[BLK - INJ_LO:BLK - INJ_LO + BLKSZ]
replay3 = O[off(0x080041BE):off(0x080041BE) + 6]
chk("v17 跳板内重放原体后 3 条半字 (%s)" % hx(replay3), replay3 in blk_bytes)
n_push = sum(1 for k in range(0, BLKSZ, 2)
             if (u16(GB, BLK - INJ_LO + k) & 0xFE00) == 0xB400)
chk("v17 跳板 push 只允许 1 次（入口 push {r4,lr}；再多一份就把垃圾压进原体的返回槽）"
    "  [区间 0x%X / 实际 %d]" % (BLKSZ, n_push), n_push == 1)
n_pop = sum(1 for k in range(0, BLKSZ, 2)
            if (u16(GB, BLK - INJ_LO + k) & 0xFE00) == 0xBC00)
chk("v17 跳板 pop 恰好 2 次（pop {r4} 复原现场 + 强制 0 路径 pop {pc} 返回）"
    "  [实际 %d]" % n_pop, n_pop == 2)
chk("v17 跳板含 `bl v17_blank_tile_C`",
    sym_addr("v17_blank_tile_C") is not None and
    sym_addr("v17_blank_tile_C") in
    [bl_target(BLK + k, u16(GB, BLK - INJ_LO + k), u16(GB, BLK - INJ_LO + k + 2))
     for k in range(0, 0x26, 2)
     if (u16(GB, BLK - INJ_LO + k) & 0xF800) == 0xF000
     and (u16(GB, BLK - INJ_LO + k + 2) & 0xF800) == 0xF800])

print("\n=== E. C 符号 ===")
NEED = ["v14_std_frame_erase_C", "v14_dlg_frame_erase_C", "v13_note_win_C",
        "v8_alloc_ui", "v17_blank_tile_C", "v10_pool_lo"]
for sym in NEED:
    chk("game.map 含 %s（0x%08X）" % (sym, sym_addr(sym) or 0), sym in MAP)
chk("game.map **不含** v8_frame_room（v16 产物已删）", "v8_frame_room" not in MAP)
# ⚠ `v8_scan_find` 是 static，GCC 已**全部内联**（game.map 里没有该符号，非缺陷）
chk("v8_scan_find 未进符号表 = 已被 GCC 内联（非缺陷）", "v8_scan_find" not in MAP)

print("\n=== F. 注入区不得出现 mov lr, pc ===")
chk("注入区 fe46 计数 == 0",
    sum(1 for k in range(0, len(GB) - 1, 2) if GB[k:k + 2] == bytes.fromhex("fe46")) == 0)

print("\n=== G. 代码区差分归因（0x08000000..0x08100000）===")
KNOWN = [
    (0x2950, 0x2960, "① 桩"), (0x29E0, 0x29E6, "③ 原地"), (0x28BC, 0x28C8, "◎ 桩"),
    (0x2C28, 0x2C74, "InitTextPrinter/InitWindow 桩区（含 0x2C70 池字）"),
    (0x32F8, 0x3300, "PrintNextChar 桩"),
    (0x41BC, 0x41C4, "**v17 GetBlankTileNum 桩**"),
    (0x41690, 0x41698, "battle 补丁"), (0x41758, 0x41764, "battle Alt1 桩 + 池字 0x41760"),
    (0x425D6, 0x425DE, "battle Alt2 桩"), (0x42620, 0x42624, "battle Alt2 池字"),
    (0x42BCA, 0x42BD2, "battle 主桩"), (0x42C38, 0x42C3C, "battle 主池字"),
    (0x62080, 0x620A0, "⑤/⑦ 桩"), (0x620A0, 0x6212C, "B/C 桩 + 桩间本体"),
    (0x62154, 0x6215C, "v14 std 桩"), (0x6266C, 0x62674, "v14 dlg 桩"),
    (0x62684, 0x62694, "⑧ 桩"),
    (0x77A0, 0x77A8, "start_menu 徽章串"), (0x7924C, 0x79254, "tiles 调色板指针"),
    (0x889F0, 0x889FC, "DrawOptionMenuChoice 桩 + 池字 0x889F8"),
    (0x8AA00, 0x8AA04, "pokedex 补丁"), (0x8AA24, 0x8AA26, "pokedex 序号 0x17→0x16"),
    (0x8AB34, 0x8AB38, "pokedex 补丁"),
    (0x8ABDA, 0x8ABDE, "pokedex 补丁"), (0x8ABFE, 0x8AC04, "pokedex 补丁"),
    (0x8DD60, 0x8DD68, "UnusedPrintMonName 桩"),
    (0x90EF0, 0x90F00, "start_menu 补丁"), (0x90F3C, 0x90F4C, "start_menu 补丁"),
    (0x90FAA, 0x90FB8, "start_menu 补丁"), (0x9F67E, 0x9F68A, "map_name_popup 桩"),
    (0xB0DA4, 0xB0DB8, "player_pc 补丁（含 0xB0DB4 movs r4）"),
    (0x1DA780, 0x1DA790, "start_menu 补丁"),
]
diff = [i for i in range(0, 0x100000) if N[i] != O[i]]
un = [i for i in diff if not any(lo <= i < hi for lo, hi, _ in KNOWN)]
print("  差异字节总数 %d；未归因 %d" % (len(diff), len(un)))
for i in un[:20]:
    print("    ✗ 0x%08X  %02x -> %02x" % (0x08000000 + i, O[i], N[i]))
chk("代码区差异全部归因", not un)

print("\n=== H. 门控完整性：框号槽的**所有**引用点 ===")
SLOTS = {
    0x03000514: ("sTextWindowBaseTileNum",
                 [(0x08062084, "⑤ 写"), (0x0806209C, "⑦ 图形装载 A"),
                  (0x080620D4, "B 图形装载 OverridePal"), (0x0806210C, "C 图形装载 OverrideStyle"),
                  (0x08062154, "⑨b tilemap 写入")]),
    0x03000516: ("sDialogueFrameBaseTileNum",
                 [(0x0806236C, "⑥ 写"), (0x08062380, "文本起点 = 框号+14"),
                  (0x080625E6, "dlg tilemap 写入"), (0x0806268E, "⑧ 图形装载")]),
    0x03000328: ("gTplSlot",
                 [(0x08002960, "① 写"), (0x080029E2, "③（已封）"), (0x08002A08, "字体装载")]),
}
for slot, (name, expect) in SLOTS.items():
    pools = [o for o in range(0, len(O) - 3, 4) if u32(O, o) == slot]
    found = []
    for p in pools:
        for pos in range(max(0, p - 0x100), p, 2):
            hw = u16(O, pos)
            if (hw & 0xF800) == 0x4800 and ldr_abs(0x08000000 + pos, hw) == (0x08000000 + p):
                found.append(0x08000000 + pos)
    got = sorted(set(found))
    exp = sorted(a for a, _ in expect)
    print("  0x%08X %-28s 引用点 %d: %s" % (slot, name, len(got),
          " ".join("0x%08X" % a for a in got)))
    chk("0x%08X 引用点清单与预期一致" % slot, got == exp,
        "缺 %s / 多 %s" % ([hex(a) for a in set(exp) - set(got)],
                          [hex(a) for a in set(got) - set(exp)]))

print("\n=== H2. 背景砖号 GetBlankTileNum 的调用者清单 ===")
blks = []
for pos in range(0, len(O) - 3, 2):
    hw1 = u16(O, pos)
    if (hw1 & 0xF800) != 0xF000:
        continue
    hw2 = u16(O, pos + 2)
    if (hw2 & 0xF800) != 0xF800:
        continue
    if bl_target(0x08000000 + pos, hw1, hw2) == 0x080041BC:
        blks.append(0x08000000 + pos)
print("  bl 0x080041BC 的调用点 %d 个: %s"
      % (len(blks), " ".join("0x%08X" % a for a in sorted(blks))))
chk("GetBlankTileNum 调用点 == 3（Text_ClearWindow ×2 / DoScroll_TextMode0）",
    len(blks) == 3, "实际 %d" % len(blks))
chk("3 个调用点全在 0x08003A00..0x08004200（text.c 原地图）",
    all(0x08003A00 <= a < 0x08004200 for a in blks))

print("\n=== I. 源码级证据 ===")
i0 = SRC_WIN.find("uint16_t v10_pool_lo(void)")
body = SRC_WIN[i0:i0 + 400].split("}")[0]
chk("v10_pool_lo 函数体不含 P_CALLS / P_TEXT（文字专用下限仍是删掉的状态）",
    "P_CALLS" not in body and "P_TEXT" not in body)
chk("v10_pool_lo 恒返 V11_POOL_LO", "return V11_POOL_LO;" in body)
for src, tag in ((SRC_TILE, "tile_alloc.c"), (SRC_HDR, "tile_alloc.h")):
    chk("%s 不再出现 v8_frame_room" % tag, "v8_frame_room" not in src)
# entry.s：只允许在「说明它已删除」的注释里出现，**代码级引用必须为零**
chk("entry.s 无 .extern v8_frame_room", ".extern v8_frame_room" not in SRC_ENTRY)
chk("entry.s 无 `bl v8_frame_room`", SRC_ENTRY.count("bl      v8_frame_room") == 0,
    "count=%d" % SRC_ENTRY.count("bl      v8_frame_room"))
_cmt = sum(1 for ln in SRC_ENTRY.splitlines()
           if "v8_frame_room" in ln and ln.lstrip().startswith("@"))
chk("entry.s 里的 v8_frame_room 只出现在 @ 注释（%d 行）" % _cmt,
    _cmt == SRC_ENTRY.count("v8_frame_room"))
chk("tile_alloc.c 定义 v17_blank_tile_C", "int v17_blank_tile_C(uint8_t *win)" in SRC_TILE)
chk("tile_alloc.h 声明 v17_blank_tile_C", "int v17_blank_tile_C(uint8_t *win);" in SRC_HDR)
chk("tile_alloc.c 仍有纯扫描 v8_scan_find", "static uint16_t v8_scan_find(" in SRC_TILE)
_v17 = SRC_TILE[SRC_TILE.find("int v17_blank_tile_C"):]
_v17 = _v17[:_v17.find("\n}")]
chk("v17 用 lo = v10_pool_lo()（与文字/框同一个 lo）", "lo = v10_pool_lo();" in _v17)
chk("v17 是纯扫描（v8_scan_find(1u …），不取号", "v8_scan_find(1u" in _v17)
chk("entry.s 两个擦除标签都在",
    "StdFrameTmap_Erase:" in SRC_ENTRY and "DlgFrameTmap_Erase:" in SRC_ENTRY)
chk("entry.s 不再有「槽非 0 就直接 resume」的老门控",
    SRC_ENTRY.count("bne     StdFrameTmap_Resume") == 0 and
    SRC_ENTRY.count("bne     DlgFrameTmap_Resume") == 0)
chk("entry.s 定义 V17BlankTile_Hook 且含 BlankTile_ForceZero",
    "V17BlankTile_Hook:" in SRC_ENTRY and "BlankTile_ForceZero:" in SRC_ENTRY)
chk("game_addrs.asm 有 GetBlankTileNum equ 0x080041BC",
    "GetBlankTileNum" in SRC_ADDR and "0x080041BC" in SRC_ADDR)
chk("hooks_origin.s 有 .org GetBlankTileNum",
    ".org GetBlankTileNum" in SRC_STUB and "V17BlankTile_Hook" in SRC_STUB)

print("\n=== 结论 ===")
if fails:
    print("  %d 项失败：" % len(fails))
    for f in fails:
        print("   ✗", f)
    sys.exit(1)
print("  全部通过 ✅   ROM sha1 = %s   game.bin = %d B"
      % (hashlib.sha1(N).hexdigest()[:12], len(GB)))
sys.exit(0)
