"""结构体表「扩 stride + 字段重排」：名字区变长，字段整体后移。

## 为什么需要这一套

名字旁路（``struct_trampoline.plan_struct_name_ptr``）要求读点形如
``adds rX, rY, #name_off`` —— 能用**同等长度**的 ``ldr rX, [rY, #name_off]``
原地替换。而秘密基地装饰名（0x3C2A44）的读点全是「字段访问」，名字根本
没被 ``StringCopyN`` 拷过（``_find_name_copy_sites`` 返回 0），所以只能让
名字区本身变长。

## 硬约束（实测，不是猜的）

* 名字起始 offset 不变（还是 1）→ 「逐字节读名字」的
  ``ldrb rX, [rY, #1..#11]`` 全部不用改；
* 字段 12/13/14 用 ``ldrb`` 访问，**imm5 上限 31 字节** → 字段起点 ≤ 29，
  名字区最多 28B；
* 字段 18 用 ``strh``（imm5×2 ≤ 62）、20 用 ``ldrh``/``ldr``、
  24 用 ``ldr``（imm5×4 ≤ 124），这三个没压力。

于是 28 → 48：

    旧: [0][1..12 名字 11B][12..20 字段][20..24 描述指针][24..28 未知指针]
    新: [0][1..29 名字 28B][29..32 原12/13/14][32..34 原18]
        [34..38 原20][38..42 原24][42..48 填充]

**代价**：最长的 1 条译文是 7 字（29B），差 1 字节装不进 28B 名字区，
它保留日文；其余 119 条（≤6 字 25B）全部写入。
"""
from __future__ import annotations

import struct

from .patch_table import GBA_BASE
from .table_stride import find_literal_sites

# 偏移单位与编码上限（T1 立即数形态）
import os as _os

_TRACE = bool(_os.environ.get("MEOWTH_STRIDE_TRACE"))

_MEM_OPS: dict[str, tuple[int, int, int]] = {
    "strb": (0x7000, 1, 31),
    "ldrb": (0x7800, 1, 31),
    "strh": (0x8000, 2, 62),
    "ldrh": (0x8800, 2, 62),
    "str": (0x6000, 4, 124),
    "ldr": (0x6800, 4, 124),
}


def _u16(rom: bytes, off: int) -> int:
    return struct.unpack_from("<H", rom, off)[0]


def scan_mul_triplets(
    rom: bytes, lo: int, hi: int, stride: int, max_gap: int = 6
) -> list[tuple[int, int, int, int, int, str]]:
    """找 ``i*stride`` 的三连，**允许第 2、3 条之间夹着无关指令**。

    返回 ``(a0, a1, a2, rd, rs, form)``，``form`` 是 ``add`` / ``sub``。

    为什么要 gap：装饰名的读点 ``0x080FA14C`` 是这样写的::

        lsls r1, r4, #3        ; 8i
        subs r1, r1, r4        ; 7i
        str  r1, [sp, #0x1c]   ; ← 中间存了一次中间值
        lsls r1, r1, #2        ; 28i

    ``table_stride._scan_mul_sites`` 要求三条严格连续，这个函数被整段
    漏掉 —— 22 个 literal 只覆盖 20 个，漏一处步长整表索引错位。
    """
    out: list[tuple[int, int, int, int, int, str]] = []
    end = min(hi, len(rom) - 6)
    for a0 in range(lo, end, 2):
        h0 = _u16(rom, a0)
        if (h0 & 0xF800) != 0x0000:  # lsls imm
            continue
        imm0 = (h0 >> 6) & 0x1F
        rd0 = h0 & 7
        rs0 = (h0 >> 3) & 7
        h1 = _u16(rom, a0 + 2)
        op = h1 & 0xFE00
        if op not in (0x1800, 0x1A00):
            continue
        rd1 = h1 & 7
        rn1 = (h1 >> 3) & 7
        rm1 = (h1 >> 6) & 7
        if rd1 != rd0:
            continue
        if op == 0x1800:
            if not ((rn1 == rd0 and rm1 == rs0) or (rn1 == rs0 and rm1 == rd0)):
                continue
            base_k = (1 << imm0) + 1
            form = "add"
        else:
            if not (rn1 == rd0 and rm1 == rs0):
                continue
            base_k = (1 << imm0) - 1
            form = "sub"
        if base_k <= 0:
            continue
        for a2 in range(a0 + 4, min(a0 + 4 + max_gap * 2, end), 2):
            h2 = _u16(rom, a2)
            if (h2 & 0xF800) != 0x0000:
                # 不是 lsls：若它写了 rd，链条就断了
                if (h2 & 7) == rd1 and (h2 & 0xF800) in (
                    0x0000, 0x1800, 0x1C00, 0x2000, 0x3000, 0x4000, 0x4800, 0x6000,
                ):
                    break
                continue
            imm2 = (h2 >> 6) & 0x1F
            rd2 = h2 & 7
            rs2 = (h2 >> 3) & 7
            if rd2 != rd1 or rs2 != rd1:
                break
            if (base_k << imm2) == stride:
                out.append((a0, a0 + 2, a2, rd2, rs0, form))
            break
    return out


def emit_triplet(rd: int, rs: int, new_stride: int) -> bytes | None:
    """把 ``((1<<n)±1)<<m == new_stride`` 编成三连，寄存器保持 rd/rs。"""
    for form in ("add", "sub"):
        for n in range(0, 32):
            base = (1 << n) + (1 if form == "add" else -1)
            if base <= 1 or new_stride % base:
                continue
            q = new_stride // base
            if q & (q - 1):  # 收尾必须是 lsls 的 2 的幂
                continue
            m = q.bit_length() - 1
            if m > 31:
                continue
            w0 = 0x0000 | (n << 6) | (rs << 3) | rd
            w1 = (0x1800 if form == "add" else 0x1A00) | (rs << 6) | (rd << 3) | rd
            w2 = 0x0000 | (m << 6) | (rd << 3) | rd
            return struct.pack("<HHH", w0, w1, w2)
    return None


def enc_mem_imm(mn: str, imm: int, rn: int, rd: int) -> bytes | None:
    spec = _MEM_OPS.get(mn)
    if spec is None:
        return None
    base, unit, limit = spec
    if imm % unit or imm > limit:
        return None
    return struct.pack("<H", base | ((imm // unit) << 6) | (rn << 3) | rd)


def _decode_mem(h: int) -> tuple[str, int, int, int] | None:
    """识别 T1 立即数形态的 load/store，返回 (mn, imm, rn, rd)。

    ⚠️ 不能按 ``h & 0x0F00`` 判族：imm5 占 bit10-6，会污染 bit8。
    ``ldr r2,[r1,#0x14]`` = 0x694A，``0x694A & 0x0F00 == 0x0900``，
    按 0x0800 匹配就漏了。正确做法是只看 bit15-12 定族，
    用 bit11 区分 load / store。
    """
    top = h & 0xF000
    if top not in (0x6000, 0x7000, 0x8000):
        return None
    unit = {0x6000: 4, 0x7000: 1, 0x8000: 2}[top]
    is_load = bool(h & 0x0800)
    mn = {
        (0x6000, True): "ldr",
        (0x6000, False): "str",
        (0x7000, True): "ldrb",
        (0x7000, False): "strb",
        (0x8000, True): "ldrh",
        (0x8000, False): "strh",
    }[(top, is_load)]
    imm = ((h >> 6) & 0x1F) * unit
    return mn, imm, (h >> 3) & 7, h & 7


def _uncond_b_target(rom: bytes, off: int) -> int | None:
    h = _u16(rom, off)
    if (h & 0xF800) != 0xE000:
        return None
    imm11 = h & 0x7FF
    if imm11 & 0x400:
        imm11 -= 0x800
    return off + 4 + imm11 * 2


def _jump_table_targets(rom: bytes, fs: int, fe: int, off: int) -> list[int]:
    """``mov pc, rX`` 前那条 ``ldr rY,[pc,#n]`` 指向的就是 switch 跳转表。"""
    for back in range(off - 2, max(fs, off - 24), -2):
        hh = _u16(rom, back)
        if (hh & 0xF800) != 0x4800:
            continue
        lit = ((back + 4) & ~3) + (hh & 0xFF) * 4
        if lit + 4 > len(rom):
            continue
        tbl = struct.unpack_from("<I", rom, lit)[0] - GBA_BASE
        if not (0 <= tbl < len(rom) - 4):
            continue
        out: list[int] = []
        for k in range(32):
            v = struct.unpack_from("<I", rom, tbl + k * 4)[0]
            t = (v & ~1) - GBA_BASE
            if not (fs <= t < fe):
                break
            out.append(t)
        return out
    return []


def collect_field_patches(
    rom: bytes,
    funcs: list[tuple[int, int]],
    base: int,
    field_map: dict[int, int],
    triplets: list[tuple[int, int, int, int, int, str]],
) -> tuple[list[dict], str | None]:
    """按控制流跟踪「表条目指针」，改写字段偏移。

    只认三种能形成条目指针的来源，其余一律当未知：

    * ``ldr rX, [pc, #n]`` 且 literal == 表基址 → ``base``
    * 三连乘法的目标寄存器 → ``entry``
    * ``adds rX, rY, rZ`` 里 rY/rZ 是 base/entry → 传播

    ## 为什么要按控制流走，不能线性扫

    ``0x080FA884`` 是 switch：:

        ldrb r0, [r0, #0xd]     ; entry+13
        cmp  r0, #9
        bls  ...
        b    0x80fa9ce          ; ← 无条件分支，case 体在另一条路上
        ...
        mov  pc, r0             ; ← 跳转表

    线性扫会在 ``b`` 处继续往下、把跳转表数据当指令；实测整批
    ``strh [rX,#0x12]``（写 entry+18）一个都没抓到，漏改就会把「数量」
    写进名字区。这里改成：``b`` 把目标压栈后结束当前路径，``mov pc``
    解析跳转表把每个 case 也压栈。

    ## 宁可整表放弃，也不改一半

    命中映射表但基址寄存器**完全没来历**、且该函数从没出现过本表访问 →
    返回失败。改一半 = 索引错位，模拟器 input callback 停摆（实测两次）。
    """
    trip = {a0: (a2, rd) for a0, a1, a2, rd, rs, form in triplets}
    patches: list[dict] = []
    seen_off: set[int] = set()

    def _add(off: int, mn: str, imm: int, rn: int, rd: int, tag: str) -> str | None:
        new_imm = field_map[imm]
        enc = enc_mem_imm(mn, new_imm, rn, rd)
        if enc is None:
            return f"{mn} 偏移 {imm:#x}→{new_imm:#x} 无法编码"
        if off not in seen_off:
            seen_off.add(off)
            patches.append({
                "off": f"0x{off:X}",
                "bytes": enc.hex(" "),
                "label": f"{mn} [r{rn},#{imm:#x}]→#{new_imm:#x}（字段平移·{tag}）",
            })
        return None

    for fs, fe in funcs:
        # 这个函数里有没有「确认指向本表」的证据（三连 / 加载表基址字面量）
        confirmed = any(fs <= a0 < fe for a0, *_ in triplets)
        if not confirmed:
            for q in range(fs, fe - 3, 2):
                hq = _u16(rom, q)
                if (hq & 0xF800) == 0x4800:
                    lit = ((q + 4) & ~3) + (hq & 0xFF) * 4
                    if lit + 4 <= len(rom):
                        if struct.unpack_from("<I", rom, lit)[0] == GBA_BASE + base:
                            confirmed = True
                            break

        pending = [fs]
        visited: set[int] = set()
        while pending:
            start = pending.pop()
            if start in visited or not (fs <= start < fe):
                continue
            visited.add(start)
            state: dict[int, str] = {}
            jump_seen = False
            off = start
            while off < fe - 1:
                h = _u16(rom, off)
                tgt = _uncond_b_target(rom, off)
                if tgt is not None:
                    # 目标压栈；**继续顺序扫**，因为内存里 b 之后紧跟的
                    # 可能正是另一段有效代码（switch 的 fallthrough 分支）。
                    # 遇到 mov pc 时才会 break 掉、改由跳转表决定 case 目标。
                    pending.append(tgt)
                    off += 2
                    continue
                if (h & 0xFF00) == 0xBD00 or (h & 0xFF87) == 0x4700:
                    break
                # mov pc, rX：switch 跳转表，之后是表数据 + 各 case 体
                if (h & 0xFF00) == 0x4600 and (h & 7) == 7 and (h & 0x80):
                    jump_seen = True
                    pending.extend(_jump_table_targets(rom, fs, fe, off))
                    break
                if off in trip:
                    a2, rd = trip[off]
                    state[rd] = "entry"
                    off = a2 + 2
                    continue
                if (h & 0xF800) == 0x4800:
                    rd = (h >> 8) & 7
                    lit = ((off + 4) & ~3) + (h & 0xFF) * 4
                    val = (
                        struct.unpack_from("<I", rom, lit)[0]
                        if lit + 4 <= len(rom)
                        else 0
                    )
                    state[rd] = "base" if val == GBA_BASE + base else "other"
                    off += 2
                    continue
                if (h & 0xFC00) in (0x1800, 0x1A00):
                    rd, rn, rm = h & 7, (h >> 3) & 7, (h >> 6) & 7
                    pair = (state.get(rn), state.get(rm))
                    if "entry" in pair:
                        state[rd] = "entry"
                    elif "base" in pair:
                        state[rd] = "base"
                    else:
                        state[rd] = "other"
                    off += 2
                    continue
                if (h & 0xFC00) in (0x1C00, 0x1E00):
                    # 含 adds rX, rY, #0（即 mov），必须传播：
                    # 0x080AF202 adds r6, r1, #0 把「别的表基址」搬进来，
                    # 不传播就会在后面被判成「来历不明」
                    rd, rn = h & 7, (h >> 3) & 7
                    imm3 = (h >> 6) & 7
                    src = state.get(rn)
                    if imm3 == 0:
                        state[rd] = src if src else "other"
                    else:
                        state[rd] = "base" if src == "base" else "other"
                    off += 2
                    continue
                if (h & 0xF800) == 0x3000:
                    rd, imm = (h >> 8) & 7, h & 0xFF
                    nxt = _u16(rom, off + 2)
                    to_stack = (nxt & 0xF800) == 0x9000 and ((nxt >> 8) & 7) == rd
                    if (
                        not to_stack
                        and state.get(rd) in ("base", "entry")
                        and imm in field_map
                    ):
                        new_imm = field_map[imm]
                        if off not in seen_off:
                            seen_off.add(off)
                            patches.append({
                                "off": f"0x{off:X}",
                                "bytes": struct.pack(
                                    "<H", 0x3000 | (rd << 8) | new_imm
                                ).hex(" "),
                                "label": f"adds r{rd},#{imm}→#{new_imm}（字段平移）",
                            })
                    off += 2
                    continue
                mem = _decode_mem(h)
                if mem:
                    mn, imm, rn, rd = mem
                    st = state.get(rn)
                    if imm in field_map:
                        if st in ("base", "entry"):
                            err = _add(off, mn, imm, rn, rd, "跟踪")
                            if err:
                                return [], err
                        elif confirmed:
                            # 该函数已确认在操作本表（有三连乘法或加载过表基址）。
                            # 这里状态可能是 None（switch case 从栈上取指针）
                            # 或 other（线性路径上被覆盖），都不可信；
                            # 只要偏移精确命中映射表就按本表字段处理。
                            err = _add(off, mn, imm, rn, rd, "函数已确认")
                            if err:
                                return [], err
                    if mn.startswith("ldr"):
                        state[rd] = "other"
                    off += 2
                    continue
                if (h & 0xFC00) == 0x4000 and (h & 0x0300) == 0x0000:
                    rd = h & 7
                    if rd in state:
                        state[rd] = "other"
                off += 2
    return patches, None


def plan_struct_stride_expand(
    rom: bytes,
    base: int,
    old_stride: int,
    new_stride: int,
    count: int,
    name_off: int,
    name_cap_new: int,
    field_map: dict[int, int],
) -> tuple[list[dict], list[dict], str | None]:
    """返回 ``(insns, literals, err)``；insns 是三连 + 字段平移补丁。

    只负责「代码侧」；blob 克隆与字面量改写由调用方（write_plan）做。
    """
    lits = list(find_literal_sites(rom, GBA_BASE + base))
    lits += [
        p
        for p in find_literal_sites(rom, GBA_BASE + base + name_off)
        if p not in lits
    ]
    if not lits:
        return [], [], "无表基字面量"

    from .table_stride import _func_bounds

    funcs = sorted({_func_bounds(rom, lit) for lit in lits})

    triplets: list[tuple[int, int, int, int, int, str]] = []
    for fs, fe in funcs:
        triplets.extend(scan_mul_triplets(rom, fs, fe, old_stride))

    covered = {a0 for a0, *_ in triplets}
    missed = [f for f in funcs if not any(f[0] <= a < f[1] for a in covered)]
    if missed:
        return [], [], (
            "有函数未找到步长乘法：" + ", ".join(f"0x{a:X}-0x{b:X}" for a, b in missed)
        )

    insns: list[dict] = []
    for a0, a1, a2, rd, rs, form in triplets:
        enc = emit_triplet(rd, rs, new_stride)
        if enc is None:
            return [], [], f"stride {new_stride} 无法用三连表示"
        insns.append({
            "off": f"0x{a0:X}",
            "bytes": enc[:2].hex(" "),
            "label": f"lsls r{rd},r{rs}（stride {old_stride}→{new_stride}）",
        })
        insns.append({
            "off": f"0x{a1:X}",
            "bytes": enc[2:4].hex(" "),
            "label": f"{'adds' if form == 'add' else 'subs'}→新形态",
        })
        insns.append({
            "off": f"0x{a2:X}",
            "bytes": enc[4:6].hex(" "),
            "label": f"lsls r{rd},r{rd}（stride {old_stride}→{new_stride}）",
        })

    field_patches, err = collect_field_patches(rom, funcs, base, field_map, triplets)
    if err:
        return [], [], err
    insns.extend(field_patches)

    lit_out: list[dict] = []
    for lit in lits:
        cur = struct.unpack_from("<I", rom, lit)[0]
        if cur in (GBA_BASE + base, GBA_BASE + (base & ~3)):
            lit_out.append({"off": f"0x{lit:X}"})
        elif cur == GBA_BASE + base + name_off:
            lit_out.append({"off": f"0x{lit:X}", "add": name_off})
    del count, name_cap_new
    return insns, lit_out, None
