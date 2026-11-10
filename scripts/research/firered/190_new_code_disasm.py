#!/usr/bin/env python3
"""调研(190) 定位汉化**新增的代码**，反汇编它如何取用字库。

═══════════════════════════════════════════════════════════════════════════
【方法转向（用户的直接指示）】
═══════════════════════════════════════════════════════════════════════════
用户指出：字库写入 ROM 时经过了**混淆/拆分**，拿渲染结果反向匹配必然找不到；
正确做法是**逆推渲染函数**，看它如何应用字库，从而反推算法，
甚至直接用这个过程生成整张字库 PNG。

【本脚本的第 1 步：把「汉化新增的代码」找全】
判据：原版该 4 字节是 0xFFFFFFFF（空区），汉化非 FF，且内容**像 Thumb 代码**。
"像 Thumb 代码"的可验证判据（不靠猜）：
  C1 该位置按 2 字节对齐
  C2 前 N 条指令用 capstone 反汇编**无 invalid**
  C3 出现至少 2 条「bl / b / ldr / push / ldm」之一

然后在这些新增代码段里搜两类关键指令：
  K1 **ldr rX,[pc,#imm]** → 后面跟 PC 相对常量
     若常量落在 ROM 区（0x08xxxxxx）= 字库表指针
     若常量落在 0x02000000/0x03000000 = RAM 缓冲
  K2 **ldr rX,[rY,#imm]** / **ldrb** 配合 shift → 位运算取位
  K3 与 DMA（0x040000D4）或 VRAM（0x06000000）有关的常量

【为什么这一步能定位字库】
渲染函数必须：(a) 算出某字的地址，(b) 读位图，(c) 写 VRAM。
(b) 的地址来源一定出现在它的 ldr 常量里 —— 那就是字库基址。

用法：python scripts/research/firered/190_new_code_disasm.py
"""
from __future__ import annotations

import json
import struct
import subprocess
from pathlib import Path

from capstone import (CS_ARCH_ARM, CS_MODE_THUMB, CS_OP_IMM, CS_OP_MEM,
                      CS_OP_REG, Cs)

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "newcode190"
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_OR = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000
FILL = 0xFF


def is_code_like(rom: bytes, off: int, n: int = 24) -> tuple[bool, list]:
    """用 capstone 判断 off 处是否像 Thumb 代码。"""
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    md.detail = True
    got = []
    for ins in md.disasm(rom[off:off + n * 2], BASE + off):
        got.append(ins)
        if len(got) >= n:
            break
    if len(got) < 6:
        return False, got
    invalid = sum(1 for i in got if i.mnemonic.startswith("invalid"))
    if invalid > len(got) * 0.2:
        return False, got
    key = sum(1 for i in got
              if i.mnemonic in ("bl", "b", "bx", "push", "pop", "ldm", "stm",
                                "ldr", "ldrb", "ldrh", "str", "mov", "adds",
                                "subs", "cmp"))
    return key >= 5, got


def find_pc_literals(rom: bytes, off: int, count: int = 64) -> list[dict]:
    """反汇编并收集 PC 相对常量（ldr rX,[pc,#imm]）。"""
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    md.detail = True
    out = []
    for ins in md.disasm(rom[off:off + count * 2], BASE + off):
        if ins.mnemonic not in ("ldr", "ldrb", "ldrh", "adr", "add"):
            continue
        for op in ins.operands:
            if op.type == CS_OP_MEM and op.mem.base == 15:  # pc
                # PC 在 Thumb 下是当前指令 +4，且按 4 对齐
                target = ((ins.address + 4) & ~3) + op.mem.disp
                if 0 <= target - BASE < len(rom) - 4:
                    val = struct.unpack_from("<I", rom, target - BASE)[0]
                else:
                    val = None
                out.append({"pc": ins.address, "insn": f"{ins.mnemonic} "
                            f"{ins.op_str}", "addr": target, "value": val})
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    zh = ROM_ZH.read_bytes()
    ja = ROM_OR.read_bytes()
    N = len(zh)
    print(f"ROM {N:,} B")

    # ── ① 找「原版 FF、汉化非 FF」的连续区段 ──────────────
    print("\n" + "=" * 78)
    print("① 原版填充区里被汉化写入的连续段")
    print("=" * 78)
    segs = []
    off = 0
    while off < N:
        if not (ja[off] == FILL and zh[off] != FILL):
            off += 1
            continue
        s = off
        e = off
        gap = 0
        while e < N:
            if ja[e] == FILL and zh[e] != FILL:
                e += 1
                gap = 0
            elif zh[e] == FILL:
                break
            else:
                gap += 1
                if gap > 32:
                    break
                e += 1
        if e - s >= 64:
            segs.append((s, e))
        off = e + 1
    segs.sort(key=lambda t: -(t[1] - t[0]))
    print(f"  连续段（>=64B）{len(segs)} 个，最大 20：")
    for s, e in segs[:20]:
        print(f"    0x{BASE+s:08X}..0x{BASE+e:08X}  {e-s:>7,} B")

    # ── ② 在每段内找像代码的窗口 ────────────────────────
    print("\n" + "=" * 78)
    print("② 各段内「像 Thumb 代码」的位置")
    print("=" * 78)
    code_sites = []
    for s, e in segs:
        for o in range(s, min(e - 48, s + 0x20000), 2):
            ok, ins = is_code_like(zh, o, 16)
            if ok:
                code_sites.append({"off": o, "addr": BASE + o,
                                   "n_ins": len(ins),
                                   "head": [f"{i.mnemonic} {i.op_str}"
                                            for i in ins[:6]]})
                break   # 每段只取第一个
    print(f"  找到 {len(code_sites)} 个代码起点")
    for c in code_sites[:30]:
        print(f"    0x{c['addr']:08X}  {' | '.join(c['head'][:4])}")

    # ── ③ 对所有代码区收集 PC 常量，找字库指针 ─────────────
    print("\n" + "=" * 78)
    print("③ 代码区的 PC 相对常量（找指向 ROM 数据的指针）")
    print("=" * 78)
    ptr_hits: dict[int, list] = {}
    for c in code_sites:
        lits = find_pc_literals(zh, c["off"], 160)
        for L in lits:
            v = L["value"]
            if v is None:
                continue
            if BASE <= v < BASE + N:
                ptr_hits.setdefault(v, []).append(
                    {"from": c["addr"], "insn": L["insn"]})

    print(f"  指向 ROM 的常量共 {len(ptr_hits)} 个不同地址")
    # 按指向区域归类
    zones: dict[str, int] = {}
    for v in ptr_hits:
        z = f"0x{v >> 16 << 16:08X}"
        zones[z] = zones.get(z, 0) + 1
    print("  按 64KB 区归类（Top 20）：")
    for z, n in sorted(zones.items(), key=lambda kv: -kv[1])[:20]:
        print(f"    {z}  {n} 个指针")

    # ── ④ 这些指针指向的内容，像不像 4bpp 字模 ─────────────
    print("\n" + "=" * 78)
    print("④ 被引用地址的内容特征（是否 4bpp 集中的 nibble）")
    print("=" * 78)
    import math
    from collections import Counter

    def nib_profile(off: int, n: int = 0x200) -> dict:
        seg = zh[off:off + n]
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

    scored = []
    for v, refs in ptr_hits.items():
        off = v - BASE
        if off < 0 or off + 0x200 > N:
            continue
        p = nib_profile(off)
        if not p:
            continue
        # 字模特征：joint 高、值种类少、熵低
        score = p["joint"] * 2 - abs(p["ent"] - 2.0) * 0.3
        scored.append({"addr": v, "refs": len(refs), **p, "score": score})
    scored.sort(key=lambda d: -d["score"])
    print(f"  评分数靠前的 25 个：")
    for s in scored[:25]:
        print(f"    0x{s['addr']:08X}  引用{s['refs']:>2}次  "
              f"joint={s['joint']:.2f} ent={s['ent']:>4.1f} "
              f"值种类={s['nvals']:>3}  hi4={[f'{v:X}' for v in s['hi4']]} "
              f"lo4={[f'{v: X}' if False else f'{v:X}' for v in s['lo4']]}")

    (OUT / "newcode.json").write_text(
        json.dumps({"segs": segs[:200], "code_sites": code_sites,
                    "ptr_zones": zones,
                    "top_ptr_targets": scored[:120]},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写 {OUT / 'newcode.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
