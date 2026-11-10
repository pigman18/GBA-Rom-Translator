#!/usr/bin/env python3
"""调研㊴ 找中文（F7 码位）字模 —— 用「码位↔字模」的映射反推。

═══════════════════════════════════════════════════════════════════════════
【㊳ 的方法为什么失败】
═══════════════════════════════════════════════════════════════════════════
用「墨量变异系数最小」判 tile 尺寸是**错的**：
  · 变异系数随 tile 变大**单调下降**（8×8: 0.170 → 16×16: 0.107）
  · 这是统计假象（大 tile 内平均化更多），不是「找到了真尺寸」
  · 代码区 8×16 也能到 0.201，与候选区无区别 ⇒ 判据无区分力

═══════════════════════════════════════════════════════════════════════════
【换成有效判据：从已知的码位映射反推】
═══════════════════════════════════════════════════════════════════════════
已知硬事实：
  · 中文码位 = `F7 hi lo`，hi ∈ 0x00–0x0A，共 2,299 个
  · 中文是汉化新增的，字模必然在**原版为空白（100% FF）**的区

⇒ 正确做法：
  ① 列出汉化占比高、原版全 FF 的区（新增区）
  ② 在这些区里找**周期性位图结构**：即「固定步长的字节块，块内墨量稳定、
     块间相邻差异小」——这才是字模数组
  ③ 关键判据：字模数组的**相邻块**应该「字形相似」但不相同，
     而文本/代码的相邻块完全无关

更强的判据（本脚本主用）：
  把候选区按不同 stride 切块，算「块内每行的墨点分布」。
  真字模的特征：**前若干行墨点少（字顶留白）、中间多、末尾少**，
  即墨量沿行号呈「低-高-低」的钟形。这个特征跟 stride 无关，能定死行高。

用法：python scripts/research/firered/39_glyph_zone.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def main() -> int:
    zh = np.frombuffer(FR_ZH.read_bytes(), dtype=np.uint8)
    ja = np.frombuffer(FR_JA.read_bytes(), dtype=np.uint8)
    n = min(len(zh), len(ja))

    print("=" * 78)
    print("① 找「原版空白、汉化有内容」的新增区（64KB 粒度）")
    print("=" * 78)
    SEG = 0x10000
    nseg = n // SEG
    a = ja[:nseg * SEG].reshape(nseg, SEG)
    b = zh[:nseg * SEG].reshape(nseg, SEG)
    free_orig = (a == 0xFF).mean(axis=1) > 0.99
    used_now = (b == 0xFF).mean(axis=1) < 0.80
    new_zones = np.flatnonzero(free_orig & used_now)
    print(f"  新增区 64KB 块：{len(new_zones)}")
    for i in new_zones.tolist()[:40]:
        f7 = (b[i] == 0xF7).mean()
        print(f"    0x{BASE+i*SEG:08X}  汉化非FF {1-(b[i]==0xFF).mean():>5.1%} "
              f"F7 {f7:>5.1%}")

    # ── ② 墨量沿行号的钟形特征（定行高）──────────────────────────
    print("\n" + "=" * 78)
    print("② 行高判定：墨量沿行号的形状（字模应是低-高-低）")
    print("=" * 78)

    def row_profile(rom: np.ndarray, off: int, size: int,
                    stride: int) -> np.ndarray | None:
        """按 stride 切块，把每块的第 k 行墨量累加，返回长度 stride 的曲线。"""
        cnt = size // stride
        if cnt < 32:
            return None
        blk = rom[off:off + cnt * stride].reshape(cnt, stride)
        ink = np.unpackbits(blk).reshape(cnt, stride * 8).sum(axis=1)
        return ink / cnt

    # 对几个新增区，试 stride = 8/12/16/24/32，看哪条曲线最像钟形
    def bell_score(p: np.ndarray) -> float:
        """钟形程度：中间平均墨量 / 两端平均墨量。越大越像字模。"""
        if p is None or len(p) < 8:
            return 0
        k = len(p) // 4
        mid = p[k:len(p) - k].mean()
        ends = (p[:k].mean() + p[-k:].mean()) / 2
        return float(mid / max(1e-6, ends)) if ends > 0 else 0

    print(f"  {'区':>14} {'stride':>7} {'钟形得分':>9}  曲线前 16 值")
    for i in new_zones.tolist()[:8]:
        off = i * SEG
        for stride in (8, 12, 16, 24, 32):
            p = row_profile(ja, off, 0x4000, stride)
            if p is None:
                continue
            s = bell_score(p)
            if s > 1.08:
                print(f"  0x{BASE+off:08X} {stride:>7} {s:>9.2f}  "
                      f"{np.round(p[:16], 1).tolist()}")

    # ── ③ 更硬的判据：字模区的相邻块相关性 ───────────────────────
    print("\n" + "=" * 78)
    print("③ 相邻块相关性：字模应「块块相似但不相同」，数据应无相关")
    print("=" * 78)
    print(f"  {'区':>14} {'stride':>7} {'相邻块相关':>10} {'块内墨量标准差':>13}")
    for i in list(new_zones[:8]) + [0, 1, 2]:
        off = i * SEG
        for stride in (12, 16, 24, 32):
            cnt = min(2048, 0x4000 // stride)
            if cnt < 64:
                continue
            blk = ja[off:off + cnt * stride].reshape(cnt, stride).astype(np.float32)
            ink = np.unpackbits(blk.astype(np.uint8)).reshape(
                cnt, stride * 8).sum(axis=1)
            # 相邻块墨量相关
            c = np.corrcoef(ink[:-1], ink[1:])[0, 1]
            print(f"  0x{BASE+off:08X} {stride:>7} {c:>10.3f} "
                  f"{ink.std():>13.2f}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
