import re

from .patch_table import GBA_BASE, TABLE_AREA_END, _off
from .struct_trampoline import _encode_body


def plan_struct_stride_reflow(
    rom: bytes,
    name: str,
    mod: dict,
    entries: list[dict],
    encoder,
    cursor: int,
    *,
    table_area_end: int = TABLE_AREA_END,
    gba_base: int = GBA_BASE,
) -> tuple[dict | None, int, str | None]:
    """按配置里的 ``read.reflow`` 扩 stride 并重排字段，整表克隆到新区。

    装饰名（0x3C2A44）走这条：名字没有 StringCopyN 读点（旁路做不了），
    只能让名字区变长；而字段 12/13/14 用 ``ldrb`` 访问（imm5 ≤ 31）、
    字段 12 还被 ``ldr`` 读过（要求 4 对齐），所以名字区定为 27B。

    配置形态::

        "read": {
          "entry_size": 28,
          "name_offset": 1,
          "reflow": {
            "new_stride": 48,
            "name_cap": 27,
            "fields": [[12, 28, 1], [13, 29, 1], [14, 30, 1],
                       [18, 32, 2], [20, 36, 4], [24, 40, 4]]
          }
        }

    ``fields`` 是 ``[旧偏移, 新偏移, 宽度]``，全部显式写出来 —— 位宽靠
    "相邻偏移差"推不出来（14 之后跳到 18，中间 15..17 是别的字段）。
    """
    from .struct_stride_expand import plan_struct_stride_expand

    read = mod.get("read") or {}
    reflow = read.get("reflow")
    if not isinstance(reflow, dict):
        return None, cursor, "未配置 read.reflow"
    try:
        old_stride = int(read["entry_size"])
        name_off = int(read.get("name_offset") or 0)
        new_stride = int(reflow["new_stride"])
        name_cap = int(reflow["name_cap"])
        fields = [
            (int(a), int(b), int(c)) for a, b, c in reflow.get("fields") or []
        ]
    except (KeyError, TypeError, ValueError) as exc:
        return None, cursor, f"reflow 配置非法：{exc}"
    if name_off + name_cap >= new_stride:
        return None, cursor, "名字区与字段区重叠"
    if not fields:
        return None, cursor, "reflow.fields 为空"

    try:
        base = _off(mod.get("start"))
    except (TypeError, ValueError):
        return None, cursor, "模块 start 非法"
    try:
        end = _off(mod.get("end"))
    except (TypeError, ValueError):
        end = base + old_stride
    if end <= base:
        return None, cursor, "模块 end 非法"
    count = (end - base) // old_stride + 1

    # 旧字段区的"名字槽"实测宽度（用于判断译文是否放得下）
    old_cap = name_cap if name_cap <= old_stride - name_off else old_stride - name_off

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
        if delta % old_stride:
            delta = a - base
            if delta % old_stride:
                continue
            idx = delta // old_stride
        else:
            idx = delta // old_stride
        if 0 <= idx < count:
            by_idx[idx] = e

    blob = bytearray()
    n_tr = 0
    n_keep = 0
    for i in range(count):
        src = base + i * old_stride
        old = bytes(rom[src:src + old_stride])
        if len(old) < old_stride:
            old = old + b"\x00" * (old_stride - len(old))
        new = bytearray(new_stride)

        # 名字：能放下就写中文，放不下保留原文
        raw = b""
        e = by_idx.get(i)
        if e is not None:
            text = e.get("translated") or ""
            if text and text != (e.get("original") or ""):
                enc = _encode_body(text, encoder)
                if enc and len(enc) <= name_cap:
                    raw = enc
                    n_tr += 1
        if not raw:
            seg = old[name_off:name_off + old_cap]
            cut = seg.find(b"\xFF")
            raw = seg[:cut + 1] if cut >= 0 else seg
            if e is not None and (e.get("translated") or ""):
                n_keep += 1
        new[name_off:name_off + len(raw)] = raw

        for old_off, new_off, width in fields:
            new[new_off:new_off + width] = old[old_off:old_off + width]
        # 首字节（索引）原样
        new[0] = old[0]
        blob += new

    if n_tr == 0:
        return None, cursor, "没有能放进新名字槽的译文"

    # 代码侧补丁（三连 + 字段平移）+ 字面量
    insns, lits, err = plan_struct_stride_expand(
        rom,
        base,
        old_stride,
        new_stride,
        count,
        name_off,
        name_cap,
        {o: n for o, n, _w in fields},
    )
    if err:
        return None, cursor, err
    if not lits:
        return None, cursor, "无表基字面量"

    total = len(blob)
    if cursor + total > table_area_end:
        return None, cursor, "补丁表区域满了"

    new_base = cursor
    next_cursor = (cursor + total + 3) & ~3

    safe = re.sub(r"[^\w\-]+", "_", name)
    table = {
        "module": name,
        "mode": "struct_stride_reflow",
        "old_base": f"0x{base:X}",
        "old_stride": old_stride,
        "new_base": f"0x{new_base:X}",
        "new_stride": new_stride,
        "count": count,
        "name_offset": name_off,
        "old_name_cap": old_cap,
        "new_name_cap": name_cap,
        "blob": f"gen/plan_table_{safe}.bin",
        "blob_name": f"plan_table_{safe}.bin",
        "blob_hex": bytes(blob).hex(),
        "insns": insns,
        "literals": lits,
        "field_map": {o: n for o, n, _w in fields},
        "note": (
            f"扩 stride + 字段重排 {old_stride}→{new_stride}"
            f"（名字 {name_off}..{name_off + name_cap} = {name_cap}B）；"
            f"translated={n_tr} keep_jp={n_keep} "
            f"insns={len(insns)} lits={len(lits)}"
        ),
    }
    return table, next_cursor, None
