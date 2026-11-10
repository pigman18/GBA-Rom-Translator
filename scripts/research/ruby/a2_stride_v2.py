#!/usr/bin/env python3
"""按火红做法重写：stride 改动的正确算法。

用户判断（2026-11-04，已由火红实测验证）：
  「火红那边是怎么做的？我的理解应该是按原本的结构等长或等距改好，
    再改一个常量，旧的长或距应该能直接从编码里推算出来的吧」

火红实测结论（firered_stride_all.py）：
  - 招式名表 28 个共同站点，**16 处净移位 +1**（stride 8→16）
  - 形态多样但改动规律一致：就是那个「2 的幂因子」+1
  - 一处不漏

关键洞察（最重要）：
  **不需要猜「哪条指令是 stride 乘法」**。
  因为 stride = A × 2^shift，其中 A 是前面的加/减组合。
  
  对每个站点，只要：
    1. 收集 ldr 前所有移位指令（lsls / lsrs）
    2. 算净移位 net
    3. 找满足 old_stride % (1 << net) == 0 的 net
    4. 把「最后一条贡献该 2 的幂因子的移位指令」的立即数 +delta

  **旧 stride 从 net 推算，新 stride = old × 2^delta。**

  这样就不需要理解 A 是什么（i*4+i 还是 i*8-i），只要 net 对得上。

用法：
    python scripts/research/ruby/a2_stride_v2.py
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

for _s in (sys.path[:], sys.stderr):
    try:
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
GBA_BASE = 0x08000000

TABLES = [
    ("招式名",         0x1CACFC, 8,  16, 40),
    ("特性名",         0x1CBC44, 8,  16, 3),
    ("属性名",         0x1CBB0C, 5,  10, 3),
    ("道具名",         0x39A648, 40, 80, 14),
    ("图鉴分类名",     0x38474C, 28, 56, 5),
    ("秘密基地装饰名", 0x3C2A44, 28, 56, 22),
]


def decode_shift_insns(rom: bytes, ldr: int, back: int = 20) -> list[dict]:
    """收集 ldr 前的所有移位指令，返回 [{off, mn, rd, rs, imm}]。"""
    out = []
    lo = max(0, ldr - back)
    for off in range(lo, ldr, 2):
        if off + 2 > len(rom):
            continue
        hw = struct.unpack_from("<H", rom, off)[0]
        mn = None
        if (hw & 0xF800) == 0x0000:
            mn = "lsls"
        elif (hw & 0xF800) == 0x0800:
            mn = "lsrs"
        elif (hw & 0xF800) == 0x1000:
            mn = "asrs"
        else:
            continue
        imm = (hw >> 6) & 0x1F
        rs = (hw >> 3) & 0x07
        rd = hw & 0x07
        if imm == 0:
            continue
        out.append({"off": off, "mn": mn, "rd": rd, "rs": rs, "imm": imm})
    return out


def net_shift(insns: list[dict]) -> int:
    """整段移位指令的净效果（简化：全部累加）。"""
    n = 0
    for i in insns:
        n += i["imm"] if i["mn"] == "lsls" else -i["imm"]
    return n


def find_stride_site(rom: bytes, ldr: int, old_stride: int) -> dict | None:
    """找决定 stride 的那条移位指令。

    判据（用户思路 + 火红验证）：
      stride = A × 2^net，A 未知但 net 可算。
      找一段移位指令，使 old_stride % (1 << net) == 0，
      且 net 尽量大（因为 2 的幂因子越大，说明找到的越准确）。
    """
    insns = decode_shift_insns(rom, ldr)
    if not insns:
        return None

    # 尝试所有前缀（从最靠近 ldr 往前），找满足整除的最大 net
    best = None
    for k in range(1, len(insns) + 1):
        subset = insns[-k:]          # 靠近 ldr 的 k 条
        net = net_shift(subset)
        if net <= 0:
            continue
        if old_stride % (1 << net) != 0:
            continue
        # 记录
        last = subset[-1]            # 最靠近 ldr 的那条（收尾缩放）
        cand = {
            "insn_off": last["off"], "mn": last["mn"],
            "rd": last["rd"], "rs": last["rs"], "imm": last["imm"],
            "net": net, "ldr": ldr, "subset": subset,
        }
        if best is None or net > best["net"]:
            best = cand
    return best


def list_ldrs_for_table(rom: bytes, base: int) -> list[int]:
    """找一张表的全部 ldr 站点。"""
    gba = base + GBA_BASE
    needle = struct.pack("<I", gba)
    lits, s = [], 0
    while True:
        i = rom.find(needle, s)
        if i < 0:
            break
        if i % 4 == 0:
            lits.append(i)
        s = i + 1

    ldrs = []
    for lit in lits:
        for off in range(max(0, lit - 4096), lit, 2):
            hw = struct.unpack_from("<H", rom, off)[0]
            if (hw & 0xF800) != 0x4800:
                continue
            imm = (hw & 0xFF) * 4
            if ((off + 4) & ~3) + imm == lit:
                ldrs.append(off)
                break
    return ldrs


def main() -> int:
    rom = ROM.read_bytes()

    print("=" * 80)
    print("=== 按火红做法：stride = A × 2^net，改 net 即可 ===")
    print("=" * 80)
    print()

    total_expect = total_found = 0
    all_ok = True

    for name, base, old_s, new_s, expect in TABLES:
        ldrs = list_ldrs_for_table(rom, base)
        ratio = new_s // old_s
        if ratio <= 0 or (ratio & (ratio - 1)) != 0:
            print(f"--- {name}: new/old = {ratio} 不是 2 的幂，跳过 ---")
            continue
        delta = ratio.bit_length() - 1

        print(f"--- {name}  base=0x{base:06X}  stride {old_s}→{new_s} "
              f"(×{ratio}, net +{delta}) ---")
        print(f"    ldr 站点 {len(ldrs)}")

        found = []
        missing = []
        for ldr in ldrs:
            site = find_stride_site(rom, ldr, old_s)
            if site is None:
                missing.append(ldr)
            else:
                found.append((ldr, site))

        total_expect += len(ldrs)
        total_found += len(found)
        if missing:
            all_ok = False

        print(f"    识别 {len(found)}/{len(ldrs)}"
              + ("" if not missing else f"  漏 {len(missing)}"))
        for ldr in missing[:5]:
            print(f"      ❌ 0x{ldr:06X} 找不到净移位")

        # 展示识别出的 net 分布
        if found:
            from collections import Counter
            nets = Counter(s["net"] for _l, s in found)
            print(f"    net 分布: {dict(nets)}")
        print()

    print("=" * 80)
    print(f"总计：{total_found}/{total_expect} 站点识别成功")
    if all_ok:
        print("✅ 全部识别，可以生成 patch")
    else:
        print("⚠️ 仍有遗漏")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
