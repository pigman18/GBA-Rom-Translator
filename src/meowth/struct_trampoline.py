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
        sites = find_getname_sites(
            rom, cand, entry_size, name_offset=name_offset
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
        base, entry_size, count, name_off, old_cap = _struct_geom(mod)
    except ValueError as exc:
        return None, cursor, str(exc)

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
    return table, cursor, None


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
        base, entry_size, count, name_off, old_cap = _struct_geom(mod)
    except ValueError as exc:
        return None, cursor, str(exc)

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

    blob = bytearray()
    n_tr = 0
    n_keep = 0
    n_overflow = 0
    for i in range(count):
        src = base + i * entry_size
        entry = bytearray(rom[src:src + entry_size])
        e = by_idx.get(i)
        raw = b""
        if e is not None:
            text = e.get("translated") or ""
            orig = e.get("original") or ""
            if text and text != orig:
                raw = _encode_body(text, encoder)
        if raw and len(raw) <= old_cap:
            # 名字区：译文 + 余下填 0x00（保持后续字段偏移）
            pad = bytes(old_cap - len(raw))
            entry[name_off:name_off + old_cap] = raw + pad
            n_tr += 1
        else:
            if raw:
                n_overflow += 1
            n_keep += 1
        blob += entry

    if n_tr == 0:
        return None, cursor, "没有能塞进原名字槽的译文"
    # 有译文却超槽：让 write_plan 回落 trampoline（可旁路长名），避免半吊子整块
    if n_overflow > 0:
        return (
            None,
            cursor,
            f"{n_overflow} 条译文超名槽({old_cap}B)，回落 trampoline",
        )

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

    table = {
        "module": name,
        "mode": "struct_same_stride_clone",
        "old_base": f"0x{base:X}",
        "old_stride": entry_size,
        "new_base": f"0x{new_base:X}",
        "new_stride": entry_size,
        "count": count,
        "name_offset": name_off,
        "old_name_cap": old_cap,
        "new_name_cap": old_cap,
        "blob": f"gen/plan_table_{safe}.bin",
        "blob_name": f"plan_table_{safe}.bin",
        "blob_hex": blob.hex(),
        "insns": [],
        "literals": lit_out,
        "field_map": {},
        "note": (
            f"同stride克隆 base=0x{base:X}; translated_fit={n_tr} "
            f"keep_jp={n_keep} lits={len(lit_out)}"
        ),
    }
    return table, cursor, None
