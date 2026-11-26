#!/usr/bin/env python3
"""从美版汉化版 ROM 导出官方 Normal / Small 字库 bin。

★ 为什么只导 7006 槽（896768B），不导满 917504B
────────────────────────────────────────────────────
用反汇编 + 逐槽实测确认（2026-11-25）：

  官方两套字库在 ROM 里是**紧邻拼接**的：
      0x090001A0 + 7006 * 128 == 0x090DB0A0     ← 实测精确相等
  即 Normal 只占槽 0..7005，紧接着就是 Small 的槽 0。

  而 Small 的槽 7006..7167（162 槽 = 20736B）是 **0xFF 填充，不是字库**
  （实测：该区间 20736 字节全为 0xFF）。

所以：
  · Normal 必须只导 7006 槽 —— 导满 0xE0000 会把 Small 的头部读进来。
  · Small 也只导 7006 槽 —— 后面 162 槽本来就不是字库；
    更重要的是**空出来让 overlay 语义保留我们自己的标点槽**
    （项目在用的 `。，！？「」～` 等落在 7012..7082，官方库没有这些）。

overlay 由 engine.py 的 bin_override 完成：源 bin 短于 slot_size 时，
保留 dst（BDF + patch_font_punct 刚生成）的尾部。

官方两库的实测规格（全部槽扫描）
────────────────────────────────────────────────────
| 项            | Normal 0x090001A0 | Small 0x090DB0A0 |
| 主墨(15)宽度  | 11px / 6486 槽    | 9px  / 6484 槽   |
| 含阴影宽度    | 12px / 6486 槽    | 10px / 6484 槽   |
| 主墨 y_min    | 2                 | 6                |
| 主墨 y_max    | 12                | 14               |
| 每槽 / 布局   | 128B, TL0/BL32/TR64/BR96 | 同       |
| nibble        | lo-first          | lo-first         |

用法：
    python scripts/font/export/export_us_cn_bins.py
    python scripts/font/export/export_us_cn_bins.py --rom work/_us_cn.gba --out-dir work/_us_cn_ref
"""

from __future__ import annotations

import argparse
from pathlib import Path

# 反汇编 0x09000190/0x09000194 处的字面量（work/_us_cn.gba）：
#   0x09000190 -> 0x090001A0  Normal 基址
#   0x09000194 -> 0x090DB0A0  Small  基址
NORMAL_VMA = 0x090001A0
SMALL_VMA = 0x090DB0A0
ROM_BASE = 0x08000000
BYTES_PER_GLYPH = 128
SLOT_COUNT = 7006          # 官方两库的实际槽数
TAIL_FF_SLOTS = 162        # Small 7006..7167，全 FF，非字库

DEFAULT_ROM = Path("work/_us_cn.gba")
DEFAULT_OUT = Path("work/_us_cn_ref")

VALID_PX = (0x0, 0xE, 0xF)  # 0 背景 / 14 阴影 / 15 主墨


def _to_file_off(vma: int) -> int:
    return vma - ROM_BASE


def _slot_px(slot: bytes) -> set[int]:
    """取一个 128B 槽里出现的所有 nibble 值。"""
    out: set[int] = set()
    for b in slot:
        out.add(b & 0x0F)
        out.add(b >> 4)
    return out


def export_variant(rom: bytes, vma: int, label: str) -> bytes:
    off = _to_file_off(vma)
    size = SLOT_COUNT * BYTES_PER_GLYPH
    if off < 0 or off + size > len(rom):
        raise SystemExit(f"[{label}] 越界: off=0x{off:X} size={size} rom={len(rom)}")

    data = rom[off : off + size]

    # 校验：像素值只允许 0/14/15；整槽全 FF 的要清零（表示"该槽无字形"）
    bad: list[int] = []
    ff_cleared = 0
    buf = bytearray(data)
    for s in range(SLOT_COUNT):
        a = s * BYTES_PER_GLYPH
        sl = data[a : a + BYTES_PER_GLYPH]
        if all(b == 0xFF for b in sl):
            buf[a : a + BYTES_PER_GLYPH] = b"\x00" * BYTES_PER_GLYPH
            ff_cleared += 1
            continue
        px = _slot_px(sl)
        if not px <= set(VALID_PX):
            bad.append(s)
    if bad:
        raise SystemExit(
            f"[{label}] {len(bad)} 个槽含非法像素值(非 0/14/15)，示例槽号 {bad[:8]}"
        )

    print(
        f"[{label}] 0x{vma:08X} (文件 0x{off:X}) → {size}B "
        f"({SLOT_COUNT} 槽), 全FF清零 {ff_cleared} 槽"
    )
    return bytes(buf)


def main() -> int:
    ap = argparse.ArgumentParser(description="导出美版汉化版官方 Normal/Small 字库")
    ap.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    if not args.rom.is_file():
        raise SystemExit(f"ROM 不存在: {args.rom}")

    rom = args.rom.read_bytes()
    print(f"ROM: {args.rom} ({len(rom)}B)")

    # ★ 关键断言：两库紧邻。成立则说明基址正确、且 7006 槽的边界正确。
    n_off = _to_file_off(NORMAL_VMA)
    expect_small = n_off + SLOT_COUNT * BYTES_PER_GLYPH
    actual_small = _to_file_off(SMALL_VMA)
    if expect_small != actual_small:
        raise SystemExit(
            f"基址校验失败：Normal 0x{NORMAL_VMA:08X} + {SLOT_COUNT}*128 "
            f"= 文件 0x{expect_small:X}，但 Small 实际在 0x{actual_small:X}"
        )
    print(f"基址校验 OK：Normal + {SLOT_COUNT}*128 == Small 起始 (0x{expect_small:X})")

    # Small 尾部 162 槽必须是 FF（证明它确实不是字库，可以安全让位给 overlay）
    s_tail_off = _to_file_off(SMALL_VMA) + SLOT_COUNT * BYTES_PER_GLYPH
    tail = rom[s_tail_off : s_tail_off + TAIL_FF_SLOTS * BYTES_PER_GLYPH]
    if len(tail) == TAIL_FF_SLOTS * BYTES_PER_GLYPH and all(b == 0xFF for b in tail):
        print(f"Small 尾部 {TAIL_FF_SLOTS} 槽确认为 FF 填充（非字库）")
    else:
        print(f"⚠ Small 尾部 {TAIL_FF_SLOTS} 槽不全是 FF，请复核基址/槽数")

    args.out_dir.mkdir(parents=True, exist_ok=True)

    for label, vma in (("Normal", NORMAL_VMA), ("Small", SMALL_VMA)):
        data = export_variant(rom, vma, label)
        out = args.out_dir / f"FontChs{label}.bin"
        out.write_bytes(data)
        print(f"  写入 {out} ({len(data)}B)")

    print()
    print("完成。注意：这两个 bin 只含 7006 槽，尾部 162 槽留给 overlay")
    print("（项目在用的标点槽 7012..7082 由 patch_font_punct.py 生成后保留）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
