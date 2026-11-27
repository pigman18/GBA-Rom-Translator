"""从美版汉化 ROM 提取与我们同位置的文本，做逐条对照。

【思路】
texts.json 里每条都有 address（产物 ROM 中的绝对地址）与 original（日文）。
美版汉化（work/_us_cn.gba）是同一代 Ruby 的汉化，文本表结构相同，
但地址可能整体偏移。所以不能直接按 address 读，而是：

  1. 用 texts.json 的 original（日文）在美版 ROM 里搜对应的**编码**？
     不行 —— 美版汉化已经把日文换成中文了。

  2. 正确做法：用我们产物的地址读美版，先验证「该处是文本」，
     再解码看内容是否是有意义的中文。若偏移整体一致就直接可用。

【编码】
美版汉化用 F7 00 hi lo（4B/字），hi/lo 经 lead_adjust 映射到 7006 字符集，
码表见 work/_us_cn_ref/PMRUS_TBL.txt（GBK，key=0x0100..0x1E5D）。

用法：
    python scripts/us_cn/extract_us_cn_text.py --module 战斗 --limit 20
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
US_ROM = ROOT / "work" / "_us_cn.gba"
TBL = ROOT / "work" / "_us_cn_ref" / "PMRUS_TBL.txt"

BASE = 0x08000000


def load_tbl() -> dict[int, str]:
    """PMRUS_TBL.txt: `0100=啊`，GBK 编码。"""
    raw = TBL.read_bytes().decode("gbk", errors="replace")
    out: dict[int, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        try:
            out[int(k, 16)] = v
        except ValueError:
            continue
    return out


def read_text(rom: bytes, addr: int, tbl: dict[int, str], max_bytes: int = 400) -> str:
    """从 addr 读一段 F7 00 hi lo 文本，遇到 FF 停止。"""
    off = addr - BASE
    if off < 0 or off >= len(rom):
        return ""
    out: list[str] = []
    i = off
    end = min(len(rom), off + max_bytes)
    while i < end:
        b = rom[i]
        if b == 0xFF:
            break
        if b == 0xF7 and i + 3 < len(rom) and rom[i + 1] == 0:
            hi, lo = rom[i + 2], rom[i + 3]
            idx = (hi << 8) | lo
            out.append(tbl.get(idx, f"<{idx:04X}>"))
            i += 4
            continue
        if b == 0x00:
            out.append(" ")
            i += 1
            continue
        if b in (0xFE,):
            out.append("\n")
            i += 1
            continue
        if b == 0xFB:
            out.append("\\p")
            i += 1
            continue
        if b == 0xFC:
            # 控制码 + 2 参数
            i += 3
            continue
        if b in (0xFD,):
            i += 1
            continue
        out.append(f"<{b:02X}>")
        i += 1
    return "".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--module", default=None, help="只处理该模块（如 战斗/招式）")
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--offset", type=lambda x: int(x, 0), default=0,
                    help="ROM 地址偏移（若美版整体偏移则指定）")
    a = ap.parse_args()

    tbl = load_tbl()
    rom = US_ROM.read_bytes()
    data = json.loads(TEXTS.read_text("utf-8"))
    entries = data["entries"]

    n_ok = n_bad = 0
    shown = 0
    for e in entries:
        mod = e.get("module", "")
        if a.module and a.module not in mod:
            continue
        addr_s = e.get("address")
        if not addr_s:
            continue
        addr = int(addr_s, 16) + a.offset
        jp = e.get("original", "")
        cn = read_text(rom, addr, tbl)
        # 判据：解出的内容里有中文（说明该处确实是美版汉化文本）
        has_cjk = any("\u4e00" <= c <= "\u9fff" for c in cn)
        if has_cjk:
            n_ok += 1
            if shown < a.limit:
                print(f"[{mod}] {addr_s}")
                print(f"  JP: {jp[:70]}")
                print(f"  US: {cn[:70]}")
                shown += 1
        else:
            n_bad += 1

    print(f"\n命中中文 {n_ok} 条，未命中 {n_bad} 条")
    if n_ok == 0:
        print("⇒ 美版地址与产物不一致，需要先定位偏移量。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
