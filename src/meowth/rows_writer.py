"""只按 ``write.plan.json`` 写入：表 blob / 指令 / 字面量、指针行、重定向。

不做通路决策。计划由 ``write_plan.build_write_plan`` 生成。
"""
from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

from .patch_table import GBA_BASE, TABLE_AREA

POINTER_OFFSET = GBA_BASE


def _off(value) -> int:
    v = int(str(value), 16) if not isinstance(value, int) else value
    if v >= GBA_BASE:
        v -= GBA_BASE
    return v


def load_plan(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_asm_from_plan(plan: dict, out_asm: Path) -> dict:
    """把 tables（+ 需要 armips 的 redirect 字面量可选项）写成 gen/patch_table.asm。"""
    out_asm = Path(out_asm)
    out_asm.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "; 唯一补丁表。由 rows_writer 根据 write.plan.json 生成，不要手改。",
        "; 等距表 = 新区整表 + 移位立即数 + 基址字面量。",
        "",
    ]
    stats = {"tables": 0, "insns": 0, "literals": 0, "bins": []}

    for table in plan.get("tables") or []:
        name = table.get("module") or "?"
        note = table.get("note") or ""
        new_base = _off(table["new_base"])
        new_gba = GBA_BASE + new_base
        blob_name = table.get("blob_name") or Path(table.get("blob") or "x.bin").name
        blob_hex = table.get("blob_hex") or ""
        if blob_hex:
            blob = bytes.fromhex(blob_hex)
            (out_asm.parent / blob_name).write_bytes(blob)
            stats["bins"].append(blob_name)

        lines.append(
            f"; {name}: {table.get('count')}×{table.get('old_stride')} → "
            f"{table.get('count')}×{table.get('new_stride')}  @ 0x{new_gba:08X}"
            + (f"  ({note})" if note else "")
        )
        for insn in table.get("insns") or []:
            off = _off(insn["off"])
            raw = bytes.fromhex(str(insn.get("bytes") or "").replace(" ", ""))
            body = ", ".join(f"0x{b:02X}" for b in raw)
            label = insn.get("label") or ""
            lines.append(f".org 0x{GBA_BASE + off:08X}")
            lines.append(f"    .byte {body}    ; {label}")
            lines.append("")
            stats["insns"] += 1
        for lit in table.get("literals") or []:
            off = _off(lit["off"])
            add = int(lit.get("add") or 0)
            target = new_gba + add
            word = struct.pack("<I", target)
            body = ", ".join(f"0x{b:02X}" for b in word)
            lines.append(f".org 0x{GBA_BASE + off:08X}")
            lines.append(
                f"    .byte {body}    ; {name} 基址 → 0x{target:08X}"
                + (f" (new+{add})" if add else "")
            )
            lines.append("")
            stats["literals"] += 1
        lines.append(f".org 0x{new_gba:08X}")
        lines.append(f'    .incbin "gen/{blob_name}"')
        lines.append("")
        stats["tables"] += 1

    # 显式补丁：算法定不出来的字节改写（config 里声明的那些）。
    # 与 tables[].insns 走同一条 .org/.byte 通道，所以不会有第二套写入逻辑。
    for patch in plan.get("patches") or []:
        off = _off(patch["off"])
        raw = bytes.fromhex(str(patch.get("bytes") or "").replace(" ", ""))
        if not raw:
            continue
        body = ", ".join(f"0x{b:02X}" for b in raw)
        label = patch.get("label") or ""
        lines.append(f".org 0x{GBA_BASE + off:08X}")
        lines.append(f"    .byte {body}    ; {label}")
        lines.append("")
        stats["insns"] += 1

    # redirect：目前 literal 模式在 apply_rows 里改 ROM；此处只留注释统计
    n_redir = len(plan.get("redirects") or [])
    if n_redir:
        lines.append(f"; redirects: {n_redir}（literal 站点由 rows_writer.apply_rows 写 ROM）")
        lines.append("")

    if not stats["tables"] and not plan.get("patches"):
        lines.append("; 这次计划里没有表。")
        lines.append("")

    out_asm.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return stats


def apply_rows(
    rom: bytearray,
    plan: dict,
    *,
    write_offset: int | None = None,
) -> tuple[bytearray, dict]:
    """写入 pointer rows 与 redirect bodies，并改指针/字面量槽。

    表本体假定已由 armips 经 patch_table.asm 写入；此处不重写 table blob。
    """
    if not isinstance(rom, bytearray):
        rom = bytearray(rom)

    # 正文扩展区：表区之后，避开 TABLE_AREA
    if write_offset is None:
        write_offset = max(0x01400000, TABLE_AREA_END_SAFE())
    # 若 ROM 已含表区数据，仍从 0x01400000 起写常规正文（与历史 inject 一致）
    if write_offset < 0x01400000:
        write_offset = 0x01400000

    stats = {
        "relocated": 0,
        "redirected": 0,
        "ptr_writes": 0,
        "errors": 0,
        "write_start": write_offset,
    }

    def _place(body: bytes) -> int:
        nonlocal write_offset
        need = write_offset + len(body)
        if need > len(rom):
            rom.extend(b"\x00" * (need - len(rom) + 0x1000))
        rom[write_offset:write_offset + len(body)] = body
        gba = POINTER_OFFSET + write_offset
        write_offset += len(body)
        # 4 对齐下一条
        write_offset = (write_offset + 3) & ~3
        return gba

    for row in plan.get("rows") or []:
        try:
            body = bytes.fromhex(str(row.get("body_hex") or "").replace(" ", ""))
            if not body:
                stats["errors"] += 1
                continue
            # 与历史 AXVJ relocate 一致：正文后补 FF 再 25×FF 填充（标题菜单盲拷）
            while body and body[-1] in (0xFA, 0xFF):
                body = body[:-1]
            body = body + bytes([0xFF]) + bytes([0xFF] * 25)
            new_ptr = _place(body)
            for src in row.get("pointer_sources") or []:
                off = _off(src)
                if off + 4 > len(rom):
                    continue
                rom[off:off + 4] = new_ptr.to_bytes(4, "little")
                stats["ptr_writes"] += 1
            stats["relocated"] += 1
        except Exception:
            stats["errors"] += 1

    for row in plan.get("redirects") or []:
        try:
            body = bytes.fromhex(str(row.get("body_hex") or "").replace(" ", ""))
            # 第③类 A：整块搬迁（块头有指针，块内串没有）。
            # body 是已经拼好的连续串流，**不能**做 FF 修剪/尾部填充 ——
            # 那会把块内第二条及以后的串吃掉。
            if row.get("kind") == "cluster":
                if not body:
                    stats["errors"] += 1
                    continue
                new_ptr = _place(body)
                for site in row.get("sites") or []:
                    off = _off(site["off"])
                    if off + 4 <= len(rom):
                        rom[off:off + 4] = new_ptr.to_bytes(4, "little")
                        stats["ptr_writes"] += 1
                stats["clustered"] = stats.get("clustered", 0) + 1
                continue
            # 第③类兜底：原地覆写（定不出指针站点的串，译文不超原槽）
            if row.get("kind") == "inplace":
                at = _off(row["at"])
                pad = int(row.get("pad") or 0)
                if not body or at + len(body) + pad > len(rom):
                    stats["errors"] += 1
                    continue
                rom[at:at + len(body)] = body
                if pad:
                    rom[at + len(body):at + len(body) + pad] = bytes([0xFF]) * pad
                stats["inplaced"] = stats.get("inplaced", 0) + 1
                continue
            if not body:
                stats["errors"] += 1
                continue
            while body and body[-1] in (0xFA, 0xFF):
                body = body[:-1]
            body = body + bytes([0xFF]) + bytes([0xFF] * 25)
            new_ptr = _place(body)
            for site in row.get("sites") or []:
                mode = site.get("mode") or "literal"
                off = _off(site["off"])
                if mode == "literal" and off + 4 <= len(rom):
                    rom[off:off + 4] = new_ptr.to_bytes(4, "little")
                    stats["ptr_writes"] += 1
                elif mode == "bl_stub" and site.get("bytes"):
                    raw = bytes.fromhex(str(site["bytes"]).replace(" ", ""))
                    rom[off:off + len(raw)] = raw
            stats["redirected"] += 1
        except Exception:
            stats["errors"] += 1

    stats["write_end"] = write_offset
    return rom, stats


def TABLE_AREA_END_SAFE() -> int:
    from .patch_table import TABLE_AREA_END

    return TABLE_AREA_END


def apply_plan(
    rom: bytearray,
    plan: dict,
    *,
    asm_out: Path | None = None,
    write_offset: int | None = None,
    tables_via_armips: bool = True,
) -> tuple[bytearray, dict]:
    """完整应用：可选写 asm；若 tables_via_armips=False 则 Python 直接写表。"""
    meta: dict[str, Any] = {}
    if asm_out is not None:
        meta["asm"] = write_asm_from_plan(plan, asm_out)

    if not tables_via_armips:
        rom, tstats = _apply_tables_python(rom, plan)
        meta["tables_python"] = tstats

    rom, rstats = apply_rows(rom, plan, write_offset=write_offset)
    meta["rows"] = rstats
    return rom, meta


def _apply_tables_python(rom: bytearray, plan: dict) -> tuple[bytearray, dict]:
    stats = {"tables": 0}
    for table in plan.get("tables") or []:
        blob_hex = table.get("blob_hex") or ""
        if not blob_hex:
            continue
        blob = bytes.fromhex(blob_hex)
        new_base = _off(table["new_base"])
        need = new_base + len(blob)
        if need > len(rom):
            rom.extend(b"\x00" * (need - len(rom) + 0x1000))
        rom[new_base:new_base + len(blob)] = blob
        new_gba = GBA_BASE + new_base
        for insn in table.get("insns") or []:
            off = _off(insn["off"])
            raw = bytes.fromhex(str(insn.get("bytes") or "").replace(" ", ""))
            rom[off:off + len(raw)] = raw
        for lit in table.get("literals") or []:
            off = _off(lit["off"])
            add = int(lit.get("add") or 0)
            rom[off:off + 4] = struct.pack("<I", new_gba + add)
        stats["tables"] += 1
    return rom, stats
