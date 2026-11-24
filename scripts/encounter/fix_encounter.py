#!/usr/bin/env python3
"""固定遇敌工具集 —— 让「野生宝可梦是哪个物种」变成确定值。

# 为什么需要它

bot 场景对比 origin vs translated 时，战斗画面的对照前提是**两侧遇到同一只怪**。
历史上为了让遇敌确定，试过三种写法，全部失败（docs/POKEMON_RUBY_AXVJ00/30-问题与验证.md）：

  ① poke 一次 RNG + hunt 40 步        → 两侧对手不同
  ② 每走一格 poke 再 walk             → 两侧对手不同
  ③ poke → hunt → 转场后重钉 RNG      → 两侧对手不同

失败原因：poke 只决定**写入那一瞬**的 RNG。从写入到「遇敌判定」之间
还要跑几十帧（转场、走路、贴图加载都会消耗 RNG），钉得再勤也追不上。

另外「写死 gBattleMons species」也不行：那只改战斗内存里的一个字段，
不改变血条名字（名字来自 party 结构的 nickname），且会被战斗初始化覆盖。

# 本工具的做法：消灭随机性源头，而不是追着随机性跑

源码依据（pokeruby，权威）：

    src/wild_encounter.c:620  u16 GetLocalWildMon(bool8 *isWaterMon)
        return landMonsInfo->wildPokemon[ChooseWildMonIndex_Land()].species;

    src/wild_encounter.c:144  static u8 ChooseWildMonIndex_Land(void)
        u8 rand = Random() % ENCOUNTER_CHANCE_LAND_MONS_TOTAL;   // 100
        // rand 分成 12 档 → 返回 0..11

⇒ land 遇敌表有 **12 个槽**，RNG 只决定「选第几个槽」。
   **把 12 个槽全部改成同一 species**，那么无论 RNG 落哪一档，
   取出来的 species 都相同 —— 随机性被消灭，遇敌物种 100% 确定。

这比钉 RNG 稳定得多，而且不依赖任何时序。

# 表结构（pokeruby include/wild_encounter.h，本工具实测校验）

    struct WildPokemon       { u8 minLevel; u8 maxLevel; u16 species; }   // 4B
    struct WildPokemonInfo   { u8 encounterRate; u8 pad[3]; const struct WildPokemon *wildPokemon; }  // 8B
    struct WildPokemonHeader {
        u8 mapGroup; u8 mapNum; u8 pad[2];
        const struct WildPokemonInfo *landMonsInfo;      // +0x04
        const struct WildPokemonInfo *waterMonsInfo;     // +0x08
        const struct WildPokemonInfo *rockSmashMonsInfo; // +0x0C
        const struct WildPokemonInfo *fishingMonsInfo;   // +0x10
    };                                                                   // 20B

`gWildMonHeaders` 是 **ROM 里的 const 表**，没有 EWRAM 副本
（wild_encounter.c 直接下标索引 gWildMonHeaders[i]），
所以只能改 ROM 字节，不能运行时注入内存。

# 实测数据（日版 AXVJ，2026-11-24）

    Route110 (0:25) header @ 0x08379804
        land  info @ 0x08378700  rate=20  wildPokemon @ 0x083786D0 （12 槽）
        water info @ 0x0837871C  rate=4   wildPokemon @ 0x08378708
    原始 land 12 槽 species：
        288 337 367 337 354 43 354 367 309 309 353 353

# ⚠ 使用边界

改的是**测试用 ROM 副本**，不要写进正式产物：
    cp roms/origin/POKEMON_RUBY_AXVJ00.gba work/_fixtest/origin_nXXX.gba
    cp roms/outputs/*_translated.gba      work/_fixtest/trans_nXXX.gba
    两侧都要打同一份补丁，否则一侧固定、另一侧混合，对照不成立。

# 命令行用法

    # 查看某地图的遇敌表（不改任何文件）
    python scripts/encounter/fix_encounter.py probe --map 0:25

    # 列出所有含目标物种的地图（找去哪触发）
    python scripts/encounter/fix_encounter.py find --species 354

    # 给测试 ROM 打补丁（12 槽全 = 目标物种）
    python scripts/encounter/fix_encounter.py apply --map 0:25 --species 354 \
        --rom work/_fixtest/origin_n354.gba

    # 一次给 origin + translated 两份都打
    python scripts/encounter/fix_encounter.py apply --map 0:25 --species 354 \
        --rom work/_fixtest/origin_n354.gba work/_fixtest/trans_n354.gba
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BASE = 0x08000000
SECTION_NAMES = ("land", "water", "rockSmash", "fishing")
LAND_SLOTS = 12
SLOT_BYTES = 4
HEADER_BYTES = 20


def load_rom(path: Path) -> bytes:
    if not path.exists():
        sys.exit(f"[ERR] ROM 不存在: {path}")
    return path.read_bytes()


def find_headers(d: bytes, group: int, num: int) -> list[int]:
    """扫 ROM 找 mapGroup:mapNum 对应的 WildPokemonHeader 地址。

    判据（不猜地址）：4 个指针字段要么 NULL，要么落在 ROM 区
    （0x08000000..0x0A000000）。翻译流程不会碰这张表
    （实测产物与 origin 该区逐字节相同），所以扫 origin ROM 得地址后
    可以直接套用到 translated ROM。
    """
    hits = []
    for a in range(0x200000, min(len(d) - 24, 0x700000), 4):
        if d[a] != group or d[a + 1] != num:
            continue
        ptrs = [struct.unpack_from("<I", d, a + 4 + i * 4)[0] for i in range(4)]
        ok = sum(1 for p in ptrs if p == 0 or 0x08000000 <= p < 0x0A000000)
        if ok >= 3:
            hits.append(BASE + a)
    return hits


def read_section_ptrs(d: bytes, header: int) -> list[int]:
    o = header - BASE
    return [struct.unpack_from("<I", d, o + 4 + i * 4)[0] for i in range(4)]


def read_info(d: bytes, info: int) -> tuple[int, int]:
    """返回 (encounterRate, wildPokemon 指针)。"""
    o = info - BASE
    return d[o], struct.unpack_from("<I", d, o + 4)[0]


def read_slots(d: bytes, wp: int, n: int = LAND_SLOTS) -> list[tuple[int, int, int]]:
    out = []
    for k in range(n):
        o = wp - BASE + k * SLOT_BYTES
        mn, mx = struct.unpack_from("<BB", d, o)
        sp = struct.unpack_from("<H", d, o + 2)[0]
        out.append((mn, mx, sp))
    return out


def parse_map(s: str) -> tuple[int, int]:
    try:
        g, n = s.split(":")
        return int(g), int(n)
    except Exception:
        sys.exit(f"[ERR] --map 格式应为 group:num（如 0:25），收到 {s!r}")


def resolve_land(d: bytes, group: int, num: int) -> tuple[int, int, int, int]:
    """定位 land 段，返回 (header, info, rate, wildPokemonPtr)。"""
    hits = find_headers(d, group, num)
    if not hits:
        sys.exit(f"[ERR] map {group}:{num} 的 WildPokemonHeader 未找到")
    header = hits[0]
    if len(hits) > 1:
        print(f"[!] {len(hits)} 个候选，取 0x{header:08X}（其余："
              + ", ".join(f"0x{h:08X}" for h in hits[1:]) + "）")
    infos = read_section_ptrs(d, header)
    info = infos[0]          # land
    if info == 0:
        sys.exit(f"[ERR] map {group}:{num} 没有 land 遇敌表")
    rate, wp = read_info(d, info)
    return header, info, rate, wp


def cmd_probe(args) -> int:
    group, num = parse_map(args.map)
    d = load_rom(Path(args.rom))
    header, info, rate, wp = resolve_land(d, group, num)
    print(f"map {group}:{num}")
    print(f"  header       0x{header:08X}")
    print(f"  land info    0x{info:08X}   encounterRate={rate}%")
    print(f"  wildPokemon  0x{wp:08X}   （{LAND_SLOTS} 槽 × {SLOT_BYTES}B）")
    print()
    slots = read_slots(d, wp)
    uniq = sorted({s[2] for s in slots})
    for k, (mn, mx, sp) in enumerate(slots):
        print(f"  slot{k:2d}  lv{mn:3d}-{mx:<3d}  species={sp}")
    print()
    print(f"  去重物种 {len(uniq)} 个：{uniq}")
    if len(uniq) > 1:
        print("  ⇒ 当前表会随机出多种怪；要固定请用 apply 子命令")
    return 0


def cmd_find(args) -> int:
    """扫全 ROM 所有 header，列出 land 表里含目标物种的地图。"""
    d = load_rom(Path(args.rom))
    target = args.species
    found = []
    seen = set()
    for a in range(0x200000, min(len(d) - 24, 0x700000), 4):
        group, num = d[a], d[a + 1]
        if group == 0xFF:
            continue
        if (group, num) in seen:
            continue
        ptrs = [struct.unpack_from("<I", d, a + 4 + i * 4)[0] for i in range(4)]
        ok = sum(1 for p in ptrs if p == 0 or 0x08000000 <= p < 0x0A000000)
        if ok < 3:
            continue
        seen.add((group, num))
        header = BASE + a
        try:
            infos = read_section_ptrs(d, header)
            if infos[0] == 0:
                continue
            rate, wp = read_info(d, infos[0])
            if not (0x08000000 <= wp < 0x0A000000):
                continue
            slots = read_slots(d, wp)
        except Exception:
            continue
        sp_list = [s[2] for s in slots]
        if target in sp_list:
            found.append((group, num, rate, header, sp_list.count(target)))
    if not found:
        print(f"未找到 land 表含 species={target} 的地图")
        return 1
    print(f"land 表含 species={target} 的地图（{len(found)} 个）：")
    for g, n, rate, h, cnt in found:
        print(f"  {g}:{n:<3d}  rate={rate:3d}%  出现 {cnt}/12 槽  header=0x{h:08X}")
    return 0


def cmd_apply(args) -> int:
    group, num = parse_map(args.map)
    roms = [Path(p) for p in args.rom] if args.rom else [DEFAULT_ROM]

    # 用第一份 ROM 定位（表地址在各版本相同，已实测产物与 origin 一致）
    d0 = load_rom(roms[0])
    header, info, rate, wp = resolve_land(d0, group, num)
    slots = read_slots(d0, wp)

    print(f"map {group}:{num}  header=0x{header:08X}  land=0x{wp:08X}  rate={rate}%")
    print("原始 12 槽：")
    for k, (mn, mx, sp) in enumerate(slots):
        mark = " ★目标" if sp == args.species else ""
        print(f"  slot{k:2d}  lv{mn}-{mx}  species={sp}{mark}")

    patch = bytearray()
    for mn, mx, _sp in slots:
        lv, lv2 = (args.level, args.level) if args.level > 0 else (mn, mx)
        patch += bytes((lv & 0xFF, lv2 & 0xFF)) + struct.pack("<H", args.species)

    print(f"\n补丁（12 槽 → species={args.species}"
          + (f"，lv={args.level}" if args.level else "") + "）：")
    print("  " + " ".join(f"{b:02X}" for b in patch))

    if args.dry_run:
        print("\n[dry-run] 未写入任何文件")
        return 0

    off = wp - BASE
    for rp in roms:
        buf = bytearray(load_rom(rp))
        # 校验该 ROM 同位置确实是同一张表（防止补丁打到错误的 ROM）
        cur = read_slots(bytes(buf), wp)
        if [s[2] for s in cur] != [s[2] for s in slots]:
            print(f"[ERR] {rp} 的遇敌表与定位 ROM 不一致，拒绝写入")
            print(f"      该处 species={[s[2] for s in cur]}")
            print(f"      定位 species={[s[2] for s in slots]}")
            return 2
        buf[off:off + len(patch)] = patch
        rp.write_bytes(bytes(buf))
        print(f"[OK] 已写入 {rp}")

    print(f"\n⇒ 这些 ROM 上 map {group}:{num} 的野生遇敌 species 已固定为 {args.species}")
    print("   无需再钉 RNG / 写 gBattleMons。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="固定遇敌：把 land 遇敌表 12 槽全改成同一物种",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("probe", help="查看某地图的遇敌表")
    p1.add_argument("--map", default="0:25")
    p1.add_argument("--rom", default=str(DEFAULT_ROM))
    p1.set_defaults(func=cmd_probe)

    p2 = sub.add_parser("find", help="列出 land 表含目标物种的地图")
    p2.add_argument("--species", type=int, required=True)
    p2.add_argument("--rom", default=str(DEFAULT_ROM))
    p2.set_defaults(func=cmd_find)

    p3 = sub.add_parser("apply", help="给 ROM 打补丁（12 槽全 = 目标物种）")
    p3.add_argument("--map", default="0:25")
    p3.add_argument("--species", type=int, required=True)
    p3.add_argument("--level", type=int, default=0, help="固定等级（0=保持原值）")
    p3.add_argument("--rom", nargs="+", help="一份或多份 ROM（两侧都要打）")
    p3.add_argument("--dry-run", action="store_true")
    p3.set_defaults(func=cmd_apply)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
