#!/usr/bin/env python3
"""从 SaveBlock1 里读 ObjectEventTemplate 数组（含 script 指针），定位可对话 NPC。

═══════════════════════════════════════════════════════════════════════════
【为什么改读 template 而不是运行时 gObjectEvents】
① 运行时结构在日版偏移不确定（实测 gObjectEvents@0x030048A0 读出来是垃圾，
   0x03004800 处解出 0x24 步长的坐标，但那几个坐标都不是可对话 NPC）。
② **template 是存档数据，偏移由 SaveBlock1 布局固定**，且权威源码给了明确注释：

     struct SaveBlock1 {
         ...
         /*0x9E0*/  struct ObjectEvent objectEvents[OBJECT_EVENTS_COUNT];
         /*0xC20*/  struct ObjectEventTemplate objectEventTemplates[64];
         ...
     };

   而 ObjectEventTemplate（pokeruby）：
     +0x00 u8 localId
     +0x01 u8 mapNum
     +0x02 u8 mapGroup
     +0x03 u8 spriteId/graphicsId
     +0x04 s16 x
     +0x06 s16 y
     +0x08 u8 elevation
     +0x09 u8 movementType
     +0x0A u8 trainerType
     +0x0B u8 range
     +0x0C u32 script          ← ★ 非 0 就是可交互（对话/告示牌）
     +0x10 u16 flagId
     ...

   ⇒ **script != 0 的对象才是能按 A 触发的东西**。这就是要找的。

【本脚本】读指定 .sav 的 SaveBlock1+0xC20 起 64 * 0x18 字节，
  按上面布局解出 (localId, x, y, script)，把 script 非 0 的列出来。
  这些坐标就是「站到相邻格按 A 一定能触发」的位置。

用法：
  python scripts/dump_obj_templates.py [sav路径]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot" / "tools"))
from savedit import rebuild, SB1_OFF  # noqa: E402

O_TEMPLATES = 0xC20
TPL_COUNT = 64
TPL_SIZE = 0x18          # 0x18 是 pokeruby 的 sizeof(ObjectEventTemplate)

# 字段偏移（pokeruby include/global.fieldmap.h）
F_LOCALID, F_MAPNUM, F_MAPGROUP, F_GFX = 0, 1, 2, 3
F_X, F_Y = 4, 6
F_ELEV, F_MOVE, F_TRAINER, F_RANGE = 8, 9, 10, 11
F_SCRIPT = 0x0C
F_FLAG = 0x10


def u16(b, o): return int.from_bytes(b[o:o + 2], "little")
def s16(b, o): return int.from_bytes(b[o:o + 2], "little", signed=True)
def u32(b, o): return int.from_bytes(b[o:o + 4], "little")


def main() -> int:
    sav = (Path(sys.argv[1]) if len(sys.argv) > 1
           else ROOT / "work" / "_probe" / "teleport.sav")
    if not sav.is_file():
        print(f"[ERR] 找不到 {sav}")
        return 1
    logical, _ = rebuild(sav.read_bytes())
    sb1 = logical[SB1_OFF:SB1_OFF + 0x3AC0]
    print(f"{sav.name}")

    pos_x, pos_y = s16(sb1, 0), s16(sb1, 2)
    mg, mn = sb1[4], sb1[5]
    print(f"存档位置 = ({pos_x},{pos_y})  map={mg}:{mn}\n")

    print(f"{'i':>2} {'localId':>7} {'map':>7} {'pos':>10} {'gfx':>4} "
          f"{'move':>4} {'tr':>3} {'script':>12} {'flag':>6}")
    print("-" * 78)
    n_script = 0
    hits = []
    for i in range(TPL_COUNT):
        o = O_TEMPLATES + i * TPL_SIZE
        t = sb1[o:o + TPL_SIZE]
        if len(t) < TPL_SIZE:
            break
        x, y = s16(t, F_X), s16(t, F_Y)
        script = u32(t, F_SCRIPT)
        flag = u16(t, F_FLAG)
        lid = t[F_LOCALID]
        tg, tn = t[F_MAPGROUP], t[F_MAPNUM]
        # 全是 0 的是空槽
        if x == 0 and y == 0 and script == 0 and lid == 0 and t[F_GFX] == 0:
            continue
        has_script = 0x08000000 <= script < 0x0A000000
        mark = "  ★ 可交互" if has_script else ""
        if has_script:
            n_script += 1
            hits.append((lid, x, y, script))
        print(f"{i:>2} {lid:>7} {tg:>3}:{tn:<3} ({x:>3},{y:>3}) "
              f"{t[F_GFX]:>4} {t[F_MOVE]:>4} {t[F_TRAINER]:>3} "
              f"0x{script:08X} {flag:>6}{mark}")

    print(f"\n可交互对象（script 指向 ROM）= {n_script} 个")
    if hits:
        print("\n站到下列坐标的**相邻格**并按 A 一定能触发：")
        for lid, x, y, sc in hits:
            print(f"  localId={lid:<3} ({x},{y})  script=0x{sc:08X}")
            print(f"    建议落点：({x},{y+1}) 朝 UP，或 ({x+1},{y}) 朝 LEFT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
