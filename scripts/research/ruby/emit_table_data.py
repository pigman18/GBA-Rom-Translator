#!/usr/bin/env python3
"""生成 gen/table_data.asm + patches/table_relink.asm：9 张定长表的新数据与基址重定向。

## 为什么重写（2026-11-05）

旧版 a2_emit_table_data.py 有两个致命问题：

1. **输入筛选条件过时**：它只挑 `type == "replace" and phrase_code is not None`
   的条目 —— 那是 F980 时代的判据。F980 通道已删除，这个条件选不到任何条目，
   生成出的新表几乎是空的（实测 0x09EB0AD4 处全是 0x00）。
   结果：stride 已改成新值，但读到的表是空白 → 摘要页直接崩。

2. **几何有多处与实测不符**：
   - 属性名 new_stride 写 17（实际应为 20，见 trampoline 说明）
   - 图鉴分类名 name_offset 写 0（实测 6）
   - 缺宝可梦名（stride 6→12）、特性说明（19→38）、树果名（无需改）

现在改为直接读 ROM 原名 + texts_translated 译文，按实测几何生成。

用法：
    python scripts/research/ruby/emit_table_data.py
"""
from __future__ import annotations

import json
import struct
import sys
from collections import defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

GAME = "POKEMON_RUBY_AXVJ00"
ROM_PATH = ROOT / "roms" / "origin" / f"{GAME}.gba"
TEXTS = ROOT / "configs" / GAME / "translate" / "texts.json"
TRANS = ROOT / "configs" / GAME / "translate" / "texts_translated.json"
HOOK = ROOT / "configs" / GAME / "hook"
OUT_DATA = HOOK / "gen" / "table_data.asm"
OUT_RELINK = HOOK / "patches" / "table_relink.asm"

GBA_BASE = 0x08000000
DATA_START = 0x01EB0000          # 文件偏移；0x09EB0000 GBA

# 实测几何（texts_ground_truth.py 逐条核过）+ stride 改动后的新布局
# name_offset + usable + meta == stride
TABLES = {
    "招式名": dict(
        base=0x1CAD04, stride=8, n=354, eos=0xFF, name_offset=0,
        usable=8, new_stride=32, sym="TblMoveNames",
    ),
    "图鉴分类名": dict(
        # ⚠️ 结构体：名字在 +6，其后 16B 是元数据（含图鉴文本指针）。
        #    stride 28 不能动 —— 游戏按硬编码偏移读，元数据一移位
        #    图鉴详情页就崩（实测已发生）。名字区仅 6B，放不下 2 汉字。
        base=0x384746, stride=28, n=386, eos=0x00, name_offset=6,
        usable=6, new_stride=28, keep_stride=True, sym="TblSpeciesCategory",
    ),
    "道具名": dict(
        # 名字区 9B → 17B（4 汉字），stride 40 → 48。
        #
        # 字段重排（关键）：新表是我们自己生成的，字段放哪里由我们定。
        # 只要保证每个访问点的偏移都在 Thumb 立即数范围内即可：
        #   ldrb 5 位 → 0..31      ldrh 5 位×2 → 0..62      adds 8 位 → 0..255
        #
        #   旧 → 新   字段            访问指令（实测）             新偏移可用？
        #   0x0A→0x12  u16   080A53B4 ldrh r0,[r1,#0xa]       0x12/2=9  ✓
        #   0x0C→0x14  u16   080A53D8 ldrh r0,[r1,#0xc]       0x14/2=10 ✓
        #   0x0E→0x16  u8    080A53FC ldrb r0,[r1,#0xe]       0x16=22   ✓
        #   0x0F→0x17  u8    080A5420 ldrb r0,[r1,#0xf]       0x17=23   ✓
        #   0x10→0x24  ptr   080A5432 adds r4,#0x10           改 #0x24   ✓(adds)
        #   0x14→0x18  u8    080A546C ldrb r0,[r1,#0x14]      0x18=24   ✓
        #   0x15→0x19  u8    080A5490 ldrb r0,[r1,#0x15]      0x19=25   ✓
        #   0x16→0x1A  u8    080A54B4 ldrb r0,[r1,#0x16]      0x1A=26   ✓
        #   0x17→0x1B  u8    080A54D8 ldrb r0,[r1,#0x17]      0x1B=27   ✓
        #   0x18→0x20  ptr   080A54EA adds r4,#0x18           改 #0x20   ✓(adds)
        #   0x1C→0x1C  u16   ★ 留在原位，指令不用改
        #                    （080A5524 ldrb / 080A56BE strh / 080A56C8 strh
        #                      三处访问点全部保持原偏移，避免 0x24 超 ldrb 上限）
        #   0x20→0x28  u32   080A5536 adds r4,#0x20           改 #0x28   ✓(adds)
        #
        # 0x1C 原地保留是这条路能通的关键：它是 1 读 2 写共 3 个访问点，
        # 且读用 ldrb（上限 31），0x24 放不下。留在 0x1C 就完全绕开。
        base=0x39A648, stride=40, n=348, eos=0xFF, name_offset=0,
        usable=9, new_stride=48, new_usable=17, sym="TblItemNames",
        field_map=[
            (0x0A, 0x12, 2),
            (0x0C, 0x14, 2),
            (0x0E, 0x16, 1),
            (0x0F, 0x17, 1),
            (0x10, 0x24, 4),
            (0x14, 0x18, 1),
            (0x15, 0x19, 1),
            (0x16, 0x1A, 1),
            (0x17, 0x1B, 1),
            (0x18, 0x20, 4),
            (0x1C, 0x1C, 2),
            (0x20, 0x28, 4),
        ],
    ),
    "秘密基地装饰名": dict(
        # ⚠️ 结构体：名字在 +13，其后 5B 元数据，不可移。
        base=0x3C2A44, stride=28, n=120, eos=0xFF, name_offset=13,
        usable=10, new_stride=28, keep_stride=True, sym="TblDecorNames",
    ),
    "特性名": dict(
        base=0x1CBC44, stride=8, n=77, eos=0xFF, name_offset=0,
        usable=8, new_stride=32, sym="TblAbilityNames",
    ),
    "属性名": dict(
        # 5 是 (4+1)，改 stride 走 trampoline，新表按 20 排
        base=0x1CBB0C, stride=5, n=18, eos=0xFF, name_offset=0,
        usable=5, new_stride=20, sym="TblTypeNames",
    ),
    "宝可梦名": dict(
        # 6 → 24（×4），67 个站点已改移位立即数
        base=0x1CA354, stride=6, n=412, eos=0xFF, name_offset=0,
        usable=6, new_stride=24, sym="TblSpeciesNames",
    ),
    "特性说明": dict(
        # 19 → 48，走 trampoline
        base=0x1CBEB4, stride=19, n=78, eos=0xFF, name_offset=0,
        usable=19, new_stride=48, sym="TblAbilityDesc",
    ),
    "树果名": dict(
        # ⚠️ 结构体：+0x10 是描述指针，不可移。
        base=0x3A1034, stride=28, n=43, eos=0xFF, name_offset=0,
        usable=10, new_stride=28, keep_stride=True, sym="TblBerryNames",
    ),
}

# 生成顺序（决定新区地址，保持稳定）
ORDER = ["招式名", "图鉴分类名", "道具名", "秘密基地装饰名",
         "特性名", "属性名", "宝可梦名", "特性说明", "树果名"]


def emit_bytes(blob: bytes) -> list[str]:
    out = []
    for i in range(0, len(blob), 16):
        chunk = blob[i:i + 16]
        out.append("    .byte " + ", ".join(f"0x{b:02X}" for b in chunk))
    return out


def read_original_name(rom: bytes, off: int, usable: int, eos: int) -> bytes:
    """读原表一项的名字字节（去掉 eos 及其后）。"""
    seg = rom[off:off + usable]
    for i, b in enumerate(seg):
        if b == eos:
            return seg[:i]
    return seg


def main() -> int:
    from meowth.charmap import Charmap
    from meowth.config_loader import get_charmap_path
    from meowth.codec import get_codec

    cm = Charmap(charmap_path=get_charmap_path(GAME), target_lang="zh-Hans")
    codec = get_codec(GAME)
    rom = ROM_PATH.read_bytes()

    tj = json.loads(TEXTS.read_text(encoding="utf-8"))
    tt = json.loads(TRANS.read_text(encoding="utf-8"))
    tr = {e["original"]: e["translated"] for e in tt if e.get("translated")}

    # 按模块收集「原串 → 译文」
    #
    # ⚠️ 匹配要同时支持两种 key：
    #   1) 原串（strip 后）—— texts.json 的 original 与 ROM 解码结果一致时
    #   2) 表索引 table_index —— 原串有全角/半角差异时靠索引兜底
    # 实测装饰名：按原串匹配 0/120，按 table_index 匹配 120/120
    # （装饰名 original 尾部带空格，strip 后对不上 tr 的 key）。
    by_module: dict[str, dict[str, str]] = defaultdict(dict)
    by_index: dict[str, dict[int, str]] = defaultdict(dict)
    for e in tj["entries"]:
        mod = e.get("module") or ""
        if mod not in TABLES:
            continue
        raw = e.get("original") or ""
        zh = (e.get("translated") or "").strip() or tr.get(raw)
        if not zh:
            continue
        if raw.strip():
            by_module[mod][raw.strip()] = zh
        idx = e.get("table_index")
        if isinstance(idx, int):
            by_index[mod][idx] = zh

    lines = [
        "; " + "=" * 79,
        "; 9 张定长表的新数据（自动生成，勿手改）",
        "; 生成器: scripts/research/ruby/emit_table_data.py",
        ";",
        "; 每项布局按新 stride 重排：[name_offset 头部][名字][eos 填充][元数据]",
        "; 基址由 patches/table_relink.asm 改字面量指过来。",
        "; " + "=" * 79,
        "",
        f".org 0x{DATA_START + GBA_BASE:08X}",
        "",
    ]

    cursor = DATA_START
    relink: list[tuple[int, int, str, int, int, str]] = []   # off,new_gba,name,old_gba,new_gba,sym
    stats = []

    for name in ORDER:
        g = TABLES[name]
        base, stride, n = g["base"], g["stride"], g["n"]
        eos, noff, usable = g["eos"], g["name_offset"], g["usable"]
        new_s = g["new_stride"]
        keep_stride = bool(g.get("keep_stride"))
        meta = stride - noff - usable
        # new_usable 可显式覆盖：道具名扩 stride 到 48 后，名字区想扩到 17B
        # 而不是「把 stride 增量全给名字」（那样元数据会移位，游戏读错字段）。
        new_usable = int(g.get("new_usable") or (new_s - noff - meta))
        if new_usable <= 0:
            raise SystemExit(f"{name}: new_stride {new_s} 放不下元数据")
        if new_usable + noff + meta > new_s:
            raise SystemExit(
                f"{name}: new_usable({new_usable}) + offset({noff}) + meta({meta}) "
                f"超过 new_stride({new_s})")
        # 元数据必须保持原相对位置：名字区扩大后，元数据紧跟其后，起始偏移变了
        # ⇒ 如果元数据里含硬编码偏移的字段，就不能扩。道具名例外：
        # 它的字段都在名字区之后、且我们给 new_usable 显式值来保持字段对齐。
        if keep_stride and new_s != stride:
            raise SystemExit(
                f"{name}: 标了 keep_stride 却给了不同的 new_stride({new_s}!={stride})")

        tr_map = by_module.get(name, {})
        idx_map = by_index.get(name, {})
        translated = hit = 0
        blob = bytearray()

        for i in range(n):
            src = base + i * stride
            head = rom[src:src + noff]
            orig = read_original_name(rom, src + noff, usable, eos)
            met = rom[src + noff + usable:src + stride]

            try:
                orig_text = codec.decode(orig) if orig else ""
            except Exception:
                orig_text = ""
            zh = None
            if orig_text and orig_text.strip() in tr_map:
                zh = tr_map[orig_text.strip()]
            elif i in idx_map:
                zh = idx_map[i]
            if zh:
                translated += 1
                body = cm.encode(zh)
                if body.endswith(b"\xFF"):
                    body = body[:-1]
            else:
                body = orig

            if len(body) > new_usable:
                # keep_stride 的表放不下时**不能截断**——截断会写出半个汉字
                # （F9 序列被切断），比保留日文更糟。这类条目留给后续
                # 「整表换指针数组」方案，这里保持原文。
                if keep_stride:
                    body = orig
                else:
                    # 截在整字边界上：F9 00 hi lo 是 4 字节一组，
                    # 按 4 的倍数往下取整，绝不切断半个字。
                    keep = (new_usable - 1) // 4 * 4
                    body = body[:keep]

            # ★ F9 组完整性（2026-11-05 实测修复）
            # 中文编码里 F9 00 hi lo 是 4 字节一组；若 body 长度不是 4 的倍数
            # （名字里有全角 ASCII，如「ＰＰ单项小补剂」开头的 ＰＰ 各占 1B），
            # 后面填充 eos 就会把最后一组 F9 切断，运行时读成
            # `f9 00 ff` → 画出错误字形/乱码（实测背包列表出现尖角乱码行）。
            #
            # 处理：若 body 含 F9 且长度非 4 倍数，按 4 向下取整截断
            # （宁可少一个字，也不写出半个字形）。
            if b"\xF9" in body and len(body) % 4:
                body = body[: len(body) // 4 * 4]

            blob += head
            # ── 布局：名字区 + 字段重排 ──────────────────────────────────
            # 字段放哪个位置由我们自己定（新表是生成的），只要保证
            # **每个访问点的偏移都能用 Thumb 立即数表达**即可。
            # 没有 field_map 时退化为「名字 + 元数据紧接」的老布局。
            blob += body
            blob += bytes([eos]) * (new_usable - len(body))
            fmap = g.get("field_map")
            if fmap:
                # fmap: [(old_off, new_off, width), ...]
                buf = bytearray(new_s)
                # 名字区已经写进 blob 尾部
                buf[:new_usable] = blob[-new_usable:]
                for old_off, new_off, width in fmap:
                    src_off = src + old_off
                    piece = rom[src_off:src_off + width]
                    if len(piece) < width:
                        piece = piece + bytes(width - len(piece))
                    buf[new_off:new_off + width] = piece
                # ⚠️ 用 head 替换掉本项刚写进 blob 的 new_usable 字节
                del blob[-new_usable:]
                blob += bytes(buf)
            elif meta:
                m = met + bytes(max(0, meta - len(met)))
                blob += m[:meta]

        gba = cursor + GBA_BASE
        note = "  [keep_stride: 元数据位置不变]" if keep_stride else ""
        lines.append(f"; ---- {name}: {len(blob):,}B  "
                     f"stride {stride}→{new_s}  {n} 项  "
                     f"name_offset={noff}  usable {usable}→{new_usable}  "
                     f"译文 {translated}/{n}{note} ----")
        lines.append(f".org 0x{gba:08X}")
        lines.append(".align 4")
        lines.append(f"{g['sym']}:")
        lines.extend(emit_bytes(bytes(blob)))
        lines.append("")

        stats.append((name, stride, new_s, n, translated, len(blob), gba))
        # 旧基址 → 新基址，供 relink
        relink.append((base, gba, name, base + GBA_BASE, gba, g["sym"]))
        cursor += len(blob)
        cursor = (cursor + 3) & ~3

    OUT_DATA.parent.mkdir(parents=True, exist_ok=True)
    OUT_DATA.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    # ---- table_relink.asm：把引用旧基址的字面量改成新基址 ----
    from meowth.table_stride import find_literal_sites

    rl = [
        "; " + "=" * 79,
        "; 表基址重定向：把指向旧表的字面量改成新表地址（自动生成，勿手改）",
        "; 生成器: scripts/research/ruby/emit_table_data.py",
        "; 数据在 gen/table_data.asm",
        "; " + "=" * 79,
        "",
    ]
    total_sites = 0
    for _base, new_gba, name, old_gba, _ng, _sym in relink:
        sites = find_literal_sites(rom, old_gba)
        if not sites:
            continue
        rl.append(f"; ---- {name}  0x{old_gba:08X} → 0x{new_gba:08X}  "
                  f"({len(sites)} 处字面量) ----")
        for s in sites:
            rl.append(f".org 0x{s + GBA_BASE:08X}")
            rl.append(f"    .byte " + ", ".join(
                f"0x{b:02X}" for b in struct.pack("<I", new_gba)))
            total_sites += 1
        rl.append("")

    OUT_RELINK.parent.mkdir(parents=True, exist_ok=True)
    OUT_RELINK.write_text("\n".join(rl) + "\n", encoding="utf-8", newline="\n")

    print(f"{'表':<16}{'旧stride':>8}{'新stride':>8}{'项数':>6}{'译文':>6}{'字节':>9}  新基址")
    print("-" * 76)
    for name, s0, s1, n, tr_n, size, gba in stats:
        print(f"{name:<16}{s0:>8}{s1:>8}{n:>6}{tr_n:>6}{size:>9}  0x{gba:08X}")
    print("-" * 76)
    print(f"字面量重定向 {total_sites} 处")
    print(f"新区 0x{DATA_START + GBA_BASE:08X}..0x{cursor + GBA_BASE:08X}"
          f"  ({cursor - DATA_START:,} B)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
