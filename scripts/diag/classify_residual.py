"""把 write.plan 里「没写进 ROM 的条目」按**数据结构形态**分类。

用法（仓库根）：
    python scripts/diag/classify_residual.py

回答的问题只有一个：每条剩余日文，是**哪一种数据形态**挡住了写入。
不是「unresolved = 不知道」，而是给出可执行的处理路径。

分类（按优先级）：

    pool    池成员：往前 0x200 内能找到**被引用的基址**，且中间字节全是
            文本字节（0x01..0xFE 或 0xFF）→ 整池搬迁即可，长度自由
    stride  定长表成员：存在 stride s，使 addr-s 与 addr+s 都是串首
            → 建 stride 表模块，扩步长
    struct  结构体内联：基址被引用，但中间夹着非文本字节
            → 名槽改指针（name_ptr / name_ptr_fold）
    orphan  全 ROM 找不到任何引用（u32 / u24 都没有）→ 死数据或压缩区
    bad     地址不在 ROM 内

只读，不写任何文件。
"""
from __future__ import annotations

import collections
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
GBA = 0x08000000


def is_text_byte(b: int) -> bool:
    return b == 0xFF or 0x01 <= b <= 0xFE


def main() -> int:
    rom = ROM.read_bytes()
    data = json.loads(BUILD.read_text(encoding="utf-8"))
    entries = data.get("entries") or []
    residual = [
        e for e in entries
        if e.get("type") == "skip"
        and (e.get("translated") or "").strip()
        and (e.get("translated") or "").strip() != (e.get("original") or "").strip()
    ]

    ref_cache: dict[int, int] = {}

    def nref(gba: int) -> int:
        if gba in ref_cache:
            return ref_cache[gba]
        pat = struct.pack("<I", gba)
        n = 0
        s = 0
        while True:
            i = rom.find(pat, s)
            if i < 0:
                break
            n += 1
            s = i + 1
        ref_cache[gba] = n
        return n

    def u24(gba: int) -> int:
        pat = (gba & 0xFFFFFF).to_bytes(3, "little")
        n = 0
        s = 0
        while True:
            i = rom.find(pat, s)
            if i < 0:
                break
            n += 1
            s = i + 1
        return n

    def is_start(gba: int) -> bool:
        off = gba - GBA
        if off < 0 or off >= len(rom):
            return False
        if off + 1 >= len(rom):
            return False
        prev = rom[off - 1] if off else 0xFF
        if prev not in (0x00, 0xFF):
            return False
        return any(b == 0xFF for b in rom[off:off + 128])

    def find_pool_head(gba: int) -> int | None:
        """往前找被引用、且与当前位置之间全是文本字节的基址。"""
        for back in range(4, 0x201, 2):
            b = gba - back
            if b < GBA:
                break
            if any(not is_text_byte(x) for x in rom[b - GBA:gba - GBA]):
                break
            if nref(b):
                return b
        return None

    def find_stride(gba: int) -> int | None:
        """定长表成员：槽里有**填充**（串的 FF 早于槽尾），不是紧邻拼接。

        只看「addr±s 也是串首」会命中对话 bank —— 那里串与串紧挨着，
        ``addr+s`` 天然是下一条串首，会把「无指针的死对话」误报成定长表。
        真定长表的特征是**槽内留白**：``start + 串长 < start + s``。
        """
        o = gba - GBA
        if o <= 0 or o >= len(rom):
            return None
        for s in (4, 5, 6, 7, 8, 10, 11, 12, 14, 16, 20, 24, 28, 32, 40, 48, 56, 64):
            end = rom.find(b"\xff", o, min(o + s + 1, len(rom)))
            if end < 0 or end - o + 1 >= s:
                continue
            if is_start(gba + s) and is_start(gba - s):
                return s
        return None

    rows: list[tuple[str, dict, str]] = []
    for e in residual:
        try:
            gba = int(str(e.get("address")), 16)
        except (TypeError, ValueError):
            rows.append(("bad", e, "地址无法解析"))
            continue
        if not (GBA <= gba < GBA + len(rom)):
            rows.append(("bad", e, "地址越界"))
            continue
        if nref(gba):
            rows.append(("ptr", e, f"u32 引用 {nref(gba)}"))
            continue
        head = find_pool_head(gba)
        if head is not None:
            rows.append(("pool", e, f"池头 0x{head:08X} +{gba - head}"))
            continue
        st = find_stride(gba)
        if st is not None:
            rows.append(("stride", e, f"stride {st}"))
            continue
        if u24(gba):
            rows.append(("struct", e, "仅 u24 引用"))
            continue
        rows.append(("orphan", e, "全 ROM 无引用"))

    print(f"剩余日文（有译文但没写进 ROM）：{len(residual)} 条\n")
    by = collections.Counter(r[0] for r in rows)
    for k, n in by.most_common():
        mods = collections.Counter(r[1].get("module") for r in rows if r[0] == k)
        print(f"{n:5d}  {k:7s}  {dict(mods.most_common(6))}")
    print()
    for kind in ("pool", "stride", "struct", "ptr", "orphan"):
        sub = [r for r in rows if r[0] == kind]
        if not sub:
            continue
        print(f"--- {kind}（{len(sub)}）---")
        seen_base: collections.Counter = collections.Counter()
        for _, e, why in sub:
            base = why.split()[1] if kind == "pool" else ""
            if base:
                seen_base[base] += 1
        if seen_base:
            print("  池头分布:", dict(seen_base.most_common(8)))
        for _, e, why in sub[:5]:
            print(f"  {e.get('address')} {why:24s} {repr(e.get('original'))[:40]}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
