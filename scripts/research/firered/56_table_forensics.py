#!/usr/bin/env python3
"""调研(56) 用实测 EWRAM 回答：F7 表在哪、指向什么、有没有解压。

═══════════════════════════════════════════════════════════════════════════
【要正面回答的问题（用户提醒）】
═══════════════════════════════════════════════════════════════════════════
我上一轮说「汉化的汉字 = 原版字符序列拼出来的」。
用户提醒：**别轻易下结论，说不定有解压算法**。

判据设计（不预设结论，让数据说话）：

  H1「拼字符」成立的条件：
     · 存在一张表，项是 ROM 指针
     · 指向的数据**以 0xFF 结尾**
     · 字节分布符合原版单字节字符集（大量落在 0x00-0xDF）
     · 串长合理（1~40）

  H2「有解压」的特征：
     · 指向的数据**没有 0xFF 结尾**，或
     · 高熵（字节值均匀分布、几乎无重复），或
     · 有 RLE/LZ 典型标记（如 0x10/0x30 之类的 header 字节）

  ⚠ 另外必须检查：0x0203F2C0 是不是真的空（(53) 测得全 0）。
    若空，说明我算错了地址，不能拿「表为空」当结论。

用法：python scripts/research/firered/56_table_forensics.py
"""
from __future__ import annotations

import struct
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "ewram3"
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def main() -> int:
    zh = ROM_ZH.read_bytes()
    ja = ROM_JA.read_bytes()
    n = min(len(zh), len(ja))

    snapped = sorted(OUT.glob("s?.ewram.bin"))
    if not snapped:
        print("没有 s?.ewram.bin，先跑 55")
        return 1

    print("=" * 78)
    print("① 先确认 0x0203F2C0 到底是不是空的（验证 (53) 的结论）")
    print("=" * 78)
    for f in snapped:
        ew = f.read_bytes()
        off = 0x0203F2C0 - 0x02000000
        blk = ew[off:off + 0x400]
        nz = sum(1 for b in blk if b != 0)
        print(f"  {f.stem}: 0x0203F2C0 起 1024 B 里非零 {nz}"
              f"  {'（空）' if nz == 0 else ''}")
        if nz:
            vals = [u32(blk, i * 4) for i in range(64)]
            print(f"    前 8 项: {[f'{v:08X}' for v in vals[:8]]}")

    # ── ② 在整个 EWRAM 里找「像指针表」的区域 ─────────────────────
    print("\n" + "=" * 78)
    print("② 全 EWRAM 搜「连续 u32 指向 ROM」的数组（不预设地址）")
    print("=" * 78)
    ew = snapped[-1].read_bytes()
    m = len(ew) // 4 * 4
    pv = np.frombuffer(ew[:m], dtype=np.uint32).astype(np.uint64)
    is_rom = (pv >= BASE) & (pv < BASE + n)
    print(f"  EWRAM 共 {len(pv):,} 个 u32，其中 ROM 指针 {int(is_rom.sum()):,}")

    # 连续 run
    runs = []
    i = 0
    while i < len(is_rom):
        if is_rom[i]:
            j = i
            while j + 1 < len(is_rom) and is_rom[j + 1]:
                j += 1
            if j - i + 1 >= 8:
                runs.append((i * 4, j - i + 1))
            i = j + 1
        else:
            i += 1
    runs.sort(key=lambda x: -x[1])
    print(f"\n  连续 ≥8 个 ROM 指针的 run：{len(runs)} 个，最长的 12 个：")
    print(f"  {'EWRAM 偏移':>12} {'项数':>6} {'首项指向':>12} {'像文本?':>8}")
    for off, cnt in runs[:12]:
        first = int(pv[off // 4]) - BASE
        # 判据：指向的内容以 FF 结尾
        e = ja.find(b"\xff", first, first + 60) if 0 <= first < n else -1
        like = "是" if e > 0 else "否"
        print(f"  0x{0x02000000+off:08X} {cnt:>6} 0x{BASE+first:08X} {like:>8}")

    # ── ③ 对最大的几个 run，验证「指向的是不是 FF 结尾的文本」──────
    print("\n" + "=" * 78)
    print("③ 验证候选表：H1（拼字符） vs H2（有解压）")
    print("=" * 78)
    for off, cnt in runs[:6]:
        print(f"\n  ---- 0x{0x02000000+off:08X}  共 {cnt} 项 ----")
        ok_ff = 0
        lens = []
        samples = []
        for k in range(min(cnt, 200)):
            v = int(pv[off // 4 + k]) - BASE
            if not (0 <= v < n):
                continue
            e = ja.find(b"\xff", v, v + 60)
            if e > 0:
                ok_ff += 1
                L = e - v
                lens.append(L)
                if len(samples) < 8:
                    samples.append((v, L, ja[v:e]))
        tot = min(cnt, 200)
        print(f"    检查 {tot} 项，以 0xFF 结尾 {ok_ff}"
              f"（{ok_ff/max(1,tot)*100:.0f}%）")
        if lens:
            a = np.array(lens)
            print(f"    串长：均值 {a.mean():.1f} 中位 {np.median(a):.0f} "
                  f"最小 {a.min()} 最大 {a.max()}")
            print(f"    样本：")
            for v, L, content in samples:
                # 计算熵，判断是否像压缩数据
                c = Counter(content)
                ent = -sum((x / len(content)) * np.log2(x / len(content))
                           for x in c.values())
                print(f"      0x{BASE+v:08X} L={L:<3} 熵={ent:.2f}  "
                      f"{content.hex(' ')}")
        else:
            print(f"    **没有一条以 0xFF 结尾** ⇒ 指向的不是文本，"
                  f"可能是压缩数据")

    # ── ④ 检查 0x081DB6D8 那个字面量的真实值 ──────────────────────
    print("\n" + "=" * 78)
    print("④ 复核对 0x081DB6D8 / 0x081DB85C 字面量的读取")
    print("=" * 78)
    for lit in (0x081DB6D8, 0x081DB85C):
        v = u32(zh, lit - BASE)
        vo = u32(ja, lit - BASE)
        print(f"  0x{lit:08X}: 汉化=0x{v:08X}  原版=0x{vo:08X}")
        if 0x02000000 <= v < 0x03000000:
            eoff = v - 0x02000000
            blob = ew[eoff:eoff + 64]
            nz = sum(1 for b in blob if b != 0)
            print(f"    → EWRAM+0x{eoff:X} 起 64 B，非零 {nz}")
            print(f"      {blob.hex(' ')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
