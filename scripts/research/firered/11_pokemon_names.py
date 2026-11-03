#!/usr/bin/env python3
"""调研⑪ 火红怎么做到「宝可梦名串档不乱」。

═══════════════════════════════════════════════════════════════════════════
【用户的原话】
═══════════════════════════════════════════════════════════════════════════
「一些旧日版汉化版，和常规日版串档时，会出现宝可梦名乱码问题，
  因为它们是宝可梦那块写入了汉化内容，导致存档也乱了，
  因此引入 slt2 不改变原本编码，从而实现汉化宝可梦名查看」

⇒ 我们的红宝石工程用 `slt2` 实时替换表来规避这个问题。
用户现在想知道：**火红是怎么解决的？**（它不用 slt2 吗？）

═══════════════════════════════════════════════════════════════════════════
【背景知识：为什么宝可梦名会「串档乱」】
═══════════════════════════════════════════════════════════════════════════
Gen3 的宝可梦昵称存在存档里，**用游戏内字符集编码**（10 字节定长）。
如果汉化把「宝可梦名字符集」改成 F7 编码：
  · 新存档里存的是 F7 xx xx 序列
  · 拿到**原版**或**日语版**游戏里读 → 那些字节被当成日文假名 → 乱码
  · 反之，原版存档拿到汉化版读 → 原名是单字节假名，汉化版若只认 F7 也会乱

═══════════════════════════════════════════════════════════════════════════
【本轮方法：查火红有没有改「宝可梦名字符集」】
═══════════════════════════════════════════════════════════════════════════
关键观察点：**宝可梦名是 10 字节定长**（0x0A），存在存档里。

如果火红**没改**字符集，那 ROM 里的宝可梦名数据（原版自带的
「フシギダネ」等日文名表）应该**原样保留**。
如果**改了**，那张表会变成 F7 编码。

做法：在 ROM 里找宝可梦名表（原版是连续日文假名的定长表），
对比两版是否一致。

用法：python scripts/research/firered/11_pokemon_names.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"

# Gen3 日文字符集：0x01-0x1F 假名/数字，0x40-0x5A 拉丁
def is_jp_text(b: int) -> bool:
    return 1 <= b <= 0x5A


def find_name_tables(rom: bytes, entry: int, count: int, min_hits: int = 20):
    """找「entry 字节定长、每项都是日文字符 + 结尾 FF/00」的连续表。"""
    out = []
    for o in range(0, len(rom) - entry * count, 4):
        ok = 0
        for k in range(count):
            base = o + k * entry
            blk = rom[base:base + entry]
            # 至少第一个字节是可打印日文，且不含明显的非文本
            if blk and is_jp_text(blk[0]) and blk[0] != 0xFF:
                # 后面应是字符 + 0xFF 填充
                txt = 0
                for b in blk:
                    if b == 0xFF or b == 0x00:
                        break
                    if is_jp_text(b):
                        txt += 1
                if txt >= 1:
                    ok += 1
        if ok >= count:
            out.append(o)
    return out


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()

    # Gen3 宝可梦名 10 字节定长（POKEMON_NAME_LENGTH）
    # 火红有 412 个 species slot，这里先用 20 项 × 10 字节做探针
    print("=== 找「10 字节定长的日文名表」（原版火红）===")
    hits_ja = find_name_tables(ja, 10, 20)
    print(f"  找到 {len(hits_ja)} 处候选")
    for o in hits_ja[:6]:
        seg = ja[o:o + 10 * 5]
        print(f"    @0x{0x08000000+o:08X}: " + seg.hex(" "))

    print("\n=== 同样位置在汉化版是什么 ===")
    for o in hits_ja[:6]:
        a = ja[o:o + 10 * 5]
        b = zh[o:o + 10 * 5]
        same = "相同" if a == b else "**不同**"
        print(f"    @0x{0x08000000+o:08X}  {same}")
        if a != b:
            print(f"      原版: {a.hex(' ')}")
            print(f"      汉化: {b.hex(' ')}")

    # 统计：汉化版里还有多少「纯日文定长表」
    print("\n=== 汉化版里残留的「10 字节定长日文表」===")
    hits_zh = find_name_tables(zh, 10, 20)
    print(f"  找到 {len(hits_zh)} 处")
    print(f"  原版有 {len(hits_ja)} 处，汉化 {len(hits_zh)} 处")
    if len(hits_zh) >= len(hits_ja) * 0.8:
        print("  ⇒ 大部分日文名表**原样保留** ⇒ 火红**没有**改宝可梦名字符集")
        print("     这解释了为什么火红串档不乱：原名还是原版编码，")
        print("     汉化只在**显示时**做映射（类似 slt2，但不改存档数据）")
    else:
        print("  ⇒ 日文表被大量替换 ⇒ 火红改了宝可梦名数据")

    print("\n=== 判读要点 ===")
    print("  · 若原版表原样保留 ⇒ 火红走的是「存档数据不动、显示时映射」")
    print("  · 这和我们红宝石工程的 slt2 思路一致")
    print("  · 若表被 F7 化 ⇒ 火红接受「串档乱」，只保证单版本可读")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
