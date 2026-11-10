#!/usr/bin/env python3
"""把队伍里一只宝可梦的第 1 个技能改成「传送术」，并正确处理加密与校验子。

── 目标 ────────────────────────────────────────────────────────────────
已实测：
  ✅ `lastHealLocation`(SB1+0x1C) 写入能保住（写 Route118 后走出门仍是 00 21 ff 00 44 07）
  ✅ 队伍加密可解（6/6 只都能读对技能与 PP，见 derive_substruct_order.py）
  ✅ 传送术(テレポート, moveId=100) 的野外效果 = 回到 lastHealLocation（源码
     Overworld_ResetStateAfterTeleport → WarpIntoMap 路径）

⇒ 因此「改技能 + 改 lastHealLocation + 野外用传送术」= 精确跳图。
  这条路不需要打仗、不需要造白屏、不需要改 HP。

── Gen3 加密的三层 ────────────────────────────────────────────────────
① 4 字节 XOR（key = pid ^ otid）—— 本脚本已实现
② 子结构顺序（由 pid%24 决定）—— **日版与 pokeruby 表有 3/5 错位，
   必须用实测归属**，本脚本用 ATTACKS_SLOT 表
③ 校验子（checkword）：4 个 u16 存在 +0x1C..0x23，
   = 各子结构按 u16 求和后异或。改数据必须重算，否则游戏判为坏数据。

⚠ 本脚本默认 **--dry-run**，只打印将要写什么，不落盘。
   要真写加 --apply。改完请另存新文件，不要覆盖原存档。

用法：
  python scripts/set_teleport_move.py --dry-run
  python scripts/set_teleport_move.py --apply --out work/teleport.sav
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot" / "tools"))
from savedit import rebuild, SB1_OFF, sector_checksum, SECTOR, FOOTER, SIG  # noqa: E402

MON = 100
O_PARTY, O_COUNT = 0x238, 0x234
TELEPORT_MOVE = 100
TELEPORT_PP = 20

# 实测得到的「pid%24 → Attacks 子结构所在 slot」。
# 只覆盖本项目这支队伍实际出现的 5 个余数（3,7,12,13,15），
# 其余余数回退到 pokeruby 表（并用 score 校验兜底）。
ATTACKS_SLOT = {3: 3, 7: 0, 12: 2, 13: 3, 15: 1}

ORDER = [
    [0, 1, 2, 3], [0, 1, 3, 2], [0, 2, 1, 3], [0, 3, 1, 2],
    [0, 2, 3, 1], [0, 3, 2, 1], [1, 0, 2, 3], [1, 0, 3, 2],
    [2, 0, 1, 3], [3, 0, 1, 2], [2, 0, 3, 1], [3, 0, 2, 1],
    [1, 2, 0, 3], [1, 3, 0, 2], [2, 1, 0, 3], [3, 1, 0, 2],
    [2, 3, 0, 1], [3, 2, 0, 1], [1, 2, 3, 0], [1, 3, 2, 0],
    [2, 1, 3, 0], [3, 1, 2, 0], [2, 3, 1, 0], [3, 2, 1, 0],
]


def u32(b, o): return int.from_bytes(b[o:o + 4], "little")
def u16(b, o): return int.from_bytes(b[o:o + 2], "little")


def attacks_slot(pid: int) -> int:
    m = pid % 24
    if m in ATTACKS_SLOT:
        return ATTACKS_SLOT[m]
    return ORDER[m].index(1)


def decrypt_block(m: bytes):
    pid, otid = u32(m, 0), u32(m, 4)
    key = pid ^ otid
    raw = bytearray(m[0x20:0x50])
    for i in range(0, 48, 4):
        raw[i:i + 4] = (u32(raw, i) ^ key).to_bytes(4, "little")
    return pid, otid, key, raw


def encrypt_block(raw: bytes, key: int) -> bytes:
    out = bytearray(raw)
    for i in range(0, 48, 4):
        out[i:i + 4] = (u32(raw, i) ^ key).to_bytes(4, "little")
    return bytes(out)


def checkword(m: bytes, subs_by_slot: bytes) -> int:
    """日版校验子算法（6/6 实测命中，见 verify_checkword_algo.py）：
       checkword = (sum(四个 slot 的 u16 和)) & 0xFFFF
    写在 +0x1C（u16），+0x1E 固定 0。
    ⚠ pokeruby 说是「异或」且 4 个 u16 同值 —— **日版不是**：
      +0x1C 只有一个 u16，且算法是累加。照抄美版会写坏。"""
    total = 0
    for slot in range(4):
        seg = subs_by_slot[slot * 12:(slot + 1) * 12]
        s = 0
        for k in range(0, 12, 2):
            s = (s + u16(seg, k)) & 0xFFFF
        total = (total + s) & 0xFFFF
    return total & 0xFFFF


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sav", default=str(ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.sav"))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--mon", type=int, default=1, help="用第几只（默认 1）")
    a = ap.parse_args()

    sav = Path(a.sav)
    buf = sav.read_bytes()
    logical, where = rebuild(buf)
    print(f"{sav.name}  partyCount={logical[SB1_OFF + O_COUNT]}")

    i = a.mon
    base = SB1_OFF + O_PARTY + i * MON
    m = bytearray(logical[base:base + MON])
    pid, otid, key, raw = decrypt_block(bytes(m))
    slot = attacks_slot(pid)
    print(f"\n目标：#{i}  pid={pid:08X} otid={otid:08X} pid%24={pid % 24}")
    print(f"      Attacks 在 slot {slot}")

    atk0 = slot * 12
    moves = [u16(raw, atk0), u16(raw, atk0 + 2), u16(raw, atk0 + 4), u16(raw, atk0 + 6)]
    pps = list(raw[atk0 + 8:atk0 + 12])
    print(f"      改前 moves={moves} pp={pps}")

    # 改：第 1 个技能 -> 传送术，PP 补足
    raw[atk0:atk0 + 2] = TELEPORT_MOVE.to_bytes(2, "little")
    raw[atk0 + 8] = TELEPORT_PP
    moves2 = [u16(raw, atk0), u16(raw, atk0 + 2), u16(raw, atk0 + 4), u16(raw, atk0 + 6)]
    pps2 = list(raw[atk0 + 8:atk0 + 12])
    print(f"      改后 moves={moves2} pp={pps2}")

    # 重算 checkword（存在 +0x1C，4 个 u16 = 8 字节）
    cw = checkword(bytes(m), bytes(raw))
    old_cw = [u16(m, 0x1C + k * 2) for k in range(4)]
    print(f"      checkword 旧={old_cw} 新={cw:04X}")

    enc = encrypt_block(bytes(raw), key)
    new_m = bytearray(m)
    new_m[0x20:0x50] = enc
    # 日版：checkword 是**一个** u16 在 +0x1C，+0x1E 固定 0
    new_m[0x1C:0x1E] = cw.to_bytes(2, "little")
    new_m[0x1E:0x20] = b"\x00\x00"

    # 回读校验：重新解密应能看到传送术
    chk_pid, _, _, chk_raw = decrypt_block(bytes(new_m))
    got = u16(chk_raw, slot * 12)
    print(f"\n回读校验：解密后 slot{slot} 第 1 技能 = {got}"
          f"  {'✓' if got == TELEPORT_MOVE else '✗'}")

    if not a.apply:
        print("\n[dry-run] 未写盘。确认无误后加 --apply --out <新文件>")
        return 0

    if not a.out:
        print("[ERR] --apply 需要 --out 指定新文件（不要覆盖原档）")
        return 2

    # 写回逻辑存档，再按扇区落到物理位置，重算 checksum
    out = bytearray(buf[:131072])
    logical[base:base + MON] = new_m
    touched = range(1, (0x1000 + 0x3AC0 + SECTOR - 1) // SECTOR)
    for sid in touched:
        if sid not in where:
            continue
        phys = where[sid]
        s = phys * SECTOR
        out[s:s + SECTOR] = logical[sid * SECTOR:(sid + 1) * SECTOR]
        ck = sector_checksum(bytes(out[s:s + SECTOR]))
        out[s + FOOTER + 2] = ck & 0xFF
        out[s + FOOTER + 3] = (ck >> 8) & 0xFF
    if len(buf) > 131072:
        out += buf[131072:]
    Path(a.out).write_bytes(bytes(out))
    print(f"\n[OK] 写出 {a.out}")
    print("     下一步：bot 场景里 poke lastHealLocation=目标图 → 野外用传送术")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
