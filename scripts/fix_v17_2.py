# -*- coding: utf-8 -*-
"""v17.2：修正 verify_v17_static.py 里 v17 跳板区间「写死 0x26」的判据缺陷。

现象：修掉 entry.s 那条多余的 `push {lr}` 之后，跳板实际长 **0x24**，
而 D 节与 HOOKS 表里都写死了 **0x26** ⇒ 多读 2 字节，正好读进**下一个函数**
开头那条 `push` ⇒ 被误判「跳板 push == 2」。

修法：加 `thunk_span()`，**从机器码自推跳板长度**（走到以 `pop {...,pc}`
结尾的那条，再对齐 4 并补上 `.pool` 字面量），两处 `0x26` 一并替换。

⚠ 为什么不能沿用 `sym_span()`：`V17BlankTile_Hook` 是 `game_syms.asm` 里
   **最后一个**符号 ⇒ 没有「相邻符号」可推，`sym_span` 会退回 cap(0x60)，更长。
"""
import io
import os

VER = r'scripts/verify_v17_static.py'


def load(path):
    raw = io.open(path, 'rb').read()
    return raw.decode('utf-8').replace('\r\n', '\n'), (b'\r\n' in raw)


def save(path, text, crlf):
    out = text.replace('\n', '\r\n') if crlf else text
    io.open(path, 'wb').write(out.encode('utf-8'))


def rep(s, old, new, tag):
    n = s.count(old)
    assert n == 1, '[%s] count=%d (want 1)' % (tag, n)
    return s.replace(old, new)


s, crlf = load(VER)

# 1) 在 D 节之前插入 thunk_span()
s = rep(s,
      'print("\\n=== D. 跳板语义（解析 ldr 字面量 + bl 目标）===")',
      '''def thunk_span(base):
    """从跳板机器码**自推长度**（别写死，也别靠相邻符号推）。

    `V17BlankTile_Hook` 是 `game_syms.asm` 里**最后一个**符号 ⇒ 没有相邻符号
    可推（`sym_span` 会退回 cap，更长、会读进下一个函数）。这里改走机器码：
      1. 逐条扫半字：`BL/BLX`(0xF0xx) 占 4 字节，其余占 2 字节；
         遇到 `pop {...,pc}`(0xBDxx) ⇒ 函数体结束；
      2. 向上对齐到 4；
      3. 每出现一条 `ldr rX,[pc,#imm]`(0x4Bxx) ⇒ `.pool` 里多一个 4 字节字面量。

    🔴 教训：跳板区间**写死**过一次（0x26），结果比真实长度(0x24)多读 2 字节、
       恰好读进下一个函数的 `push` ⇒ 判据误报。
    """
    k, n_pool = 0, 0
    while True:
        hw = u16(GB, base - INJ_LO + k)
        if (hw & 0xF800) == 0xF000:          # BL / BLX：4 字节
            k += 4
            continue
        if (hw & 0xFF00) == 0x4B00:          # ldr rX,[pc,#imm] ⇒ 一个 .pool 字
            n_pool += 1
        if (hw & 0xFF00) == 0xBD00:          # pop {...,pc}：函数最后一条
            k += 2
            break
        k += 2
    return ((k + 3) & ~3) + 4 * n_pool


print("\\n=== D. 跳板语义（解析 ldr 字面量 + bl 目标）===")''',
      'thunk_span 定义')

# 2) HOOKS 表里 v17 那一行改用 thunk_span
s = rep(s,
      '''    (BLK, "V17BlankTile_Hook", None, None,
     [0x080041C5], "GetBlankTileNum 续跑点 0x080041C4", 0x26),''',
      '''    (BLK, "V17BlankTile_Hook", None, None,
     [0x080041C5], "GetBlankTileNum 续跑点 0x080041C4", thunk_span(BLK)),''',
      'HOOKS v17 区间')

# 3) D 节里的 BLKSZ 也改用 thunk_span
s = rep(s,
      'BLKSZ = 0x26\nblk_bytes = GB[BLK - INJ_LO:BLK - INJ_LO + BLKSZ]',
      'BLKSZ = thunk_span(BLK)          # 自推，别写死\n'
      'blk_bytes = GB[BLK - INJ_LO:BLK - INJ_LO + BLKSZ]',
      'D 节 BLKSZ')

# 4) 顺手把 push 计数那条判据的说明补上「区间自推」
s = rep(s,
      'chk("v17 跳板 push 只允许 1 次（入口 push {r4,lr}；再多一份就把垃圾压进原体的返回槽）"\n'
      '    "  [实际 %d]" % n_push, n_push == 1)',
      'chk("v17 跳板 push 只允许 1 次（入口 push {r4,lr}；再多一份就把垃圾压进原体的返回槽）"\n'
      '    "  [区间 0x%X / 实际 %d]" % (BLKSZ, n_push), n_push == 1)',
      'push 判据说明')

save(VER, s, crlf)
print('WROTE %s  %d B  (CRLF=%s)' % (VER, os.path.getsize(VER), crlf))
print('OK')
