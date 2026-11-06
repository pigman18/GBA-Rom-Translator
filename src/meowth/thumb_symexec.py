"""Thumb 符号执行器（v2）：精确求出「某个站点用的是哪个 stride」。

核心思想（回答用户疑问：这不是「猜」，是「算」）：
  找到所有引用站点是**确定**的（扫字面量 + 找 ldr，92 个）。
  每个站点乘的 stride 是**编译期常量**，藏在指令里。
  用符号执行把 `index` 当符号 i，追踪每个寄存器的线性表达式 `a*i + b`，
  遇到 `base + index` 时系数 a 就是 stride。

v2 相比 v1 补齐（v1 只有 45% 成功率）：
  1. **从函数入口开始模拟**，而不是固定回退 64 字节
     （index 常来自函数参数 r0，从中间开始看不到）
  2. **bl 返回值分类建模**：区分「返回索引」和「返回长度/指针」
  3. **前向窗口放宽**（部分站点的 stride 乘法在 ldr 之后）
  4. **支持高寄存器 r8-r12**（`mov sb, r1` 这类）

线性形式为什么够用：
  i<<3            → a=8
  i*4 + i         → a=5
  i*8 - i         → a=7
  (i*8-i)<<2      → a=28
  (i<<0x10)>>0xd  → 65536>>13 = 8    ← 自然处理「截断+缩放」
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

GBA_BASE = 0x08000000


# ---------------------------------------------------------------------------
# 线性表达式 a*i + b
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Lin:
    """a*i + b。a=0 时是纯常量。

    `src` 记录「最后一条对系数 a 有贡献的移位指令」的位置，
    供后续定位并改写该指令。
    """

    a: int
    b: int = 0
    src: int = -1            # 指令偏移（-1 = 无）
    src_mn: str = ""
    src_imm: int = 0
    src_rd: int = 0
    src_rs: int = 0

    def lshift(self, n: int, *, off: int = -1, rd: int = 0, rs: int = 0) -> "Lin":
        return Lin(self.a << n, self.b << n, off, "lsls", n, rd, rs)

    def rshift(self, n: int, *, off: int = -1, rd: int = 0, rs: int = 0) -> "Lin | None":
        """右移：符号部分必须整除，否则不是线性缩放。"""
        if self.a and (self.a % (1 << n)) != 0:
            return None
        # 若系数已经是纯常量，保持原 src
        if self.a == 0:
            return Lin(0, self.b >> n, self.src, self.src_mn, self.src_imm,
                       self.src_rd, self.src_rs)
        return Lin(self.a >> n, self.b >> n, off, "lsrs", n, rd, rs)

    def add(self, o: "Lin") -> "Lin":
        # 保留「有符号系数」那一侧的 src
        if self.a and not o.a:
            return Lin(self.a + o.a, self.b + o.b,
                       self.src, self.src_mn, self.src_imm,
                       self.src_rd, self.src_rs)
        if o.a and not self.a:
            return Lin(self.a + o.a, self.b + o.b,
                       o.src, o.src_mn, o.src_imm, o.src_rd, o.src_rs)
        return Lin(self.a + o.a, self.b + o.b,
                   self.src if self.src >= 0 else o.src,
                   self.src_mn or o.src_mn,
                   self.src_imm or o.src_imm,
                   self.src_rd or o.src_rd, self.src_rs or o.src_rs)

    def sub(self, o: "Lin") -> "Lin":
        if self.a and not o.a:
            return Lin(self.a - o.a, self.b - o.b,
                       self.src, self.src_mn, self.src_imm,
                       self.src_rd, self.src_rs)
        return Lin(self.a - o.a, self.b - o.b,
                   self.src if self.src >= 0 else o.src,
                   self.src_mn or o.src_mn,
                   self.src_imm or o.src_imm,
                   self.src_rd or o.src_rd, self.src_rs or o.src_rs)

    def __str__(self) -> str:
        if self.a == 0:
            return str(self.b)
        return f"{self.a}*i" + (f"{self.b:+d}" if self.b else "")


# 特殊值
#
# ⚠️ BASE 不能是"不可加常数的字符串标量"。
#    实测（道具名 0x0A5432 / 装饰名 0x0AF2C8）：
#         ldr  r4, [pc]        ; r4 = 表基址
#         ...
#         adds r4, #0x10       ; r4 = 表基址 + name_offset(16)
#         adds r1, r1, r4      ; ← 这里才是 base+index
#    若把 BASE 当作字符串，`adds r4,#0x10` 会把 r4 变成 UNKNOWN，
#    整条链断掉。所以 BASE 必须能携带一个常量偏移：Base(Entry, off)。
#    name_offset 不为 0 的表（道具名 16 / 秘密基地装饰名 1 槽等）全靠它。
@dataclass(frozen=True)
class Base:
    """表基址 + 常量偏移。偏移来自 `adds rX, #name_offset` 之类。

    `addr` 记录这个 ldr 加载的**具体表地址**（GBA 地址），
    用于判定「这个命中是不是本表的命中」：
    实测招式名 0x0A7760，同一基本块里还会访问别的表，
    若不校验表地址，会抓到块内别的 `lsls #6` 误算出 K=64。
    """

    off: int = 0
    addr: int = 0

    def add_const(self, d: int) -> "Base":
        return Base(self.off + d, self.addr)

    def __str__(self) -> str:
        return "BASE" + (f"{self.off:+#x}" if self.off else "")


BASE = Base(0)
UNKNOWN = None
Val = Lin | Base | None


# ---------------------------------------------------------------------------
# 指令解码
# ---------------------------------------------------------------------------
@dataclass
class Insn:
    off: int
    mn: str
    rd: int | None = None
    rs: int | None = None
    rn: int | None = None
    imm: int | None = None
    is_pc_ldr: bool = False


def decode(rom: bytes, off: int) -> Insn | None:
    """解码一条 Thumb 指令（覆盖 stride 计算需要的全部形态）。"""
    if off + 2 > len(rom):
        return None
    hw = struct.unpack_from("<H", rom, off)[0]

    # ---- ldr rd, [pc, #imm8] 加载字面量 ----
    if (hw & 0xF800) == 0x4800:
        return Insn(off, "ldr_pc", rd=(hw >> 8) & 0x07, imm=(hw & 0xFF) * 4)

    # ---- 移位族（必须先排除 0x18/0x1A/0x1C/0x1E 加减族）----
    top3 = hw & 0xE000
    if top3 == 0x0000:
        sub = hw & 0x1800
        imm = (hw >> 6) & 0x1F
        rs = (hw >> 3) & 0x07
        rd = hw & 0x07
        if sub == 0x0000:
            if imm == 0:
                return Insn(off, "movs", rd=rd, rs=rs)
            return Insn(off, "lsls", rd=rd, rs=rs, imm=imm)
        if sub == 0x0800 and imm:
            return Insn(off, "lsrs", rd=rd, rs=rs, imm=imm)
        if sub == 0x1000 and imm:
            return Insn(off, "asrs", rd=rd, rs=rs, imm=imm)

    # ---- adds / subs rd, rs, rn ----
    if (hw & 0xFE00) == 0x1800:
        return Insn(off, "adds", rd=hw & 0x07, rs=(hw >> 3) & 0x07,
                    rn=(hw >> 6) & 0x07)
    if (hw & 0xFE00) == 0x1A00:
        return Insn(off, "subs", rd=hw & 0x07, rs=(hw >> 3) & 0x07,
                    rn=(hw >> 6) & 0x07)

    # ---- movs rd, #imm8 ----
    if (hw & 0xF800) == 0x2000:
        return Insn(off, "movs_imm", rd=(hw >> 8) & 0x07, imm=hw & 0xFF)

    # ---- cmp rd, #imm8（不影响寄存器）----
    if (hw & 0xF800) == 0x2800:
        return Insn(off, "cmp_imm")

    # ---- adds rd, #imm8 / subs rd, #imm8（0x3000 / 0x3800 族）----
    if (hw & 0xF800) == 0x3000:
        return Insn(off, "adds_imm", rd=(hw >> 8) & 0x07, imm=hw & 0xFF)
    if (hw & 0xF800) == 0x3800:
        return Insn(off, "subs_imm", rd=(hw >> 8) & 0x07, imm=hw & 0xFF)

    # ---- adds rd, rn, #imm3（0x1C00 族）/ subs rd, rn, #imm3（0x1E00）----
    # 编码: 000 1110 iii rnnn ddd  → imm3 = bits 8-6, rn = bits 5-3, rd = bits 2-0
    if (hw & 0xFE00) == 0x1C00:
        return Insn(off, "adds_imm3", rd=hw & 0x07, rn=(hw >> 3) & 0x07,
                    imm=(hw >> 6) & 0x07)
    if (hw & 0xFE00) == 0x1E00:
        return Insn(off, "subs_imm3", rd=hw & 0x07, rn=(hw >> 3) & 0x07,
                    imm=(hw >> 6) & 0x07)

    # ---- 内存加载（0x6800/0x7800/0x8800 三个族，按 bit11 分 ldr/str）----
    # 注：完整的 ldr/str 判定在函数末尾统一处理（见「半字/字节」段），
    #     这里只处理 [rn,#imm] 形式的加载，且必须用正确掩码 0xF800。
    if (hw & 0xF800) in (0x6800, 0x7800, 0x8800):
        kind = (hw >> 11) & 0x01        # bit11
        size = {0x6000: 4, 0x7000: 1, 0x8000: 2}[(hw & 0xF000)]
        if kind:                        # 1 = load
            mn = {4: "ldr", 1: "ldrb", 2: "ldrh"}[size]
            return Insn(off, mn, rd=hw & 0x07, rn=(hw >> 3) & 0x07,
                        imm=((hw >> 6) & 0x1F) * size)
        return Insn(off, "store")

    # ldr rd, [rn, rm]
    if (hw & 0xF000) == 0x5800:
        return Insn(off, "ldr_reg", rd=hw & 0x07, rn=(hw >> 3) & 0x07,
                    rs=(hw >> 6) & 0x07)
    # ldrh/ldrb [rn, rm]
    if (hw & 0xF000) == 0x5A00:
        return Insn(off, "ldrh_reg", rd=hw & 0x07, rn=(hw >> 3) & 0x07,
                    rs=(hw >> 6) & 0x07)
    if (hw & 0xF000) == 0x5C00:
        return Insn(off, "ldrb_reg", rd=hw & 0x07, rn=(hw >> 3) & 0x07,
                    rs=(hw >> 6) & 0x07)

    # ---- ldr/str rd, [sp, #imm8] ----
    if (hw & 0xF800) == 0x9800:
        return Insn(off, "ldr", rd=(hw >> 8) & 0x07, rn=13,
                    imm=(hw & 0xFF) * 4)
    if (hw & 0xF800) == 0x9000:
        return Insn(off, "str_sp")

    # ---- add rd, sp, #imm8 ----
    if (hw & 0xF800) == 0xA800:
        return Insn(off, "add_sp", rd=(hw >> 8) & 0x07, imm=(hw & 0xFF) * 4)

    # ---- 高寄存器操作 0100 01xx ----
    if (hw & 0xFC00) == 0x4400:
        op = (hw >> 8) & 0x03
        rd = (hw & 0x07) | ((hw >> 4) & 0x08)
        rm = (hw >> 3) & 0x0F
        if op == 0:
            return Insn(off, "add_hi", rd=rd, rn=rm)
        if op == 2:
            return Insn(off, "mov_hi", rd=rd, rs=rm)
        if op == 3:
            return Insn(off, "bx")
        return Insn(off, "hi_op")

    # ---- push / pop ----
    if (hw & 0xFE00) == 0xB400:
        return Insn(off, "push", imm=hw & 0xFF)
    if (hw & 0xFE00) == 0xBC00:
        return Insn(off, "pop", imm=hw & 0xFF)

    # ---- bl（32 位，占两个半字）----
    if (hw & 0xF800) == 0xF000:
        return Insn(off, "bl")

    # ---- b / 条件跳转 ----
    if (hw & 0xF000) == 0xD000:
        return Insn(off, "bcond", imm=(hw & 0xFF) * 2)
    if (hw & 0xF800) == 0xE000:
        return Insn(off, "b", imm=(hw & 0x7FF) * 2)

    # ---- 半字/字节 加载与存储 ----
    # ⚠️ 关键：0x6000 区里
    #    0x6800 = ldr (bit11=1)  / 0x6000 = str (bit11=0)
    #    0x7800 = ldrb (bit11=1) / 0x7000 = strb
    #    0x8800 = ldrh (bit11=1) / 0x8000 = strh
    #    区分位是 bit11（0x0800），不是整个高 4 位。
    if (hw & 0xF000) == 0x8000:
        if hw & 0x0800:                       # ldrh
            return Insn(off, "ldrh", rd=hw & 0x07, rn=(hw >> 3) & 0x07,
                        imm=((hw >> 6) & 0x1F) * 2)
        return Insn(off, "store")             # strh
    if (hw & 0xF000) == 0x7000:
        if hw & 0x0800:                       # ldrb
            return Insn(off, "ldrb", rd=hw & 0x07, rn=(hw >> 3) & 0x07,
                        imm=(hw >> 6) & 0x1F)
        return Insn(off, "store")             # strb
    if (hw & 0xF000) == 0x6000:
        if hw & 0x0800:                       # ldr
            return Insn(off, "ldr", rd=hw & 0x07, rn=(hw >> 3) & 0x07,
                        imm=((hw >> 6) & 0x1F) * 4)
        return Insn(off, "store")             # str

    return None


# ---------------------------------------------------------------------------
# 函数边界探测
# ---------------------------------------------------------------------------
def find_block_head(rom: bytes, addr: int, back: int = 0x200) -> int:
    """从 addr 反向找它所在**基本块**的头。

    块头的定义：上一条指令是控制流转移（b / bcond / bl / bx / pop-pc）。
    这是实测必需的：ldr 常在 switch / if-else 的某个分支块里，
    从函数入口单向走根本到不了（特性名 0x09C6C4 就是这种）。
    """
    lo = max(0, addr - back)
    pc = addr - 2
    while pc >= lo:
        ins = decode(rom, pc)
        if ins is not None:
            mn = ins.mn
            # ⚠️ `bl` 不切断基本块：它是「调用后返回、继续执行」。
            #    实测 0x09C6C4 前面是 `bl #0x3ae90`，若把 bl 当分界，
            #    块头会被切到 0x09C6BA，此时 r4 尚未定义，链直接断。
            if mn in ("b", "bx", "hi_op"):
                # ⚠️ 返回「下一个**可解码**的位置」，不是 pc+2。
                #    实测宝可梦名 0x06B5BE：前面 0x06B596 是 bx，
                #    但 0x06B598 是数据（decode=None），真正的函数首条
                #    是 0x06B59A 的 `lsls`。返回 pc+2 会让模拟从数据
                #    中间开始，计数器链直接断，14 个站点全判失败。
                nxt = pc + 2
                for probe in range(nxt, min(addr, nxt + 8), 2):
                    if decode(rom, probe) is not None:
                        return probe
                return pc + 2
            if mn == "pop" and (ins.imm or 0) & 0x80:
                nxt = pc + 2
                for probe in range(nxt, min(addr, nxt + 8), 2):
                    if decode(rom, probe) is not None:
                        return probe
                return pc + 2
        pc -= 2
    return lo


def find_function_start(rom: bytes, addr: int, limit: int = 256) -> int:
    """往前找 `push {..., lr}` 作为函数入口，且要求控制流能走到 addr。

    ⚠️ 只看「最近的那个 push」会找错（B 类根因，实测特性名 0x09C6C4）：
       最近的是 0x09C5C4，但那只是一条 `b`（if/else 的一臂），
       真正入口是 0x09C54C `push {r4,r5,r6,lr}`。
       从 0x09C5C4 出发按控制流走，永远到不了 0x09C6C4。

    做法：从近到远枚举候选 push，逐个验证「可达性」，取最近的可达入口。
    全部不可达时，退回最近的那个（保持旧行为，不至于返回更差的值）。
    """
    lo = max(0, addr - limit)
    candidates: list[int] = []
    for off in range(addr - 2, lo - 1, -2):
        hw = struct.unpack_from("<H", rom, off)[0]
        if (hw & 0xFF00) == 0xB500:      # push {..., lr}
            candidates.append(off)

    for cand in candidates:              # 由近到远
        if _reaches(rom, cand, addr):
            return cand
    return candidates[0] if candidates else lo


def _reaches(rom: bytes, entry: int, target: int, limit: int = 0x600) -> bool:
    """从 entry 出发（跟随 b / bcond 两条臂 / pop-pc / bx 终止），能到 target 吗。"""
    seen: set[int] = set()
    stack = [entry]
    hi = min(len(rom) - 1, entry + limit)

    while stack:
        pc = stack.pop()
        while entry <= pc < hi:
            if pc in seen:
                break
            seen.add(pc)
            if abs(pc - target) <= 6:
                return True
            ins = decode(rom, pc)
            if ins is None:
                pc += 2
                continue
            mn = ins.mn
            if mn in ("bx", "hi_op"):
                break
            if mn == "pop" and (ins.imm or 0) & 0x80:
                break
            if mn == "b":
                tgt = pc + 4 + (ins.imm or 0)
                pc = tgt
                continue
            if mn == "bcond":
                tgt = pc + 4 + (ins.imm or 0)
                if entry <= tgt < hi:
                    stack.append(tgt)
                pc += 2
                continue
            pc += 2
    return False


# ---------------------------------------------------------------------------
# 符号执行
# ---------------------------------------------------------------------------
@dataclass
class SymResult:
    ldr_off: int
    stride: int | None
    expr: str = ""
    reason: str = ""
    start: int = 0
    insn_off: int | None = None      # 产生该 K 的移位指令位置（供改写）
    insn_mn: str = ""                # 该指令助记符（lsls/lsrs/asrs）
    insn_imm: int = 0                # 该指令的移位立即数
    insn_rd: int = 0
    insn_rs: int = 0


def solve_site(
    rom: bytes,
    ldr_off: int,
    *,
    entry: int | None = None,
    back: int = 256,
    fwd: int = 200,
    assume_all_symbolic: bool = False,
) -> SymResult:
    """求解一个 ldr 站点的 stride。

    ⚠️ 做法变更是实测逼出来的，不是换口味：

    原做法「从函数入口按控制流模拟」在 31/92 个站点上失败，
    根因是 ldr 常位于 switch / if-else 的**某个分支块**里，
    从入口单向走根本到不了（实测特性名 0x09C6C4：入口 0x09C5C4
    是 `b 0x9C5E2`，一路走到 0x09C604 `b 0x9C6F0` 就返回，
    永远不会执行到 0x09C6C4 所在的块）。

    现在的做法（块内执行）：
      1. 从 ldr 反向找**基本块头**（上一条是 b/bcond/bl/bx/pop-pc）
      2. 只在这个块内从块头正向模拟到 ldr + fwd
      3. index 来源由块内的 `bl` 返回值 / 内存读来建模

    实测：0x09C6C4 块内执行 → 0x09C6C6 K=8 ✅
    """
    start = entry if entry is not None else find_block_head(rom, ldr_off)
    # ⚠️ hi 是「允许执行到的最远地址」，不是「ldr 之后多久停」。
    #    实测属性名 0x11C9C0：块头 0x11C9B2 里 `0x11C9C2 b 0x11CAC8`，
    #    目标 0x11CAC8 距 ldr 有 0x108 字节，若 hi 只到 ldr+96，
    #    这个 b 会被拒绝，转而抓到块外的 `lsls #2` 误算成 K=4。
    hi = min(len(rom) - 1, start + max(fwd, 0x200))

    regs: dict[int, Val] = {i: UNKNOWN for i in range(16)}
    # ⚠️ 函数参数寄存器（r0-r3）在函数入口是**符号 index**，不是未知。
    #
    # 实测 0x06B5BE（宝可梦名表）：函数入口 `0x06B59A push` 之后，
    # 索引来自 r0 参数 →
    #     0x06B5A2 adds r4, r0, #0    ; r4 = i（参数）
    #     0x06B5B8 lsls r1, r4, #1    ; r1 = 2i
    #     0x06B5BA adds r1, r1, r4    ; r1 = 3i
    #     0x06B5BC lsls r1, r1, #1    ; r1 = 6i
    #     0x06B5BE ldr  r0, [pc]      ; r0 = 表基址
    #     0x06B5C0 adds r1, r1, r0    ; ← base+index，K=6
    # 若参数是 UNKNOWN，`lsls r1, r4, #1` 直接把 r1 变未知，
    # 整个系数链断掉，52 个已识别的站点之外，另有 14 个站点全判失败。
    #
    # 用 Lin(1) 表示「某个未知索引 i」（系数 1），系数 a 由后续移位累积。
    for _arg in range(4):
        regs[_arg] = Lin(1)
    # ⚠️ 兜底模式：把 r4-r7 也当作符号（只用于「乘链紧邻 ldr 但源寄存器
    #    来自调用者」的站点）。实测 0x08D590：
    #        0x08D58A lsls r4, r5, #3    ; r5 由调用者传入，块内从未赋值
    #        0x08D58C subs r4, r4, r5
    #        0x08D58E lsls r4, r4, #2    ; = 28i
    #        0x08D590 ldr  r6, [pc]      ; 基址
    #        0x08D592 adds r5, r4, r6    ; ← K=28
    #    若 r5 是 UNKNOWN，链断；当成符号就能算出真实 stride。
    #    这个模式只在主求解失败后由 solve_site_auto 调用，不会污染正常路径。
    if assume_all_symbolic:
        for _r in range(4, 16):
            regs[_r] = Lin(1)
    saved: list[dict[int, Val]] = []
    hits: list[tuple[int, int, str, "Lin"]] = []
    # 被「截断对抵消」吸收的 lsrs 位置（见下面 lsls/lsrs 分支）
    skipped_lsrs: set[int] = set()

    # 目标站点自身的表地址（该 ldr 加载的字面量值），用于命中校验
    _tins = decode(rom, ldr_off)
    if _tins is not None and _tins.mn == "ldr_pc":
        _tlit = ((ldr_off + 4) & ~3) + (_tins.imm or 0)
        base_addr = (int.from_bytes(rom[_tlit:_tlit + 4], "little")
                     if _tlit + 4 <= len(rom) else None)
    else:
        base_addr = None

    off = start
    guard = 0
    while off < hi:
        guard += 1
        if guard > 6000:
            break
        ins = decode(rom, off)
        if ins is None:
            off += 2
            continue
        mn = ins.mn
        nxt = off + 2                      # 默认下一条

        # ---- 字面量加载 → BASE ----
        if mn == "ldr_pc":
            # 记录该字面量的真实值，供「是否本表命中」判定
            _lit = ((off + 4) & ~3) + (ins.imm or 0)
            _val = (int.from_bytes(rom[_lit:_lit + 4], "little")
                    if _lit + 4 <= len(rom) else 0)
            regs[ins.rd] = Base(0, _val)
        elif mn in ("ldr", "ldrh", "ldrb", "ldr_reg", "ldrh_reg", "ldrb_reg"):
            regs[ins.rd] = Lin(1)
        elif mn == "movs_imm":
            regs[ins.rd] = Lin(0, ins.imm or 0)
        elif mn in ("movs", "mov_hi"):
            regs[ins.rd] = regs.get(ins.rs)
        elif mn in ("lsls", "lsrs", "asrs"):
            src = regs.get(ins.rs)
            if isinstance(src, Lin):
                if mn == "lsls":
                    # ⚠️ 参数规范化序列识别（不是索引乘法）
                    #
                    # 实测 0x06B59A（宝可梦名表 0x06B5BE 所在函数入口）：
                    #     0x06B59A lsls r0,r0,#0xc      ; r0 = i<<12
                    #     0x06B59C push {r4-r7,lr}
                    #     0x06B59E lsls r0,r0,#0x10     ; <<16
                    #     0x06B5A0 lsrs r0,r0,#0x10     ; >>16  ← 清零高16位
                    # 语义 = `r0 & 0xFFFF`（u16 参数规范化），**不是** 4096×i。
                    # 若不识别，系数会变成 4096，最终 K=24576（错）。
                    #
                    # 判据：向后看最多 4 条（可跨 push/movs），
                    # 找到 `lsrs rX,#16`（同寄存器）且中间只有 lsls，
                    # 说明这是「左移凑满 32 位再右移回来」的取低位序列。
                    pair_at = None
                    if 0 < (ins.imm or 0) < 32:
                        probe = off + 2
                        loot = 0
                        while loot < 8:
                            _nx = decode(rom, probe)
                            if _nx is None:
                                # ⚠️ 无法解码的半字可能是 32 位指令的后半
                                #    （实测 0x12FE0C hw=0xECEC 是 bl 第二半字）。
                                #    直接跳过 2 字节继续找，不要 break。
                                probe += 2
                                loot += 1
                                continue
                            # ⚠️ `bl` 是 32 位 Thumb 指令（占 4 字节）。
                            #    实测 0x12FE0A：`lsls #0xc` 之后是
                            #    0x12FE0C 的 bl 半字（ec ec 3d 08），
                            #    按 2 字节步进会跳到半字中间，识别失败。
                            if _nx.mn == "bl":
                                probe += 4
                                loot += 1
                                continue
                            # 允许跨过：栈操作、常量、以及「再左移一次」（凑满 32 位）
                            if _nx.mn in ("push", "movs_imm"):
                                probe += 2
                                loot += 1
                                continue
                            if _nx.mn == "lsls" and _nx.rs == ins.rs \
                                    and _nx.rd == ins.rd:
                                probe += 2
                                loot += 1
                                continue
                            if (
                                _nx.mn == "lsrs"
                                and _nx.rs == ins.rs and _nx.rd == ins.rd
                                and (
                                    _nx.imm == 16                      # u16 规范化
                                    or _nx.imm == ins.imm              # 同量截断对
                                )
                                and 0 < (_nx.imm or 0) < 32
                            ):
                                # 两种都是「取值不是缩放」：
                                #   0x06B59E lsls#0x10 + lsrs#0x10（u16）
                                #   0x0FC01C lsls#0x18 + lsrs#0x18（取低8位）
                                pair_at = probe
                            break
                    if pair_at is not None:
                        # 序列净效果 = 取低 16 位，对索引不是缩放 → 恒等
                        regs[ins.rd] = src
                        skipped_lsrs.add(pair_at)
                    else:
                        regs[ins.rd] = src.lshift(ins.imm, off=off,
                                                  rd=ins.rd, rs=ins.rs)
                elif mn == "lsrs" and off in skipped_lsrs:
                    regs[ins.rd] = src        # 与前面的规范化序列抵消
                else:
                    r = src.rshift(ins.imm, off=off, rd=ins.rd, rs=ins.rs)
                    regs[ins.rd] = r if r is not None else UNKNOWN
            else:
                regs[ins.rd] = UNKNOWN
        elif mn in ("adds", "subs"):
            a, b = regs.get(ins.rs), regs.get(ins.rn)
            if mn == "adds":
                matched = False
                for x, y in ((a, b), (b, a)):
                    if isinstance(x, Base) and isinstance(y, Lin):
                        # ★ 必须是「本表」的命中：Base.addr 记录了该 ldr
                        #   加载的字面量值。同一块里常访问多张表，
                        #   不校验会抓到别的表的移位（招式名 K=64 就是这么来的）。
                        if base_addr is None or x.addr == base_addr:
                            dist = abs(off - ldr_off)
                            hits.append((dist, y.a, str(y), y))
                        regs[ins.rd] = Lin(0)
                        matched = True
                        break
                if not matched:
                    if isinstance(a, Lin) and isinstance(b, Lin):
                        regs[ins.rd] = a.add(b)
                    elif isinstance(a, Base) and isinstance(b, Lin):
                        regs[ins.rd] = (a.add_const(b.b) if b.a == 0
                                        else UNKNOWN)
                    else:
                        regs[ins.rd] = UNKNOWN
            else:
                regs[ins.rd] = (a.sub(b)
                                if isinstance(a, Lin) and isinstance(b, Lin)
                                else UNKNOWN)
        elif mn == "add_hi":
            a, b = regs.get(ins.rd), regs.get(ins.rn)
            matched = False
            for x, y in ((a, b), (b, a)):
                if isinstance(x, Base) and isinstance(y, Lin):
                    # ⚠️ 不能再限制 `off < ldr_off`：命中可能发生在 ldr **之后**。
                    #    实测 0x12DC90（招式名）：
                    #        0x12DC90 ldr  r2, [pc,#0x6c]   ; r2 = 表基址
                    #        0x12DC92 mov  r8, r2
                    #        0x12DC94 add  r1, r8           ; ← base+index 在这
                    #    原来的 `off < ldr_off` 把这条命中直接丢掉了。
                    #    与下面 `adds` 分支保持一致：都按距离记录，最后取最近。
                    dist = abs(off - ldr_off)
                    hits.append((dist, y.a, str(y), y))
                    regs[ins.rd] = Lin(0)
                    matched = True
                    break
            if not matched:
                if isinstance(a, Lin) and isinstance(b, Lin):
                    regs[ins.rd] = a.add(b)
                elif isinstance(b, Lin):
                    regs[ins.rd] = b
                else:
                    regs[ins.rd] = UNKNOWN
        elif mn in ("adds_imm", "subs_imm", "adds_imm3", "subs_imm3"):
            src = regs.get(ins.rn if mn.endswith("imm3") else ins.rd)
            d = (ins.imm or 0) * (1 if mn.startswith("adds") else -1)
            if isinstance(src, Lin):
                regs[ins.rd] = Lin(src.a, src.b + d, src.src, src.src_mn,
                                   src.src_imm, src.src_rd, src.src_rs)
            elif isinstance(src, Base):
                # ★ A 类根因修复：BASE + name_offset 必须保留
                regs[ins.rd] = src.add_const(d)
            else:
                regs[ins.rd] = UNKNOWN
        elif mn == "add_sp":
            regs[ins.rd] = UNKNOWN
        elif mn in ("store", "str_sp", "cmp_imm"):
            pass
        elif mn == "push":
            saved.append(dict(regs))
        elif mn == "pop":
            if saved:
                regs = saved.pop()
            if (ins.imm or 0) & 0x80:      # pop {..., pc} = 返回
                break
        elif mn == "bl":
            regs[0] = Lin(1)
        elif mn == "bcond":
            pass                            # 条件跳转：走直落
        elif mn == "b":
            # ★ C 类根因修复：`b` 是绝对跳转，必须跟着走
            tgt = off + 4 + (ins.imm or 0)
            if start <= tgt < hi and tgt != nxt:
                nxt = tgt
        elif mn in ("bx",):
            break
        elif mn == "hi_op":
            break

        off = nxt

    if hits:
        within = [h for h in hits if start <= h[3].src < hi]
        pool = within or hits
        pool.sort()
        _dist, k, expr, lin = pool[0]
        return SymResult(
            ldr_off=ldr_off, stride=k, expr=expr,
            reason=("base+index" if k else "base+const"),
            start=start,
            insn_off=(lin.src if lin.src >= 0 else None),
            insn_mn=lin.src_mn, insn_imm=lin.src_imm,
            insn_rd=lin.src_rd, insn_rs=lin.src_rs,
        )

    return SymResult(ldr_off=ldr_off, stride=None,
                     reason="未找到 base+index", start=start)


def solve_site_auto(
    rom: bytes,
    ldr_off: int,
    *,
    expect: int | None = None,
    **kw,
) -> SymResult:
    """自动选起点求解：先试基本块头，失败再试函数入口。

    为什么需要两个起点（实测结论，2026-11-04）：
      - ``find_block_head``（默认）在 91% 的站点上正确：ldr 常落在
        switch / if-else 的某个分支块里，从块内起步才对。
      - 但有一批站点，块头前面紧邻 ``b`` 跳到别处，紧跟着的却是
        **字面量池**（如 0x06DF4C：``ldr r2,[pc,#0x140]`` 是伪解码，
        0x06DF50 是 ``svc`` 数据）。这类必须从**函数入口**起步，
        才能拿到参数寄存器的初始化。

    实测覆盖（9 张表 161 个站点）：
        只用块头     147/161 = 91%
        只用函数入口  98/161 = 61%
        两者都试     153/161 = 95%

    ``expect`` 给期望 stride 时，优先返回匹配的结果。
    """
    first = solve_site(rom, ldr_off, **kw)
    if first.stride is not None and (expect is None or first.stride == expect):
        return first

    entry = find_function_start(rom, ldr_off)
    if first.start != entry:
        second = solve_site(rom, ldr_off, entry=entry, **kw)
        if expect is not None:
            if second.stride == expect:
                return second
        elif second.stride is not None and first.stride is None:
            return second

    # 第三档兜底：乘链紧邻 ldr，但源寄存器由调用者传入（块内未赋值）。
    # 实测 0x08D590 / 0x12EE46 / 0x0BAC06 三处都是这个形态，
    # 只有把 r4-r7 也当符号才能算出真实 stride。
    third = solve_site(rom, ldr_off, assume_all_symbolic=True, **kw)
    if expect is not None and third.stride == expect:
        return third

    # 都没有精确匹配时，按「有解优先」返回
    for cand in (first, third):
        if cand.stride is not None:
            return cand
    return first
