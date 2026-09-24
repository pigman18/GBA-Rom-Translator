# -*- coding: utf-8 -*-
import io

LOG = '.workbuddy/memory/2026-09-21.md'
MEM = '.workbuddy/memory/MEMORY.md'

log_add = u"""

## v37 判据级定论：引擎字模缓存 = 整块，我方砖无立足点（2026-09-21 下午）

用户质疑「池子就是静态避让带 2.0」，核实后**成立**，且目标本身不可满足。

- 全 42 页实测：`tpl[+8]=3`（⇒ `InitWindowTileData` 走 `index*64` 分支，512 槽）、
  `tpl[+9]=1`（⇒ 预取器 `0x080029E0` 只在 font==1 时执行，而它恒为 1）、`TB` 恒 1。
  预取器逐指令：`r2 = counter & 0xFF` 作**槽号**传给 `InitWindowTileData`，`counter += 16`，
  `counter == 0x100` 返回 1 ⇒ 每次窗口激活**重写 `tileData` 块槽 `[1,513)`**。
- 约束链（显示侧）：引擎 map 号 = `win[+0x16](TB) + 2*glyph`，写砖槽 = `TB + 2*glyph`
  ⇒ 两者相等 ⇒ **`tileData` 必须 == 该层 charBase**。实测两例吻合：
  人口 0 `tileData=0x06004000`(cb1)/`mapBase=0x0600F000`(sb30)；人口 1 `0x06008000`(cb2)/`0x0600F800`(sb31)。
- 我方砖的 map 号经同层 charBase 寻址 ⇒ **必须落在同一 charBlock**。
- ⇒ **块内只剩槽 0 一块砖（32 B）没被覆盖**。所以「找空档」是可满足性问题（解集为空），
  不是采样密度问题 —— 避让带族（含 v35/v36 池子）在数学上无解，正式判死，不要再出 3.0。
- 模板表静态核对：`0x081BB000..0x081BC000` 共 105 条候选模板，`tileData` 指向
  cb0=24 / cb1=13 / cb2=29 / cb3=38 / OBJ=1 ⇒ 四个块都至少有一条模板指过来。
- 12px 步进的必然结果：11px 墨 + 12px 步进 ⇒ 字形跨 8px 网格
  ⇒ 借引擎自己的网格渲染只能退到 16px 步进（用户已否决）⇒ **自写渲染器不能省**。
- 唯一还成立的方向：**不再与引擎共享 charBlock** —— 让引擎缓存落到邻块（`TB` 抬到 512 或
  `TB=0`），并在我们已有的 `UpdateTilemap` 钩子里给引擎那套号加偏移（`TB+2g` → `+512`），
  层 `charBase` 不动。风险点 = 4 个 charBlock 的预算（tilemap / 静态美术 / 我方砖 / 引擎缓存）。
- 纪律：**先出 4 块完整预算表（屏 × 层），表闭合才写代码**；不闭合就报「哪一屏没位置」，
  不许先改码再撞。
"""

s = io.open(LOG, 'a', encoding='utf-8', newline='')
s.write(log_add)
s.close()

mem = io.open(MEM, encoding='utf-8').read()
old = u"待定：先用桩做一次**运行时完备记录**（只有 2 个调用点，集合有限）定论 tileData 实际可达集。"
new = (u"\U0001F534 **v37 定论（判据级）**：全 42 页实测 `tpl[+8]=3`（512 槽）、`tpl[+9]=1`（预取器只在 font==1 跑）、\n"
       u"`TB=1` ⇒ 每次窗口激活**重写 `tileData` 块槽 `[1,513)`**；显示侧必须 `tileData == 该层 charBase`\n"
       u"（引擎 map 号 `TB+2g` == 写砖槽 `TB+2g`；cb1/sb30、cb2/sb31 两例吻合）⇒ 我方砖必与引擎缓存同块\n"
       u"⇒ **块内只剩槽 0（32 B）没被覆盖**。「找空档」是**可满足性问题，解集为空** ⇒\n"
       u"**避让带族（含 v35/v36 池子）数学上无解，正式判死，勿再出 3.0**。\n"
       u"12px 步进必跨 8px 网格 ⇒ 借引擎渲染必退 16px（已否决）⇒ 自写渲染器不能省。\n"
       u"唯一方向：**不共享 charBlock**（引擎缓存落邻块 + `UpdateTilemap` 钩子里给引擎号加偏移），\n"
       u"先出 4 块预算表再写码。")
assert old in mem, "anchor not found"
mem = mem.replace(old, new, 1)
io.open(MEM, 'w', encoding='utf-8', newline='').write(mem)
print("OK log+=%d chars, mem now %d chars" % (len(log_add), len(mem)))
