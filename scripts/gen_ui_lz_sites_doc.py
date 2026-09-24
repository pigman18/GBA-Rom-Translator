#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""gen_ui_lz_sites_doc.py — 生成 docs/UI_LZ_SITES.md（常规 UI 装载点全表）。

数据来源 = 现算（不抄）：
  · `scripts/lz77_args.py` 的 Thumb 顺序解码 → 每个 `bl LZ77UnCompVram/Wram`
    站点的 (src, 解压大小, 砖数, dst)
  · 原盘 ROM 的 LZ77 头（byte0=0x10，byte1..3 = 解压后字节数）
按 dst 归组输出 markdown。

用法：python scripts/gen_ui_lz_sites_doc.py
"""
from __future__ import annotations

import importlib.util
import io
import os
import sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("lz77_args", os.path.join(HERE, "lz77_args.py"))
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)

OUT = os.path.join(ROOT, "docs", "UI_LZ_SITES.md")
ROM = os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba")

# 「野外 tileset」的源区（实测：全部野外 tileset blob 都在 0x087Fxxxx，
#  其余 UI 美术的 src 最大只到 0x083Exxxx ⇒ 中间有 ~4.5 MB 的空档，无歧义）
TILESET_SRC_LO = 0x087F0000

# 按 dst 归组时的注解（依据 docs/UI_HOOK_SURVEY.md 的 pokeruby 源码 + 本表实证）
DST_NOTE = {
    0x06000000: "cb0 起点 —— **混合区**：野外 primary tileset / 信息页美术 / 队伍美术 / 大幅面背景",
    0x06003000: "screenblock 6 —— 队伍菜单落盘区（`DmaCopy16Defvars(3,…,VRAM+0x3000)`）",
    0x06003800: "screenblock 7 —— 队伍菜单 tilemap（`gPartyMenuMisc_Tilemap`）",
    0x06004000: "cb1 起点 / screenblock 8 —— **混合区**：野外 secondary tileset、以及部分 UI tilemap",
    0x06004800: "screenblock 9 —— **信息页 tilemap**（`gStatusScreen_Tilemap`，全盘唯一站点）",
    0x06005000: "screenblock 10",
    0x06006500: "非 0x800 对齐 —— 队伍菜单的零散小块",
    0x06006800: "screenblock 13",
    0x06007000: "screenblock 14 —— 领航员 / 简易聊天",
    0x06007800: "screenblock 15 —— 开始菜单 / 领航员",
    0x06008000: "cb2 起点 —— 图集 / UI 美术（**可能是假名图集，需逐个核函数**）",
    0x06008020: "cb2 内偏移",
    0x06008200: "cb2 内偏移",
    0x06009000: "cb2 内",
    0x0600A000: "cb2 内",
    0x0600B000: "cb2 内",
    0x0600B800: "cb2 内",
    0x0600BF80: "cb2 尾部",
    0x0600C000: "cb3 起点",
    0x0600C800: "cb3 内",
    0x0600D800: "cb3 内",
    0x0600E000: "cb3 内",
    0x0600E800: "**领航员 / PC 箱子 / 简易聊天**",
    0x0600F000: "**领航员 / PC 箱子 / 简易聊天**",
    0x0600F800: "**领航员 / PC 箱子 / 简易聊天**",
    0x06010000: "OBJ cb4 起点",
    0x06010020: "OBJ cb4 内",
}


def main() -> int:
    rom = io.open(ROM, "rb").read()
    sites = [(s, t) for s, t, _ in L.blx_targets(rom) if t in (L.LZ_VRAM, L.LZ_WRAM)]
    rows = []
    for site, tgt in sites:
        reg = L.walk(rom, site - L.LOOKBACK, site)
        src = reg[0] if isinstance(reg[0], int) else None
        dst = reg[1] if isinstance(reg[1], int) else None
        size = L.lz_size(rom, src) if src else None
        rows.append({"site": site, "wram": tgt == L.LZ_WRAM, "src": src,
                     "size": size, "dst": dst})

    vram_rows = [r for r in rows
                 if isinstance(r["dst"], int) and L.VRAM_LO <= r["dst"] < L.VRAM_HI]
    ts = [r for r in vram_rows if r["src"] and r["src"] >= TILESET_SRC_LO]

    groups = OrderedDict()
    for r in sorted(vram_rows, key=lambda r: r["dst"]):
        groups.setdefault(r["dst"], []).append(r)

    o = []
    w = o.append
    w("# 常规 UI 装载点全表（`bl LZ77UnCompVram` / `LZ77UnCompWram`）")
    w("")
    w("> 生成：`python scripts/gen_ui_lz_sites_doc.py`（数据现算，不手抄）")
    w("> 背景：用户实测 v18 后判定「接管的 UI 目前好像只有对话框那种 UI，常规 UI 都没接管到」，")
    w("> 并指出「不需要单一 hook 点啊，本来就是多个点申请 tile」。")
    w("> 本文是该判断的**机器级答复**：把「多个申请点」一个不漏地列出来。")
    w("")
    w("## 0. 三条硬结论")
    w("")
    w("1. **收敛层确实存在**：`LZ77UnCompVram`(0x081B1298, `svc 0x12; bx lr`) 与")
    w("   `LZ77UnCompWram`(0x081B129C, `svc 0x11; bx lr`) 是全游戏「LZ77→内存」的唯一一对蹦床。")
    w("   原盘实测：`bl 0x081B1298` **%d** 处、`bl 0x081B129C` **%d** 处，其中"
      % (sum(1 for r in rows if not r["wram"]), sum(1 for r in rows if r["wram"])))
    w("   目标落在 VRAM 的有 **%d** 处（下表）。" % len(vram_rows))
    w("2. 🔴 **但收敛层不能当总闸**：`0x06000000` 上**同时**住着野外 primary tileset 与信息页美术 ——")
    w("   `0811E28A src=0x087F9D0C(512砖) → 0x06000000`（野外）与")
    w("   `080791BA src=0x0836D268(312砖) → 0x06000000`（信息页）**落点字节级同一地址**。")
    w("   ⇒ 「按 dst 落 VRAM 就清 0」必然连地图一起清。这也正是 `docs/UI_HOOK_SURVEY.md`")
    w("   §4 方案② 被预先判死的理由（v19 违反此判，已撤，见 §4）。")
    w("3. ⇒ **只能按「调用点」作用域**（桩用 `bx` 不改 `lr`，进跳板时 `lr` = 调用者的返回地址）。")
    w("   也就是：一个桩架在 `0x081B1298`，配一张**已逐个核对过函数归属的站点白名单**。")
    w("")
    w("## 1. 野外 tileset 的站点（**必须排除**，否则地图空白）")
    w("")
    w("| site | src | size | tiles | dst |")
    w("|---|---|---|---|---|")
    for r in ts:
        w("| `%08X` | `0x%08X` | `0x%X` | %d | `0x%08X` |"
          % (r["site"], r["src"], r["size"], r["size"] // 32, r["dst"]))
    w("")
    w("野外 tileset 的 blob 全部落在 `0x%08X` 以上；其余所有 UI 美术的 src 最大只到" % TILESET_SRC_LO)
    w("`0x083EE670` ⇒ 中间有约 4.5 MB 无歧义空档。")
    w("")
    w("## 2. 按 dst 归组的全表（dst 落 VRAM 的 %d 处）" % len(vram_rows))
    w("")
    for dst, rs in groups.items():
        note = DST_NOTE.get(dst, "")
        w("### `0x%08X` × %d%s" % (dst, len(rs), (" —— " + note) if note else ""))
        w("")
        w("| site | 入口 | src | size | tiles |")
        w("|---|---|---|---|---|")
        for r in rs:
            w("| `%08X` | %s | %s | %s | %s |"
              % (r["site"], "Wram" if r["wram"] else "Vram",
                 ("`0x%08X`" % r["src"]) if r["src"] else "—",
                 ("`0x%X`" % r["size"]) if r["size"] else "—",
                 (r["size"] // 32) if r["size"] else "—"))
        w("")
    w("## 3. 未解出参数的站点")
    w("")
    w("下面这些站点的 `r0/r1` 在向前 64 字节内没有可静态判定的赋值 —— 多数是")
    w("`LZDecompressVram` / `LZDecompressWram` 这类**纯转发包装**（参数直接来自调用者），")
    w("少数是取参路径里有不可静态解析的间接寻址。**打桩前必须单独反汇编核对。**")
    w("")
    w("| site | 入口 |")
    w("|---|---|")
    for r in rows:
        if r["src"] is None or r["dst"] is None:
            w("| `%08X` | %s |" % (r["site"], "Wram" if r["wram"] else "Vram"))
    w("")
    w("## 4. v19 的撤销记录（2026-09-12）")
    w("")
    w("v19 把总闸架在 `0x081B1298`，判据 = 「dst 落 VRAM 就清 0」。静态复核 24 项全过，")
    w("**但判据本身错**：本表 §1 已证明它会清掉野外 tileset。已用 `scripts/revert_v19.py`")
    w("精确撤销，`game.bin` 回到 **11548 B**、`verify_v17_static.py` 全过、")
    w("`_translated.gba` 注入区与 build 逐字节相同（sha1 `1f6b26460fe3`）。")
    w("")
    w("教训（与 v17 的 `v8_frame_room` 同源）：**判据「能自证」≠ 判据「对」**。")
    w("静态复核只能证明「我实现了我想实现的」，证明不了「我想实现的是对的」。")
    w("")
    w("## 5. 下一步（按调用点作用域）")
    w("")
    w("1. 跳板改造：入口 `mov r2, lr`（`bx` 进桩 ⇒ `lr` 未被改写 = 调用者返回地址），")
    w("   转交 `v19_lz_gate_C(src, dst, site)`。")
    w("2. 站点白名单**逐个反汇编核对函数归属**后才准写入 —— 尤其 `0x06008000/0x0600C000`")
    w("   一组（cb2/cb3）疑似假名图集，若误伤则**文字一起消失**，实验直接失去意义。")
    w("3. 优先从证据最强的族开始：**信息页**（`0x06004800` 全盘唯一站点 `080791C2`）、")
    w("   其次是 `0x0600E800/0xF000/0xF800` 一族（领航员 / PC 箱子 / 简易聊天）。")
    w("")

    io.open(OUT, "wb").write("\n".join(o).encode("utf-8"))
    print("WROTE %s (%d 行, %d B)"
          % (os.path.relpath(OUT, ROOT), len(o), os.path.getsize(OUT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
