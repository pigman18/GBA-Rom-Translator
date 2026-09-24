#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""gen_lz_ui_sites.py — 生成「常规 UI 的 LZ77→VRAM 装载点白名单」头文件。

背景（见 docs/UI_LZ_SITES.md）：
  · `LZ77UnCompVram`(0x081B1298) / `LZ77UnCompWram`(0x081B129C) 是全游戏
    「LZ77 → 内存」的唯一一对 BIOS 蹦床（原盘 `bl 0x081B1298` 118 处 / `129C` 42 处）。
  · 常规 UI（队伍菜单 / 宝可梦信息页 / 领航员 / PC 箱子 / 简易聊天）的**图形**
    统统从这里解压进 VRAM —— 这是「多个申请点」背后的收敛层。
  · 🔴 但**不能按 dst 当总闸**：`0x06000000` 上同时住着野外 primary tileset 与
    信息页美术（`0811E28A` 与 `080791BA` 落点字节级同一地址）⇒ 只能按**调用点**。
  · 调用点判据 = `lr`。桩用 `bx`（不是 `bl`）⇒ 改写 lr 的是调用者的 `bl`，
    进跳板时 `lr` 恒 = 调用者的返回地址 = **`bl` 指令地址 + 4**。

排除规则（必须按**函数**排除，不能按 src/dst —— 运行时的 src 是 `tileset->tiles`，
静态解出的只是默认值，`080077DE` 与 `08008660` 会解出同一个假 src）：
  见下面 EXCLUDE_FUNCS，每条都写了理由。

用法：python scripts/gen_lz_ui_sites.py [--check]
  --check 只报告差异，不写文件。
"""
from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lz77_args import blx_targets, walk, lz_size, LZ_VRAM, LZ_WRAM  # noqa: E402
from lz77_own import func_start  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM = os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba")
OUT = os.path.join(ROOT, "configs", "POKEMON_RUBY_AXVJ00", "hook",
                   "include", "lz_ui_sites.h")
VRAM_LO, VRAM_HI = 0x06000000, 0x06018000

# ---- 排除的函数组 ---------------------------------------------------------
# 🔴 只排除「野生动物」——野外地图 tileset。它们的 dst 与 UI 重叠，绝不能清。
EXCLUDE_FUNCS = {
    0x08007724: "野外 primary tileset 装载（CopyPrimaryTilesetToVram 族）"
                "—— dst=cb0(0x6000000)+screenblock7；src 运行时由 tileset 决定",
    0x080085E8: "野外 secondary tileset 装载（CopySecondaryTilesetToVram 族）"
                "—— 与 0x08007724 同构",
    0x0811031C: "地图 tileset 装载（src 0x087Fxxxx 真值：256砖→cb0 / 512砖→cb1）",
    0x0811E03C: "地图 tileset 装载（src 0x087F9D0C：512砖→cb0）",
    0x080F38E4: "疑似另一条地图 tileset 路径：dst = cb0 + cb1，"
                "与野外那两条同构（src 静态解不出）⇒ 保守排除",
    # ---- 以下不是「野外」，但同样绝不能进白名单 ----------------------------
    0x0800A770: "🔴 LZDecompressVram **包装函数**（内层就是本桩）—— 它的 lr 是"
                "固定值 0x0800A776，被**所有**转发调用共享 ⇒ 列白名单等于把"
                "全部经包装的调用（含非 UI）一起门控。参数直传、静态解不出。",
    0x08053D9C: "src 静态解不出，且其中一个 dst = 0x02000000(EWRAM) ⇒ "
                "疑似非图形的解压/搬运，不属 VRAM 装载 ⇒ 排除",
    0x0813E020: "孤立函数，仅 1 个站点且 src/dst 均解不出 ⇒ 无法判定归属，"
                "保守排除（宁可漏，不可误伤）",
}


def main() -> int:
    check = "--check" in sys.argv
    rom = io.open(ROM, "rb").read()
    sites = [(s, t) for s, t, _ in blx_targets(rom) if t in (LZ_VRAM, LZ_WRAM)]

    rows = []
    for site, tgt in sites:
        if tgt != LZ_VRAM:
            continue                      # Wram 站点不在 VRAM，不需要门控
        reg = walk(rom, site - 64, site)
        src = reg[0] if isinstance(reg[0], int) else None
        dst = reg[1] if isinstance(reg[1], int) else None
        size = lz_size(rom, src) if src else None
        fn = func_start(rom, site)
        rows.append((site, src, size, dst, fn))

    keep = [r for r in rows if r[4] not in EXCLUDE_FUNCS]
    drop = [r for r in rows if r[4] in EXCLUDE_FUNCS]
    keep.sort()

    lines = []
    A = lines.append
    A("/* lz_ui_sites.h — 自动生成，不要手改。")
    A(" * 生成器：scripts/gen_lz_ui_sites.py（数据现算，不手抄）")
    A(" * 依据：docs/UI_LZ_SITES.md")
    A(" *")
    A(" * 每个条目 = `bl 0x081B1298` 的**下一条指令地址**（= 进跳板时的 lr）。")
    A(" * 桩用 `bx` 不改 lr ⇒ 跳板入口 `mov r2, lr` 拿到的就是调用者的返回地址。")
    A(" *")
    A(" * 口径：`bl LZ77UnCompVram` 共 %d 处（`LZ77UnCompWram` 的 42 处写"
      % sum(1 for _, t in sites if t == LZ_VRAM))
    A(" *       EWRAM/IWRAM，不经 VRAM，不需要门控）；排除 %d 处"
      % len(drop))
    A(" *       （野外地图 tileset + 包装函数 + 无法判定者，共 %d 个函数组），"
      % len(EXCLUDE_FUNCS))
    A(" *       纳入 %d 处。" % len(keep))
    A(" *")
    A(" * 🔴 为什么不按 dst 判定：`0x06000000` 上同时住着野外 primary tileset")
    A(" *    与信息页美术（字节级同一地址）⇒ 按 dst 必误伤地图。")
    A(" * 🔴 为什么不按 src 判定：运行时 src = `tileset->tiles`（动态），静态解出的")
    A(" *    只是默认值 —— `080077DE` 与 `08008660` 会解出同一个假 src。")
    A(" * ⇒ 只有**函数归属 + 调用点**是稳定判据。")
    A(" */")
    A("#ifndef LZ_UI_SITES_H")
    A("#define LZ_UI_SITES_H")
    A("")
    A("#include <stdint.h>")
    A("")
    A("#define V20_UI_SITE_COUNT %d" % len(keep))
    A("")
    A("static const uint32_t v20_ui_sites[V20_UI_SITE_COUNT] = {")
    prev_fn = None
    for site, src, size, dst, fn in keep:
        if fn != prev_fn:
            A("    /* FUNC 0x%08X */" % fn)
            prev_fn = fn
        A("    0x%08Xu,   /* %08X  src=%s size=%-7s %s */"
          % (site + 4, site,
             ("0x%08X" % src) if src else "?",
             ("0x%X" % size) if size else "-",
             ("-> 0x%08X" % dst) if dst else "-> ?"))
    A("};")
    A("")
    A("#endif /* LZ_UI_SITES_H */")
    A("")

    text = "\n".join(lines)

    print("Vram 站点 %d 处；纳入 %d / 排除 %d"
          % (len(rows), len(keep), len(drop)))
    print()
    print("排除明细：")
    for fn in sorted(EXCLUDE_FUNCS):
        rs = [r for r in drop if r[4] == fn]
        print("  0x%08X  %d 站点  %s" % (fn, len(rs), EXCLUDE_FUNCS[fn]))

    if check:
        old = io.open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        print()
        print("--check: %s" % ("一致" if old == text else "**有差异**"))
        return 0 if old == text else 1

    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print()
    print("已写入 %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
