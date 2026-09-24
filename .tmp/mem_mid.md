## 屏上 UI 两套体系 / Step B 判决 / 采集 / 框链 / 官方机制
⇒ **完整实证见 `docs/MEMORY_附录_逆向实证.md`**（本文件只留结论）。
- 「UI」是**两套体系**：**A 窗口体系（走分配器）** vs **B 静态 BG 层（不走分配器**，
  美术由 `LZ77UnCompVram @0x081B1298` 直解到固定 VRAM）。v20 已接管 B 类
  （`v20_lz_ui_C` + 104 处白名单）。🔴 **不能按 `dst` 也不能按 `src` 归组，只能按函数**。
- 🔴 **Step B 两条「借道官方」路线全否决**：
  ① 钩 GGTP —— 只覆盖 2 条路径、font 2/3/5/6 不经它、官方 tm 装不下 11×11；
  ② tm1 借道 `TILE_BASE` —— 该区**被官方图集预先 LZ77 解入占用**，实机堆叠成乱码。
- 采集：GDB 注入点 `0x0800043E`；画面 = `PrintWindow`+`PW_RENDERFULLCONTENT` 截 mGBA 窗口；
  读档法 = 把 `.sav` 拷成 `<rom同名>.sav`。🔴 采集不许依赖 Ctrl-C；I/O 寄存器不可靠。
