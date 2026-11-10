#!/usr/bin/env python3
"""调研⑰ 纠正⑫的错误，并真正定位火红的宝可梦名表。

═══════════════════════════════════════════════════════════════════════════
【⑫ 错在哪】
═══════════════════════════════════════════════════════════════════════════
⑫ 的判据是「原版假名占比 ≥50% 且汉化含 F7 ≥4」，找到 0x08126300 / 0x08138540
两个 64 字节块，就下结论「火红只改了 2 处名字表」。

**实际上这两处是 Thumb 代码：**

    0x08138540 原版: 12 02 3e 08  58 02 3e 08  ...  ff f7 15 f8 ...
                    └─ u32 指针 ┘                    └── bl 指令 ──┘
    0x08138540 汉化: 68 4b 6d 08  c0 4b 6d 08  ...  ff f7 15 f8 ...

  · `FF F7 xx F8` 是 Thumb 的 `bl`（长跳转），不是 F7 文本前缀
  · 原版那两个 u32 是 0x083E0212 / 0x083E0258，汉化改成了 0x086D4B68 / 0x086D4BC0
    —— 这是**代码里的字面量池被改指到新区**，属于「改指针」而非「改名字表」
  · 「原版假名占比高」判据被 Thumb 编码污染（Thumb 里 0x01–0x1F 极常见）

⇒ **⑫ 的结论作废。宝可梦名到底怎么处理，目前**未查明**。

═══════════════════════════════════════════════════════════════════════════
【本脚本：用结构特征直接找名字表】
═══════════════════════════════════════════════════════════════════════════
Gen3 名字表铁特征（与编码无关）：
  · 火红 412 个 species 槽位
  · 每项 11 字节（POKEMON_NAME_LENGTH=10 + 终止符）
  · 名字不足 10 字 → **尾部补 0xFF**，所以每一项的**最后一字节必然是 0xFF**

⇒ 扫描「步长 11、连续 412 项末字节都是 0xFF」的位置。
   这个判据与字符编码完全无关，原版/汉化都能用。

关键判别：若汉化版**同一位置仍是完整的 412×11 表**，说明名字没被改成 F7
⇒ 印证「不改存档结构」；若表被撑破，说明名字被就地汉化了。

用法：python scripts/research/firered/17_species_names.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"

BASE = 0x08000000
NUM_SPECIES = 412
REC = 11          # POKEMON_NAME_LENGTH(10) + 1


def find_table(rom: bytes, need: int = 380) -> list[tuple[int, int]]:
    """扫描满足「步长 REC、连续 NUM_SPECIES 项末字节=0xFF」的起点。"""
    hits = []
    limit = len(rom) - NUM_SPECIES * REC
    for o in range(0, limit):
        if rom[o + REC - 1] != 0xFF:
            continue
        ok = 0
        for k in range(1, NUM_SPECIES):
            if rom[o + k * REC + REC - 1] == 0xFF:
                ok += 1
                if ok >= need:
                    break
            else:
                # 早期失败就跳出，省时间
                if k < 40:
                    break
        else:
            if ok >= need:
                hits.append((o, ok))
        if ok >= need:
            hits.append((o, ok))
    return hits


def decode_gen3_jp(b: bytes) -> str:
    """粗解：把 0xA1–0xDF 当假名占位，其他显示为 <xx>。仅供肉眼判断是不是名字表。"""
    out = []
    for x in b:
        if x == 0xFF:
            break
        if 0xA1 <= x <= 0xDF:
            out.append(chr(0x3041 + (x - 0xA1)))   # 粗略：平假名序列
        else:
            out.append(f"<{x:02X}>")
    return "".join(out)


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()

    print("=" * 74)
    print("找火红宝可梦名表（结构判据，与字符编码无关）")
    print(f"步长 {REC}，species {NUM_SPECIES}，要求 ≥380 项末字节为 0xFF")
    print("=" * 74)

    for rom, name in ((ja, "原版 BPRJ"), (zh, "汉化 2.2")):
        print(f"\n--- {name} ---")
        hits = find_table(rom)
        print(f"  命中起点 {len(hits)} 个")
        for o, ok in hits[:8]:
            print(f"    ROM 0x{BASE+o:08X}  匹配 {ok}/{NUM_SPECIES-1}")

        if hits:
            o = hits[0][0]
            print(f"\n  首个命中的前 12 项（原样 hex + 粗解）：")
            for k in range(12):
                rec = rom[o + k * REC: o + (k + 1) * REC]
                print(f"    [{k:>3}] {rec.hex(' ')}  {decode_gen3_jp(rec)}")

    # 对比：同一位置两版是否一致
    hits_ja = find_table(ja)
    if hits_ja:
        o = hits_ja[0][0]
        a = ja[o:o + NUM_SPECIES * REC]
        b = zh[o:o + NUM_SPECIES * REC]
        diff = sum(1 for x, y in zip(a, b) if x != y)
        print("\n" + "=" * 74)
        print(f"两版在 0x{BASE+o:08X} 的 {len(a)} 字节对比：")
        print(f"  不同字节 {diff:,}（{diff/len(a)*100:.2f}%）")
        if diff == 0:
            print("  ⇒ **完全一致：宝可梦名没有被汉化改动**")
            print("  ⇒ 存档里仍是原版字符集 ⇒ 串档不乱，与用户描述一致")
        else:
            print("  ⇒ 有改动，需要进一步看改了什么")
            # 找第一处不同
            for i in range(len(a)):
                if a[i] != b[i]:
                    print(f"    首个差异 @+{i}（第 {i//REC} 项 第 {i%REC} 字节）")
                    print(f"      原版 {a[max(0,i-8):i+16].hex(' ')}")
                    print(f"      汉化 {b[max(0,i-8):i+16].hex(' ')}")
                    break

    # 检查汉化版是否还有 F7 出现在名字表区域
    if hits_ja:
        o = hits_ja[0][0]
        seg = zh[o:o + NUM_SPECIES * REC]
        n_f7 = seg.count(0xF7)
        print(f"\n  汉化版该区域内 F7 字节数：{n_f7}")
        print(f"  ⇒ {'名字表未被 F7 化' if n_f7 < 20 else '名字表含大量 F7，可能被就地汉化'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
