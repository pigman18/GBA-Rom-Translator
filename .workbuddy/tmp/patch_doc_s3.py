# -*- coding: utf-8 -*-
"""把设计文档 §4 的 S3 行换成「已实现」版本（落点由 ①/② 修正为 ⑤）。"""
import io

P = 'docs/开发_20260911_接管全部charblock_设计.md'
raw = io.open(P, encoding='utf-8', newline='').read()
crlf = '\r\n' in raw
s = raw.replace('\r\n', '\n')

new_line = (
    "| **S3** ✅ **已实现（2026-09-11），待实机验收** | "
    "🔴 **落点修正：实际接管 ⑤ `0x08062080`（`TextWindow_SetBaseTileNum`）**，不是初稿写的 ①/②。"
    "理由（反汇编实证）：① 是 16B 主体 + **PC 相对 `ldr`**，入口要重放 6 条指令、出口只有 4 字节空间，都放不下跳板；"
    "而 ⑤ 是**纯叶函数**「记下号 → 返回 +9」（源码 `text_window.c:101` 与反汇编**逐指令一致**），"
    "**且 ⑥（+14）与 ⑦⑧ 框图形装载全部由它的返回值驱动** ⇒ 接管这一处即控制整条框链。"
    "**做法**：12B 桩（`push{r4,lr}`+`ldr/bx`+pool，`hooks_origin.s`）→ 跳板（`entry.s: V10SetFrameBase_Hook`）"
    "→ C（`win_alloc.c: v10_set_frame_base_C`）里发号并复刻「写 `0x03000514` + 返回 +9」。"
    "🔴 **发号器游标复用 `ADDR_V8_CURSOR`（文字游标）**，不另开变量 —— ⑤ 在 `v8_alloc_begin` **之前**执行，"
    "读到的是上一窗口用完的位置 ⇒ 框与文字成一条严格串行序列；若另开游标，第 2 个窗口的框会**正好压在第 1 个窗口已画好的汉字上**。"
    "`v8_alloc_n` 的起址下限改为 `v10_text_lo()`（＝本窗口框之后；未发过框时返回 0，行为与改动前一致）。"
    "**⑤⑥⑦⑧ 一行汇编不改**（自动跟随）。⇒ 窗口1 框 `[512,535)` 字 `[535,595)`；窗口2 框 `[595,618)` 字 `[618,…)` —— **互不重叠**。"
    "⚠ 仍守铁律：**不建账、不登记归属、不扫 VRAM**；只有「下一个可用号」；越界回卷，真回收留 S6。 | "
    "实机截图：领航员全部路线名 + 训练家名**同时出现、不互相覆盖**。"
    "日志判读看 `[UIH] ChsAllocFrame9` 新增的「v10 发号器」副行（`[框起点, 文字起点)` / 第几次发框 / 上限），"
    "跑法见 `../scripts/GDB_UI_TAKEOVER.md` |"
)

lines = s.split('\n')
hit = [i for i, ln in enumerate(lines) if ln.startswith('| **S3**')]
assert len(hit) == 1, 'S3 行命中 %d 次' % len(hit)
i = hit[0]
old = lines[i]
assert old.startswith('| **S3** |'), old[:60]
lines[i] = new_line

out = '\n'.join(lines)
io.open(P, 'w', encoding='utf-8', newline=('\r\n' if crlf else '\n')).write(out)
print('S3 行已更新（第 %d 行，原 %d 字 → 新 %d 字）' % (i + 1, len(old), len(new_line)))
