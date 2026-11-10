"""从 texts.json + 译文生成唯一写入计划 ``write.plan.json``。

**重定向**（与 ``hook/patches/start_menu.asm`` 同义）：
新区放译文体 → 改原引用站点（``.word`` 字面量，或读点 ``ldr+bx``/``bl`` 钩子）
指向新区。无传统指针、动态拼接、超短槽，只要定得出站点，都走这条。

写入类（不做原地 F9 写回原槽）：

1. **stride 表** → tables[]：按**最长译文**选 ``old×2^k`` 新步长；
   整表进新区；改基址字面量 + 改步长移位指令；无译文槽填原文。
2. **常规有指针** → rows[]（kind=pointer）：改登记/展开的指针槽。
3. **struct 名字** → 整块规划后**按子值重定向**：
   能定读点时 → tables[] ``mode=trampoline_name_ptrs``
   （旁路 name_ptr 表 + 读点 ``ldr+bx``；原结构体不动；每槽有译用译、无译用原文）；
   否则 → 回落逐条 redirects[] / rows[]（与下项同一条路，禁止整模块死刑）。
4. **常规无指针 / 超短等兜底** → redirects[]（发现字面量站点）；定不出 → skip。

写入器只消费本计划，见 ``rows_writer``。
"""
from __future__ import annotations

import json
import re
import struct
from pathlib import Path
from typing import Any, Callable

from .patch_table import (
    GBA_BASE,
    TABLE_AREA,
    TABLE_AREA_END,
    _choose_stride,
    _code_base,
    _fit,
    _groups_intact,
    _off,
)
from .table_relink import parse_ldr_literal_target
from .table_stride import _func_bounds, find_literal_sites, plan_stride_rewrite
from .thumb_symexec import solve_site_auto

# stride → tables[] 扩步长；struct → 整块按值重定向（读点钩或逐条 redirect）
STRIDE_TABLE_TYPES = frozenset({"stride"})
STRUCT_TYPES = frozenset({"struct"})
TABLE_TYPES = STRIDE_TABLE_TYPES  # 兼容旧名：扩步长仅 stride
Encoder = Callable[[str], bytes]


def _write_disabled(mod: dict) -> bool:
    write = mod.get("write") or {}
    return (
        write.get("relocate") is False
        and write.get("replace") is False
        and write.get("slot") is False
    )


def _prepare_text(text: str, *, game_id: str = "", module: str = "") -> str:
    """折行：按模块 ``word_count`` / ``wrap_pages`` 重排（道具说明=9 字只插 ``\\n``）。"""
    if not text:
        return text
    import re

    from .charmap import normalize_zh_punct
    from .config_loader import module_wrap_kwargs
    from .text_wrap import wrap_text

    t = (
        text.replace("{\\n}", "\n")
        .replace("{\\p}", "\n\n")
        .replace("{\\l}", "\\l")
    )
    t = re.sub(r"(?<![\\])\{([^\\}]+)\}", r"\1", t)
    t = t.replace("\\p", "\n\n").replace("\\n", "\n")
    if not (game_id or module):
        return t
    try:
        return wrap_text(
            normalize_zh_punct(t),
            target_lang="zh-Hans",
            **module_wrap_kwargs(game_id, module or None),
        )
    except Exception:
        return t


def _encode(
    text: str,
    encoder: Encoder | None,
    *,
    game_id: str = "",
    module: str = "",
) -> bytes:
    if not text or encoder is None:
        return b""
    text = _prepare_text(text, game_id=game_id, module=module)
    try:
        raw = encoder(text)
    except Exception:
        return b""
    if raw and raw[-1] != 0xFF:
        raw += b"\xFF"
    return raw


def _entry_file_off(entry: dict) -> int | None:
    raw = entry.get("address")
    if raw in (None, ""):
        return None
    try:
        return _off(raw)
    except (TypeError, ValueError):
        return None


def _module_entries(entries: list[dict], module: str) -> list[dict]:
    return [e for e in entries if (e.get("module") or "") == module]


def _stride_geom(rom: bytes, mod: dict) -> tuple[int, int, int]:
    read = mod.get("read") or {}
    stride = int(read["stride"])
    declared = _off(mod["start"])
    end = _off(mod["end"])
    base = _code_base(rom, declared, stride)
    span = end - base + 1
    if stride <= 0 or span % stride:
        raise ValueError("区间不是步长整数倍")
    return base, stride, span // stride


def _rows_by_index(
    entries: list[dict],
    base: int,
    stride: int,
    count: int,
    name_off: int,
    encoder: Encoder | None,
    *,
    game_id: str = "",
) -> dict[int, bytes]:
    rows: dict[int, bytes] = {}
    for entry in entries:
        addr = _entry_file_off(entry)
        if addr is None:
            continue
        delta = addr - base - name_off
        if delta % stride or not (0 <= delta // stride < count):
            # 语料地址有时直接是条目起点（name_offset=0）
            delta2 = addr - base
            if delta2 % stride or not (0 <= delta2 // stride < count):
                continue
            idx = delta2 // stride
        else:
            idx = delta // stride
        text = entry.get("translated") or ""
        orig = entry.get("original") or ""
        if not text or text == orig:
            continue
        raw = _encode(
            text,
            encoder,
            game_id=game_id,
            module=str(entry.get("module") or ""),
        )
        if not raw:
            continue
        rows[idx] = raw
    return rows


def _try_fit_name(raw: bytes, cap: int) -> bytes | None:
    """等距槽：整字放入 cap，放不下返回 None（调用方改用原文）。"""
    fitted = _fit(raw, cap)
    if fitted is not None:
        return fitted
    body = raw[:-1] if raw.endswith(b"\xFF") else raw
    while body and not _groups_intact(body):
        body = body[:-1]
    if not body:
        return None
    return _fit(body + b"\xFF", cap)


def _plan_table_stride(
    rom: bytes,
    name: str,
    mod: dict,
    entries: list[dict],
    encoder: Encoder | None,
    cursor: int,
    *,
    game_id: str = "",
) -> tuple[dict | None, int, str | None]:
    """成功返回 (table_dict, new_cursor, None)；失败 (None, cursor, reason)。

    新步长 = 能放下最长译文的最小 ``old×2^k``；整表搬新区并改指针/移位。
    """
    try:
        base, stride, count = _stride_geom(rom, mod)
    except ValueError as exc:
        return None, cursor, str(exc)
    rows = _rows_by_index(
        entries, base, stride, count, 0, encoder, game_id=game_id
    )
    if not rows:
        return None, cursor, "没有译文"
    need = max(len(raw) for raw in rows.values())
    new_stride = _choose_stride(stride, need)
    if new_stride is None:
        new_stride = stride  # 最长已 ≤ 旧步长，仍搬表改基址
    return _finish_table(
        rom, name, base, stride, count, rows, new_stride,
        name_off=0, old_cap=stride, new_cap=new_stride,
        field_map=None, cursor=cursor,
    )


def _finish_table(
    rom: bytes,
    name: str,
    base: int,
    old_stride: int,
    count: int,
    rows: dict[int, bytes],
    new_stride: int,
    *,
    name_off: int,
    old_cap: int,
    cursor: int,
    field_map: dict | None,
    new_cap: int | None = None,
) -> tuple[dict | None, int, str | None]:
    if new_cap is None:
        new_cap = new_stride

    insns: list[dict] = []
    literals: list[dict] = []
    note = ""

    if new_stride != old_stride:
        try:
            plan = plan_stride_rewrite(rom, base, old_stride, new_stride)
        except ValueError as exc:
            # 非 2 幂比：仍写表与基址，步长指令记入 note，由后续补乘法
            plan = None
            note = f"stride_rewrite:{exc}"
        if plan is not None and plan.patches:
            ldrs: list[int] = []
            ok = True
            for patch in plan.patches:
                match = re.search(r"ldr 0x([0-9A-Fa-f]+)", patch.label)
                if not match:
                    ok = False
                    break
                ldrs.append(int(match.group(1), 16))
            muls_imm = any("muls stride" in (p.label or "") for p in plan.patches)
            if ok and len(ldrs) == len(plan.patches):
                old_gba = GBA_BASE + base
                lit_ok = True
                lit_offs: list[int] = []
                for ldr in ldrs:
                    lit = parse_ldr_literal_target(rom, ldr)
                    if lit is None or lit + 4 > len(rom):
                        lit_ok = False
                        break
                    if struct.unpack_from("<I", rom, lit)[0] != old_gba:
                        lit_ok = False
                        break
                    lit_offs.append(lit)
                if lit_ok:
                    accept = False
                    need = max((len(r) for r in rows.values()), default=0)
                    # movs#K+muls：乘法在 ldr 之前，改完后 symexec 仍可能报
                    # base+const；立即数已是 new_stride 即可信任。
                    if muls_imm and new_stride >= need:
                        accept = True
                        note = note or f"movs+muls stride→{new_stride}"
                    else:
                        sim = bytearray(rom)
                        for patch in plan.patches:
                            sim[patch.offset:patch.offset + len(patch.data)] = (
                                patch.data
                            )
                        want = new_stride
                        actuals = [
                            solve_site_auto(bytes(sim), ldr, expect=want).stride
                            for ldr in ldrs
                        ]
                        # 复合乘法（如 ×19）改一位移位可能得到 79 而非 76：
                        # 各站实测 K 一致且 ≥ 最长译文 → 采用实测步长
                        if (
                            actuals
                            and all(a == actuals[0] for a in actuals)
                            and actuals[0]
                            and actuals[0] >= need
                        ):
                            if actuals[0] != want:
                                note = (
                                    f"stride_rewrite实测K={actuals[0]}"
                                    f"（原目标{want}）"
                                )
                            new_stride = int(actuals[0])
                            new_cap = new_stride
                            accept = True
                        else:
                            bad = sum(1 for a in actuals if a != want)
                            note = f"改完 {bad} 处 K 不是 {want}（实测{actuals}）"
                    if accept:
                        for patch in plan.patches:
                            insns.append({
                                "off": f"0x{patch.offset:X}",
                                "bytes": patch.data.hex(" "),
                                "label": patch.label,
                            })
                        for lit in sorted(set(lit_offs)):
                            literals.append({"off": f"0x{lit:X}"})
                        insns.extend(
                            _copy_limit_patches(
                                rom, ldrs, old_stride, new_stride
                            )
                        )
                        insns.extend(
                            _name_window_patches(
                                rom, ldrs, old_stride, new_stride,
                                {int(i["off"], 16) for i in insns},
                            )
                        )
                else:
                    note = note or "字面量对不上基址"
            else:
                note = note or "移位指令没有对应的 ldr"
        elif plan is not None and not plan.patches:
            note = note or f"没有 K 等于旧步长 {old_stride} 的站点"

    # 基址字面量：即使没改步长指令也要指到新区
    if not literals:
        for lit in find_literal_sites(rom, GBA_BASE + base):
            literals.append({"off": f"0x{lit:X}"})

    # 步长变了却改不了指令 → 半吊子表会读错槽，整张不写
    if new_stride != old_stride and not insns:
        return None, cursor, note or "步长已变但无可用移位指令"
    # 步长不变但找不到基址字面量：写了也没人读，跳过免占区
    if new_stride == old_stride and not literals:
        return None, cursor, "找不到表基址字面量"

    blob = bytearray()
    for i in range(count):
        src = base + i * old_stride
        prefix = bytes(rom[src:src + name_off])
        suffix_off = name_off + old_cap
        suffix = bytes(rom[src + suffix_off:src + old_stride])
        raw = rows.get(i)
        if raw is None:
            old_name = bytes(rom[src + name_off:src + suffix_off])
            if 0xFF in old_name:
                old_name = old_name[: old_name.index(0xFF) + 1]
            raw = old_name if old_name else b"\xFF"
        fitted = _try_fit_name(raw, new_cap)
        if fitted is None and new_stride == old_stride:
            # 等长等距：放不下就退回该槽原文
            old_name = bytes(rom[src + name_off:src + suffix_off])
            if 0xFF in old_name:
                old_name = old_name[: old_name.index(0xFF) + 1]
            fitted = _try_fit_name(
                old_name if old_name else b"\xFF", new_cap
            )
        if fitted is None:
            return None, cursor, "译文切不开整字"
        entry = prefix + fitted + suffix
        if len(entry) < new_stride:
            entry = entry + bytes(new_stride - len(entry))
        elif len(entry) > new_stride:
            entry = entry[:new_stride]
        blob += entry

    blob_size = len(blob)
    if cursor + blob_size > TABLE_AREA_END:
        return None, cursor, "补丁表区域满了"
    new_base = cursor
    cursor = (cursor + blob_size + 3) & ~3
    bin_name = f"plan_table_{name}.bin".replace("/", "_")
    # 文件名简化
    safe = re.sub(r"[^\w\-]+", "_", name)
    bin_name = f"plan_table_{safe}.bin"

    table = {
        "module": name,
        "old_base": f"0x{base:X}",
        "old_stride": old_stride,
        "new_base": f"0x{new_base:X}",
        "new_stride": new_stride,
        "count": count,
        "name_offset": name_off,
        "old_name_cap": old_cap,
        "new_name_cap": new_cap,
        "blob": f"gen/{bin_name}",
        "blob_name": bin_name,
        "blob_hex": blob.hex(),  # writer 可直接用；落盘时拆 bin
        "insns": insns,
        "literals": literals,
        "field_map": field_map or {},
        "note": note,
    }
    return table, cursor, None


def _copy_limit_patches(
    rom: bytes, ldrs: list[int], old_stride: int, new_stride: int
) -> list[dict]:
    """把站点附近的 ``cmp/movs #旧上限`` 放大到 ``new_stride-1``。

    物种名复制循环是 ``cmp r1, #0x0A``（最多 11 字节），步长改成 24 后
    仍按 11 截断会切断 F9 组 → 图鉴列表空白。
    """
    if new_stride <= old_stride:
        return []
    new_lim = min(new_stride - 1, 255)
    lo = max(old_stride - 1, 5)
    hi = max(old_stride + 6, 12)
    out: list[dict] = []
    seen: set[int] = set()
    for ldr in ldrs:
        for off in range(max(0, ldr - 0x40), min(len(rom) - 1, ldr + 0x60), 2):
            if off in seen:
                continue
            b0, b1 = rom[off], rom[off + 1]
            # cmp rn,#imm8 : 00101 nnn iiiiiiii → hi=0x28|rn
            # 只改 cmp 复制上限。不改 movs：摘要页等处 movs r3,#9 常是
            # 打印坐标/宽度（后接 bl），当成 len 改成 new_stride-1 会让特性名空白。
            if (b1 & 0xF8) == 0x28 and lo <= b0 <= hi and b0 < new_lim:
                seen.add(off)
                out.append({
                    "off": f"0x{off:X}",
                    "bytes": bytes([new_lim, b1]).hex(" "),
                    "label": f"cmp r{b1 & 7},#{b0:#x}→#{new_lim:#x}",
                })
    return out


def _name_window_patches(
    rom: bytes, ldrs: list[int], old_stride: int, new_stride: int,
    taken: set[int] | None = None,
) -> list[dict]:
    """定长名表被 stride 扩展后，读取函数的**栈缓冲窗口**必须同步放大。

    这是 stride 改写的一部分，不是额外 hook：读取函数自己按
    ``base + idx*old_stride`` 算地址，再逐字节拷进栈上定长缓冲。

    典型（图鉴名字 @0x0808AD44 / 详情页 @0x0808DCBC）::

        sub   sp, #12          ; 栈 12 字节
        mov   r0, sp
        movs  r1, #0xFF
        strb  r1, [r0, #5]     ; buf[5] = FF  ← 名字上限 old_stride
        ...
        cmp   r4, #4           ; 清 5 字节
        ...
        cmp   r4, #9           ; 拷贝上限（_copy_limit_patches 已放）
        add   sp, #12

    只改 ×6→×24 的话，拷贝上限变成 23 而缓冲仍是 6/12 字节 →
    写穿栈帧、覆盖返回地址 → 图鉴详情上下翻页必崩。

    识别（同一栈帧内，``sub sp`` 与 ``add sp`` 之间）：
      * ``mov rX,sp`` + ``strb rX,[rX,#old_stride-1]``（终止符位置）
      * ``cmp rX,#imm`` + ``bls`` 回跳（清零/拷贝/占位循环上限）
    三处一起放大：栈大小、终止符位置、各循环上限。
    """
    if new_stride <= old_stride:
        return []
    new_cap = min(new_stride, 255)
    if new_cap < 16:
        return []
    stack = ((new_cap + 8) // 8) * 8
    if stack > 508:
        return []

    taken = set(taken or ())
    cap_lim = new_cap - 1
    cap_lo, cap_hi = max(old_stride - 2, 1), old_stride * 2 + 4
    out: list[dict] = []
    done: set[int] = set()

    for ldr in ldrs:
        fstart, fend = _func_bounds(rom, ldr)
        if fstart in done:
            continue

        sub_off = add_off = term = None
        sub_sp = 0
        sp_reg = -1
        loops: list[tuple[int, int]] = []
        for off in range(fstart, fend - 1, 2):
            h = struct.unpack_from("<H", rom, off)[0]
            # mov Rd,sp : 0100 0110 1 Rm(13) Rd
            if (h & 0xFF00) == 0x4600 and ((h >> 3) & 0xF) == 13:
                sp_reg = h & 7
                continue
            # strb rX,[rY,#imm5] : 0111 0 imm5 rn rt
            if (h & 0xF800) == 0x7000 and ((h >> 6) & 0x1F) == old_stride - 1:
                # 只认「先 mov rX,sp、再 strb [rX,#old_stride-1]」的栈缓冲。
                # 不校验会把全局结构体上的 6 字节字段也放大 → 写穿别的内存。
                if sp_reg >= 0 and ((h >> 3) & 7) == sp_reg and term is None:
                    term = off
                continue
            # sub sp,#imm7 : 1011 0000 1 imm7
            if (h & 0xFF80) == 0xB080:
                if sub_off is None:
                    sub_off = off
                    sub_sp = (h & 0x7F) * 4
                continue
            # add sp,#imm7 : 1011 0000 0 imm7
            if (h & 0xFF80) == 0xB000:
                if add_off is None and sub_off is not None:
                    add_off = off
                continue
            # cmp rX,#imm8 + bls 回跳 → 循环上限
            if (h & 0xF800) == 0x2800 and off + 2 < fend:
                h2 = struct.unpack_from("<H", rom, off + 2)[0]
                if (h2 & 0xFF00) == 0xD900:
                    loops.append((off, h & 0xFF))
                continue

        if sub_off is None or sub_sp >= stack:
            continue
        frame_end = add_off if add_off is not None else fend
        if term is not None and not (sub_off < term < frame_end):
            term = None
        caps = [
            (o, i) for o, i in loops
            if sub_off < o < frame_end and cap_lo <= i <= cap_hi
        ]
        if term is None and not caps:
            continue
        done.add(fstart)
        imm7 = stack // 4

        if term is not None and term not in taken:
            h = struct.unpack_from("<H", rom, term)[0]
            rn, rt = (h >> 3) & 7, h & 7
            out.append({
                "off": f"0x{term:X}",
                "bytes": struct.pack(
                    "<H", 0x7000 | ((new_cap - 1) << 6) | (rn << 3) | rt
                ).hex(" "),
                "label": f"buf[{old_stride - 1}]=FF→[{new_cap - 1}] "
                         f"(stride {old_stride}→{new_stride})",
            })
            taken.add(term)

        if sub_off not in taken:
            out.append({
                "off": f"0x{sub_off:X}",
                "bytes": struct.pack("<H", 0xB080 | imm7).hex(" "),
                "label": f"sub sp,#{sub_sp}→#{stack}"
                         f"（名表缓冲 {old_stride}→{new_cap}）",
            })
            taken.add(sub_off)
        if add_off is not None and add_off not in taken:
            out.append({
                "off": f"0x{add_off:X}",
                "bytes": struct.pack("<H", 0xB000 | imm7).hex(" "),
                "label": f"add sp,#{sub_sp}→#{stack}",
            })
            taken.add(add_off)

        for o, i in caps:
            if o in taken:
                continue
            hc = struct.unpack_from("<H", rom, o)[0]
            out.append({
                "off": f"0x{o:X}",
                "bytes": struct.pack("<H", 0x2800 | (hc & 0x0700)
                                     | cap_lim).hex(" "),
                "label": f"循环上限 #{i}→#{cap_lim}",
            })
            taken.add(o)
    return out


def _text_ptr_index(rom: bytes) -> dict[int, list[int]]:
    """一次性建立「文本地址 -> 所有指向它的 u32 站点」反查表。

    全 ROM 逐字节滑动窗口，包含**非 4 对齐**站点 —— 日版脚本的内联指针
    大量落在 +3 位置，只扫对齐位置会漏掉一半以上。
    numpy 可用时向量化（~0.3s），否则退化为纯 Python（慢但结果一致）。
    """
    n = len(rom)
    idx: dict[int, list[int]] = {}
    try:
        import numpy as np

        a = np.frombuffer(rom, dtype=np.uint8)
        w = (
            a[:-3].astype(np.uint32)
            | (a[1:-2].astype(np.uint32) << 8)
            | (a[2:-1].astype(np.uint32) << 16)
            | (a[3:].astype(np.uint32) << 24)
        )
        mask = (w >= GBA_BASE) & (w < GBA_BASE + 0x08000000)
        offs = np.nonzero(mask)[0]
        vals = (w[offs] - GBA_BASE).tolist()
        for v, o in zip(vals, offs.tolist()):
            idx.setdefault(int(v), []).append(int(o))
        return idx
    except ImportError:
        pass

    import struct as _st

    for o in range(0, n - 3):
        v = _st.unpack_from("<I", rom, o)[0]
        if v >= GBA_BASE:
            idx.setdefault(v - GBA_BASE, []).append(o)
    return idx


def _find_anchor(
    rom: bytes,
    ptr_idx: dict[int, list[int]],
    addr: int,
) -> tuple[int, list[int]] | None:
    """从一条无指针的串向前回溯，找到第一个**有引用**的串（锚点）。

    日版脚本的 message 是一条条 FF 分隔的串，代码只在块头挂一个指针，
    之后顺序读到底。所以「目标串 + 块头」共享同一份数据，搬块头即可。

    两条护栏，都不涉及「走了多少字节」：

    1. **紧邻**：上一条串的 FF 必须正好落在 ``cur - 1``。这是「同一块」
       的充分证据 —— 中间夹了任何别的东西就断链。正是这条取代了以前的
       512 字节距离上限：0x14ab56 的块头在 0x14a8e6（624 字节外），
       中间 7 条串严丝合缝，是**合法**长块，而旧上限把它一刀切掉了。
    2. **像文本**：路径上每一条都要过 ``looks_like_jp_text``。ROM 里大量
       索引表/偏移表的字节也恰好以 FF 分隔（实测 0x154E89 是 u16 索引，
       被误当串、还查到假站点），照着搬会把数据区一起重编码 → 破坏索引。

    紧邻判据保证 ``s < cur`` 严格递减，所以不需要步数或距离上限。
    """
    from .jp_pcs import looks_like_jp_text

    # 单条串的搜索窗口：AXVJ 有 220~284 字节的长对话块，留 1024 足够。
    window = 1024
    cur = addr
    while True:
        p = rom.rfind(b"\xff", max(0, cur - window), cur - 1)
        if p < 0:
            return None
        s = p + 1
        e = rom.find(b"\xff", s, min(s + window, len(rom)))
        if e < 0:
            return None
        # 紧邻：这条串必须正好结束在目标起点前一个字节。
        # 不紧邻说明中间夹着别的东西（数据区/另一块），立刻放弃。
        if e != cur - 1:
            return None
        body = rom[s:e + 1]
        # ⚠️ 2026-11-10 试过放行「极短串」（≤3 字节正文，`おー‥` / ` ？` 这类
        # 被语种比例判据拒掉的行）来续上链条：unresolved 398→334，但
        # trainer_card 场景直接卡死 —— 极短串的形态（`xx 00 FF`）在数据表里
        # 到处都是，链条照样会穿进数据区抓到假锚点。别再加宽这里。
        if not looks_like_jp_text(body):
            return None
        # 脚本指令流（指针 + 命令 + 少量日文）的字节同样能解成日文，
        # 整块重编码会把指令拆碎 —— 逐段拦，见 _segment_is_script。
        if _segment_is_script(rom, s, e):
            return None
        sites = ptr_idx.get(s)
        if sites:
            return s, sites
        cur = s


def _chain_has_rom_ptr(rom: bytes, start: int, end: int) -> bool:
    """锚点到目标这一整段是否**不是**纯 message 流。

    两条判据，任一命中就拒绝整块搬迁：

    1. **目标不是独立段**：``[start, end)`` 里一个 FF 都没有，说明目标串
       没被任何 FF 隔出来 —— 例如训练卡标题 0x389D50 是「7 个 u32 指针 +
       のトレーナーカード」，那条绘制路径按表内固定偏移取文本、不解 PCS，
       整块搬走只会把后缀变成空白。
    2. **是脚本指令流**：非对齐 u32 ROM 指针密度 > 3%。0x174xxx 那一片
       全是「指针 + 命令 + 少量文本」的脚本块，``looks_like_jp_text``
       会把它们一律放行（字节都在可解范围），但整块重编码会把指令流拆碎。
       实测密度：脚本块 4.4%~9%，纯文本块 0.8%~1.5%，分界很清楚。

    为什么不用「4 对齐处有连续两个指针」：脚本块里的指针是**非对齐**的
    （``0x1746BD: c0 46 17 08``），对齐扫描一个都抓不到。
    为什么不用「含 u32 指针」：日文 PCS 字节全在 0x00–0xF9，第 4 字节恰为
    0x08/0x09 的位置遍地都是，624 字节的正常对话块也会中招。
    """
    return b"\xff" not in rom[start:end]


def _segment_is_script(rom: bytes, s: int, e: int) -> bool:
    """``rom[s:e+1]`` 这一段是否其实是**脚本指令流**而不是 message 正文。

    0x174xxx 那一片是「u32 指针 + 命令字节 + 少量日文」的混合块，
    ``looks_like_jp_text`` 会把它们一律放行（字节全在可解范围），于是
    回溯链会穿过它们抓到假锚点，整块重编码会把指令流拆碎。

    判据是**非对齐 u32 ROM 指针密度**（脚本块里的指针不是 4 对齐的，
    ``0x1746BD: c0 46 17 08``）：脚本段实测 6.5%~9%，纯文本段 0.8%~1.5%。
    取 3% 为界、并要求至少 3 个命中。

    为什么从 2 改成 3：**短段（40~50 字节）里 2 个命中就是 4%~5% 密度**，
    正好落进脚本区间，于是正常 message 被误杀。实测两类 46 字节段：

        正文 0x16A72B  命中 2  值 0x08020016 / 0x08051350（指到 1.3MB 外）
        脚本 0x1746B6  命中 3  值 0x081746C0 / 0x0817FDA0（都指到自身附近）

    要求 3 个命中后，0x174C34 那条假链（段内 6.5%）仍然被拦，而
    「紧邻在有指针串之后的正文段」能正常接上锚点了。

    逐段判、而不是整条链判：短词条池（0x3B2A72 那批 8 字节特性名）
    每段都不含指针，按整链判会误伤 129 条。
    """
    span = e + 1 - s
    if span < 16:
        return False
    n = 0
    rom_hi = GBA_BASE + len(rom)
    for q in range(s, min(e - 2, len(rom) - 3)):
        w = int.from_bytes(rom[q:q + 4], "little")
        if GBA_BASE <= w < rom_hi:
            n += 1
    return n >= 3 and n * 100 > span * 3


def _looks_like_ptr_array(rom: bytes, site: int) -> bool:
    """站点是否处在指针数组里（相邻 4 字节也是指向 ROM 的 GBA 指针）。

    池头保护的目的是「别把唯一的那个字面量改走」，而不是禁止改数组元素。
    地点名 0x3BEF78 起就是一串 u32，指向 0x3BECB7 之后的连续串池：
    逐条改写安全，一刀切保护会把整个模块判死（实测 2259 条 redirect=0）。
    """
    if site + 8 > len(rom):
        return False
    v = struct.unpack_from("<I", rom, site)[0]
    for q in (site - 4, site + 4):
        if q < 0 or q + 4 > len(rom):
            continue
        w = struct.unpack_from("<I", rom, q)[0]
        if 0x08000000 <= w < 0x0A000000 and w != v:
            return True
    return False


def _struct_table_base_bus(modules: dict[str, Any]) -> set[int]:
    """Struct 表基址（总线）。这些字面量是整表入口，禁止当单条名字 pointer 改写。"""
    out: set[int] = set()
    for mod in modules.values():
        if not isinstance(mod, dict) or mod.get("type") not in STRUCT_TYPES:
            continue
        try:
            base = _off(mod["start"])
        except (KeyError, TypeError, ValueError):
            continue
        read = mod.get("read") or {}
        name_off = int(read.get("name_offset") or 0)
        out.add(GBA_BASE + base)
        if name_off:
            out.add(GBA_BASE + base + name_off)
    return out


def _packed_scan_pool_heads(
    rom: bytes,
    modules: dict[str, Any],
    entries: list[dict],
) -> set[int]:
    """Scan 模块里「打包串池」的首址（总线）。

    训练家 class 名等是连续 ``…FF 下一条…``，代码字面量常只挂池头
    （如 ``ポケモントレーナー`` @ 0x1C4A14）。把该字面量改成单条扩展译文
    后，后续 class 名全部失联 → 领航员训练家信息列表错位乱画。

    ⚠️ **只有「真被代码当基址用」的地址才配保护**（``_is_code_base``：
    存在 ``ldr rX,[pc,#imm]`` 加载该字面量）。否则误伤普通指针：

    * 地点名 0x3BECB7 —— range 起点，但 ``find_ldrs`` 为 0；它的
      0x3BEF78 是「[ptr][flags][ptr][flags]」混排表里的普通指针，
      单条改安全，却因为 ``heads.add(GBA_BASE + lo)`` 被整条拒掉。
    * 道具说明 0x3984DC 同理。
    * 训练卡 0x389D6C 有 1 处 ldr → 确实是基址，保护正确。
    """
    by_mod: dict[str, list[dict]] = {}
    for e in entries:
        by_mod.setdefault(str(e.get("module") or ""), []).append(e)

    from .table_stride import find_ldrs

    def _is_code_base(addr: int) -> bool:
        return bool(find_ldrs(rom, addr))

    heads: set[int] = set()
    for name, mod in modules.items():
        if not isinstance(mod, dict) or mod.get("type") != "scan":
            continue
        ranges = mod.get("ranges")
        if not ranges:
            if mod.get("start") in (None, "") or mod.get("end") in (None, ""):
                continue
            ranges = [{"start": mod["start"], "end": mod["end"]}]
        ents = sorted(
            (e for e in by_mod.get(name, []) if _entry_file_off(e) is not None),
            key=lambda e: _entry_file_off(e) or 0,
        )
        for rg in ranges:
            try:
                lo = _off(rg["start"])
                hi = _off(rg["end"])
            except (KeyError, TypeError, ValueError):
                continue
            in_rg = [
                e for e in ents
                if (a := _entry_file_off(e)) is not None and lo <= a <= hi
            ]
            if len(in_rg) < 2:
                continue
            # 多数 class 名池是「FF 后紧接下一条」，偶有数字节垫片；
            # 不要求完美无缝——只要同 range 内 ≥2 条，池头字面量就不能单条改写。
            near = 0
            for i in range(len(in_rg) - 1):
                a = _entry_file_off(in_rg[i])
                b = _entry_file_off(in_rg[i + 1])
                if a is None or b is None:
                    continue
                end = rom.find(0xFF, a, min(a + 256, len(rom)))
                if end >= 0 and end < b <= end + 16:
                    near += 1
            if near < max(1, (len(in_rg) - 1) // 2):
                continue
            head = _entry_file_off(in_rg[0])
            for cand in (head, lo):
                if cand is None:
                    continue
                # 只有被代码 ldr 当基址加载的才保护；普通指针不要误伤
                if _is_code_base(cand):
                    heads.add(GBA_BASE + cand)
    return heads


def _ptr_sources_for_entry(
    rom: bytes,
    entry: dict,
    *,
    text_spans: list[tuple[int, int]] | None,
    lz_spans: list | None,
    struct_bases: set[int] | None = None,
) -> list[str]:
    from .policy import expand_pointer_sources
    from .translate_plan import _ptr_sources

    addr = _entry_file_off(entry)
    if addr is None:
        return []
    raw = list(_ptr_sources(entry))
    module_id = entry.get("module") or ""
    offs = expand_pointer_sources(
        rom,
        addr,
        raw,
        category=module_id,
        original=entry.get("original") or "",
        expected_pointer=GBA_BASE + addr,
        lz_spans=lz_spans,
        text_spans=text_spans,
    )
    # 树果名[0] 等：名字嵌在表头，extract 会把「=gBerries」整表字面量当成
    # 第 0 条的 pointer_sources；逐条 relocate 会改掉表基 → 元数据全毁。
    bases = struct_bases or set()
    if bases:
        kept: list[int] = []
        for p in offs:
            if p + 4 > len(rom):
                continue
            cur = struct.unpack_from("<I", rom, p)[0]
            if cur in bases:
                continue
            kept.append(p)
        offs = kept
    return [f"0x{p:X}" for p in offs]


def _collect_patches(texts: dict) -> list[dict]:
    """收集「没法算法化」的字节补丁，统一由 plan 落盘、writer 写入。

    能进主流程的补丁（改 stride 立即数、改读点指令、改基址字面量）都由
    各自的 plan 函数**算**出来，走 ``tables[].insns`` / ``tables[].literals``；
    这里只放算法定不出来的显式声明，避免把它们写死在 Python 里。

    两个来源，语义相同：

    * ``texts["patches"]`` —— 全游戏级（例如某个渲染函数里的常量）
    * ``modules[X]["patches"]`` —— 模块级，方便和该表的配置放一起

    每条 ``{"off": "0x1234", "bytes": "68 61", "label": "..."}``，``off``
    是**文件偏移**（不带 0x08000000 基址），``bytes`` 是十六进制串。
    支持 ``patches`` 里写 ``enabled: false`` 临时关掉。
    """
    out: list[dict] = []
    seen: set[int] = set()

    def _add(items, scope: str) -> None:
        for it in items or []:
            if not isinstance(it, dict) or it.get("enabled") is False:
                continue
            try:
                off = int(str(it.get("off")), 16) & 0xFFFFFF
                raw = bytes.fromhex(
                    str(it.get("bytes") or "").replace(" ", "").replace(",", "")
                )
            except (TypeError, ValueError):
                continue
            if not raw or off in seen:
                continue
            seen.add(off)
            out.append({
                "off": f"0x{off:X}",
                "bytes": raw.hex(" "),
                "label": it.get("label") or f"{scope} 补丁",
            })

    _add(texts.get("patches"), "全局")
    for mod_name, mod in (texts.get("modules") or {}).items():
        if isinstance(mod, dict):
            _add(mod.get("patches"), str(mod_name))
    return out


def build_write_plan(
    rom: bytes,
    texts_path: Path,
    entries: list[dict],
    *,
    encoder: Encoder | None,
    game_id: str = "",
    out_path: Path | None = None,
) -> dict:
    """生成写入计划。``entries`` 须已带 translated / original / module。"""
    from .extract import trusted_lz_spans
    from .policy import collect_entry_text_spans
    from .translate_plan import dedupe_entries_by_id

    texts = json.loads(Path(texts_path).read_text(encoding="utf-8"))
    modules: dict[str, Any] = texts.get("modules") or {}
    entries = dedupe_entries_by_id(list(entries))
    lz_spans = trusted_lz_spans(rom)
    text_spans = collect_entry_text_spans(entries)
    # 非文本数据（人工/算法标记 noise:true 的条目）：不写、也不算「缺译文」。
    # 例如 0x1D4xxx 是「u16 递增序列 + FF FF」的坐标数据，扫描器把 FF FF
    # 当串终止符，切出一堆解码后是乱码的假文本。
    noise_addrs: set[int] = set()
    for _e in texts.get("entries") or []:
        if not isinstance(_e, dict) or not _e.get("noise"):
            continue
        try:
            noise_addrs.add(_off(_e["address"]))
        except (KeyError, TypeError, ValueError):
            continue
    # 整表/打包池基址字面量：禁止当单条 pointer/redirect 改写
    protected_bases = _struct_table_base_bus(modules) | _packed_scan_pool_heads(
        rom, modules, entries
    )

    # 文本地址 → 全部 u32 站点（含非对齐）反查表；以及 地址 → 译文。
    # 供「向前找锚点、整块搬」用：块内串虽然没有自己的指针，但地址能查到译文。
    ptr_idx = _text_ptr_index(rom)
    tr_by_addr: dict[int, str] = {}
    for e in entries:
        a0 = _entry_file_off(e)
        t0 = e.get("translated") or ""
        if a0 is not None and t0:
            tr_by_addr.setdefault(a0, t0)

    tables: list[dict] = []
    rows: list[dict] = []
    redirects: list[dict] = []
    skip: list[dict] = []
    table_notes: list[tuple[str, str]] = []
    cursor = TABLE_AREA

    # 仅 stride 算「整表已写入」；struct 只有读点钩成功才加入，失败回落逐条 redirect
    table_modules: set[str] = {
        n for n, m in modules.items()
        if isinstance(m, dict) and m.get("type") in STRIDE_TABLE_TYPES
    }
    handled_ids: set[str] = set()

    for name, mod in modules.items():
        if not isinstance(mod, dict):
            continue
        if _write_disabled(mod):
            for e in _module_entries(entries, name):
                eid = str(e.get("id") or "")
                skip.append({"id": eid, "module": name, "reason": "write_disabled"})
                if eid:
                    handled_ids.add(eid)
            continue

        is_stride = mod.get("type") in STRIDE_TABLE_TYPES
        is_struct = mod.get("type") in STRUCT_TYPES
        if not is_stride and not is_struct:
            continue

        mod_entries = _module_entries(entries, name)
        live = [
            e for e in mod_entries
            if not e.get("_reject")
            and (e.get("translated") or "")
            and (e.get("translated") or "") != (e.get("original") or "")
        ]

        if is_struct:
            from .struct_trampoline import (
                plan_struct_name_ptr,
                plan_struct_same_stride_clone,
                plan_struct_trampoline,
            )
            from .struct_reflow import plan_struct_stride_reflow

            # 名字读法决定能不能翻：
            #   ① 有「返回名字指针」的读点 → trampoline 旁路，名字长度不限（最好）
            #   ② 没有读点、只能按固定偏移内联读 → 整块克隆，能放几个放几个
            # 顺序不能反：结构体内联名槽往往只有 6~11 字节，先克隆会为了
            # 几条长译名把整表判死，白丢覆盖率。
            table = None
            cursor_saved = cursor
            errs: list[str] = []
            for label, fn in (
                ("trampoline", plan_struct_trampoline),
                ("name_ptr", plan_struct_name_ptr),
                # 扩 stride + 字段重排：只在配置里写了 read.reflow 的表上启用
                ("reflow", plan_struct_stride_reflow),
                ("clone", plan_struct_same_stride_clone),
            ):
                t, c, e = fn(
                    rom, name, mod, mod_entries, encoder, cursor_saved
                )
                if t is not None:
                    table, cursor = t, c
                    if label == "clone" and errs:
                        table_notes.append(
                            (name, f"名字指针旁路未成（{errs[0]}），回落整块克隆")
                        )
                    break
                errs.append(f"{label}: {e}")
            if table is None:
                table_notes.append(
                    (name, f"名字指针旁路与整块克隆均失败（{' | '.join(errs)}），回落逐条")
                )
                for e in mod_entries:
                    if e.get("_reject"):
                        eid = str(e.get("id") or "")
                        skip.append(
                            {"id": eid, "module": name, "reason": "reject"}
                        )
                        if eid:
                            handled_ids.add(eid)
                # 不 continue：留给下方 rows/redirects
            if table is not None:
                for e in mod_entries:
                    eid = str(e.get("id") or "")
                    if eid:
                        handled_ids.add(eid)
                    if e.get("_reject"):
                        skip.append({"id": eid, "module": name, "reason": "reject"})
                tables.append(table)
                table_modules.add(name)
                if table.get("note"):
                    table_notes.append((name, str(table["note"])))
            continue

        for e in mod_entries:
            eid = str(e.get("id") or "")
            if eid:
                handled_ids.add(eid)
            if e.get("_reject"):
                skip.append({"id": eid, "module": name, "reason": "reject"})

        table, cursor, err = _plan_table_stride(
            rom, name, mod, live, encoder, cursor, game_id=game_id,
        )
        if table is None:
            table_notes.append((name, err or "失败"))
            # 扩步长失败：撤销 handled，回落逐条重定向（超短/无指针兜底）
            for e in mod_entries:
                eid = str(e.get("id") or "")
                if eid:
                    handled_ids.discard(eid)
            table_modules.discard(name)
            for e in mod_entries:
                if e.get("_reject"):
                    eid = str(e.get("id") or "")
                    skip.append({"id": eid, "module": name, "reason": "reject"})
                    if eid:
                        handled_ids.add(eid)
        else:
            tables.append(table)
            if table.get("note"):
                table_notes.append((name, str(table["note"])))
            # 扩步长后仍塞不进新槽的 → 从整表摘出，改走逐条重定向
            new_cap = int(table.get("new_name_cap") or table.get("new_stride") or 0)
            if new_cap:
                for e in live:
                    raw = _encode(
                        e.get("translated") or "",
                        encoder,
                        game_id=game_id,
                        module=name,
                    )
                    if raw and _try_fit_name(raw, new_cap) is None:
                        eid = str(e.get("id") or "")
                        if eid:
                            handled_ids.discard(eid)
                        table_notes.append((
                            name,
                            f"超短槽回落重定向 id={eid}",
                        ))

    # 已整表克隆的地址区间（供 per-entry 阶段判断「已覆盖」）
    table_ranges: list[tuple[int, int]] = []
    for _t in tables:
        try:
            lo = _off(_t["old_base"])
            hi = lo + int(_t["count"]) * int(_t["old_stride"])
        except (KeyError, TypeError, ValueError):
            continue
        table_ranges.append((lo, hi))

    for entry in entries:
        eid = str(entry.get("id") or "")
        if eid and eid in handled_ids:
            continue
        module = entry.get("module") or ""
        mod = modules.get(module) if module in modules else {}
        if isinstance(mod, dict) and _write_disabled(mod):
            skip.append({"id": eid, "module": module, "reason": "write_disabled"})
            continue
        if entry.get("_reject"):
            skip.append({"id": eid, "module": module, "reason": "reject"})
            continue
        if noise_addrs and _entry_file_off(entry) in noise_addrs:
            skip.append({"id": eid, "module": module, "reason": "noise"})
            continue
        translated = entry.get("translated") or ""
        original = entry.get("original") or ""
        if not translated or translated == original:
            skip.append({"id": eid, "module": module, "reason": "no_translation"})
            continue
        # 表模块已处理；落单条目若仍挂在表模块上（无译文已 skip）则忽略
        if module in table_modules:
            continue
        # 地址落在「已整表克隆」的区间内 → 内容已随表写入，不再单条处理。
        # 实测「秘密基地装饰名」同一地址在 entries 里有重复条目（239 条 vs
        # 表 count 121），多出来的 118 条会全部变成 unresolved 噪音。
        a_tbl = _entry_file_off(entry)
        if a_tbl is not None and any(
            lo <= a_tbl < hi for lo, hi in table_ranges
        ):
            continue

        body = _encode(
            translated, encoder, game_id=game_id, module=module,
        )
        if not body:
            skip.append({"id": eid, "module": module, "reason": "encode_failed"})
            continue

        # S2：正文目标必须是真 PCS。WindowTemplate 等「xx 00 yy 00 FF」会被
        # looks_like_jp_text 误收成「み お 」；改指针 → 领航员训练家信息爆错。
        # 列对齐 UI（write.space_pad）放宽 00 密度，仍拒 is_struct_like_pcs。
        addr = _entry_file_off(entry)
        if addr is not None:
            from .jp_pcs import looks_like_jp_text
            from .policy import is_struct_like_pcs

            end = rom.find(0xFF, addr, addr + 513)
            if end < 0:
                skip.append({"id": eid, "module": module, "reason": "bad_text_target"})
                continue
            raw = bytes(rom[addr : end + 1])
            space_pad = bool((mod.get("write") or {}).get("space_pad"))
            if is_struct_like_pcs(raw) or not looks_like_jp_text(
                raw, allow_space_pad=space_pad
            ):
                skip.append({"id": eid, "module": module, "reason": "bad_text_target"})
                continue

        ptrs = _ptr_sources_for_entry(
            rom,
            entry,
            text_spans=text_spans,
            lz_spans=lz_spans,
            struct_bases=protected_bases,
        )
        if ptrs:
            rows.append({
                "id": eid,
                "module": module,
                "kind": "pointer",
                "address": entry.get("address"),
                "body_hex": body.hex(" "),
                "pointer_sources": ptrs,
            })
            continue

        # 无登记指针：全 ROM 发现后再走同一套 filter（禁止裸 find 直写）
        filtered: list[int] = []
        if addr is not None:
            from .policy import discover_pointer_sources, filter_pointer_sources

            discovered = discover_pointer_sources(rom, addr)
            filtered = filter_pointer_sources(
                rom,
                discovered,
                addr,
                category=module,
                original=original,
                expected_pointer=GBA_BASE + addr,
                lz_spans=lz_spans,
                text_spans=text_spans,
            )
            # 与 rows 相同：整表/打包池基址字面量不得进 redirects。
            # 但「池头保护」只针对**单个字面量**：如果该站点其实是一个
            # 指针数组的元素（相邻 4 字节也是指向文本区的 GBA 指针），
            # 逐条改写是安全的 —— 地点名 0x3BEF78 就是这样，一刀切会把
            # 整模块 2259 条全判死。
            if protected_bases:
                filtered = [
                    p for p in filtered
                    if p + 4 <= len(rom)
                    and (
                        struct.unpack_from("<I", rom, p)[0] not in protected_bases
                        or _looks_like_ptr_array(rom, p)
                    )
                ]
        if filtered:
            redirects.append({
                "id": eid,
                "module": module,
                "kind": "redirect",
                "address": entry.get("address"),
                "body_hex": body.hex(" "),
                "sites": [
                    {"off": f"0x{p:X}", "mode": "literal"} for p in filtered
                ],
            })
        else:
            # 第③类 A：向前找锚点、整块搬迁。
            # 日版脚本的 message 是一条条 FF 分隔的串，代码常在**块头**挂一个
            # 指针，之后顺着 FF 顺序读到底。所以目标串虽然没有自己的指针，
            # 但和块头共享同一份数据 —— 把 [块头, 目标串尾] 整段重编码搬走、
            # 改块头的全部站点，效果等同于「整块搬」。
            cluster = None
            if addr is not None:
                anc = _find_anchor(rom, ptr_idx, addr)
                # 锚点到目标的这一段里若夹着 u32 ROM 指针，说明这个「块」
                # 不是 message print 流，而是「指针表 + 尾随文本」的混合
                # 结构（训练卡标题 0x389D50 = 7 个指针 + のトレーナーカード）。
                # 整块搬走 + 改块头指针后，那条绘制路径仍按「表内 +0x1C 取
                # 文本」的方式读，但它的绘制不走 PCS 解码（不认 F7），于是
                # 标题只剩玩家名、后缀一片空白 —— 比保留日文更糟。
                # 正常 message 块是纯文本 + 控制码，不会出现 u32 指针。
                if anc and _chain_has_rom_ptr(rom, anc[0], addr):
                    anc = None
                if anc:
                    s0, sites0 = anc
                    end_t = rom.find(0xFF, addr, min(addr + 512, len(rom)))
                    if end_t > addr:
                        # 切点 = 锚点 ∪ 区间内所有**已知译文地址**。
                        # 只按 FF 切段会出事：0x389D50「7 个指针 + 日文」之间
                        # 没有 FF，整段被当成一段、查不到译文 → 原样复制，
                        # 于是训练卡标题永远是日文（而读点已改到新区，页面上
                        # 表现为标题只剩玩家名、后面一片空白）。
                        # 已知译文地址才是真正的「串起点」，比 FF 更可靠。
                        cuts = [s0]
                        cuts += sorted(
                            a for a in tr_by_addr if s0 < a <= end_t
                        )
                        cuts.append(end_t + 1)
                        blob = bytearray()
                        ok = True
                        for i in range(len(cuts) - 1):
                            a, b = cuts[i], cuts[i + 1]
                            tr = tr_by_addr.get(a)
                            if tr:
                                enc = _encode(
                                    tr, encoder, game_id=game_id, module=module
                                )
                                if not enc:
                                    enc = bytes(rom[a:b])
                                elif not enc.endswith(b"\xFF"):
                                    enc += b"\xFF"
                                blob += enc
                                continue
                            # 无译文的区间：内部再按 FF 切，逐串原样复制。
                            p = a
                            while p < b:
                                e = rom.find(0xFF, p, b)
                                if e < 0:
                                    blob += rom[p:b]
                                    break
                                blob += rom[p:e + 1]
                                p = e + 1
                        if ok and blob:
                            from .policy import filter_pointer_sources as _fps

                            fsites = _fps(
                                rom,
                                [f"0x{GBA_BASE + x:08X}" for x in sites0],
                                s0,
                                trust_unaligned=True,
                                category=module,
                                original=original,
                                expected_pointer=GBA_BASE + s0,
                                lz_spans=lz_spans,
                                text_spans=text_spans,
                            )
                            if fsites:
                                cluster = {
                                    "id": eid,
                                    "module": module,
                                    "kind": "cluster",
                                    "address": entry.get("address"),
                                    "anchor": f"0x{s0:X}",
                                    "body_hex": blob.hex(" "),
                                    "sites": [
                                        {"off": f"0x{x:X}", "mode": "literal"}
                                        for x in fsites
                                    ],
                                }
                if cluster:
                    redirects.append(cluster)
                    continue

            # 第③类 B：定不出任何可改指针站点时，若译文放得进原槽
            # （等长或更短），直接原地覆写。这是唯一不需要改指针的写法，
            # 适用于被「基址+偏移」「代码内联」等方式引用、静态找不到站点的串。
            raw_len = 0
            if addr is not None:
                end0 = rom.find(0xFF, addr, min(addr + 512, len(rom)))
                if end0 >= 0:
                    raw_len = end0 - addr + 1
            if raw_len and len(body) <= raw_len:
                redirects.append({
                    "id": eid,
                    "module": module,
                    "kind": "inplace",
                    "address": entry.get("address"),
                    "at": f"0x{addr:X}",
                    "body_hex": body.hex(" "),
                    "pad": raw_len - len(body),
                })
            else:
                # 模块声明了「名字没有读取点」时，这些条目本来就不会显示，
                # 单列成 no_reader，不要混进 unresolved 里虚高。
                reason = "unresolved_redirect"
                if isinstance(mod, dict) and (mod.get("read") or {}).get("no_reader"):
                    reason = "no_reader"
                skip.append({
                    "id": eid,
                    "module": module,
                    "reason": reason,
                })

    plan = {
        "game_id": game_id,
        "tables": tables,
        "rows": rows,
        "redirects": redirects,
        "patches": _collect_patches(texts),
        "skip": skip,
        "table_notes": [{"module": n, "note": m} for n, m in table_notes],
        "summary": {
            "tables": len(tables),
            "rows": len(rows),
            "redirects": len(redirects),
            "skip": len(skip),
            "skip_unresolved": sum(
                1 for s in skip if s.get("reason") == "unresolved_redirect"
            ),
            "table_area_cursor": f"0x{cursor:X}",
        },
    }
    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # 落盘时去掉 blob_hex 的巨型重复：bins 旁路；保留 hex 以便单文件自洽
        slim = dict(plan)
        out_path.write_text(
            json.dumps(slim, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return plan


def plan_to_translate_build_mirror(plan: dict, entries: list[dict]) -> dict:
    """兼容旧 inject 路径的调试镜像（无 keep 假通路）。"""
    by_id = {str(e.get("id") or ""): e for e in entries}
    out_entries: list[dict] = []
    for row in plan.get("rows") or []:
        e = by_id.get(row.get("id") or "", {})
        out_entries.append({
            "id": row.get("id"),
            "type": "relocate",
            "address": row.get("address") or e.get("address"),
            "module": row.get("module"),
            "original": e.get("original", ""),
            "translated": e.get("translated", ""),
            "original_hex": e.get("original_hex", ""),
            "target_hex": row.get("body_hex"),
            "pointer_sources": row.get("pointer_sources"),
        })
    for row in plan.get("redirects") or []:
        e = by_id.get(row.get("id") or "", {})
        out_entries.append({
            "id": row.get("id"),
            "type": "redirect",
            "address": row.get("address") or e.get("address"),
            "module": row.get("module"),
            "original": e.get("original", ""),
            "translated": e.get("translated", ""),
            "original_hex": e.get("original_hex", ""),
            "target_hex": row.get("body_hex"),
            "redirect_sites": row.get("sites"),
        })
    for s in plan.get("skip") or []:
        e = by_id.get(s.get("id") or "", {})
        out_entries.append({
            "id": s.get("id"),
            "type": "skip",
            "address": e.get("address", ""),
            "module": s.get("module"),
            "original": e.get("original", ""),
            "translated": e.get("translated", ""),
            "original_hex": e.get("original_hex", ""),
            "target_hex": e.get("original_hex", ""),
            "reason": s.get("reason"),
        })
    return {
        "game_id": plan.get("game_id"),
        "count": len(out_entries),
        "entries": out_entries,
        "write_plan_summary": plan.get("summary"),
    }
