"""诊断 relocate 的"全 ROM 逐字节指针扫描"误改。

_write_relocated() 用 _axvj_pointer_sites() 做 rom.find(needle, pos) 逐字节
滑窗，无 4 字节对齐、无区域过滤。凡字节序列恰等于旧文本地址（0x083xxxxx）
的位置，都会被改写成扩展区指针（0x092xxxxx）。

本脚本对每条 relocate 条目：
  - 复现扫描 → 得到"实际会被改的点"
  - 与 translate.build.json 记录的 pointer_sources（真指针表位置）求差集
  - 差集 = 额外改写点（碰撞嫌疑），分类统计并判定所在区域
"""
import json
import sys
from collections import Counter, defaultdict

ORIG = r"roms\origin\POKEMON_RUBY_AXVJ00.gba"
HAN = r"roms\outputs\POKEMON_RUBY_AXVJ00_translated.gba"
BUILD = r"work\POKEMON_RUBY_AXVJ00\translate.build.json"

PTR_BASE = 0x08000000

# 已知数据区（ROM 文件偏移）— 用于改写点的区域归属判定
REGIONS = [
    (0x00000000, 0x00100000, "代码区(0x08000000-)"),
    (0x001D36DC, 0x001D5900, "★动画脚本本体"),
    (0x001D997C, 0x001DA350, "★动画表 gBattleAnims_Moves"),
    (0x00300000, 0x00400000, "文本区(0x083xxxxx)"),
]


def region_of(off: int) -> str:
    for lo, hi, name in REGIONS:
        if lo <= off < hi:
            return name
    return f"未分类(0x{off:06X})"


def find_all(buf: bytes, needle: bytes) -> list[int]:
    out, pos = [], buf.find(needle)
    while pos >= 0:
        out.append(pos)
        pos = buf.find(needle, pos + 1)
    return out


def be32(buf: bytes, off: int) -> int:
    return int.from_bytes(buf[off:off + 4], "little")


def looks_like_ptr_slot(han: bytes, off: int) -> bool:
    """邻居指针特征：左右相邻槽也存着 0x083xxxxx/0x092xxxxx 指针。"""
    for d in (-4, 4):
        n = off + d
        if 0 <= n + 4 <= len(han):
            v = be32(han, n)
            if (v >> 24) in (0x08, 0x09):
                return True
    return False


def main() -> int:
    orig = open(ORIG, "rb").read()
    han = open(HAN, "rb").read()
    data = json.load(open(BUILD, encoding="utf-8"))
    entries = data["entries"] if isinstance(data, dict) else data

    total_sites = 0
    extra_all: list[tuple[int, int, int]] = []  # (off, old_ptr, entry_idx)
    unpatched: list[tuple[int, list[int]]] = []
    per_entry_extra = Counter()

    for i, e in enumerate(entries):
        if (e.get("type") or "") != "relocate":
            continue
        addr = int(str(e["address"]), 16)
        old_ptr = addr if addr >= PTR_BASE else PTR_BASE + addr
        needle = old_ptr.to_bytes(4, "little")
        sites = find_all(orig, needle)
        expected = {int(str(p), 16) for p in (e.get("pointer_sources") or [])}
        # build.json 里 pointer_sources 可能是绝对地址，统一转文件偏移
        expected = {p - PTR_BASE if p >= PTR_BASE else p for p in expected}
        total_sites += len(sites)
        if not sites:
            unpatched.append((old_ptr, sorted(expected)))
            continue
        for s in sites:
            if s not in expected:
                extra_all.append((s, old_ptr, i))
                per_entry_extra[i] += 1

    print(f"条目数 {len(entries)}  扫描命中总数 {total_sites}")
    print(f"build.json 记录的真指针点 {sum(len(e.get('pointer_sources') or []) for e in entries)}")
    print(f"额外改写点（碰撞嫌疑） {len(extra_all)}")
    print(f"未命中任何指针点的条目 {len(unpatched)}")
    for p, exp in unpatched[:5]:
        print(f"   0x{p:08X}  期望点 {[hex(x) for x in exp]}")

    # 确认这些额外点在汉化 ROM 里真的被改成了 0x092xxxxx
    confirmed, untouched = [], []
    for off, old_ptr, ei in extra_all:
        newv = be32(han, off)
        if (newv >> 24) == 0x09:
            confirmed.append((off, old_ptr, newv, ei))
        else:
            untouched.append((off, old_ptr, newv, ei))

    print(f"\n其中在汉化 ROM 中确实被改成 0x09xxxxxx 的: {len(confirmed)}")
    print(f"未被改写（说明这些条目没真正注入）: {len(untouched)}")

    # 区域分布
    by_region = Counter(region_of(o) for o, _, _, _ in confirmed)
    print("\n=== 额外改写点区域分布（已确认被改） ===")
    for name, n in by_region.most_common():
        print(f"  {n:6d}  {name}")

    # 对齐与邻居特征
    aligned = sum(1 for o, _, _, _ in confirmed if o % 4 == 0)
    neigh = sum(1 for o, _, _, _ in confirmed if looks_like_ptr_slot(han, o))
    print(f"\n4 字节对齐的: {aligned}/{len(confirmed)}")
    print(f"邻居也是指针（像指针表）: {neigh}/{len(confirmed)}")

    # 最可疑：非代码区外 且 未对齐 且 邻居不是指针
    suspicious = [
        (o, op, nv, ei) for (o, op, nv, ei) in confirmed
        if o % 4 != 0 and not looks_like_ptr_slot(han, o)
    ]
    print(f"\n=== 高度可疑（未对齐 + 邻居非指针）: {len(suspicious)} ===")
    per_mod = Counter(entries[ei].get("module") for _, _, _, ei in suspicious)
    for m, n in per_mod.most_common():
        print(f"  {n:6d}  module={m}")
    print("\n前 30 条明细：")
    for o, op, nv, ei in suspicious[:30]:
        e = entries[ei]
        print(
            f"  off=0x{o:06X} (0x{PTR_BASE+o:08X})  {region_of(o)}  "
            f"0x{op:08X} -> 0x{nv:08X}  entry={e.get('id')} "
            f"@ {e.get('address')} ctx={orig[o-4:o+8].hex()}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
