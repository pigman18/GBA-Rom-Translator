# -*- coding: utf-8 -*-
"""v17.1 一次性补丁。

修掉 `V17BlankTile_Hook` 里多出的一条 `push {lr}`：
  进入跳板时 lr 已经（且仍然）是**调用者的返回地址** —— 桩用的是 `bx r3`，不回写 lr；
  `push {r4, lr}` / `pop {r4}` 之后，栈顶留的那一份**正是原体 `push {lr}` 的等价物**。
  v17 原版在正常路径上又 `push {lr}` 一次，压进去的是 `bl v17_blank_tile_C` 后残留
  在 lr 里的垃圾 ⇒ 跳到 0x080041C4 续跑后，原体末尾 `pop {pc}` 弹出垃圾当 PC
  ⇒ **打开开始菜单立刻重启**（用户实测）。

本补丁：
  1) entry.s —— 删掉那条 `push {lr}`，改写头注释 / 行内注释，把道理钉住。
  2) scripts/verify_v17_static.py —— D 节判据从「重放 4 条半字」改为
     「重放后 3 条 + 跳板内 push 只允许 1 次 + pop 恰好 2 次」，让这类栈失衡无法再漏过。
"""
import io
import os

ENTRY = r'configs/POKEMON_RUBY_AXVJ00/hook/src/text/entry.s'
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


edits = []

# ---------------------------------------------------------------- 1. entry.s
s, crlf = load(ENTRY)

s = rep(s,
"""@ 桩型 = 8B「不碰栈」纯跳转，覆盖 0x080041BC..0x080041C3（4 条半字）：
@     b500 push {lr} / 1c02 adds r2,r0,#0 / 7a90 ldrb r0,[r2,#10] / 2801 cmp r0,#1
@   跳板**必须重放**这 4 条再落到 0x080041C4；「强制 0」路径用入口那份 lr
@   （桩没碰 lr；跳板 push/pop 成对 ⇒ 栈完全平衡）。""",
"""@ 桩型 = 8B「不碰栈」纯跳转，覆盖 0x080041BC..0x080041C3（4 条半字）：
@     b500 push {lr} / 1c02 adds r2,r0,#0 / 7a90 ldrb r0,[r2,#10] / 2801 cmp r0,#1
@ 🔴 跳板**只重放后 3 条** —— 第 1 条 `push {lr}` 不许重放：
@   入口时 lr 就是**调用者的返回地址**（桩用 `bx`，不回写 lr），它经跳板开头的
@   `push {r4,lr}` / `pop {r4}` 之后正留在栈顶 ⇒ **已等价于原体那条 push**。
@   再压一次 = 把 `bl v17_blank_tile_C` 残留在 lr 里的**垃圾**压进原体的返回槽
@   ⇒ 续跑 0x080041C4 后原体末尾 `pop {pc}` 弹垃圾当 PC ⇒ **打开菜单立刻重启**
@   （v17 原版就是这么写的，v17.1 修；用户实测「打开开始菜单直接就重启了」）。
@   ⇒ 正常路径栈相对入口净 0，与原体一致。「强制 0」路径用入口那份 lr（`pop {pc}`）。""",
    'entry 头注释')

s = rep(s,
"""    @ —— 照官方走：重放被桩覆盖的 4 条半字，再落到 0x080041C4 ——
    push    {lr}                       @ 重放 0x080041BC
    adds    r2, r0, #0                 @ 重放 0x080041BE""",
"""    @ —— 照官方走：重放被桩覆盖的**后 3 条**半字，再落到 0x080041C4 ——
    @ 🔴 原体第 1 条 `push {lr}` **不许重放**：入口 lr = 调用者返回地址（桩用 bx，
    @   不回写 lr），经上面 `push {r4,lr}` / `pop {r4}` 后它正留在栈顶，已等价于
    @   原体那条 push。v17 原版在这里又压了一次，压进去的是 `bl v17_blank_tile_C`
    @   残留在 lr 里的垃圾 ⇒ 原体 `pop {pc}` 弹垃圾 ⇒ 打开菜单立刻重启（v17.1 修）。
    adds    r2, r0, #0                 @ 重放 0x080041BE""",
    'entry 跳板体')

s = rep(s,
"""    pop     {pc}                       @ 栈顶正是入口那份 lr""",
"""    pop     {pc}                       @ 栈顶 = 入口那份 lr（跳板净留 1 字 = 原体 push{lr}）""",
    'entry force-zero 注释')

edits.append((ENTRY, s, crlf))

# ------------------------------------------------- 2. verify_v17_static.py
v, crlf2 = load(VER)

v = rep(v,
    "    V17 跳板必须重放原体 4 条半字并含续跑点 0x080041C5",
    "    V17 跳板只重放原体后 3 条半字（`push {lr}` 由栈上那份代替）并含续跑点 0x080041C5；\n"
    "    跳板内 push 只允许 1 次（多一次 = 把垃圾压进原体返回槽 ⇒ 开菜单即重启）",
    'verify docstring')

v = rep(v,
"""# v17 跳板：必须重放原体前 4 条半字（push {lr} / adds r2 / ldrb / cmp）
orig4 = O[off(0x080041BC):off(0x080041BC) + 8]
chk("v17 跳板内重放原体 4 条半字 (%s)" % hx(orig4),
    orig4 in GB[BLK - INJ_LO:BLK - INJ_LO + 0x26])""",
"""# v17 跳板：只重放原体的**后 3 条**半字（0x080041BE / C0 / C2）。
# 🔴 第 1 条 `push {lr}` 不许重放：入口 lr 就是调用者返回地址（桩用 bx 不回写 lr），
#    它经 `push {r4,lr}` / `pop {r4}` 后留在栈顶 = 原体那条 push 的等价物。
#    v17 原版在这里多压一次，压进的是 C 调用残留在 lr 的垃圾 ⇒ 原体 pop {pc} 弹垃圾
#    ⇒ 打开开始菜单立刻重启（用户实测）。本判据把它钉死。
BLKSZ = 0x26
blk_bytes = GB[BLK - INJ_LO:BLK - INJ_LO + BLKSZ]
replay3 = O[off(0x080041BE):off(0x080041BE) + 6]
chk("v17 跳板内重放原体后 3 条半字 (%s)" % hx(replay3), replay3 in blk_bytes)
n_push = sum(1 for k in range(0, BLKSZ, 2)
             if (u16(GB, BLK - INJ_LO + k) & 0xFE00) == 0xB400)
chk("v17 跳板 push 只允许 1 次（入口 push {r4,lr}；再多一份就把垃圾压进原体的返回槽）"
    "  [实际 %d]" % n_push, n_push == 1)
n_pop = sum(1 for k in range(0, BLKSZ, 2)
            if (u16(GB, BLK - INJ_LO + k) & 0xFE00) == 0xBC00)
chk("v17 跳板 pop 恰好 2 次（pop {r4} 复原现场 + 强制 0 路径 pop {pc} 返回）"
    "  [实际 %d]" % n_pop, n_pop == 2)""",
    'verify 判据')

edits.append((VER, v, crlf2))

for path, text, crlf in edits:
    save(path, text, crlf)
    print('WROTE %-72s %d B  (CRLF=%s)' % (path, os.path.getsize(path), crlf))
print('OK')
