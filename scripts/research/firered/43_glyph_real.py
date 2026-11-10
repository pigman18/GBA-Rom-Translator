#!/usr/bin/env python3
"""调研㊸ 渲染协议①：定位火红的字模区（两版都不动）与中文字模来源。

═══════════════════════════════════════════════════════════════════════════
【已确定的地基（前面实证）】
═══════════════════════════════════════════════════════════════════════════
 E1 原版编码 = **1 字节**（㊶ 三判据：高字节 204 种、0x00 均匀分布、名字 4~6 字节）
 E2 火红**只往原版 100% FF 的空区写东西**，所有改动块 orig_FF = 100%
 E3 中文字模**不在** 0x6D0000..0x08730000（那是纯文本，F7 占 23~30%）
 E4 原版字模区**一个字节都没改**（「原版非空 + 高改动率」= 0 个块）

⇒ 那么中文字模在哪？只剩一个可能：
   **汉化把中文字模写进了原版空区**，而且那些区不含 F7 也不含 FF。

═══════════════════════════════════════════════════════════════════════════
【判据设计（避开㊳/㊴ 的错误）】
═══════════════════════════════════════════════════════════════════════════
㊳ 错在「变异系数随 tile 变大单调下降」；㊴ 错在把 00/FF 当成墨。
这次用**形状判据**：

 真字模的行墨量曲线必须满足：
   ① 首行墨量很低（字顶留白）
   ② 中间行墨量最高
   ③ 末行墨量低
   ④ 整字墨量不能是 0 或满

 对候选区、候选 tile 尺寸，统计「满足上述四条的 tile 占比」。
 真字模区该占比会很高；非字模区接近随机。

用法：python scripts/research/firered/43_glyph_real.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def row_ink(tile: bytes, w: int, h: int) -> np.ndarray | None:
    rb = (w + 7) // 8
    if len(tile) < rb * h:
        return None
    out = np.zeros(h, dtype=np.int32)
    for y in range(h):
        row = np.frombuffer(tile[y * rb:(y + 1) * rb], dtype=np.uint8)
        out[y] = np.unpackbits(row)[:w].sum()
    return out


def glyph_score(tiles: list[bytes], w: int, h: int) -> tuple[float, float]:
    """返回 (合格率, 平均填充率)。合格 = 墨量钟形。"""
    ok = 0
    tot = 0
    fills = []
    for t in tiles:
        r = row_ink(t, w, h)
        if r is None:
            continue
        tot += 1
        s = int(r.sum())
        cap = w * h
        if s == 0 or s > cap * 0.85:
            continue
        fills.append(s / cap)
        # 钟形判据
        k = max(1, h // 4)
        top = r[:k].mean()
        mid = r[k:h - k].mean() if h - k > k else r.mean()
        bot = r[-k:].mean()
        if mid > top and mid > bot and mid >= 1 and s >= 4:
            ok += 1
    return (ok / max(1, tot), float(np.mean(fills)) if fills else 0.0)


def main() -> int:
    zh = np.frombuffer(FR_ZH.read_bytes(), dtype=np.uint8)
    ja = np.frombuffer(FR_JA.read_bytes(), dtype=np.uint8)
    n = min(len(zh), len(ja))

    SEG = 0x8000
    nseg = n // SEG
    a = ja[:nseg * SEG].reshape(nseg, SEG)
    b = zh[:nseg * SEG].reshape(nseg, SEG)
    mid_o = ((a != 0) & (a != 0xFF)).mean(axis=1)
    mid_z = ((b != 0) & (b != 0xFF)).mean(axis=1)

    print("=" * 78)
    print("① 两种候选区")
    print("=" * 78)
    # 候选 A：火红新增的密集区（原版中密度低、汉化中密度高）
    zone_a = np.flatnonzero((mid_o < 0.05) & (mid_z > 0.30))
    # 候选 B：原版本来就密集的区（可能是原版字模，汉化没动）
    zone_b = np.flatnonzero((mid_o > 0.90) & (mid_z > 0.90))
    print(f"  候选 A（火红新增的密集区）：{len(zone_a)} 个 32KB 块")
    for i in zone_a.tolist()[:15]:
        print(f"    0x{BASE+i*SEG:08X}  原版 mid {mid_o[i]:>5.1%} → "
              f"汉化 mid {mid_z[i]:>5.1%}")
    print(f"\n  候选 B（原版就密集，汉化也密集）：{len(zone_b)} 个")
    for i in zone_b.tolist()[:10]:
        print(f"    0x{BASE+i*SEG:08X}  mid {mid_o[i]:>5.1%}")

    # ── ② 对候选区做字模形状评分 ──────────────────────────────────
    print("\n" + "=" * 78)
    print("② 字模形状评分（钟形行墨量）—— 合格率高者才是字模")
    print("=" * 78)

    def evaluate(rom: np.ndarray, off: int, label: str) -> None:
        print(f"\n  {label}  0x{BASE+off:08X}")
        print(f"    {'尺寸':>8} {'tile字节':>9} {'合格率':>8} {'平均填充':>9}")
        best = None
        for w, h in ((8, 8), (8, 12), (8, 16), (16, 12), (16, 16), (12, 12)):
            tb = ((w + 7) // 8) * h
            cnt = min(1024, 0x4000 // tb)
            if cnt < 64:
                continue
            tiles = [rom[off + k * tb:off + (k + 1) * tb].tobytes()
                     for k in range(cnt)]
            rate, fill = glyph_score(tiles, w, h)
            mark = ""
            if best is None or rate > best[0]:
                best = (rate, f"{w}×{h}", fill)
            if rate > 0.30:
                mark = " ★"
            print(f"    {w}×{h:<6} {tb:>9} {rate:>8.1%} {fill:>9.1%}{mark}")
        if best:
            print(f"    ⇒ 最佳 {best[1]}，合格率 {best[0]:.1%}")

    for i in zone_a.tolist()[:4]:
        evaluate(zh, i * SEG, "候选A（汉化新增）")

    # 对照：代码区与文本区
    print("\n  ---- 对照组 ----")
    evaluate(ja, 0x00000, "代码区（应很低）")
    evaluate(zh, 0x6D0000, "中文文本区（应很低）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
