"""在 probe dump 的内存里定位 Gen3 队伍结构（gPlayerParty / gEnemyParty）。

【为什么要自己找地址】
符号表 pokeruby_jp.sym 里 gPlayerParty/gEnemyParty 标着 KEEP-US（沿用美版），
但实测 prove 得到的 SaveBlock2=0x02024C04 与美版不同 ⇒ 地址不可想当然沿用。
上一轮 probe 读 0x030045C0 / 0x02024A80 全是 0（明确已在战斗中）⇒ 必须实测定位。

【判据（来自 Gen3 struct Pokemon，100B/只，6 只一组）】
  +0x54  level     1..100
  +0x56  curHP     > 0 且 <= maxHP
  +0x58  maxHP     > 0
  +0x5A..0x62 atk/def/spe/spa/spd 合理（< 1000）
  +0x00  personality 非 0
  且同组第 2..6 只要么同样合法，要么整块全 0（空槽）

用法：
    python scripts/encounter/find_party.py <scene.log 或 run 目录>
"""
from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

PARTY_STRUCT = 100
PARTY_SLOTS = 6


def parse_probes(log_path: Path) -> dict[int, bytes]:
    """从 scene.log 里解析 [PROBE] 行 → {addr: bytes}。"""
    out: dict[int, bytearray] = {}
    pat = re.compile(r"\[PROBE\].*addr=0x([0-9A-Fa-f]+).*len=(\d+)\s+hex=([0-9A-Fa-f]+)")
    for line in log_path.read_text("utf-8", errors="replace").splitlines():
        m = pat.search(line)
        if not m:
            continue
        addr = int(m.group(1), 16)
        data = bytes.fromhex(m.group(3))
        if addr in out:
            out[addr].extend(data)
        else:
            out[addr] = bytearray(data)
    return {a: bytes(b) for a, b in out.items()}


def build_mem(probes: dict[int, bytes]) -> dict[int, int]:
    """把分段 dump 拼成 {addr: byte} 的稀疏视图。"""
    mem: dict[int, int] = {}
    for base, data in probes.items():
        for i, b in enumerate(data):
            mem[base + i] = b
    return mem


def u8(mem, a):
    return mem.get(a)


def u16(mem, a):
    lo, hi = mem.get(a), mem.get(a + 1)
    if lo is None or hi is None:
        return None
    return lo | (hi << 8)


def u32(mem, a):
    v = 0
    for i in range(4):
        b = mem.get(a + i)
        if b is None:
            return None
        v |= b << (i * 8)
    return v


def looks_like_mon(mem: dict[int, int], base: int) -> tuple[bool, str]:
    """判断 base 处是否是一只合法的 struct Pokemon。"""
    personality = u32(mem, base)
    if personality is None:
        return False, "缺数据"
    level = u8(mem, base + 0x54)
    curhp = u16(mem, base + 0x56)
    maxhp = u16(mem, base + 0x58)
    if level is None or curhp is None or maxhp is None:
        return False, "缺数据"
    if personality == 0:
        return False, "personality=0"
    if not (1 <= level <= 100):
        return False, f"level={level}"
    if maxhp == 0 or maxhp > 999:
        return False, f"maxHP={maxhp}"
    if curhp > maxhp:
        return False, f"curHP{curhp}>maxHP{maxhp}"
    stats = {}
    for name, off in (("atk", 0x5A), ("def", 0x5C), ("spe", 0x5E),
                      ("spa", 0x60), ("spd", 0x62)):
        v = u16(mem, base + off)
        if v is None or v == 0 or v > 999:
            return False, f"{name}={v}"
        stats[name] = v
    return True, (f"lv{level} hp{curhp}/{maxhp} "
                  f"a{stats['atk']} d{stats['def']} s{stats['spe']} "
                  f"sa{stats['spa']} sd{stats['spd']} pers={personality:08X}")


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python scripts/encounter/find_party.py <scene.log|run目录>")
        return 2
    p = Path(sys.argv[1])
    if p.is_dir():
        logs = list(p.rglob("scene.log"))
        if not logs:
            print(f"[ERR] {p} 下没有 scene.log")
            return 2
        p = logs[0]
    print(f"读取 {p}")
    probes = parse_probes(p)
    if not probes:
        print("[ERR] 没有解析到 [PROBE] 行")
        return 2
    mem = build_mem(probes)
    print(f"内存视图 {len(mem)} 字节，{len(probes)} 段")
    lo_addr = min(probes)
    hi_addr = max(a + len(d) for a, d in probes.items())
    print(f"覆盖 0x{lo_addr:08X}..0x{hi_addr:08X}")

    # 扫描每 4 字节对齐位置，找「6 连组」里至少 1 只合法
    hits = []
    for base in range(lo_addr, hi_addr - PARTY_STRUCT, 4):
        ok, info = looks_like_mon(mem, base)
        if not ok:
            continue
        # 检查它作为「组的第 n 只」是否成立（前一只全零或也合法）
        n_valid = 0
        for k in range(PARTY_SLOTS):
            o, _ = looks_like_mon(mem, base + k * PARTY_STRUCT)
            if o:
                n_valid += 1
            else:
                break
        hits.append((base, n_valid, info))

    if not hits:
        print("没找到合法的队伍结构")
        return 1

    # 按「连续合法只数」降序，取最像的
    hits.sort(key=lambda x: (-x[1], x[0]))
    print(f"\n候选 {len(hits)} 处，前 12：")
    for base, n, info in hits[:12]:
        print(f"  0x{base:08X}  连续 {n} 只   首只: {info}")

    # 对最佳候选把 6 只都列出来
    best = hits[0][0]
    # 回退到组起点（若 best 在组中间，按 mod 100 对齐）
    print(f"\n最佳候选组（从 0x{best:08X} 起 6 只）：")
    for k in range(PARTY_SLOTS):
        a = best + k * PARTY_STRUCT
        ok, info = looks_like_mon(mem, a)
        print(f"  [{k}] 0x{a:08X}  {'OK ' if ok else '空 '} {info if ok else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
