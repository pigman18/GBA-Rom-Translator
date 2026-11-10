"""成品 ROM 验收（静态字节核对，不启模拟器）。

用法（仓库根）：
    C:\\Python314\\python.exe scripts\\verify_output_rom.py [ROM路径]

默认 ROM：roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba

检查项（全部为 docs/PATCHES_INVENTORY.md 台账的落地验证）：
  1. game.bin @0x08800000 与 hook/out/game.bin 一致；EngineEntry 跳板
  2. P01/P04/P07/P08 订址桩的 bx 目标 == out/game_syms.asm 回填地址 |1
  3. P03 三处血条池 == 0x04000006（原版 0x04000008）
  4. PhraseOffsets u32 单调 / PhraseTable 为 F9 00 流；SLT2 已废弃（仅提示）
  5. 字库 Normal/Small/Sym 非空

退出码 0 = 全通过，1 = 有失败项。
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROM = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"
# 主文件被 mGBA 锁住时流水线会改写 *_translated_new.gba
ALT_ROM = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated_new.gba"
GAME_BIN = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "hook" / "out" / "game.bin"
GAME_SYMS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "hook" / "out" / "game_syms.asm"

ROM_BASE = 0x08000000

# 与 docs/PATCHES_INVENTORY.md 对应：(标签, ROM 地址, game_syms 符号名 or None)
JMP_HOOKS = [
    ("P01 PrintNextChar", 0x080032F8, None),  # P01 用 ldr r1+mov pc，单独判
    ("P04 MapNamePopup", 0x0809F67E, "MapName_DisplayCellLength"),
    ("P07 UnusedPrintMonName", 0x0808DD60, "UnusedPrintMonName_Hook"),
    ("P08 DrawOptionMenuChoice", 0x080889F0, "DrawOptionMenuChoice_Hook"),
    ("P25 InitWindowTileData", 0x08002A50, "InitWindowTileData_Entry"),
]
NICK_POOLS = [("P03 Main", 0x08042C38), ("P03 Alt1", 0x08041760), ("P03 Alt2", 0x08042620)]


def load_syms() -> dict[str, int]:
    syms: dict[str, int] = {}
    if not GAME_SYMS.is_file():
        return syms
    for line in GAME_SYMS.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(";") or " equ " not in line:
            continue
        name, _, val = line.partition(" equ ")
        try:
            syms[name.strip()] = int(val.strip(), 16)
        except ValueError:
            pass
    return syms


def _ink_bbox(blob: bytes, idx: int) -> tuple[int, int] | None:
    """16x16 槽位里第 idx 个字模的墨迹 (宽, 高)；空槽返回 None。

    槽位布局：128B = TL 32B + BL 32B + TR 32B + BR 32B，4bpp。
    **左像素占低 4 位**（lo-first = `*_unshadow` 布局，hook 按此读取）。
    见 scripts/build_chinese_font.py 的 pack_slot16_4bpp(lo_first=...)。
    """
    off = idx * 128
    if off + 128 > len(blob):
        return None
    g = blob[off : off + 128]
    pts: list[tuple[int, int]] = []
    for tcol in range(2):
        for trow in range(2):
            base = (tcol * 2 + trow) * 32
            for ty in range(8):
                for tx in range(4):
                    val = g[base + ty * 4 + tx]
                    # lo-first：偶数像素取低半字节，奇数像素取高半字节
                    for k, nib in enumerate((val & 0xF, val >> 4)):
                        if nib:
                            pts.append((tcol * 8 + tx * 2 + k, trow * 8 + ty))
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return max(xs) - min(xs) + 1, max(ys) - min(ys) + 1


def ldr_literal(rom: bytes, addr: int) -> int | None:
    """找函数头附近的 ldr rX,[pc,#imm]，返回其池中 u32。

    Thumb: PC = (指令地址 + 4) & ~3，再 + imm8*4。
    """
    for i in range(0, 10, 2):
        instr = struct.unpack_from("<H", rom, addr - ROM_BASE + i)[0]
        if (instr & 0xF800) != 0x4800:
            continue
        imm = (instr & 0xFF) * 4
        pc = (addr + i + 4) & ~3
        pool = pc + imm
        return struct.unpack_from("<I", rom, pool - ROM_BASE)[0]
    return None


def _pick_default_rom() -> Path:
    """优先较新的交付物；主盘被模拟器锁住时用 *_translated_new.gba。"""
    cands = [p for p in (DEFAULT_ROM, ALT_ROM) if p.is_file()]
    if not cands:
        return DEFAULT_ROM
    return max(cands, key=lambda p: p.stat().st_mtime)


def main(argv: list[str]) -> int:
    rom_path = Path(argv[1]) if len(argv) > 1 else _pick_default_rom()
    if not rom_path.is_file():
        print(f"ROM 不存在: {rom_path}")
        return 1
    rom = rom_path.read_bytes()
    syms = load_syms()

    results: list[tuple[str, bool, str]] = []

    def chk(label: str, cond: bool, extra: str = "") -> None:
        results.append((label, cond, extra))

    def at(addr: int, n: int) -> bytes:
        return rom[addr - ROM_BASE : addr - ROM_BASE + n]

    print(f"=== 成品 ROM 验收 ===\n{rom_path}\n{len(rom):#x} bytes\n")

    # 1. 引擎嵌入
    if GAME_BIN.is_file():
        gb = GAME_BIN.read_bytes()
        chk("game.bin 与当前源码一致", at(0x08800000, len(gb)) == gb, f"{len(gb)}B")
        # game.bin 前 8 字节 = P01 订址桩：ldr r1,=(EngineEntry|1); bx r1
        # 池中目标必须落在 game.bin 自身范围内（即 EngineEntry 已被重定位到 0x0880xxxx）
        if gb[:2] == b"\x00\x49" and gb[2:4] == b"\x08\x47":
            entry = struct.unpack_from("<I", gb, 4)[0]
            ok = 0x08800000 <= (entry & ~1) < 0x08800000 + len(gb)
            chk("EngineEntry 跳板已重定位", ok, f"-> {entry:#010x}")
        else:
            chk("EngineEntry 跳板已重定位", False, "前 8 字节不是 ldr r1/bx r1 桩")
    else:
        chk("game.bin 存在", False, str(GAME_BIN))

    # P01 特殊：ldr r1,=entry | bx r1
    seg = at(0x080032F8, 8)
    chk("P01 PrintNextChar", seg[0] == 0x00 and seg[1] == 0x49 and seg[3] == 0x47,
        f"ldr r1,[pc]; bx r1  {seg.hex(' ')}")

    # 2. 其余订址桩
    for label, addr, sym in JMP_HOOKS[1:]:
        target = ldr_literal(rom, addr)
        expect = (syms.get(sym, 0) | 1) if sym else None
        ok = target is not None and expect is not None and target == expect
        chk(label, ok, f"bx {target:#010x}" if target else "no ldr found")

    # 3. P03 血条池
    for label, addr in NICK_POOLS:
        val = struct.unpack_from("<I", rom, addr - ROM_BASE)[0]
        chk(label, val == 0x04000006, f"{val:#010x}")

    # 4. 数据区
    po = at(0x08810000, 0x10000)
    offs = [struct.unpack_from("<I", po, i * 4)[0] for i in range(2000)]
    chk("PhraseOffsets 非空", sum(1 for x in po if x) > 1000, f"{sum(1 for x in po if x)} nz")
    chk("  u32 单调", all(offs[i] <= offs[i + 1] for i in range(1999)))
    pt = at(0x08820000, 8)
    chk("PhraseTable F9 00 流", pt[0] == 0xF9 and pt[1] == 0x00, pt.hex(" "))
    # SLT2 于 2026-11-05 彻底移除；缺席不算失败（旧验收口径作废）
    slt2 = at(0x09EA0000, 4)
    results.append(
        (
            "SlotTable SLT2(已废)",
            True,
            "absent(ok)" if slt2 != b"SLT2" else "present(legacy)",
        )
    )

    # 5. 字库（四个槽位；2026-11-02 起 Middle 为独立第 4 套）
    for label, addr, size in [
        ("Font Normal", 0x09000000, 0xE0000),
        ("Font Middle", 0x09320000, 0xE0000),
        ("Font Small", 0x09100000, 0xE0000),
        ("Sym", 0x091E0000, 0x240),
    ]:
        nz = sum(1 for x in at(addr, size) if x)
        chk(label, nz > 0, f"{nz} nz")

    # 5b. 墨迹尺寸众数：允许 11–13 软几何（非硬锁死 12）
    for label, addr, lo, hi in [
        ("Normal ink", 0x09000000, (10, 11), (12, 13)),
        ("Middle ink", 0x09320000, (8, 9), (10, 11)),
        ("Small ink", 0x09100000, (8, 9), (9, 9)),
    ]:
        blob = at(addr, 0xE0000)
        widths: dict[int, int] = {}
        heights: dict[int, int] = {}
        for idx in range(400):
            bb = _ink_bbox(blob, idx)
            if bb:
                widths[bb[0]] = widths.get(bb[0], 0) + 1
                heights[bb[1]] = heights.get(bb[1], 0) + 1
        if not widths:
            chk(label, False, "no glyphs")
            continue
        tw = max(widths.items(), key=lambda kv: kv[1])[0]
        th = max(heights.items(), key=lambda kv: kv[1])[0]
        ok = lo[0] <= tw <= hi[0] and lo[1] <= th <= hi[1]
        chk(label, ok, f"{tw}x{th} (allow {lo[0]}-{hi[0]}x{lo[1]}-{hi[1]})")

    chk("游戏码 AXVJ", rom[0xAC:0xB0] == b"AXVJ")

    # 输出
    failed = 0
    for label, cond, extra in results:
        print(f"  [{'PASS' if cond else 'FAIL'}] {label:32s} {extra}")
        if not cond:
            failed += 1
    print()
    print("=== 全部通过 ===" if failed == 0 else f"!!! {failed} 项失败 !!!")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
