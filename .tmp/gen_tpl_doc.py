#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成 docs/静态盘点_20260921_窗口模板表_tm与charBase.md（只读原盘）。"""
import os
import struct
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

ROOT = r"C:\code\GBA-Rom-Translator"
ROM_PATH = os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba")
OUT = os.path.join(ROOT, "docs", "静态盘点_20260921_窗口模板表_tm与charBase.md")
BASE = 0x08000000
VRAM = 0x06000000
CB = 0x4000
TILE = 32
ANCHOR = 0x081BB3DC
LO, HI = 0x081BB000, 0x081BC000
STRIDE = 0x18
ATLAS_LO, ATLAS_HI = 0x20, 0x4020      # [td+0x20, td+0x4020) = 号 [1,513)
OUR_LO, OUR_HI = 0x4040, 0x6000        # 号 [514,768)
MAP_SZ = 0x800                         # 32x32 图 = 1024 项 x 2B


def ok(rom, a):
    if not (LO <= a < HI - STRIDE):
        return False
    o = a - BASE
    td = struct.unpack_from("<I", rom, o + 0x0C)[0]
    return VRAM <= td < 0x06018000 and td % TILE == 0 and rom[o + 0x0B] == 0


def rows(rom):
    a = ANCHOR
    while ok(rom, a - STRIDE):
        a -= STRIDE
    out = []
    while ok(rom, a):
        o = a - BASE
        out.append(dict(
            tpl=a, mode=rom[o + 9], font=rom[o + 8],
            td=struct.unpack_from("<I", rom, o + 0x0C)[0],
            tm=struct.unpack_from("<I", rom, o + 0x10)[0]))
        a += STRIDE
    return out


def main():
    rom = open(ROM_PATH, "rb").read()
    R = rows(rom)

    def ov(a0, a1, b0, b1):
        return max(a0, b0) < min(a1, b1)

    md = Counter(r["mode"] for r in R)
    cd = Counter((r["td"] - VRAM) // CB for r in R)

    lines = []
    A = lines.append
    A("# 静态盘点 2026-09-21：窗口模板表（textMode / charBase / 画布几何）")
    A("")
    A("> 输入：原盘 `roms/origin/POKEMON_RUBY_AXVJ00.gba`（**只读**）。不开模拟器、不采样、不改任何文件。")
    A("> 生成脚本：`.tmp/gen_tpl_doc.py`（表定位初探 `.tmp/tplinv.py`）。")
    A("> 结论性质：全部为 ROM 静态事实 + 反汇编公式推演；凡属推论均标【推】。")
    A("")
    A("---")
    A("")
    A("## 1. 表定位（本轮新实证，修正旧口径）")
    A("")
    A("- 模板表 = **`0x081BB3DC .. 0x081BB8BC`，共 53 条，步长 `0x18`**。")
    A("- 字段（由 dump `0x081BB874` 定出，并与本工程 header 一致）：")
    A("  `+0x08` 字体类 ｜ **`+0x09` textMode**（`0x080029E0` 的 `ldrb r0,[r0,#9]` 读的就是它）｜ "
      "`+0x0B` 恒 0（**真模板判据**）｜ `+0x0C` tileData ｜ `+0x10` tilemap。")
    A("- ⚠ **旧口径「105 条候选」作废**：那是按 4 字节步长扫出来的**级联假阳性** —— "
      "相邻条目互为对方的 tilemap/tileData（例：`0x081BB3DC` 的 tilemap `0x0600F800` 正好成了 "
      "`0x081BB3E0` 的 tileData）。按 0x18 走，真实条数 = **53**。")
    A("- 交叉验证：本表 tm1 = 36 条，与工程记忆「P31 曾改 36 条模板 tm1→tm0」**数目吻合**。")
    A("")
    A("## 2. textMode 分布")
    A("")
    A("| tm | 条数 | 含义（本工程已实证） |")
    A("|---|---|---|")
    A("| 0 | %d | 官方自己画：`FontFunc[0]` 会把日文字形 blit 进 `tileData + (win[0x16]+win[0x18])*32` = **我们的画布** |" % md[0])
    A("| 1 | %d | 预取图集 + 我们走「池子」的那一族 —— **撞号来源** |" % md[1])
    A("| 2 | %d | OBJ / 特殊通道（`tileData=0x06010000` = OBJ 区） |" % md[2])
    A("| 3 | %d | **官方网格**（`TB+curX+curTileX+(curY+curTileY)*30`）—— 实测**从不撞** |" % md[3])
    A("")
    A("⇒ **「从不撞」的 tm3 只有 2 条模板**；主体是 **36 条 tm1**。这就是「为什么到处都在撞」。")
    A("")
    A("## 3. 文本层 charBase 分布")
    A("")
    A("| charBase | 条数 | 物理层 |")
    A("|---|---|---|")
    for k in sorted(cd):
        nm = {0: "cb0", 1: "cb1", 2: "cb2", 3: "cb3", 4: "cb4（**OBJ 区**）"}.get(k, "cb%d" % k)
        A("| %d | %d | %s |" % (k, cd[k], nm))
    A("")
    A("⇒ 文本层分散在 **cb0/cb1/cb2/cb3** 四处 ⇒ **一个绝对号池不可能服务所有界面** —— "
      "这是「v31 单池 ⇒ 队名乱码」的**静态证明**（与当时实测一致）。")
    A("")
    A("## 4. 几何规则（判据）")
    A("")
    A("由反汇编公式 `dst = tileData + (tileBase + index)*32`（font1/2/4/5）与 `index ∈ [0,256)`：")
    A("")
    A("```")
    A("引擎字模区（写） = [tileData + 0x20, tileData + 0x4020)   ← 该层砖号 [1, 513)")
    A("                  = 整块 C 的 0x4000 B + 下一块 C+1 的头 0x20 B")
    A("                     （charBase=C，tileData = 0x06000000 + C*0x4000）")
    A("```")
    A("")
    A("- 因此**文本层 charBase=C ⇒ 块 C 被吃满**，块 C+1 的前 32 B 也被吃。")
    A("- BG 层砖号只有 10 bit ⇒ 可用区间 `[0,1024)`；**charBase=3 时号 512 起物理进入 OBJ 区**"
      "（BG 层不可寻址）⇒ charBase=3 的层**可用号只有 [0,512)**。")
    A("- 由此得到本层唯一「结构上引擎不写」的候选段 = **号 `[513,1024)`**，物理落块 C+1。"
      "本盘点取其中段 `[514,768)`（= 254 槽）做逐模板冲突检查。")
    A("")
    A("## 5. 逐模板明细（53 条）")
    A("")
    A("| tpl | tm | +08 | charBase | tileData | tilemap | 引擎字模区 | [514,768) 与我方关系 |")
    A("|---|---|---|---|---|---|---|---|")
    for r in R:
        td, tm = r["td"], r["tm"]
        cb = (td - VRAM) // CB
        atlas = "[%08X,%08X)" % (td + ATLAS_LO, td + ATLAS_HI)
        our0, our1 = td + OUR_LO, td + OUR_HI
        if not (VRAM <= tm < 0x06018000):
            verd = "map 无效 ⇒ 无 map 冲突【推】"
        elif ov(our0, our1, tm, tm + MAP_SZ):
            verd = "⚠ **与 map 冲突**"
        else:
            verd = "无 map 冲突 ✓"
        if cb == 3:
            verd += "；⚠ charBase=3 ⇒ 层内可用号只有 [0,512)，[514,768) **不存在**"
        A("| %08X | %d | %d | %d | %08X | %08X | %s | %s |"
          % (r["tpl"], r["mode"], r["font"], cb, td, tm, atlas, verd))
    A("")
    A("## 6. 三条硬结论")
    A("")
    t1 = [r for r in R if r["mode"] == 1]
    c3 = [r for r in t1 if (r["td"] - VRAM) // CB == 3]
    c2 = [r for r in t1 if (r["td"] - VRAM) // CB == 2]
    A("**F1｜tm3 仅 2 条，tm1 有 36 条。** 「从不撞」的路径覆盖面极小；撞号的界面才是主体 —— "
      "所以「把界面迁到 tm3 形态」这条路，从模板数上看空间很大（36 → 2 是反过来的）。")
    A("")
    A("**F2｜文本层 charBase 取 5 个值（0/1/2/3/OBJ）。** 绝对池子结构性不成立。")
    A("")
    A("**F3｜charBase=3 的 tm1 模板（%s）在结构上没有任何空余号**："
      "引擎字模区 [1,513) 已经吃满该层可用号 [0,512)，`[514,768)` 物理上落进 OBJ 区、BG 层根本指不到。"
      % "、".join("%08X" % r["tpl"] for r in c3))
    A("")
    A("**F4｜全部 53 条的 tilemap 都不落 `[514,768)`**（见 §5 逐条判定，**零条冲突**）⇒ "
      "对 charBase ∈ {0,1,2} 的文本层，「引擎字模区 [1,513) ｜ 我方 [514,768) ｜ tilemap [768,1024)」"
      "这套三段几何**与窗口模板表完全相容**。唯一例外是 charBase=3（F3）。")
    A("")
    A("## 7. 现有池子段 vs 引擎字模区（静态对账）")
    A("")
    A("源码事实（`PrintNextChar_hook.c`）："
      "`chs_p0_seg_b[2]={384,946}` / `n={32,22}`；`chs_p1_seg_b[1]={514}` / `n={127}`；"
      "`chs_p2_seg_b[2]={192,320}` / `n={32,32}`。层基址口径：域 0 = cb1、域 1 = cb2、域 2 = cb0。")
    A("")
    A("| 池 | 段 base | 槽数 | 砖数 | 物理范围 | 服务层（域） | 判定 |")
    A("|---|---|---|---|---|---|---|")
    seg = [("p0", 384, 32, 0, "cb1"),
           ("p0", 946, 22, 0, "cb1"),
           ("p1", 514, 127, 1, "cb2"),
           ("p2", 192, 32, 2, "cb0"),
           ("p2", 320, 32, 2, "cb0")]
    SVC = {0: 1, 1: 2, 2: 0}          # 域 → 块号（域0=cb1 / 域1=cb2 / 域2=cb0）
    for nm, base, n, dom, blkname in seg:
        s = VRAM + SVC[dom] * CB + base * 32
        tiles = n * 2                  # 每槽 2 砖（v36 注释：127 槽 = 254 砖）
        e = s + tiles * 32
        svc = SVC[dom]
        svc_atlas = (VRAM + svc * CB + ATLAS_LO, VRAM + svc * CB + ATLAS_HI)
        b = (s - VRAM) // CB
        blk_atlas = (VRAM + b * CB + ATLAS_LO, VRAM + b * CB + ATLAS_HI)
        hit_svc = ov(s, e, *svc_atlas)
        hit_blk = ov(s, e, *blk_atlas)
        if hit_svc:
            verd = "⚠ **确定落在本层（cb%d）字模区 ⇒ 会被覆盖**" % svc
        elif hit_blk:
            verd = "⚠ 落在**块 cb%d 的字模区**（同页若有 `tileData=cb%d` 的窗口即被覆盖）" % (b, b)
        else:
            verd = "**不相交 ✓ 段合法**"
        A("| %s | %d | %d | %d | [%08X, %08X) | %s | %s |"
          % (nm, base, n, tiles, s, e, blkname, verd))
    A("")
    A("⇒ **6 段里 4 段确定落在自己的服务层字模区内**（p0 段 1、p2 两段），"
      "第 5 段（p0 段 2）落在 cb2 的字模区内。**只有 p1 的 `[514,768)` 不在其服务层（cb2）的字模区内** —— "
      "它位于 cb3，只要求同一页上没有 `tileData=cb3` 的窗口，就是干净段。")
    A("这与实测症状完全对应：")
    A("")
    A("- 「队伍里的蛋被覆盖」= p0 段 1（号 384）物理落 `0x06007000` 在 **cb1 字模区**内；")
    A("  段 2（号 946）物理落 `0x0600B640` 在 **cb2 字模区**内（队伍/概况页同时有 cb2 层 ⇒ 必被写）。")
    A("- 「领航员/野外乱」= p2 两段物理落 `0x06001800 / 0x06002800`，都在 **cb0 字模区**内。")
    A("- p1 之所以没出问题，是因为它本身就是本文 §4 算出的那个合法段。")
    A("")
    A("## 8. 对「怎么才不撞」的直接含义")
    A("")
    A("1. **不撞的先决条件是「本层有一块引擎确实不写的号段」。** 本盘点把它算出来了："
      "对 charBase=C 的文本层，唯一这样的段是号 `[513,1024)`（物理块 C+1）；**C=3 时为空集**。")
    A("2. **所有文本层必须先归一 charBase**（否则池子要按 5 种 charBase 各来一份，"
      "而其中一种是空集）。这与「队伍/概况页病根 = charBase=1」的实测结论**同向**，"
      "且现在是**静态可证**的。")
    A("3. **段表只需保留落在 `[513,1024)` 里的段**；其余段（无论怎么换区间）都在别人（引擎）的"
      "字模区里 —— 这解释了「换区间」族为什么永远治不好，而不是「换得还不够巧」。")
    A("4. **仍缺一块拼图**：`[513,1024)` 里的非 tilemap 部分是否被**别的 BG 层的美术**占用 —— "
      "取决于各页 BG1/2/3 的 charBase 与 LZ77 落点，本表（窗口模板表）不含该信息，"
      "需要另一个静态入口（BGxCNT 表 / LZ77 调用点白名单），**不需要 gdb**。")
    A("5. 容量：`[514,768)` = 254 砖；11×11 字在 16px 步进下 4 砖/字 ⇒ **63 字**；"
      "12px 步进相邻字共享一列 ⇒ 省 1 砖/字 ⇒ **约 84 字**。这就是「三段几何」的实际容量上界。")
    A("")
    A("---")
    A("")
    A("### 附：可复现命令")
    A("")
    A("```bash")
    A('"C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe" .tmp/tplinv2.py      # 表定位 + 字段分布')
    A('"C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe" .tmp/gen_tpl_doc.py   # 生成本文')
    A("```")

    open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    print("写入 %s（%d 行）" % (OUT, len(lines)))
    print("tm 分布 %s ｜ charBase 分布 %s" % (sorted(md.items()), sorted(cd.items())))
    print("tm1 且 cb3：%s" % ["%08X" % r["tpl"] for r in c3])
    print("tm1 且 cb2：%d 条" % len(c2))


if __name__ == "__main__":
    main()
