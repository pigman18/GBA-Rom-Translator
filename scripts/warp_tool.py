#!/usr/bin/env python3
"""warp 工具：给存档植入「传送术」技能，运行时配合 lastHealLocation 实现精确跳图。

═══════════════════════════════════════════════════════════════════════════
【已跑通的完整方案（2026-11-03 实测成功）】
═══════════════════════════════════════════════════════════════════════════
目标：让 bot 能跳到任意地图做场景验证，不再依赖人工走位。

两步组合：

**Step 1（离线，一次性）** 给某只宝可梦植入「テレポート（传送术，moveId=100）」
  用本脚本 `--apply`，产出一份新 .sav。之后所有场景都用这份存档读档。

**Step 2（运行时，每个场景）** bot 场景里：
  ```lua
  api.poke{                       -- ① 设目的地
      { sb1 = 0x1C, width = 1, value = group },   -- lastHealLocation.mapGroup
      { sb1 = 0x1D, width = 1, value = num   },   -- lastHealLocation.mapNum
      { sb1 = 0x1E, width = 1, value = 0xFF  },   -- warpId = -1
      { sb1 = 0x20, width = 2, value = x     },   -- x (s16)
      { sb1 = 0x22, width = 2, value = y     },   -- y (s16)
  }
  ```
  然后在菜单里对该宝可梦执行「使用技能/查看能力」那一路按键，
  游戏会走 `Overworld_ResetStateAfterTeleport → WarpIntoMap`
  ⇒ **精确落到 (x, y)，实测坐标一字不差**。

═══════════════════════════════════════════════════════════════════════════
【权威结构（pret/pokeruby include/global.h）—— 别再猜偏移】
═══════════════════════════════════════════════════════════════════════════
    struct WarpData {
        s8  mapGroup;   // +0
        s8  mapNum;     // +1
        s8  warpId;     // +2
        s16 x, y;       // +4(x)  +6(y)     ← s16 对齐，不是 +5！
    };
    struct SaveBlock1 {
        /*0x00*/ struct Coords16 pos;
        /*0x04*/ struct WarpData location;
        /*0x0C*/ struct WarpData warp1;
        /*0x14*/ struct WarpData dynamicWarp;
        /*0x1C*/ struct WarpData lastHealLocation;   ← 我们用这个
        ...
        /*0x234*/ u8 playerPartyCount;
        /*0x238*/ struct Pokemon playerParty[6];
    };

⚠ 我曾把 y 写到 +0x05，结果 y 覆盖了 x 的高字节：
  x 变成 0x0744 = 1860，角色落进水里。
  正确是 x@+0x04(s16)、y@+0x06(s16)。

═══════════════════════════════════════════════════════════════════════════
【队伍加密三层（改技能必须全对，缺一个游戏就判数据损坏）】
═══════════════════════════════════════════════════════════════════════════
① XOR：key = pid ^ otid，每 4 字节异或。往返 6/6 通过。
② 子结构顺序：由 pid%24 决定。
   **日版与 pokeruby 的 gSubstructOrder 有 3/5 错位**（实测），
   所以用「PP 必须 <= 上限」打分反推，见 scripts/derive_substruct_order.py。
③ 校验子 checkword：
   **日版 = (四个 slot 的 u16 和 的累加) & 0xFFFF**，写在 +0x1C（单个 u16），
   +0x1E 固定 0。
   ⚠ pokeruby 说是「异或 + 4 个同值 u16」—— 照抄会把数据写坏。
   6/6 命中，见 scripts/verify_checkword_algo.py。

用法：
  python scripts/warp_tool.py --check                 # 只体检，不改
  python scripts/warp_tool.py --apply --out x.sav     # 植入传送术
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot" / "tools"))
from savedit import rebuild, SB1_OFF, sector_checksum, SECTOR, FOOTER  # noqa: E402

MON = 100
O_PARTY, O_COUNT = 0x238, 0x234
TELEPORT_MOVE = 100
TELEPORT_PP = 20

# 实测得到的 pid%24 → Attacks 子结构所在 slot（覆盖本队伍出现的余数）
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
    return ATTACKS_SLOT.get(m, ORDER[m].index(1))


def decrypt(m: bytes):
    pid, otid = u32(m, 0), u32(m, 4)
    key = pid ^ otid
    raw = bytearray(m[0x20:0x50])
    for i in range(0, 48, 4):
        raw[i:i + 4] = (u32(raw, i) ^ key).to_bytes(4, "little")
    return pid, otid, key, bytes(raw)


def encrypt(raw: bytes, key: int) -> bytes:
    out = bytearray(raw)
    for i in range(0, 48, 4):
        out[i:i + 4] = (u32(raw, i) ^ key).to_bytes(4, "little")
    return bytes(out)


def checkword(raw: bytes) -> int:
    total = 0
    for slot in range(4):
        seg = raw[slot * 12:(slot + 1) * 12]
        s = sum(u16(seg, k) for k in range(0, 12, 2)) & 0xFFFF
        total = (total + s) & 0xFFFF
    return total


def read_moves(m: bytes):
    pid, _, _, raw = decrypt(m)
    slot = attacks_slot(pid)
    o = slot * 12
    return ([u16(raw, o + k * 2) for k in range(4)], list(raw[o + 8:o + 12]), slot)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sav", default=str(ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.sav"))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--mon", type=int, default=1)
    a = ap.parse_args()

    sav = Path(a.sav)
    buf = sav.read_bytes()
    logical, where = rebuild(buf)
    sb1 = logical[SB1_OFF:SB1_OFF + 0x3AC0]
    cnt = sb1[O_COUNT]
    print(f"{sav.name}\n  partyCount={cnt}")

    # ── 体检：逐只验证 XOR / 顺序 / 校验子 ───────────────────────────────
    print("\n[体检]")
    bad = 0
    for i in range(cnt):
        m = sb1[O_PARTY + i * MON: O_PARTY + (i + 1) * MON]
        pid, otid, key, raw = decrypt(m)
        cw_calc = checkword(raw)
        cw_file = u16(m, 0x1C)
        moves, pps, slot = read_moves(m)
        ok = (cw_calc == cw_file) and (pps[0] > 0 or moves[0] == 0)
        if not ok:
            bad += 1
        print(f"  #{i} lv={m[0x54]:3d} pid%24={pid % 24:2d} slot={slot} "
              f"moves={moves} pp={pps} "
              f"checkword {cw_file:04X}/{cw_calc:04X} {'✓' if cw_calc == cw_file else '✗'}")
    print(f"  校验子不一致 {bad} 只")

    # ── 植入传送术 ───────────────────────────────────────────────────────
    i = a.mon
    m = bytearray(sb1[O_PARTY + i * MON: O_PARTY + (i + 1) * MON])
    pid, _, key, raw = decrypt(bytes(m))
    slot = attacks_slot(pid)
    o = slot * 12
    old_moves = [u16(raw, o + k * 2) for k in range(4)]
    print(f"\n[植入] #{i}  Attacks@slot{slot}")
    print(f"  改前 moves={old_moves}")

    raw_b = bytearray(raw)
    raw_b[o:o + 2] = TELEPORT_MOVE.to_bytes(2, "little")
    raw_b[o + 8] = TELEPORT_PP
    cw = checkword(bytes(raw_b))
    print(f"  改后 moves={[u16(raw_b, o + k * 2) for k in range(4)]}  checkword=0x{cw:04X}")

    new_m = bytearray(m)
    new_m[0x20:0x50] = encrypt(bytes(raw_b), key)
    new_m[0x1C:0x1E] = cw.to_bytes(2, "little")
    new_m[0x1E:0x20] = b"\x00\x00"

    # 回读
    chk_moves, chk_pp, _ = read_moves(bytes(new_m))
    print(f"  回读 move[0]={chk_moves[0]}  {'✓' if chk_moves[0] == TELEPORT_MOVE else '✗'}")

    if not a.apply:
        print("\n[dry-run] 未写盘。加 --apply --out <新文件> 才写。")
        return 0
    if not a.out:
        print("[ERR] --apply 需要 --out")
        return 2

    out = bytearray(buf[:131072])
    logical[SB1_OFF + O_PARTY + i * MON: SB1_OFF + O_PARTY + (i + 1) * MON] = new_m
    for sid in range(1, (0x1000 + 0x3AC0 + SECTOR - 1) // SECTOR):
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
    print(f"\n[OK] {a.out}")
    print("     场景里 poke lastHealLocation(group,num,x,y) 后用该宝可梦的传送即可跳图")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
