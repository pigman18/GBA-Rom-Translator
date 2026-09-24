"""静态预演：全 ROM 所有「解压到 VRAM」调用的 (源, 目的, 大小)。

回答 S1→S2 的参数问题里**静态可得的那一半**：
  41 处 cb2/cb3 装载各自的目标区间到底在哪、多大、是否与 v10 池冲突。
运行时才知道的那一半（**何时**触发）交给 `--preset cb-load`。

做法（纯静态，只读 ROM）：
  1. 扫全 ROM 找 `bl 0x0800A770`（LZ77UnCompVram 包装）与 `bl 0x081B1298`（svc 0x12 蹦床）调用点；
  2. 对每个调用点向前回溯 r0 / r1 的最近一次赋值，支持三种写法：
       · `ldr rX, [pc, #imm]`  → 直读字面量池
       · `adds rX, rY, #imm`   → 基址 + 偏移（继承 rY 的已知值）
       · `movs rX, #imm`       → 立即数
  3. 从源地址读 LZ77 头得解压大小 → 目的地址 + 大小 = 覆盖 tile 区间。

用法：
    python scripts/preview_cb_loads.py            # 默认表格
    python scripts/preview_cb_loads.py --cb2cb3   # 只看 cb2/cb3
    python scripts/preview_cb_loads.py --json out/preview_cb_loads.json
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

REPO = Path(__file__).resolve().parents[1]
ROM = REPO / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"

VRAM_BG0 = 0x06000000
CALL_TARGETS = {0x0800A770: "LZ77→VRAM(包装)", 0x081B1298: "svc12 蹦床"}
# v10 §3 层 3 规划的接管池
V10_POOL = {2: (32, 512), 3: (128, 512)}


def load_rom() -> bytes:
    if not ROM.is_file():
        raise SystemExit(f"缺 ROM: {ROM}")
    return ROM.read_bytes()


def u32(raw: bytes, vma: int) -> int:
    off = vma - 0x08000000
    if off < 0 or off + 4 > len(raw):
        return 0
    return struct.unpack_from("<I", raw, off)[0]


def lz77_size(raw: bytes, src: int) -> int:
    """读 LZ77 头（0x10 + 24bit 小端）→ 解压字节数；非 LZ77 返回 -1。"""
    if not (0x08000000 <= src < 0x0A000000):
        return -1
    off = src - 0x08000000
    if off + 4 > len(raw) or raw[off] != 0x10:
        return -1
    return raw[off + 1] | (raw[off + 2] << 8) | (raw[off + 3] << 16)


def scan_calls(raw: bytes, md: Cs) -> list[tuple[int, int]]:
    """全 ROM 扫 bl → 目标在 CALL_TARGETS 的所有调用点 (call_site, target)。"""
    out = []
    # Thumb BL：从 ROM 起点按 2 字节步长扫，用 capstone 逐条反汇编代价太高；
    # 直接手工解码 BL/BLX（与 scripts/find_callers.py 同款，已验证）。
    body = raw[0x000000:0x800000]
    for i in range(0, len(body) - 4, 2):
        h1 = body[i] | (body[i + 1] << 8)
        h2 = body[i + 2] | (body[i + 3] << 8)
        if (h1 & 0xF800) != 0xF000 or (h2 & 0xD000) not in (0xD000, 0xC000):
            continue
        if (h2 & 0xC000) == 0xC000:      # BLX 后缀
            if (h2 & 0x1000) == 0:
                continue
        S = (h1 >> 10) & 1
        imm10 = h1 & 0x3FF
        J1 = (h2 >> 13) & 1
        J2 = (h2 >> 11) & 1
        imm11 = h2 & 0x7FF
        I1 = 1 - (J1 ^ S)
        I2 = 1 - (J2 ^ S)
        off = (S << 24) | (I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1)
        if off & (1 << 24):
            off -= 1 << 25
        pc = 0x08000000 + i
        tgt = (pc + 4 + off) & 0xFFFFFFFF
        if tgt in CALL_TARGETS:
            out.append((pc, tgt))
    return out


def backtrace(raw: bytes, md: Cs, pc: int, limit: int = 40) -> dict:
    """从调用点向前找 r0 / r1 的最近一次可解析赋值。

    返回 {"r0": val|None, "r1": val|None}；None 表示没找到（运行时才知道）。
    """
    regs: dict[str, int | None] = {"r0": None, "r1": None}
    start = max(0x08000000, pc - limit * 4)
    code = raw[start - 0x08000000: pc - 0x08000000]
    insns = list(md.disasm(code, start))
    for ins in reversed(insns):
        m, ops = ins.mnemonic, ins.op_str
        if m in ("push", "pop"):
            break
        if m == "ldr" and "[pc" in ops:
            try:
                rX = ops.split(",")[0].strip()
                imm = int(ops.split("#0x")[1].rstrip("]"), 16)
            except Exception:
                continue
            if rX in regs and regs[rX] is None:
                tgt = ((ins.address + 4) & ~3) + imm
                regs[rX] = u32(raw, tgt)
        elif m == "adds" and "#" in ops and len(ops.split(",")) == 3:
            try:
                dst, src, imm = [s.strip() for s in ops.split(",")]
                imm_v = int(imm.lstrip("#"), 0)
            except Exception:
                continue
            if dst in regs and regs[dst] is None and src in regs and regs[src] is not None:
                regs[dst] = (regs[src] + imm_v) & 0xFFFFFFFF
        elif m == "movs" and len(ops.split(",")) == 2:
            dst, imm = [s.strip() for s in ops.split(",")]
            if dst in regs and regs[dst] is None and imm.startswith("#"):
                try:
                    regs[dst] = int(imm.lstrip("#"), 0)
                except Exception:
                    pass
        if regs["r0"] is not None and regs["r1"] is not None:
            break
    return regs


def classify(dst: int | None, size: int) -> dict:
    if dst is None:
        return {"zone": "未知", "cb": -1}
    if not (VRAM_BG0 <= dst < 0x06018000):
        return {"zone": f"非 VRAM（0x{dst:08X}）", "cb": -1}
    cb = (dst - VRAM_BG0) // 0x4000
    off = dst - (VRAM_BG0 + cb * 0x4000)
    t0 = off // 32
    t1 = (off + size - 1) // 32 if size > 0 else t0
    info = {"zone": f"cb{cb}+0x{off:03X}", "cb": cb, "t0": t0, "t1": t1, "span": t1 - t0 + 1}
    # 0x0600F000..0x06010000 = screenblock 30/31（tilemap 区），与 cb3 的 t384..t511 物理重叠
    if 0x0600F000 <= dst < 0x06010000:
        info["note"] = "⚠sb30/31(tilemap 区)⇔cb3 t384..t511"
    pool = V10_POOL.get(cb)
    if pool and t1 >= pool[0] and t0 < pool[1]:
        info["pool_conflict"] = f"cb{cb}[{pool[0]},{pool[1]})"
    return info


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="静态预演 LZ77→VRAM 调用的 (源,目的,大小)")
    ap.add_argument("--cb2cb3", action="store_true", help="只列 cb2/cb3 目标")
    ap.add_argument("--json", help="同时写 JSON")
    args = ap.parse_args(argv)

    raw = load_rom()
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    md.detail = False
    calls = scan_calls(raw, md)
    print(f"全 ROM 「bl → LZ77UnCompVram」调用点：{len(calls)} 处\n")

    rows = []
    for pc, tgt in calls:
        regs = backtrace(raw, md, pc)
        src, dst = regs["r0"], regs["r1"]
        size = lz77_size(raw, src) if src else -1
        info = classify(dst, size)
        rows.append({"site": pc, "via": CALL_TARGETS[tgt], "src": src, "dst": dst,
                     "size": size, **info})

    shown = [r for r in rows if r["cb"] in (2, 3)] if args.cb2cb3 else rows
    print(f"{'调用点':>10} {'经':<18} {'源':>10} {'大小':>7} {'目的地':>18} "
          f"{'覆盖 tile':<16} 冲突 / 备注")
    print("-" * 108)
    for r in shown:
        ss = f"{r['size']}B" if r["size"] > 0 else "?"
        dv = f"0x{r['dst']:08X}" if r["dst"] else "?"
        if r["cb"] >= 0:
            span = f"t{r['t0']}..t{r['t1']}({r['span']})"
        else:
            span = ""
        star = "★" if r["cb"] in (2, 3) else " "
        note = r.get("pool_conflict", "") or r.get("note", "")
        print(f"0x{r['site']:08X} {r['via']:<18} {(hex(r['src']) if r['src'] else '?'):>10} "
              f"{ss:>7} {dv:>18} {span:<16} {star}{note}")

    c2 = [r for r in rows if r["cb"] == 2]
    c3 = [r for r in rows if r["cb"] == 3]
    sb = [r for r in rows if "note" in r]
    print(f"\n合计：{len(rows)} 处 → cb2 {len(c2)} / cb3 {len(c3)} / "
          f"其他（非 VRAM 或未解出）{len(rows) - len(c2) - len(c3)}"
          f"｜其中 sb30/31（tilemap 区）{len(sb)} 处")
    conf = [r for r in rows if "pool_conflict" in r]
    if conf:
        print("\n🔴 与 v10 计划池相交的装载：")
        for r in conf:
            print(f"  0x{r['site']:08X} → cb{r['cb']} t{r['t0']}..t{r['t1']}（{r['span']} tile,"
                  f" {r['size']}B）⇒ 冲突 {r['pool_conflict']}")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nJSON → {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
