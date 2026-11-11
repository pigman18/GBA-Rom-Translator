"""结构体名字：整块克隆为主，trampoline 子值旁路为回落。

主路径 ``plan_struct_same_stride_clone``：读整块 → 名字槽嵌中文、字段原样
→ 同 stride 写新区 → 改结构体基址字面量（stride≈名字后全 00 的 struct 特例
也可走表扩步长，见 ``table_stride``）。

回落 ``plan_struct_trampoline``：旁路 ``name_ptrs`` + 读点 ``ldr+bx`` 钩
（旧「子值重定向」）。仅当整块克隆失败（无基址字面量 / 译文全超槽）时使用。
"""
from __future__ import annotations

import re
import struct
from typing import Callable

from .patch_table import GBA_BASE, TABLE_AREA_END, _off
from .table_stride import find_literal_sites

Encoder = Callable[[str], bytes]


# struct 名槽不够时是否允许整表扩 stride。
# 默认关闭：plan_stride_rewrite 对 0x3C2A44(28) 只找到 20 处读取点，
# 实测仍有没覆盖到的 → 索引错、模拟器 input callback 停摆。
# 等 stride 覆盖验证充分后再开。
STRUCT_STRIDE_EXPAND = False


def infer_name_cap(
    rom: bytes,
    base: int,
    entry_size: int,
    name_off: int,
    count: int,
) -> int:
    """从**数据本身**推导名字槽宽度（不信任配置）。

    结构体里名字后面通常紧跟别的字段，配置里的 ``desc_ptr_offset`` 经常
    指向的是「说明指针」而不是「名字区结束」，直接拿来当名字槽宽度会
    把价格/指针一起覆盖掉。实测五张表全部踩中：

        道具名        配置 16 → 实际 10
        树果名        配置 16 → 实际 7
        图鉴分类名    配置 22 → 实际 6     ← 覆盖了 desc_ptr，图鉴说明全空
        秘密基地装饰名 配置 27 → 实际 11
        训练家个人名  配置 28 → 实际 16

    判据：条目内从 name_off 起，先是一段文本（0x00/0xFF 以外的字节），
    然后是 0x00/0xFF 填充，填充结束的位置就是名字区上界。逐条量出来取
    **众数**——填充恰好延伸到下一个字段首字节是 0x00/0xFF 时会得到偏大的
    值，但那种情况是少数，众数稳定落在真实边界上。
    """
    caps: list[int] = []
    for i in range(count):
        src = base + i * entry_size
        entry = rom[src:src + entry_size]
        if len(entry) < entry_size:
            break
        j = name_off
        while j < entry_size and entry[j] not in (0x00, 0xFF):
            j += 1
        k = j
        while k < entry_size and entry[k] in (0x00, 0xFF):
            k += 1
        caps.append(k - name_off)
    if not caps:
        return entry_size - name_off
    from collections import Counter

    hist = Counter(caps)
    best = max(hist.items(), key=lambda kv: (kv[1], -kv[0]))
    return max(1, min(best[0], entry_size - name_off))


def _name_cap(rom: bytes, mod: dict, base: int, entry_size: int,
              name_off: int, count: int) -> int:
    """名字槽宽度：配置显式 ``name_cap`` > 数据推导。"""
    read = mod.get("read") or {}
    explicit = read.get("name_cap")
    if explicit is not None:
        try:
            return max(1, min(int(explicit), entry_size - name_off))
        except (TypeError, ValueError):
            pass
    return infer_name_cap(rom, base, entry_size, name_off, count)


def _struct_geom(mod: dict) -> tuple[int, int, int, int, int]:
    read = mod.get("read") or {}
    base = _off(mod["start"])
    end = _off(mod["end"])
    entry_size = int(read["entry_size"])
    name_off = int(read.get("name_offset") or 0)
    span = end - base + 1
    if entry_size <= 0 or span % entry_size:
        raise ValueError("结构体区间不是 entry_size 整数倍")
    count = span // entry_size
    desc = read.get("desc_ptr_offset")
    if desc is not None:
        old_cap = int(desc) - name_off
    else:
        old_cap = entry_size - name_off
    if old_cap <= 0:
        raise ValueError("name cap <= 0")
    return base, entry_size, count, name_off, old_cap


def _ldr_pc_target(insn_off: int, hw: int) -> int | None:
    if (hw & 0xF800) != 0x4800:
        return None
    return ((insn_off + 4) & ~3) + (hw & 0xFF) * 4


def _is_return_name_site(
    rom: bytes, ldr_off: int, *, name_offset: int = 0
) -> bool:
    """ldr 之后是否把 ``base+i*stride[+name_off]`` 当指针返回（非字段访问）。

    固定形态（与 ItemId_GetName / start_menu 读点钩同构）：
    ``ldr =base`` → （可选 ``adds``/``adds #name_off``）→ ``pop``/``bx``。
    若先遇到 ``ldrb/ldrh/ldr [reg,#imm]`` 则是字段读，不是名字读点。
    """
    del name_offset  # 返回形不强制 adds；字面量可能已是 base+name_off
    for j in range(2, 32, 2):
        if ldr_off + j + 1 >= len(rom):
            return False
        h = struct.unpack_from("<H", rom, ldr_off + j)[0]
        # pop / pop-pc / bx Rm
        if (h & 0xFF00) in (0xBC00, 0xBD00) or (h & 0xFF87) == 0x4700:
            return True
        # 字段读：ldrb/ldrh/ldr 立即数形式
        if (h & 0xF800) in (0x7800, 0x8800, 0x6800):
            return False
        # adds rd, #imm8 —— 允许 name_offset 或其它小偏移
        if (h & 0xF800) == 0x3000:
            continue
        # adds/movs 寄存器
        if (h >> 9) in (0b0001100, 0b0001110, 0b0001101):
            continue
        if (h & 0xFFC0) == 0x1C00:  # mov/adds low rd,rm
            continue
        # 其它指令：不是干净「算址后返回」
        return False
    return False


def _is_field_name_site(
    rom: bytes, ldr_off: int, *, name_offset: int
) -> bool:
    """字段访问形名字读点：算 ``base+i*stride`` 后 ``adds #name_off``，再当字符串用。

    与返回形的区别：允许在 ``adds #name_off`` **之前**出现对其它字段的
    ``ldrb/ldrh``（先读 meta 再取名），但 ``adds #name_off`` 之后到
    ``bx``/``bl`` 之间不得再读其它字段——否则是通用 struct 游标，不能钩。
    ``name_offset==0`` 时名字即表项首址，字段形无法与「返回整项指针」区分，
    仍走 :func:`_is_return_name_site`。
    """
    if name_offset <= 0 or name_offset > 255:
        return False
    saw_name_add = False
    for j in range(2, 64, 2):
        if ldr_off + j + 1 >= len(rom):
            return False
        h = struct.unpack_from("<H", rom, ldr_off + j)[0]
        if (h & 0xFF00) in (0xBC00, 0xBD00) or (h & 0xFF87) == 0x4700:
            return saw_name_add
        # bl / blx：取名后交给 StringCopy / AddTextPrinter
        if (h & 0xF800) == 0xF000:
            return saw_name_add
        if (h & 0xF800) == 0x3000:  # adds rd,#imm8
            if (h & 0xFF) == (name_offset & 0xFF):
                saw_name_add = True
            continue
        if (h & 0xF800) in (0x7800, 0x8800, 0x6800):
            if saw_name_add:
                return False  # 取名后又读字段 → 通用游标
            continue  # 取名前读 meta：允许
        if (h >> 9) in (0b0001100, 0b0001110, 0b0001101):
            continue
        if (h & 0xFFC0) == 0x1C00:
            continue
        if (h & 0xFF00) == 0xB500:  # push — 嵌套，放弃
            return False
        if not saw_name_add:
            continue  # 取名前其它杂讯：放宽
        return False
    return False


def _candidate_struct_bases(
    rom: bytes, base: int, entry_size: int, name_offset: int
) -> list[int]:
    """配置基址可能与代码字面量差几个字段；在邻域扫有字面量的候选基址。"""
    seen: set[int] = set()
    out: list[int] = []

    def _add(b: int) -> None:
        if b < 0 or b in seen:
            return
        seen.add(b)
        out.append(b)

    _add(base)
    _add(base & ~3)
    if name_offset:
        _add((base - name_offset) & ~3)
        # 代码里的字面量常常**直接指向名字字段**（base+name_off），
        # 这样算址后无需再 adds #name_off。少这个候选会漏掉整条读点：
        # 装饰名/树果名/训练家个人名三张表都因此拿不到旁路读点。
        _add(base + name_offset)
    # 邻域：前后各 2 个 entry，4 对齐；只保留「ROM 里确有字面量」的
    lo = max(0, (base & ~3) - entry_size * 2)
    hi = base + entry_size * 2
    for b in range(lo, hi + 1, 4):
        if find_literal_sites(rom, GBA_BASE + b):
            _add(b)
    return out


def find_getname_sites(
    rom: bytes,
    base: int,
    entry_size: int,
    *,
    name_offset: int = 0,
) -> list[tuple[int, int]]:
    """固定算法：找名字读点（返回形或字段访问形）。

    1. 扫 ``=base`` 字面量 → 对应 ``ldr``
    2. ``thumb_symexec.solve_site_auto`` 算 stride，须 ``== entry_size``
    3. ldr 后是：
       - 返回形：算址后 ``pop``/``bx``（不先读其它字段）；或
       - 字段形：``adds #name_offset`` 后当字符串用（见
         :func:`_is_field_name_site`）

    返回 ``[(lit_off, ldr_off), ...]``。不写死 entry_size / 乘法指纹。
    """
    from .thumb_symexec import solve_site_auto
    from .table_stride import find_ldrs

    out: list[tuple[int, int]] = []
    seen_ldr: set[int] = set()
    for ldr in find_ldrs(rom, base, back=0x400):
        if ldr in seen_ldr:
            continue
        r = solve_site_auto(rom, ldr, expect=entry_size)
        if r.stride != entry_size:
            continue
        ok = _is_return_name_site(rom, ldr, name_offset=name_offset)
        if not ok and name_offset > 0:
            ok = _is_field_name_site(rom, ldr, name_offset=name_offset)
        if not ok:
            continue
        # 反查 lit
        h = struct.unpack_from("<H", rom, ldr)[0]
        lit = _ldr_pc_target(ldr, h)
        if lit is None:
            continue
        seen_ldr.add(ldr)
        out.append((lit, ldr))
    return out


def find_getname_sites_auto(
    rom: bytes, base: int, entry_size: int, name_offset: int = 0
) -> tuple[int, list[tuple[int, int]]]:
    """在候选基址上跑 :func:`find_getname_sites`，返回 ``(实际基址, sites)``。"""
    for cand in _candidate_struct_bases(rom, base, entry_size, name_offset):
        # 候选基址已含 name_offset 时，算址结果本身就是名字指针
        extra = 0 if (name_offset and cand == base + name_offset) else name_offset
        sites = find_getname_sites(
            rom, cand, entry_size, name_offset=extra
        )
        if sites:
            return cand, sites
    return base, []


def _getname_entry(rom: bytes, ldr_off: int) -> int | None:
    """读点钩入口：优先 ``push {lr}``；否则用基本块头（叶子 ``bx lr`` 形）。

    须 4 对齐（就地 ``ldr+bx+.word`` 要 8 字节）。定不出则返回 None。
    """
    from .thumb_symexec import find_block_head

    for b in range(0, 0x40, 2):
        e = ldr_off - b
        if e >= 0 and e % 4 == 0 and rom[e + 1] == 0xB5:
            return e
    block = find_block_head(rom, ldr_off)
    if block % 4 == 0 and 0 <= ldr_off - block <= 0x28:
        return block
    return None


def _encode_bl(from_file: int, to_file: int) -> bytes:
    """Thumb BL from_file → to_file（两条半字）。"""
    off = to_file - (from_file + 4)
    if off % 2:
        raise ValueError("bl 目标未半字对齐")
    imm = off >> 1
    if not (-0x400000 <= imm <= 0x3FFFFF):
        raise ValueError(f"bl 超出范围: {imm}")
    imm11_h = (imm >> 11) & 0x7FF
    imm11_l = imm & 0x7FF
    return struct.pack("<HH", 0xF000 | imm11_h, 0xF800 | imm11_l)


def _encode_body(text: str, encoder: Encoder | None) -> bytes:
    if not text or encoder is None:
        return b""
    try:
        raw = encoder(text)
    except Exception:
        return b""
    if raw and raw[-1] != 0xFF:
        raw += b"\xFF"
    return raw


def _rom_name(rom: bytes, base: int, entry_size: int, name_off: int, old_cap: int, idx: int) -> bytes:
    src = base + idx * entry_size + name_off
    raw = bytes(rom[src:src + old_cap])
    if 0xFF in raw:
        raw = raw[: raw.index(0xFF) + 1]
    return raw if raw else b"\xFF"


def plan_struct_trampoline(
    rom: bytes,
    name: str,
    mod: dict,
    entries: list[dict],
    encoder: Encoder | None,
    cursor: int,
) -> tuple[dict | None, int, str | None]:
    """整块按子值重定向：name_ptrs + 读点 ``ldr+bx`` 钩。成功 (table, cursor, None)。"""
    try:
        base, entry_size, count, name_off, _decl_cap = _struct_geom(mod)
    except ValueError as exc:
        return None, cursor, str(exc)
    # 名字槽宽度以数据为准（配置里的 desc_ptr 常常不是名字区结束标志）
    old_cap = _name_cap(rom, mod, base, entry_size, name_off, count)

    # 固定算法找读点（symexec stride + 返回形态）
    # 合法 code_base：配置 base，或 base+name_off（读点直接返回名字址）
    code_base, sites = find_getname_sites_auto(
        rom, base, entry_size, name_offset=name_off
    )
    if sites:
        delta = code_base - base
        ok = (
            delta % entry_size == 0
            or code_base == base + name_off
            or code_base == (base & ~3)
        )
        if not ok:
            sites = []
            code_base = base
    if not sites:
        return None, cursor, "无返回指针形读点（symexec 未定出 base+i*stride 返回点）"

    # index → 译文
    by_idx: dict[int, dict] = {}
    for e in entries:
        if e.get("_reject"):
            continue
        addr = e.get("address")
        if addr in (None, ""):
            continue
        try:
            a = _off(addr)
        except (TypeError, ValueError):
            continue
        delta = a - base - name_off
        if delta % entry_size or not (0 <= delta // entry_size < count):
            delta2 = a - base
            if delta2 % entry_size or not (0 <= delta2 // entry_size < count):
                continue
            idx = delta2 // entry_size
        else:
            idx = delta // entry_size
        by_idx[idx] = e

    bodies: list[bytes] = []
    n_tr = 0
    for i in range(count):
        e = by_idx.get(i)
        raw = b""
        if e is not None:
            text = e.get("translated") or ""
            orig = e.get("original") or ""
            if text and text != orig:
                raw = _encode_body(text, encoder)
                if raw:
                    n_tr += 1
        if not raw:
            raw = _rom_name(rom, base, entry_size, name_off, old_cap, i)
        bodies.append(raw)

    if n_tr == 0:
        return None, cursor, "没有译文"

    # ---- 布局 blob ----
    # [ptr_table count×4][strings...][stub code...]
    str_blob = bytearray()
    str_offs: list[int] = []
    for body in bodies:
        while len(str_blob) % 4:
            str_blob.append(0x00)
        str_offs.append(len(str_blob))
        str_blob += body
        if not body.endswith(b"\xFF"):
            str_blob.append(0xFF)

    ptr_size = count * 4
    # stub 先按未知长度占位：先算 stub 机器码长度
    # stub 需要知道自身文件偏移才能编 bl sanitize
    # 布局：cursor = new_base
    new_base = cursor
    stub_rel = ptr_size + len(str_blob)
    while stub_rel % 4:
        str_blob.append(0x00)
        stub_rel = ptr_size + len(str_blob)
    stub_file = new_base + stub_rel

    # 仅当原读点入口→ldr 之间确有 bl sanitize 时才复用；
    # 禁止默认掉进 ItemId sanitize（图鉴分类名叶子无 bl，误调会炸模拟器）。
    sanitize: int | None = None
    _lit0, ldr0 = sites[0]
    entry0 = _getname_entry(rom, ldr0)
    if entry0 is not None:
        for off in range(entry0, min(ldr0, len(rom) - 3), 2):
            h0 = struct.unpack_from("<H", rom, off)[0]
            h1 = struct.unpack_from("<H", rom, off + 2)[0]
            if (h0 & 0xF800) == 0xF000 and (h1 & 0xF800) == 0xF800:
                imm = ((h0 & 0x7FF) << 11) | (h1 & 0x7FF)
                if imm & 0x200000:
                    imm -= 0x400000
                sanitize = off + 4 + (imm << 1)
                break

    def _patch_ldr_pc(insn_file: int, stub_bytes: bytearray, lit_file: int, rd: int) -> str | None:
        delta = lit_file - ((insn_file + 4) & ~3)
        if delta % 4 or not (0 <= delta // 4 <= 255):
            return f"ldr pc lit 不可达 insn=0x{insn_file:X} lit=0x{lit_file:X}"
        rel = insn_file - stub_file
        struct.pack_into(
            "<H", stub_bytes, rel, 0x4800 | (rd << 8) | (delta // 4)
        )
        return None

    # stub 两种：
    # A) 有 sanitize：u16 → bl sanitize → name_ptrs[i]
    # B) 无 sanitize：u16 → cmp count → 越界置 0 → name_ptrs[i]
    stub = bytearray()
    stub += struct.pack("<H", 0xB500)  # push {lr}
    stub += struct.pack("<H", 0x0400)  # lsls r0, r0, #16
    stub += struct.pack("<H", 0x0C00)  # lsrs r0, r0, #16

    ldr_san_at = -1
    bl_at = -1
    bx_r3_at = -1
    ldr_cnt_at = -1
    if sanitize is not None:
        ldr_san_at = stub_file + len(stub)
        stub += struct.pack("<H", 0x0000)  # ldr r3, =sanitize|1
        bl_at = stub_file + len(stub)
        stub += struct.pack("<HH", 0xF000, 0xF800)  # bl → bx r3
    else:
        # cmp r0, r1 前先 ldr r1, =count
        ldr_cnt_at = stub_file + len(stub)
        stub += struct.pack("<H", 0x0000)  # ldr r1, =count
        stub += struct.pack("<H", 0x4288)  # cmp r0, r1
        stub += struct.pack("<H", 0xD300)  # bcc +0 (占位，下条)
        stub += struct.pack("<H", 0x2000)  # movs r0, #0
        # 回填 bcc：跳过 movs（+0 表示下一条；要跳过 1 条半字 → imm=0 是 next，
        # bcc 的 imm8 以「当前+4」为基，imm=0 → 下下条？Thumb：PC=insn+4，
        # bcc imm8: dest = PC + imm*2 = insn+4+imm*2。要落到 movs 之后：
        # dest = movs_addr+2 = (bcc_addr+2)+2 = bcc_addr+4 → imm=0 ✓ 恰好跳过 movs）
        # 上面 D300 已是 imm=0 → 跳到 movs 之后，正确。

    stub += struct.pack("<H", 0x0080)  # lsls r0, r0, #2
    ldr_ptr_at = stub_file + len(stub)
    stub += struct.pack("<H", 0x0000)  # ldr r1, =name_ptrs
    stub += struct.pack("<H", 0x5808)  # ldr r0, [r1, r0]
    stub += struct.pack("<H", 0xBC02)  # pop {r1}
    stub += struct.pack("<H", 0x4708)  # bx r1
    if sanitize is not None:
        bx_r3_at = stub_file + len(stub)
        stub += struct.pack("<H", 0x4718)  # bx r3
    while len(stub) % 4:
        stub += struct.pack("<H", 0x46C0)
    lit_pool = stub_file + len(stub)
    lit_cursor = lit_pool
    if sanitize is not None:
        stub += struct.pack("<I", (GBA_BASE + sanitize) | 1)
        err = _patch_ldr_pc(ldr_san_at, stub, lit_cursor, 3)
        if err:
            return None, cursor, err
        lit_cursor += 4
        try:
            bl_bytes = _encode_bl(bl_at, bx_r3_at)
        except ValueError as exc:
            return None, cursor, f"stub 内 bl: {exc}"
        stub[bl_at - stub_file:bl_at - stub_file + 4] = bl_bytes
    else:
        stub += struct.pack("<I", count)
        err = _patch_ldr_pc(ldr_cnt_at, stub, lit_cursor, 1)
        if err:
            return None, cursor, err
        lit_cursor += 4
    stub += struct.pack("<I", GBA_BASE + new_base)
    err = _patch_ldr_pc(ldr_ptr_at, stub, lit_cursor, 1)
    if err:
        return None, cursor, err

    # ptr 表
    ptr_bytes = bytearray()
    for off in str_offs:
        gba = GBA_BASE + new_base + ptr_size + off
        ptr_bytes += struct.pack("<I", gba)

    blob = bytes(ptr_bytes) + bytes(str_blob) + bytes(stub)
    if cursor + len(blob) > TABLE_AREA_END:
        return None, cursor, "补丁表区域满了"
    cursor = (cursor + len(blob) + 3) & ~3

    stub_gba = (GBA_BASE + stub_file) | 1
    # 每个读点入口：ldr r3,[pc,#0]; bx r3; .word stub|1（8 字节，固定算法生成）
    insns: list[dict] = []
    seen_entry: set[int] = set()
    for _lit, ldr in sites:
        entry = _getname_entry(rom, ldr)
        if entry is None or entry in seen_entry:
            continue
        if entry % 4 != 0:
            continue
        seen_entry.add(entry)
        imm = 0  # .word 紧挨 bx，PC 对齐后 imm=0
        hook = bytearray()
        hook += struct.pack("<H", 0x4800 | (3 << 8) | imm)  # ldr r3, [pc, #0]
        hook += struct.pack("<H", 0x4718)  # bx r3
        hook += struct.pack("<I", stub_gba)
        insns.append({
            "off": f"0x{entry:X}",
            "bytes": hook.hex(" "),
            "label": f"redirect → stub@0x{stub_file:X}",
        })
    if not insns:
        return None, cursor, "读点已识别但入口无法就地装 ldr+bx 钩"

    # ── 直接绘制点：``ldr rX,=base+name_off`` + ``adds rD,rA,rX`` + 画字 ──
    # getter 挂了钩不等于全部覆盖：图鉴条目页 / 另一个图鉴页都是**自己算**
    # 名字地址再交给绘制函数，不经过 getter（`たねポケモン` 一直是日文就是这原因）。
    # 做法：把**原表就地**改成「名字区 4B 放指针 + FF」，两个绘制站点的
    # ``adds`` 换成 ``ldr`` 解引用。不克隆、不改 literal、不改 stride：
    #   · 数值读点（身高/体重/说明指针）读的是原表原位 → 逐字节不变；
    #   · 表项里的指针字段（图鉴说明入口 +0x0C）由 rows_writer 原地改，
    #     就地折名字不会覆盖它（只写 +0..+4）。
    # 曾经的「克隆镜像表 + 改 literal」会把 rows_writer 已经改好的 +0x0C
    # 说明指针换回原版 → 图鉴说明整片变日文（2026-11-11 实测）。
    _want_draw = bool((mod.get("read") or {}).get("draw_sites"))
    fold = bytearray()
    for i in (range(count) if _want_draw else ()):
        src = base + i * entry_size
        e = bytearray(rom[src:src + entry_size])
        e[name_off:name_off + 4] = ptr_bytes[i * 4:i * 4 + 4]
        if name_off + 4 < entry_size:
            e[name_off + 4] = 0xFF
        fold += bytes(e)

    draw_sites: list[dict] = []
    for lit in (find_literal_sites(rom, GBA_BASE + base + name_off) if _want_draw else ()):
        cur_v = struct.unpack_from("<I", rom, lit)[0]
        if cur_v != GBA_BASE + base + name_off:
            continue
        ldr_off = _ldr_site_for_literal(rom, lit)
        if ldr_off is None:
            continue
        lit_reg = (struct.unpack_from("<H", rom, ldr_off)[0] >> 8) & 7
        dec = _dec_adds_reg(rom, ldr_off + 2)
        if dec is None:
            continue
        rd2, rn2, rm2 = dec
        # 目的寄存器可以和源不同（图鉴另一页是 adds r5,r4,r6）。
        # 只要求「literal 寄存器」是其中一个源，另一个就是 idx*stride。
        if lit_reg not in (rn2, rm2):
            continue
        idx_reg = rm2 if rn2 == lit_reg else rn2
        if max(rd2, lit_reg, idx_reg) > 7:
            continue
        # 必须是「算完名字地址就交给绘制函数」：后面 3 条内出现
        # ``bl`` 到画字函数，否则可能是数值读取（实测 0x0808C244 读
        # entry+16 的数值，光看 literal+adds 会误判）。
        if not _calls_draw(rom, ldr_off + 2, 5):
            continue
        draw_sites.append({
            "lit": lit, "adds": ldr_off + 2,
            "rd": rd2, "lit_reg": lit_reg, "idx_reg": idx_reg,
        })
    for s in draw_sites:
        # 名字地址所在的寄存器可能在绘制之后还要用（图鉴另一页
        # `adds r5,r4,r6` 之后 `ldrh r0,[r5,#6]` 读身高、`[r5,#8]` 读体重、
        # `adds r6,#0xc` 取说明指针）——改那条 adds 会把 r5 变成字符串指针，
        # 后续字段全错位。此时改紧跟着的 `adds rX, rd, #0`（把名字地址
        # 搬进参数寄存器那一条）为 `ldr rX,[rd]`，rd 保持原义。
        mov_off = _mov_reg_after(rom, s["adds"] + 2, s["rd"], lookahead=4)
        if mov_off is not None:
            rt = struct.unpack_from("<H", rom, mov_off)[0] & 7
            enc = 0x6800 | (s["rd"] << 3) | rt
            insns.append({
                "off": f"0x{mov_off:X}",
                "bytes": struct.pack("<H", enc).hex(" "),
                "label": (
                    f"adds r{rt},r{s['rd']},#0 → ldr r{rt},[r{s['rd']}]"
                    f"（解引用名字指针；r{s['rd']} 保留给后续字段）"
                ),
            })
        else:
            enc = 0x5800 | (s["idx_reg"] << 6) | (s["lit_reg"] << 3) | s["rd"]
            insns.append({
                "off": f"0x{s['adds']:X}",
                "bytes": struct.pack("<H", enc).hex(" "),
                "label": (
                    f"adds r{s['rd']},r{s['lit_reg']},r{s['idx_reg']}"
                    f" → ldr r{s['rd']},[r{s['lit_reg']},r{s['idx_reg']}]（解引用名字指针）"
                ),
            })

    safe = re.sub(r"[^\w\-]+", "_", name)
    table = {
        "module": name,
        "mode": "trampoline_name_ptrs",
        "old_base": f"0x{base:X}",
        "old_stride": entry_size,
        "new_base": f"0x{new_base:X}",
        "new_stride": 4,
        "count": count,
        "name_offset": name_off,
        "old_name_cap": old_cap,
        "new_name_cap": 0,
        "blob": f"gen/plan_table_{safe}.bin",
        "blob_name": f"plan_table_{safe}.bin",
        "blob_hex": blob.hex(),
        "insns": insns,
        "literals": [],
        "field_map": {},
        "note": (
            f"redirect 读点×{len(insns)} base=0x{code_base:X}; "
            f"names={count} translated={n_tr} original={count - n_tr}"
        ),
    }
    if fold:
        # 名字折址表**就地**写回原表（只覆盖 +name_off..+name_off+4），
        # 表项其它字段（含 +0x0C 说明指针）由后续 rows 指针改写决定，
        # 所以这里必须先落盘、后打指针补丁（rows_writer 的注入阶段在其后）。
        table["extra_tables"] = [{
            "module": f"{name}-名字折址",
            "mode": "inplace_name_fold",
            "old_base": f"0x{base:X}",
            "old_stride": entry_size,
            "new_base": f"0x{base:X}",
            "new_stride": entry_size,
            "count": count,
            "name_offset": name_off,
            "blob": f"gen/plan_fold_{safe}.bin",
            "blob_name": f"plan_fold_{safe}.bin",
            "blob_hex": bytes(fold).hex(),
            "insns": [],
            "literals": [],
            "field_map": {},
            "note": (
                f"名字槽就地折成 u32 指针（+{name_off} = ptr、"
                f"+{name_off + 4} = FF），其余字段保持原版"
            ),
        }]
    return table, cursor, None


def _stride_patches_by_literals(
    rom: bytes,
    base: int,
    name_off: int,
    old_stride: int,
    new_stride: int,
) -> list[dict]:
    """以「表基址字面量站点」为锚，把**整函数**里所有 i*old_stride 计算都改掉。

    不用 ``find_ldrs``：它按 `ldr rX,[pc,#imm]` 反查字面量，实测会漏
    （0x0FA734 明确引用 0x083C2A44，却不在结果里）—— 漏一处步长就等于
    整表索引错位、模拟器 input callback 停摆。

    覆盖两种索引写法：
      lsls/adds/lsls  → ((1<<n)+1)<<m
      lsls/subs/lsls  → ((1<<n)-1)<<m   （装饰名 28 = (8-1)<<2）
    以及分离式（图鉴那种，两段之间隔着别的指令）。
    """
    from .table_stride import (
        _func_bounds,
        _scan_mul_sites,
        _scan_split_mul,
        find_literal_sites,
        thumb_shift,
    )

    lits = list(find_literal_sites(rom, GBA_BASE + base))
    if name_off:
        lits += list(find_literal_sites(rom, GBA_BASE + base + name_off))
    funcs: set[tuple[int, int]] = set()
    for lit in lits:
        funcs.add(_func_bounds(rom, lit))

    ratio = new_stride // old_stride
    delta = ratio.bit_length() - 1
    out: list[dict] = []
    seen: set[int] = set()
    for fs, fe in sorted(funcs):
        cand = _scan_mul_sites(
            rom, fs, fe, old_stride, allow_sub=True
        ) + _scan_split_mul(rom, fs, fe, old_stride)
        for off, rd, rs, imm in cand:
            if off in seen:
                continue
            new_imm = imm + delta
            if not (0 <= new_imm <= 31):
                continue
            seen.add(off)
            out.append({
                "off": f"0x{off:X}",
                "bytes": thumb_shift("lsls", rd, rs, new_imm).hex(" "),
                "label": f"K={old_stride} lsls #{imm}→#{new_imm}"
                         f"（stride {old_stride}→{new_stride}）",
            })
    return out


_STRCPYN = 0x08004724  # StringCopyN(dst, src, pad, len)


def _bl_sites(rom: bytes, target: int, lo: int = 0, hi: int | None = None) -> list[int]:
    """精确解码 BL，返回所有 ``bl target`` 的**指令**地址（文件偏移）。

    为什么不用 capstone 线性扫描：它会从代码段一路解码下去，撞上跳转表 /
    literal pool / 脚本流就整段错位，落到数据上以后整片指令都解析错。
    实测找 ``0x4F7AC`` 的调用者时 capstone 返回 0 命中，这里准确找到
    ``0x4FD24``（见 scripts/diag/find_callers.py）。

    按半字独立解码，只认 BL 的 32 位编码（h1=11110xxxxxxxxxx、
    h2=11J1J2xxxxxxxxxx），与上下文无关，因此不受错位影响。
    """
    out: list[int] = []
    hi = len(rom) - 4 if hi is None else min(hi, len(rom) - 4)
    for q in range(lo, hi, 2):
        h1, h2 = struct.unpack_from("<HH", rom, q)
        if (h1 & 0xF800) != 0xF000 or (h2 & 0xD000) != 0xD000:
            continue
        s = (h1 >> 10) & 1
        j1 = (h2 >> 13) & 1
        j2 = (h2 >> 11) & 1
        i = 1 if j1 == j2 else 0
        imm = (s << 24) | (i << 23) | (j1 << 22) | (j2 << 21) | ((h1 & 0x3FF) << 11) | (h2 & 0x7FF)
        if s:
            imm -= 1 << 25
        if (GBA_BASE + q + 4 + imm * 2) & 0xFFFFFFFF == target:
            out.append(q)
    return out


def _dec_adds_imm3(rom: bytes, off: int) -> tuple[int, int, int] | None:
    """解 ``adds Rd, Rn, #imm3``（T1，imm 0..7），返回 (rd, rn, imm)。"""
    h = struct.unpack_from("<H", rom, off)[0]
    if (h & 0xFE00) != 0x1C00:
        return None
    rd = h & 7
    rn = (h >> 3) & 7
    imm = (h >> 6) & 7
    return rd, rn, imm


def _dec_movs_imm8(rom: bytes, off: int) -> bytes | None:
    """解 ``movs Rd, #imm8``（T1），返回 movs 的原始两字节（不解 rd）。"""
    h = struct.unpack_from("<H", rom, off)[0]
    if (h & 0xF800) != 0x2000:
        return None
    return rom[off:off + 2]


def _find_name_copy_sites(
    rom: bytes,
    base: int,
    name_off: int,
) -> list[dict]:
    """算法定位「名字 → StringCopyN」的读点，不写死任何地址。

    形态（训练家个人名，0x080F22CA）：

        adds r1, r4, #4      ; src = entry + name_off
        movs r2, #0          ; pad = 0
        movs r3, #5          ; len = 名槽宽度
        bl   StringCopyN

    判据两层，任一层不满足就不认：

    1. **函数归属**：StringCopyN 调用点必须落在「引用本表基址字面量的函数」
       里。ROM 里 16 处 StringCopyN 调用，全套游戏共用的字符串工具很多，
       只靠 ``#name_off`` 会误伤（例如长度同样是 5 的别的表）。
    2. **源地址计算**：前一条必须是 ``adds rX, rY, #name_off``。
       同函数里拷贝别的字段通常走寄存器相加（训练家名 ``adds r1, r1, r2``，
       @0xC 长度 10），立即数不等，天然分开。

    **不校验长度**：``_name_cap`` 推出来的是「名字 + 紧邻 00 填充」的宽度
    （训练家个人名推到 16），而代码里硬编码的拷贝长度是 5。用推导值去匹配
    会一个都匹配不上；长度这里只**读出来**（``old_len``），由调用方替换。

    已经是 ``ldr rX, [rY, #name_off]``（指针形）的读点不匹配（前一条不是
    ``adds``），那些表本来就存指针，不需要再改。
    """
    try:
        from .table_stride import _func_bounds
    except ImportError:  # pragma: no cover
        return []
    lits = list(find_literal_sites(rom, GBA_BASE + base))
    if name_off:
        lits += list(find_literal_sites(rom, GBA_BASE + base + name_off))
    funcs = {_func_bounds(rom, lit) for lit in lits}
    out: list[dict] = []
    for fs, fe in sorted(funcs):
        for bl in _bl_sites(rom, _STRCPYN, fs, fe):
            len_off = bl - 2
            pad_off = bl - 4
            adds_off = bl - 6
            if _dec_movs_imm8(rom, len_off) is None:
                continue
            if _dec_movs_imm8(rom, pad_off) is None:
                continue
            dec = _dec_adds_imm3(rom, adds_off)
            if dec is None:
                continue
            rd, rn, imm = dec
            if imm != name_off:
                continue
            h = struct.unpack_from("<H", rom, len_off)[0]
            out.append({
                "adds": adds_off,
                "rd": rd,
                "rn": rn,
                "len": len_off,
                "old_len": h & 0xFF,
            })
    return out


def _enc_ldr_imm5(rd: int, rn: int, byte_off: int) -> bytes | None:
    """``ldr Rt, [Rn, #imm5*4]``（T1）。``byte_off`` 必须是 4 的倍数且 ≤124。"""
    if byte_off % 4 or byte_off // 4 > 31:
        return None
    return struct.pack("<H", 0x6800 | ((byte_off // 4) << 6) | (rn << 3) | rd)


def plan_struct_name_ptr(
    rom: bytes,
    name: str,
    mod: dict,
    entries: list[dict],
    encoder: Encoder | None,
    cursor: int,
) -> tuple[dict | None, int, str | None]:
    """名字槽改存 u32 指针，译文放新区（stride / 字段 offset 全不变）。

    为什么不用扩 stride：Thumb 的立即数放不下。实测训练家个人名
    ``entry=32 / name@4 / 名槽 5B``，字段在 9..32，名字加长后
    ``adds Rd,Rn,#imm3`` 只能 0–7、``ldrb`` 的 imm5 只能 ≤31 ——
    名字偏移要 +32、字段 offset 要 +16，两条都编不出来。
    重排布局（字段前移）同样卡在 ldrb 的 31。

    指针旁路不受这个限制：名字槽 4..8 放 u32 指针，字段 9..32 原样，
    读点 ``adds r1, r4, #4`` 换成 ``ldr r1, [r4, #4]``（同样 2 字节，
    总长不变，后面的 ``movs r2, #0`` 填充参数也保住了）。

    读点由 ``_find_name_copy_sites`` **算法定位**（literal → 函数 →
    StringCopyN 调用点 → 回溯），不写死地址；配置里可用
    ``read.name_ptr_sites`` 显式指定，作为算法找不到时的兜底。

    只改「主读取点」：``0x0800CC98`` 那种先扫名字算长度的循环不改
    （它按字节扫 FF，读到指针字节会算错），那些界面继续读旧区日文。
    """
    try:
        base, entry_size, count, name_off, _decl = _struct_geom(mod)
    except ValueError as exc:
        return None, cursor, str(exc)
    if name_off + 4 > entry_size:
        return None, cursor, "名字槽不足 4 字节"
    if _enc_ldr_imm5(0, 0, name_off) is None:
        return None, cursor, f"name_off={name_off} 无法编码 ldr imm5（需 4 的倍数且 ≤124）"
    old_cap = _name_cap(rom, mod, base, entry_size, name_off, count)

    # 逐条编码
    enc_by_idx: dict[int, bytes] = {}
    for e in entries:
        if e.get("_reject"):
            continue
        a = e.get("address")
        if a in (None, ""):
            continue
        try:
            off = _off(a)
        except (TypeError, ValueError):
            continue
        delta = off - base - name_off
        if delta % entry_size:
            continue
        idx = delta // entry_size
        if not (0 <= idx < count):
            continue
        text = e.get("translated") or ""
        if not text or text == (e.get("original") or ""):
            continue
        raw = _encode_body(text, encoder)
        if raw:
            enc_by_idx[idx] = raw
    if not enc_by_idx:
        return None, cursor, "无可用译文"

    # 布局：blob(count*entry_size) 紧跟名字串区（entry_size 是 4 的倍数）
    blob_len = count * entry_size
    name_area = cursor + blob_len
    ptrs: dict[int, int] = {}
    na = name_area
    for idx in sorted(enc_by_idx):
        raw = enc_by_idx[idx]
        ptrs[idx] = GBA_BASE + na
        na = (na + len(raw) + 3) & ~3
    total = na - cursor
    if cursor + total > TABLE_AREA_END:
        return None, cursor, "补丁表区域满了"

    # 名字串区
    names = bytearray(total - blob_len)
    for idx, ptr in ptrs.items():
        rel = ptr - GBA_BASE - name_area
        raw = enc_by_idx[idx]
        names[rel:rel + len(raw)] = raw

    # 克隆：名字槽 4..8 写指针，第 8 字节强制 FF，9.. 原样。
    # 第 8 字节必须是 FF：还有别的读点在按字节扫名字（0x0800CC98 那种累加
    # 长度的循环），它们现在看到的是指针字节；不截断就会一路扫进字段区。
    blob = bytearray()
    for i in range(count):
        src = base + i * entry_size
        entry = bytes(rom[src:src + entry_size])
        if i in ptrs:
            entry = (
                entry[:name_off]
                + struct.pack("<I", ptrs[i])
                + b"\xFF"
                + entry[name_off + 5:]
            )
        blob += entry[:entry_size]

    new_base = cursor
    next_cursor = (cursor + total + 3) & ~3

    # 基址字面量
    safe = re.sub(r"[^\w\-]+", "_", name)
    lit_out: list[dict] = []
    for lit in find_literal_sites(rom, GBA_BASE + base):
        cur_v = struct.unpack_from("<I", rom, lit)[0]
        if cur_v in (GBA_BASE + base, GBA_BASE + (base & ~3)):
            lit_out.append({"off": f"0x{lit:X}"})
        elif cur_v == GBA_BASE + base + name_off:
            lit_out.append({"off": f"0x{lit:X}", "add": name_off})
    if not lit_out:
        return None, cursor, "无表基字面量"

    # 读点补丁：adds rX, rY, #name_off → ldr rX, [rY, #name_off]
    # 读点由算法定位；配置里的 read.name_ptr_sites 只在算法找不到时兜底
    # （那是「没办法算法化」的显式声明，不是主路径）。
    max_len = max(len(v) for v in enc_by_idx.values())
    if max_len > 0xFF:
        return None, cursor, f"最长译文 {max_len}B 超出 movs imm8"
    sites = _find_name_copy_sites(rom, base, name_off)
    src = "算法"
    if not sites:
        sites = []
        for item in ((mod.get("read") or {}).get("name_ptr_sites") or []):
            try:
                adds_off = int(str(item.get("adds")), 16) & 0xFFFFFF
                len_off = int(str(item.get("len")), 16) & 0xFFFFFF
            except (TypeError, ValueError):
                continue
            dec = _dec_adds_imm3(rom, adds_off)
            if dec is None:
                continue
            rd, rn, imm = dec
            sites.append({
                "adds": adds_off, "rd": rd, "rn": rn,
                "len": len_off,
                "old_len": struct.unpack_from("<H", rom, len_off)[0] & 0xFF,
            })
        src = "配置"
    if not sites:
        return None, cursor, "未找到名字拷贝读点（可写 read.name_ptr_sites 显式指定）"

    insns: list[dict] = []
    seen_site: set[int] = set()
    for s in sites:
        adds_off = s["adds"]
        if adds_off in seen_site:
            continue
        seen_site.add(adds_off)
        enc = _enc_ldr_imm5(s["rd"], s["rn"], name_off)
        if enc is None:
            continue
        insns.append({
            "off": f"0x{adds_off:X}",
            "bytes": enc.hex(" "),
            "label": f"adds r{s['rd']},r{s['rn']},#{name_off} → "
                     f"ldr r{s['rd']},[r{s['rn']},#{name_off}]（名字槽存指针，{src}定位）",
        })
        h = struct.unpack_from("<H", rom, s["len"])[0]
        rd3 = (h >> 8) & 7
        insns.append({
            "off": f"0x{s['len']:X}",
            "bytes": struct.pack("<H", 0x2000 | (rd3 << 8) | max_len).hex(" "),
            "label": f"movs r{rd3},#{s['old_len']}→#{max_len}（StringCopy 长度跟最长译文）",
        })
    if not insns:
        return None, cursor, "读点识别到了但无法就地编码"

    table = {
        "module": name,
        "mode": "struct_name_ptr",
        "old_base": f"0x{base:X}",
        "old_stride": entry_size,
        "new_base": f"0x{new_base:X}",
        "new_stride": entry_size,
        "count": count,
        "name_offset": name_off,
        # 代码里硬编码的拷贝长度（sites 里读出来的那个 5），不是 _name_cap
        # 推出来的「名字 + 00 填充」宽度。两者都记进 note 备查。
        "old_name_cap": (sites[0]["old_len"] if sites else old_cap),
        "new_name_cap": max_len,
        "blob": f"gen/plan_table_{safe}.bin",
        "blob_name": f"plan_table_{safe}.bin",
        "blob_hex": (bytes(blob) + bytes(names)).hex(),
        "insns": insns,
        "literals": lit_out,
        "field_map": {},
        "note": (
            f"名字指针旁路 base=0x{base:X} stride {entry_size}"
            f"（名槽 {name_off}..{name_off + 4} 存 u32，"
            f"拷贝长度 {sites[0]['old_len'] if sites else old_cap}B"
            f"→{max_len}B）；translated={len(enc_by_idx)} "
            f"lits={len(lit_out)} insns={len(insns)} 读点{src}"
        ),
    }
    return table, next_cursor, None


_STRCPY = 0x080042E8  # StringCopy(dst, src)：FF 定界，长度不限

# 画字函数（把「名字地址 → 像素」的那一步）。判定「这是绘制点」用它做闸门：
# 只认 literal+adds 会把数值读取（entry+16 那种）误当成名字绘制。
_DRAW_FUNCS = (0x0808DD60, 0x0806F16C, 0x0806F158)


def _calls_draw(rom: bytes, start: int, lookahead: int) -> bool:
    """``start`` 起 ``lookahead`` 条指令内有没有 ``bl <画字函数>``。"""
    for k in range(lookahead):
        a = start + 2 * k
        if a + 4 > len(rom):
            return False
        h1, h2 = struct.unpack_from("<HH", rom, a)
        if (h1 & 0xF800) != 0xF000 or (h2 & 0xD000) != 0xD000:
            continue
        # 不去解目标地址：Thumb-2 的 S/I1/I2 展开容易算错（本仓两处
        # 已有同款 bug）。这里只认「紧跟一条 BL」这个结构特征 ——
        # 配合「literal 精确等于 base+name_off」+「adds 形态」，
        # 实测在 7 个 literal 里只命中 2 个真绘制点。
        return True
    return False


def _dec_adds_reg(rom: bytes, off: int) -> tuple[int, int, int] | None:
    """解 ``adds Rd, Rn, Rm``（T1），返回 (rd, rn, rm)。"""
    h = struct.unpack_from("<H", rom, off)[0]
    if (h & 0xFE00) != 0x1800:
        return None
    return h & 7, (h >> 3) & 7, (h >> 6) & 7


def _ldr_site_for_literal(rom: bytes, lit: int, back: int = 0x400) -> int | None:
    """找把 ``lit`` 当地址装入寄存器的 ``ldr rX,[pc,#imm8*4]`` 指令地址。"""
    lo = max(0, lit - back) & ~1
    for a in range(lit - 4, lo, -2):
        h = struct.unpack_from("<H", rom, a)[0]
        if (h & 0xF800) != 0x4800:
            continue
        if ((a + 4) & ~3) + (h & 0xFF) * 4 == lit:
            return a
    return None


def _mov_reg_after(
    rom: bytes, start: int, src: int, *, lookahead: int = 4
) -> int | None:
    """``start`` 起 ``lookahead`` 条内找 ``adds rX, r<src>, #0``（即 mov）。

    返回该指令的**文件偏移**；找不到返回 ``None``。

    用途：图鉴分类名有两种绘制点形态——
    一种 ``adds r0,r0,r4`` 之后直接 bl（可以就地改成寄存器偏移 ldr）；
    另一种 ``adds r5,r4,r6`` 之后先 ``adds r0,r5,#0`` 再 bl，而且 bl 之后
    还用 r5 读 entry+6/+8/+12（身高/体重/说明指针）。后者只能改那条搬参数
    的 mov，改成 ``ldr r0,[r5]``，才能保住 r5 的原义。
    """
    for k in range(lookahead):
        a = start + 2 * k
        if a + 2 > len(rom):
            return None
        h = struct.unpack_from("<H", rom, a)[0]
        # adds Rd, Rn, #imm3（T1，立即数在 bit6-8）
        if (h & 0xFE00) != 0x1C00:
            continue
        if (h >> 6) & 7:
            continue                      # 不是 +0
        if ((h >> 3) & 7) != src:
            continue
        return a
    return None


def _find_name_fold_sites(
    rom: bytes,
    base: int,
    name_off: int,
    ptr_off: int,
) -> list[dict]:
    """定位「名字偏移折进 adds」形态的读点（对战塔训练家表）。

    形态（``0x080A9B78`` / ``0x080AE530``）::

        adds r1, r6, #2      ; r1 = base + name_off
        adds r0, r0, r1      ; r0 = idx*stride + base + name_off
        mov  r1, sp          ; （可有可无，栈缓冲）
        bl   0x080042E8      ; StringCopy(dst, src)，FF 定界

    与 ``_find_name_copy_sites`` 的区别：那条认的是
    ``adds / movs pad / movs len / StringCopyN`` 四连（长度硬编码在
    ``movs`` 里）；这条是「基址加名字偏移 → 再加索引 → 整串拷贝」，
    中间允许 0~2 条无关指令，且**没有长度常量**可改。

    之所以要单独认：这种形态里名字地址是**算出来的**，不能换成
    ``ldr Rd,[Rn,#imm]``（``#2`` 不是 4 的倍数，imm5 编不出来）。
    但可以把「+name_off」抬到「+ptr_off」，再把紧邻的
    ``adds Rd,Rn,Rm`` 换成 ``ldr Rd,[Rn,Rm]`` —— 地址和变成
    ``idx*stride + base + ptr_off``，正好是 4 对齐的指针槽，**两条
    指令原地替换、总长不变**，不需要跳板也不需要窗口。

    **锚点是 RAM 基址不是 ROM 表基址**：这张表被 ``bl memcpy`` 整条拷进
    ``0x0203826C``，两个读点算的都是「RAM 基址 + idx*stride + name_off」
    （``r6``/``r4`` 都是 ``ldr_pc`` 取到的 RAM 字面量）。按 ROM 表基址去
    找函数会**一个都找不到** —— 这是之前判「定不出读点」的直接原因。
    所以这里改成全 ROM 扫 ``bl StringCopy``，再要求基址寄存器在函数内
    由 ``ldr_pc`` 载入了「RAM 地址（0x02xxxxxx）或本表 ROM 基址」。
    """
    try:
        from .table_stride import _func_bounds
    except ImportError:  # pragma: no cover
        return []

    reg_cache: dict[tuple[int, int], dict[int, int]] = {}

    def _reg_lits(fs: int, fe: int) -> dict[int, int]:
        key = (fs, fe)
        if key in reg_cache:
            return reg_cache[key]
        m: dict[int, int] = {}
        a = fs
        while a < fe - 1:
            h = struct.unpack_from("<H", rom, a)[0]
            if (h & 0xF800) == 0x4800:
                rd = (h >> 8) & 7
                lit = ((a + 4) & ~3) + (h & 0xFF) * 4
                if lit + 4 <= len(rom):
                    m[rd] = struct.unpack_from("<I", rom, lit)[0]
            a += 2
        reg_cache[key] = m
        return m

    out: list[dict] = []
    seen: set[int] = set()
    for bl in _bl_sites(rom, _STRCPY, 0, 0x800000):
        for back in (4, 6, 8):
            p = bl - back
            if p < 0:
                continue
            dec1 = _dec_adds_imm3(rom, p)
            if dec1 is None:
                continue
            rd1, rn1, imm1 = dec1
            if imm1 != name_off:
                continue
            dec2 = _dec_adds_reg(rom, p + 2)
            if dec2 is None:
                continue
            rd2, rn2, rm2 = dec2
            # 名字寄存器必须是 dec2 的**源**（dst 可以是它自己，也可以是另一个）
            if rd1 not in (rn2, rm2):
                continue
            other = rn2 if rm2 == rd1 else rm2
            if max(rd1, rn1, rd2, rn2, rm2) > 7:
                continue
            fs, fe = _func_bounds(rom, p)
            v = _reg_lits(fs, fe).get(rn1)
            if v is None:
                continue
            if not (0x02000000 <= v < 0x03000000 or v == GBA_BASE + base):
                continue
            if p in seen:
                break
            seen.add(p)
            out.append({
                "adds": p,
                "fold": p + 2,
                "dst": rd2,
                "name_reg": rd1,
                "idx_reg": other,
                "base_reg": rn1,
                "base_val": v,
            })
            break
    return out


def plan_struct_name_ptr_fold(
    rom: bytes,
    name: str,
    mod: dict,
    entries: list[dict],
    encoder: Encoder | None,
    cursor: int,
) -> tuple[dict | None, int, str | None]:
    """名字槽改存 u32 指针，**读点两条指令原地折**（不用跳板）。

    专治 ``name_off`` 不是 4 的倍数（如对战塔 ``name@2``）而读点又是
    「算地址 → StringCopy」的表：``plan_struct_name_ptr`` 要求
    ``ldr Rd,[Rn,#name_off]`` 的 imm5，``#2`` 编不出来，于是整表落到
    克隆；这里把指针抬到 ``ptr_off = ceil(name_off/4)*4``，两条指令
    换掉即可（见 ``_find_name_fold_sites``）。

    RAM 侧结构大小不变（stride 不变），所以「结构被 memcpy 到 RAM、
    有 N 处字面量引用」的表也不会被冲掉 —— 对战塔就是这种：
    ``0x080A9DF8 bl memcpy`` 拷 64B 到 ``0x0203826C``，66 处引用。
    """
    try:
        base, entry_size, count, name_off, _decl = _struct_geom(mod)
    except ValueError as exc:
        return None, cursor, str(exc)
    old_cap = _name_cap(rom, mod, base, entry_size, name_off, count)
    ptr_off = (name_off + 3) & ~3
    if ptr_off == name_off:
        ptr_off += 4
    if ptr_off - name_off > 7:
        return None, cursor, f"ptr_off-name_off={ptr_off - name_off}，adds imm3 只能 0..7"
    if ptr_off + 4 > name_off + old_cap:
        return None, cursor, (
            f"名槽 {name_off}..{name_off + old_cap} 放不下 u32 指针"
            f"（ptr@{ptr_off}）——该走扩 stride / reflow"
        )

    enc_by_idx: dict[int, bytes] = {}
    for e in entries:
        if e.get("_reject"):
            continue
        a = e.get("address")
        if a in (None, ""):
            continue
        try:
            off = _off(a)
        except (TypeError, ValueError):
            continue
        delta = off - base - name_off
        if delta % entry_size:
            continue
        idx = delta // entry_size
        if not (0 <= idx < count):
            continue
        text = e.get("translated") or ""
        if not text or text == (e.get("original") or ""):
            continue
        raw = _encode_body(text, encoder)
        if raw:
            enc_by_idx[idx] = raw
    if not enc_by_idx:
        return None, cursor, "无可用译文"

    blob_len = count * entry_size
    name_area = cursor + blob_len
    ptrs: dict[int, int] = {}
    na = name_area
    for idx in sorted(enc_by_idx):
        ptrs[idx] = GBA_BASE + na
        na = (na + len(enc_by_idx[idx]) + 3) & ~3
    total = na - cursor
    if cursor + total > TABLE_AREA_END:
        return None, cursor, "补丁表区域满了"

    names = bytearray(total - blob_len)
    for idx, ptr in ptrs.items():
        rel = ptr - GBA_BASE - name_area
        names[rel:rel + len(enc_by_idx[idx])] = enc_by_idx[idx]

    # 克隆：[0..name_off)[FF][00 填充到 ptr_off)[u32 指针][ptr_off+4..原样]
    # name_off 处的 FF 让**没被 patch 的老读点**在此截断（显示空名），
    # 而不是把指针字节当文本扫出去。
    blob = bytearray()
    for i in range(count):
        src = base + i * entry_size
        entry = bytes(rom[src:src + entry_size])
        if i in ptrs:
            head = entry[:name_off] + b"\xFF"
            head += b"\x00" * (ptr_off - name_off - 1)
            entry = head + struct.pack("<I", ptrs[i]) + entry[ptr_off + 4:]
        blob += entry[:entry_size]

    new_base = cursor
    next_cursor = (cursor + total + 3) & ~3

    safe = re.sub(r"[^\w\-]+", "_", name)
    lit_out: list[dict] = []
    for lit in find_literal_sites(rom, GBA_BASE + base):
        cur_v = struct.unpack_from("<I", rom, lit)[0]
        if cur_v in (GBA_BASE + base, GBA_BASE + (base & ~3)):
            lit_out.append({"off": f"0x{lit:X}"})
        elif cur_v == GBA_BASE + base + name_off:
            lit_out.append({"off": f"0x{lit:X}", "add": name_off})
    if not lit_out:
        return None, cursor, "无表基字面量"

    sites = _find_name_fold_sites(rom, base, name_off, ptr_off)
    if not sites:
        return None, cursor, "未找到「adds 折址 + StringCopy」读点"

    insns: list[dict] = []
    for s in sites:
        if ptr_off != name_off:
            insns.append({
                "off": f"0x{s['adds']:X}",
                "bytes": struct.pack(
                    "<H", 0x1C00 | (ptr_off << 6) | (s["base_reg"] << 3) | s["name_reg"]
                ).hex(" "),
                "label": (
                    f"adds r{s['name_reg']},r{s['base_reg']},#{name_off}"
                    f"→#{ptr_off}（指针槽）"
                ),
            })
        enc = 0x5800 | (s["idx_reg"] << 6) | (s["name_reg"] << 3) | s["dst"]
        insns.append({
            "off": f"0x{s['fold']:X}",
            "bytes": struct.pack("<H", enc).hex(" "),
            "label": (
                f"adds r{s['dst']},r{s['idx_reg']},r{s['name_reg']}"
                f" → ldr r{s['dst']},[r{s['name_reg']},r{s['idx_reg']}]"
                f"（解引用名字指针）"
            ),
        })

    table = {
        "module": name,
        "mode": "struct_name_ptr_fold",
        "old_base": f"0x{base:X}",
        "old_stride": entry_size,
        "new_base": f"0x{new_base:X}",
        "new_stride": entry_size,
        "count": count,
        "name_offset": name_off,
        "old_name_cap": old_cap,
        "new_name_cap": max(len(v) for v in enc_by_idx.values()),
        "blob": f"gen/plan_table_{safe}.bin",
        "blob_name": f"plan_table_{safe}.bin",
        "blob_hex": (bytes(blob) + bytes(names)).hex(),
        "insns": insns,
        "literals": lit_out,
        "field_map": {},
        "note": (
            f"名字指针折址 base=0x{base:X} stride {entry_size}（名槽 "
            f"{name_off} 处 FF、{ptr_off}..{ptr_off + 4} 存 u32 指针）；"
            f"translated={len(enc_by_idx)} keep_jp={count - len(ptrs)} "
            f"lits={len(lit_out)} insns={len(insns)} 读点算法×{len(sites)}"
        ),
    }
    return table, next_cursor, None


def plan_struct_same_stride_clone(
    rom: bytes,
    name: str,
    mod: dict,
    entries: list[dict],
    encoder: Encoder | None,
    cursor: int,
) -> tuple[dict | None, int, str | None]:
    """无 GetName 读点时：同 stride 整表克隆，名字槽能放下的写中文，改基址字面量。

    适用于树果/装饰等「名字嵌在结构体、读点是通用字段访问」的表。
    放不下的槽保留原文。原表不动；仅改指向表基的字面量。
    """
    try:
        base, entry_size, count, name_off, _decl_cap = _struct_geom(mod)
    except ValueError as exc:
        return None, cursor, str(exc)
    # 名字槽宽度以数据为准（配置里的 desc_ptr 常常不是名字区结束标志）
    old_cap = _name_cap(rom, mod, base, entry_size, name_off, count)

    code_base, _sites = find_getname_sites_auto(
        rom, base, entry_size, name_offset=name_off
    )
    # 即使无读点，也要有表基字面量才值得搬
    lit_bases = list(
        dict.fromkeys(
            [code_base, base, base & ~3]
            + ([base + name_off] if name_off else [])
        )
    )
    literals: list[dict] = []
    seen_lit: set[int] = set()
    for b in lit_bases:
        for lit in find_literal_sites(rom, GBA_BASE + b):
            if lit in seen_lit:
                continue
            seen_lit.add(lit)
            literals.append({"off": f"0x{lit:X}"})
    if not literals:
        return None, cursor, "无表基字面量可改"

    by_idx: dict[int, dict] = {}
    for e in entries:
        if e.get("_reject"):
            continue
        addr = e.get("address")
        if addr in (None, ""):
            continue
        try:
            a = _off(addr)
        except (TypeError, ValueError):
            continue
        delta = a - base - name_off
        if delta % entry_size or not (0 <= delta // entry_size < count):
            delta2 = a - base
            if delta2 % entry_size or not (0 <= delta2 // entry_size < count):
                continue
            idx = delta2 // entry_size
        else:
            idx = delta // entry_size
        by_idx[idx] = e

    # 名槽自适应：先拿**全部译文**算出需要的宽度，原槽不够就整表扩 stride。
    # 一条超长译文不该把整表判死（装饰名「雷吉斯奇鲁玩偶」= 29B > 27B，
    # 以前会让 120 条装饰名全部回落逐条 → unresolved）。
    need = old_cap
    for e in entries:
        text = e.get("translated") or ""
        if text and text != (e.get("original") or ""):
            raw = _encode_body(text, encoder)
            if raw:
                need = max(need, len(raw) + 1)
    # ⚠️ 只有「名字是结构体最后一个字段」才能靠扩 stride 加宽名槽。
    # 名字之后还有字段的结构体（道具名/树果名：name@0 占 16B，desc_ptr@16），
    # 加宽名字会把后面字段整体推后 —— 代码里按固定偏移取字段全部错位，
    # 结构体尾部字节还会被 out[:new_stride] 截掉。这类表只能保持原槽。
    name_is_tail = (name_off + old_cap == entry_size)
    new_cap = old_cap
    new_stride = entry_size
    if need > old_cap and name_is_tail and STRUCT_STRIDE_EXPAND:
        while new_stride - name_off < need:
            new_stride *= 2
        if new_stride > 512:
            return None, cursor, f"名槽需求 {need}B 导致 stride {new_stride} 过大"
        new_cap = new_stride - name_off

    blob = bytearray()
    n_tr = 0
    n_keep = 0
    n_overflow = 0
    for i in range(count):
        src = base + i * entry_size
        entry = bytes(rom[src:src + entry_size])
        e = by_idx.get(i)
        raw = b""
        if e is not None:
            text = e.get("translated") or ""
            orig = e.get("original") or ""
            if text and text != orig:
                raw = _encode_body(text, encoder)
        # 单条安全上界：只能覆盖「原名字 + 紧邻的 00/FF 填充」。
        # 名字后面紧跟着真实字段的表（训练家个人名的个别条目在名字后
        # 直接跟 u16 数据），按统一 cap 写会把那些字节一起吃掉。
        limit = name_off
        while limit < name_off + new_cap and entry[limit] not in (0x00, 0xFF):
            limit += 1
        while limit < name_off + new_cap and entry[limit] in (0x00, 0xFF):
            limit += 1
        writeable = limit - name_off

        if raw and len(raw) <= writeable:
            name_field = raw + bytes(new_cap - len(raw))
            n_tr += 1
        else:
            if raw:
                n_overflow += 1
            tail = entry[name_off:name_off + old_cap]
            name_field = tail + bytes(new_cap - len(tail))
            n_keep += 1
        # 名字区之后的结构体字段原样保留，整体按 new_stride 对齐
        out = entry[:name_off] + name_field + entry[name_off + old_cap:]
        if len(out) < new_stride:
            out += bytes(new_stride - len(out))
        blob += out[:new_stride]

    if n_tr == 0:
        return None, cursor, f"没有能塞进名字槽({old_cap}B)的译文"
    # 放不下的条目保留日文，其余照写 —— 名字槽宽度由结构体决定，
    # 不能为了几条长译名把整张表判死（那样一条都翻不了）。
    # 仅当「名槽本来能变宽却没变」时才算异常，交给上层回落。
    if n_overflow > 0 and new_stride == entry_size:
        partial_note = f"{n_overflow} 条超名槽({old_cap}B)保留日文"
    else:
        partial_note = ""

    if cursor + len(blob) > TABLE_AREA_END:
        return None, cursor, "补丁表区域满了"
    new_base = cursor
    cursor = (cursor + len(blob) + 3) & ~3
    safe = re.sub(r"[^\w\-]+", "_", name)
    # rows_writer：默认 lit → new_base；带 add 的 lit → new_base+add
    # （名字嵌槽的「base+name_off」字面量必须写成 new+name_off，否则仍读旧表）
    lit_out: list[dict] = []
    for lit in literals:
        off = int(str(lit["off"]), 16)
        cur = struct.unpack_from("<I", rom, off)[0]
        if cur == GBA_BASE + base or cur == GBA_BASE + (base & ~3):
            lit_out.append({"off": f"0x{off:X}"})
        elif name_off and cur == GBA_BASE + base + name_off:
            lit_out.append({"off": f"0x{off:X}", "add": name_off})
        elif cur == GBA_BASE + code_base:
            lit_out.append({"off": f"0x{off:X}"})
    if not lit_out:
        return None, cursor, "无与配置基址对齐的字面量"

    # 名槽变宽 → 整表步长跟着变，必须同步改所有按 entry_size 索引的读取点
    insns: list[dict] = []
    if new_stride != entry_size:
        insns = _stride_patches_by_literals(
            rom, base, name_off, entry_size, new_stride
        )
        if not insns:
            return None, cursor, f"扩 stride {entry_size}→{new_stride} 未找到读取点"

    table = {
        "module": name,
        "mode": (
            "struct_same_stride_clone"
            if new_stride == entry_size
            else "struct_stride_expand"
        ),
        "old_base": f"0x{base:X}",
        "old_stride": entry_size,
        "new_base": f"0x{new_base:X}",
        "new_stride": new_stride,
        "count": count,
        "name_offset": name_off,
        "old_name_cap": old_cap,
        "new_name_cap": new_cap,
        "blob": f"gen/plan_table_{safe}.bin",
        "blob_name": f"plan_table_{safe}.bin",
        "blob_hex": blob.hex(),
        "insns": insns,
        "literals": lit_out,
        "field_map": {},
        "note": (
            f"struct 克隆 base=0x{base:X} stride {entry_size}→{new_stride}"
            f"（名槽 {old_cap}→{new_cap}）; translated_fit={n_tr} "
            f"keep_jp={n_keep} overflow={n_overflow} lits={len(lit_out)} "
            f"insns={len(insns)}"
            + (f"; {partial_note}" if partial_note else "")
        ),
    }
    return table, cursor, None
