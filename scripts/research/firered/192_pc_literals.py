#!/usr/bin/env python3
"""调研(192) 正确反汇编渲染函数并解析 PC 字面量 —— 找字库指针。

═══════════════════════════════════════════════════════════════════════════
【(191) 的教训】
═══════════════════════════════════════════════════════════════════════════
(191) 反汇编本身成功了（能看到 0x081DB630 / 0x081DB660 的真代码），
但 **PC 字面量提取一个都没出来**：我用 `CS_OP_MEM and op.mem.base == 15`
判断，在 capstone 5 的 Thumb 模式下 `ldr r1,[pc,#0x14]` 的 mem.base
并不是 15，所以全漏。

⇒ 本脚本**不依赖 capstone 的 operand 元数据**，改为直接解析指令字节：
   Thumb `LDR Rd,[PC,#imm8*4]` 编码 = 01001 Rd(3) imm8(8)
   ⇒ 字面量地址 = ((PC + 4) & ~3) + imm8*4
   Thumb-2 `LDR.W Rd,[PC,#±imm12]` 编码 = 1111 1000 11?1 1111 ... imm12
这两个覆盖所有实际出现的 PC 相对加载。

【目标函数】
  0x081DB630  字宽判定（cmp #0xA0 / bhi→12 / beq→2 / else 10）
  0x081DB660  转码主函数（F6/F7 分支，含 0x0203F2C0 字面量）
  0x081DB800  多 F8 组合

【判据】找到的 ROM 指针若指向「nibble 高度集中」的区域 → 字库

用法：python scripts/research/firered/192_pc_literals.py
"""
from __future__ import annotations

import json
import math
import struct
from collections import Counter
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "pclit192"
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_OR = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def decode_pc_lit(rom: bytes, off: int) -> list[dict]:
    """扫描 off 起的一段，手工解出所有「PC 相对加载」。"""
    out = []
    addr = BASE + off
    i = off
    end = len(rom) - 4
    while i < end:
        hw = rom[i] | (rom[i + 1] << 8)
        # ── Thumb: LDR Rd,[PC,#imm8*4] = 01001 Rd(3) imm8(8) ──
        if (hw & 0xF800) == 0x4800:
            rd = (hw >> 8) & 0x07
            imm = (hw & 0xFF) * 4
            tgt = ((addr + 4) & ~3) + imm
            out.append({"pc": addr, "kind": "ldr", "rd": rd,
                        "lit_addr": tgt})
            i += 2
            addr += 2
            continue
        # ── Thumb: ADR Rd, label = 10100 Rd(3) imm8*4 ──
        if (hw & 0xF800) == 0xA000:
            rd = (hw >> 8) & 0x07
            imm = (hw & 0xFF) * 4
            tgt = ((addr + 4) & ~3) + imm
            out.append({"pc": addr, "kind": "adr", "rd": rd,
                        "lit_addr": tgt})
            i += 2
            addr += 2
            continue
        # ── Thumb-2: LDR.W Rd,[PC,#±imm12] ──
        #   1111 1000 U101 1111 | 1111 Rd(4) imm12
        if i + 4 <= end:
            hw2 = rom[i + 2] | (rom[i + 3] << 8)
            if (hw & 0xFF7F) == 0xF85F:
                u = (hw >> 7) & 1
                rd = (hw2 >> 8) & 0x0F
                imm12 = hw2 & 0x0FFF
                tgt = ((addr + 4) & ~3) + (imm12 if u else -imm12)
                out.append({"pc": addr, "kind": "ldr.w", "rd": rd,
                            "lit_addr": tgt})
                i += 4
                addr += 4
                continue
        i += 2
        addr += 2
    return out


def nib_profile(rom: bytes, off: int, n: int = 0x400) -> dict:
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

    for name, lo, hi in (("width_fn", 0x081DB630, 0x081DB660),
                         ("transcode", 0x081DB660, 0x081DB800),
                         ("f8_combo", 0x081DB800, 0x081DB980)):
        off = lo - BASE
        n = hi - lo
        print("\n" + "=" * 78)
        print(f"{name}  0x{lo:08X}..0x{hi:08X}  ({n} B)")
        print("=" * 78)

        # 反汇编
        md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
        for ins in md.disasm(zh[off:off + n], lo):
            raw = zh[ins.address - BASE:ins.address - BASE + ins.size]
            o = struct.unpack_from("<H", ja, ins.address - BASE)[0] \
                if ins.address - BASE + 2 <= len(ja) else None
            newv = struct.unpack_from("<H", raw)[0] if ins.size == 2 else None
            mark = " *" if (newv is not None and o is not None
                            and newv != o) else "  "
            print(f"  0x{ins.address:08X}{mark} {raw.hex():<8} "
                  f"{ins.mnemonic:<8} {ins.op_str}")

        # PC 字面量
        lits = decode_pc_lit(zh, off)[:400]
        print(f"\n  ── PC 相对加载 {len(lits)} 处 ──")
        seen = set()
        for L in lits:
            t = L["lit_addr"]
            if (t, L["kind"]) in seen:
                continue
            seen.add((t, L["kind"]))
            to = t - BASE
            if not (0 <= to < len(zh) - 4):
                continue
            val = struct.unpack_from("<I", zh, to)[0]
            oval = struct.unpack_from("<I", ja, to)[0]
            ch = "  ← 汉化改" if val != oval else ""
            print(f"    0x{L['pc']:08X}  {L['kind']:<6} lit@0x{t:08X}  "
                  f"值=0x{val:08X}  原=0x{oval:08X}{ch}")

    # ── 全 ROM 里所有「指向 nibble 集中区」的 PC 字面量 ──────
    print("\n" + "=" * 78)
    print("全 ROM：PC 字面量指向的地址里，哪些像 4bpp 字模")
    print("=" * 78)
    all_lits = decode_pc_lit(zh, 0)
    print(f"  全 ROM PC 相对加载：{len(all_lits)} 处")
    seen_vals = {}
    for L in all_lits:
        t = L["lit_addr"] - BASE
        if not (0 <= t < len(zh) - 4):
            continue
        val = struct.unpack_from("<I", zh, t)[0]
        if BASE <= val < BASE + len(zh):
            seen_vals.setdefault(val, 0)
            seen_vals[val] += 1

    print(f"  其中指向 ROM 内地址的不同值：{len(seen_vals)}")
    scored = []
    for v, cnt in seen_vals.items():
        o = v - BASE
        p = nib_profile(zh, o, 0x400)
        if not p:
            continue
        if p["joint"] < 0.85 or p["ent"] > 4.2:
            continue
        scored.append({"addr": v, "refs": cnt, **p})
    scored.sort(key=lambda d: (-d["joint"], -d["refs"]))
    print(f"  joint>=0.85 且 ent<=4.2 的：{len(scored)}")
    for s in scored[:40]:
        print(f"    0x{s['addr']:08X}  引用{s['refs']:>3}  "
              f"joint={s['joint']:.3f} ent={s['ent']:>4.2f} "
              f"值种类={s['nvals']:>3} "
              f"hi4={[f'{x:X}' for x in s['hi4']]} "
              f"lo4={[f'{x:X}' for x in s['lo4']]}")

    (OUT / "pclit.json").write_text(
        json.dumps({"rom_ptr_targets": scored[:200]},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写 {OUT / 'pclit.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
