#!/usr/bin/env python3
"""把「美版汉化版导出 BDF」的私有区编码映射到真实 Unicode。

═══════════════════════════════════════════════════════════════════
码表来源
═══════════════════════════════════════════════════════════════════
GitHub `Wokann/Pokemon_GBA_Font_Patch` —— 美版红宝石中字增益版的原始发布包，
其 `old_(PMxxUS_CHPLUS_RELEASE)/PMRUS_CHPLUS_RELEASE1/` 下附带官方 TBL 码表：

    PMRUS_CHPLUS_RELEASE1_TBL.txt

格式：`0100=<字符>`，**GBK 编码**，共 7006 行，key 范围 0x0100..0x1E5D。

这个 key 就是汉化版字库的字形序号 idx —— 实测校验：
    idx 1405 -> 火    idx 3791 -> 焰    idx 1425 -> 鸡
拼起来正是「火焰鸡」（Blaziken），与游戏内宝可梦名一致 ⇒ 码表正确。

═══════════════════════════════════════════════════════════════════
本脚本做什么
═══════════════════════════════════════════════════════════════════
读 `small_us_cn.bdf`（ENCODING = 0xE100 + 顺序号，每字带 `COMMENT "font_idx=N"`），
按 font_idx 查码表得到真实字符，重写 BDF 的 ENCODING 为该字符的 Unicode。

查不到的 idx 保留私有区编码并在 COMMENT 标注。

用法
====
    python scripts/font/export/map_us_cn_to_unicode.py
    python scripts/font/export/map_us_cn_to_unicode.py --stats
"""

from __future__ import annotations

import argparse
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

SRC_BDF = ROOT / "configs/POKEMON_RUBY_AXVJ00/fonts/small_us_cn.bdf"
OUT_BDF = ROOT / "configs/POKEMON_RUBY_AXVJ00/fonts/small_us_cn_uni.bdf"

TBL_URL = (
    "https://raw.githubusercontent.com/Wokann/Pokemon_GBA_Font_Patch/main/"
    "old_%28PMxxUS_CHPLUS_RELEASE%29/PMRUS_CHPLUS_RELEASE1/"
    "PMRUS_CHPLUS_RELEASE1_TBL.txt"
)
TBL_CACHE = ROOT / "work/_us_cn_ref/PMRUS_TBL.txt"


def load_tbl(path: Path = TBL_CACHE) -> dict[int, str]:
    """读 TBL 码表 → {idx: 字符}。文件是 GBK 编码。"""
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"下载码表 {TBL_URL}")
        urllib.request.urlretrieve(TBL_URL, path)
    raw = path.read_bytes().decode("gbk", errors="replace")
    m: dict[int, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        try:
            m[int(k, 16)] = v
        except ValueError:
            continue
    return m


def gbk_order_map() -> dict[int, str]:
    """按 GBK 标准顺序枚举所有双字节汉字 → {顺序号: 字符}。

    码表实测规律：idx 与 GBK 码位**同向递增**（6762 个相邻项里 6665 个差值
    完全一致，另外 97 处是码表作者跳过了个别字，idx 也随之跳过）。
    所以码表里缺失的 idx 可以用「GBK 顺序 → 字符」补全。

    GBK 双字节区：首字节 0x81..0xFE，次字节 0x40..0xFE（跳过 0x7F）。
    """
    order: dict[int, str] = {}
    seq = 0
    for hi in range(0x81, 0xFF):
        for lo in range(0x40, 0xFF):
            if lo == 0x7F:
                continue
            try:
                ch = bytes([hi, lo]).decode("gbk")
            except UnicodeDecodeError:
                continue
            if len(ch) == 1:
                order[seq] = ch
                seq += 1
    return order


def build_full_map(tbl: dict[int, str]) -> tuple[dict[int, str], int]:
    """在原始码表基础上，用 GBK 顺序补全缺失 idx。

    补全方式：对每个已知 (idx, ch) 锚点，用该字的 GBK 顺序号算出
    `idx - gbk_seq` 的偏移；统计偏移众数，再用它外推缺失段。
    """
    order = gbk_order_map()
    char2seq = {ch: s for s, ch in order.items()}

    # 统计锚点偏移
    offsets: dict[int, int] = {}
    anchors = []
    for idx, ch in tbl.items():
        if len(ch) != 1:
            continue
        s = char2seq.get(ch)
        if s is None:
            continue
        anchors.append((idx, s))
        offsets[idx - s] = offsets.get(idx - s, 0) + 1

    if not offsets:
        return dict(tbl), 0
    # 众数偏移（按区间取，因为跳字会让偏移漂移）
    full = dict(tbl)
    added = 0
    seq2char = order
    # 分段处理：用最近锚点的偏移外推
    anchors.sort()
    for idx in range(0x0100, 0x2100):
        if idx in full:
            continue
        # 找最近的左右锚点
        prev = None
        nxt = None
        for a_idx, a_seq in anchors:
            if a_idx <= idx:
                prev = (a_idx, a_seq)
            else:
                nxt = (a_idx, a_seq)
                break
        cand = None
        if prev and nxt:
            # 两侧偏移一致才补
            if prev[0] - prev[1] == nxt[0] - nxt[1]:
                off = prev[0] - prev[1]
                s = idx - off
                if s in seq2char and prev[1] < s < nxt[1]:
                    cand = seq2char[s]
        if cand:
            full[idx] = cand
            added += 1
    return full, added


def main() -> int:
    ap = argparse.ArgumentParser(description="idx → Unicode，重写 BDF 编码")
    ap.add_argument("--src", type=Path, default=SRC_BDF)
    ap.add_argument("--out", type=Path, default=OUT_BDF)
    ap.add_argument("--stats", action="store_true", help="只打印统计，不写文件")
    args = ap.parse_args()

    tbl = load_tbl()
    print(f"码表 {len(tbl)} 条，key 0x{min(tbl):04X}..0x{max(tbl):04X}")

    text = args.src.read_text(encoding="utf-8")
    lines = text.splitlines()
    n = len(lines)

    n_glyph = 0
    mapped = 0
    um_seq = 0
    unmapped: list[int] = []
    out_lines: list[str] = []

    i = 0
    while i < n:
        line = lines[i]
        if not line.startswith("STARTCHAR"):
            out_lines.append(line)
            i += 1
            continue

        # 收集本块
        j = i + 1
        font_idx = None
        while j < n and not lines[j].startswith("ENDCHAR"):
            m = re.match(r'COMMENT "font_idx=(\d+)"', lines[j])
            if m:
                font_idx = int(m.group(1))
            j += 1

        ch = tbl.get(font_idx) if font_idx is not None else None
        ok = bool(ch) and len(ch) == 1
        n_glyph += 1
        if ok:
            mapped += 1
        else:
            unmapped.append(font_idx if font_idx is not None else -1)
            um_seq += 1

        for k in range(i, j + 1):
            ln = lines[k]
            if ln.startswith("ENCODING"):
                if ok:
                    out_lines.append(f"ENCODING {ord(ch)}")
                else:
                    # 未映射：按顺序号发私有区编码，保证 <= 0xFFFF
                    out_lines.append(f"ENCODING {0xE000 + um_seq}")
            elif ln.startswith("COMMENT \"font_idx=") and not ok:
                out_lines.append(ln)
                out_lines.append('COMMENT "unmapped"')
            else:
                out_lines.append(ln)
        i = j + 1

    print(f"{args.src.name}: {n_glyph} 个字形")
    print(f"  可映射 {mapped}，未映射 {len(unmapped)}")
    if unmapped[:10]:
        print("  未映射 idx 示例:", unmapped[:10])

    if args.stats:
        shown = 0
        for idx, ch in sorted(tbl.items()):
            if 1405 <= idx <= 1420:
                print(f"    idx {idx:5d} -> {ch!r} U+{ord(ch):04X}")
                shown += 1
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"写入 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())