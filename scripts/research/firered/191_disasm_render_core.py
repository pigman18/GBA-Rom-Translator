#!/usr/bin/env python3
"""调研(191) 反汇编火红文本渲染核心 0x081DB600..0x081DBA00，提取字库指针。

═══════════════════════════════════════════════════════════════════════════
【为什么锁定这一段】
═══════════════════════════════════════════════════════════════════════════
检查点已确证（来自前几轮反汇编）：
  · 0x081DB630 —— 字宽判定：cmp #160 / bhi→12 / beq→2 / 否则 10
  · 0x081DB660 —— 转码函数（F6 / F7 二分支）
  · 0x081DB800 —— 多 F8 组合转码
  · 字面量 0x081DB6D8 / 0x081DB85C = 0x0203F2C0（EWRAM）

这些函数**都在原版文本区**，说明汉化是**直接改写原版渲染代码**，
而不是新写一套。⇒ 字库指针就在这些函数的 PC 字面量里。

【本脚本做的事（用户指示的「逆推渲染函数」）】
 ① 反汇编 0x081DB580..0x081DBA00（含所有嵌入字面量池）
 ② 抽取每一条 ldr rX,[pc,#imm]，算出实际读取地址与**读到的值**
 ③ 把「读到的值」按类型归类：
      指向 ROM（0x08xxxxxx）→ 可能是字库/字宽表/字符映射表
      指向 EWRAM/IWRAM     → RAM 缓冲
      小整数                → 常量
 ④ 对每个「指向 ROM」的值，dump 目标处 256 字节并做 nibble 画像
 ⑤ 同时对比原版同地址的字节，标出汉化改动点（改了什么逻辑）

【关键输出】
 若某个 ROM 指针指向的区域 nibble 高度集中（4bpp 特征），
 那它就是字库；接着按该指针的用法（stride / 偏移计算）即可还原索引方式。

用法：python scripts/research/firered/191_disasm_render_core.py
"""
from __future__ import annotations

import json
import math
import struct
from collections import Counter
from pathlib import Path

from capstone import (CS_ARCH_ARM, CS_MODE_THUMB, CS_OP_MEM, Cs)

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "render191"
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_OR = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000

LO, HI = 0x081DB580, 0x081DBA00


def nib_profile(rom: bytes, off: int, n: int = 0x100) -> dict:
    seg = rom[off:off + n]
    if len(seg) < n:
        return {}
    c = Counter(seg)
    ent = -sum((k / n) * math.log2(k / n) for k in c.values())
    hi = Counter(b >> 4 for b in seg)
    lo = Counter(b & 0x0F for b in seg)
    hi4 = set(v for v, _ in hi.most_common(4))
    lo4 = set(v for v, _ in lo.most_common(4))
    joint = sum(1 for b in seg
                if (b >> 4) in hi4 and (b & 0x0F) in lo4) / n
    return {"ent": ent, "joint": joint, "nvals": len(c),
            "hi4": sorted(hi4), "lo4": sorted(lo4)}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    zh = ROM_ZH.read_bytes()
    ja = ROM_OR.read_bytes()

    # ── ① 反汇编 ─────────────────────────────────────────
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    md.detail = True
    lines = []
    lits = []
    for ins in md.disasm(zh[LO - BASE:HI - BASE], LO):
        raw = zh[ins.address - BASE:ins.address - BASE + ins.size]
        new = struct.unpack_from("<H", raw)[0] if ins.size == 2 else None
        r_off = ins.address - BASE
        old = (struct.unpack_from("<H", ja, r_off)[0]
               if r_off + 2 <= len(ja) else None)
        changed = (new is not None and old is not None and new != old)
        mark = " *" if changed else ""
        lines.append(f"0x{ins.address:08X}  {raw.hex():<8} "
                     f"{ins.mnemonic:<7} {ins.op_str}{mark}")

        if ins.mnemonic in ("ldr", "ldrb", "ldrh", "adr", "add"):
            for op in ins.operands:
                if op.type == CS_OP_MEM and op.mem.base == 15:
                    tgt = ((ins.address + 4) & ~3) + op.mem.disp
                    val = None
                    if 0 <= tgt - BASE < len(zh) - 4:
                        val = struct.unpack_from("<I", zh, tgt - BASE)[0]
                        oldv = struct.unpack_from("<I", ja, tgt - BASE)[0]
                    else:
                        oldv = None
                    lits.append({"pc": ins.address,
                                 "insn": f"{ins.mnemonic} {ins.op_str}",
                                 "lit_addr": tgt, "value": val,
                                 "orig_value": oldv,
                                 "changed": oldv is not None and val != oldv})

    (OUT / "disasm.txt").write_text("\n".join(lines), encoding="utf-8")
    print("=" * 78)
    print(f"① 反汇编 0x{LO:08X}..0x{HI:08X}  {len(lines)} 条指令")
    print("=" * 78)
    for ln in lines:
        print("  " + ln)

    # ── ② PC 字面量清单 ─────────────────────────────────
    print("\n" + "=" * 78)
    print("② PC 相对字面量（读到的实际值）")
    print("=" * 78)
    print("  指令地址     指令                    字面量地址   值          原版值")
    for L in lits:
        v = L["value"]
        ov = L["orig_value"]
        vs = f"0x{v:08X}" if v is not None else "?"
        os_ = f"0x{ov:08X}" if ov is not None else "?"
        flag = "  ← 汉化改" if L["changed"] else ""
        print(f"  0x{L['pc']:08X}  {L['insn']:<22} 0x{L['lit_addr']:08X}  "
              f"{vs:<12} {os_:<12}{flag}")

    # ── ③ 值归类 ─────────────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 值归类")
    print("=" * 78)
    rom_ptrs, ram_ptrs, smalls = {}, {}, {}
    for L in lits:
        v = L["value"]
        if v is None:
            continue
        if BASE <= v < BASE + len(zh):
            rom_ptrs.setdefault(v, []).append(L)
        elif 0x02000000 <= v < 0x04000000:
            ram_ptrs.setdefault(v, []).append(L)
        elif v < 0x10000:
            smalls.setdefault(v, []).append(L)
    print(f"  指向 ROM  : {len(rom_ptrs)}")
    for v in sorted(rom_ptrs):
        print(f"    0x{v:08X}  被引用 {len(rom_ptrs[v])} 次")
    print(f"  指向 RAM  : {len(ram_ptrs)}")
    for v in sorted(ram_ptrs):
        print(f"    0x{v:08X}  被引用 {len(ram_ptrs[v])} 次")
    print(f"  小常量    : {sorted(smalls)[:25]}")

    # ── ④ ROM 指针目标的内容画像 ──────────────────────────
    print("\n" + "=" * 78)
    print("④ ROM 指针目标的 nibble 画像（字库会有 4bpp 集中特征）")
    print("=" * 78)
    for v in sorted(rom_ptrs):
        off = v - BASE
        p = nib_profile(zh, off)
        if not p:
            continue
        print(f"  0x{v:08X}  joint={p['joint']:.3f} ent={p['ent']:>4.2f} "
              f"值种类={p['nvals']:>3} hi4={[f'{x:X}' for x in p['hi4']]} "
              f"lo4={[f'{x:X}' for x in p['lo4']]}")
        # 前 32 字节
        seg = zh[off:off + 32]
        print(f"      前32B: {seg.hex(' ')}")
        # 与原版比较
        same = sum(1 for a, b in zip(zh[off:off + 64], ja[off:off + 64]) if a == b)
        print(f"      与原版前64B相同字节: {same}/64")

    (OUT / "lits.json").write_text(
        json.dumps({"lits": lits}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"\n已写 {OUT / 'disasm.txt'} / {OUT / 'lits.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
