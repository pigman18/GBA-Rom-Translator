"""唯一补丁表。

流水线在打包时写 ``gen/patch_table.asm``，main.asm 只 include 这一份。
手写的界面补丁（PC 宽度、图鉴列、默认名、单位）不在这里。

主线三类（见 ``docs/ALGO_PIPELINE.md`` §八；**不做原地写回**）：

1. 等长/等距表 → 整表进新区；新步长按该表最长译文；改基址 + 改步长
2. 常规文本有指针 → 新区正文 + 改全部引用指针（进本表）
3. 常规文本无指针 → 重定向进本表（不得 keep）

有译文时不应因「放不下 / 没指针」落成 keep。
主路径已改为 ``write_plan`` → ``rows_writer``；本模块保留给无 write.plan 时的回退扫描。
"""
from __future__ import annotations

import json
import re
import struct
from pathlib import Path

from .table_relink import parse_ldr_literal_target
from .table_stride import plan_stride_rewrite
from .thumb_symexec import solve_site_auto

GBA_BASE = 0x08000000
# 文件偏移。文本搬迁大约在 0x01400000，字库在 0x01000000，这张表放在二者之后。
TABLE_AREA = 0x01EB0000
TABLE_AREA_END = 0x01F00000


def _off(value) -> int:
    v = int(str(value), 16) if not isinstance(value, int) else value
    if v >= GBA_BASE:
        v -= GBA_BASE
    return v


def _load_modules(texts_path: Path) -> dict:
    data = json.loads(texts_path.read_text(encoding="utf-8"))
    return data.get("modules") or {}


def _encoded_rows(
    build: dict, module: str, base: int, stride: int, count: int, encoder
) -> dict[int, bytes]:
    """用译文重新编码。build.json 里放不进旧槽的条目是 keep，target_hex 仍是日文。"""
    rows: dict[int, bytes] = {}
    for entry in build.get("entries") or []:
        if entry.get("module") != module:
            continue
        addr = entry.get("address")
        if not addr:
            continue
        idx = (_off(addr) - base) // stride
        if not (0 <= idx < count) or (_off(addr) - base) % stride:
            continue
        text = entry.get("translated") or ""
        raw = b""
        if text and encoder is not None:
            try:
                raw = encoder(text)
            except Exception:
                raw = b""
        if not raw:
            hex_text = (entry.get("target_hex") or "").replace(" ", "")
            if hex_text:
                try:
                    raw = bytes.fromhex(hex_text)
                except ValueError:
                    raw = b""
        if not raw:
            continue
        if raw[-1] != 0xFF:
            raw += b"\xFF"
        rows[idx] = raw
    return rows


def _code_base(rom: bytes, declared: int, stride: int) -> int:
    """语料起点常常跳过第 0 条空槽。乘法用的是含空槽的基址。"""
    from .table_stride import find_ldrs

    best = declared
    best_n = -1
    for base in (declared, declared - stride):
        if base < 0:
            continue
        hit = 0
        for ldr in find_ldrs(rom, base):
            got = solve_site_auto(rom, ldr, expect=stride)
            if got.stride == stride:
                hit += 1
        if hit > best_n:
            best, best_n = base, hit
    return best


def _choose_stride(old: int, need: int) -> int | None:
    """最小的 old×2^k，能放下 need，且倍数是 2 的幂。"""
    if need <= old:
        return None
    new = old
    for _ in range(4):
        new *= 2
        if new >= need:
            return new
    return None


def _groups_intact(body: bytes) -> bool:
    """F9 一组 4 字节。中间可以夹单字节假名，不能把一组切断。"""
    i = 0
    n = len(body)
    while i < n:
        if body[i] == 0xF9:
            if i + 4 > n:
                return False
            i += 4
        else:
            i += 1
    return True


def _fit(raw: bytes, slot: int) -> bytes | None:
    body = raw[:-1] if raw.endswith(b"\xFF") else raw
    if not _groups_intact(body):
        return None
    if not raw.endswith(b"\xFF"):
        raw += b"\xFF"
    if len(raw) > slot:
        return None
    return raw + bytes([0xFF]) * (slot - len(raw))


def plan_patch_table(
    rom: bytes, texts_path: Path, build_path: Path, encoder=None
) -> tuple[str, list[tuple[str, bytes]], dict]:
    """返回 (asm 文本, [(bin 文件名, 字节)], 统计)。"""
    modules = _load_modules(texts_path)
    build = json.loads(build_path.read_text(encoding="utf-8")) if build_path.is_file() else {}
    lines = [
        "; 唯一补丁表。打包时由 meowth.patch_table 生成，不要手改。",
        "; 每张纯步长表 = 新区整表 + 移位立即数 + 这些站点的基址字面量。",
        "; 结构体表和校验没过的表只记在下面，不写字节。",
        "",
    ]
    bins: list[tuple[str, bytes]] = []
    cursor = TABLE_AREA
    stats = {"emitted": [], "skipped": []}

    for name, mod in modules.items():
        if not isinstance(mod, dict):
            continue
        write = mod.get("write") or {}
        if write.get("relocate") is False and write.get("replace") is False and write.get("slot") is False:
            stats["skipped"].append((name, "write 全关"))
            continue
        if mod.get("type") == "struct":
            stats["skipped"].append((name, "结构体，字段偏移另算"))
            lines.append(f"; {name}: 结构体，字段偏移另算，未写入")
            continue
        if mod.get("type") != "stride":
            continue
        read = mod.get("read") or {}
        if "stride" not in read or "start" not in mod or "end" not in mod:
            continue
        stride = int(read["stride"])
        declared = _off(mod["start"])
        end = _off(mod["end"])
        base = _code_base(rom, declared, stride)
        span = end - base + 1
        if stride <= 0 or span % stride:
            stats["skipped"].append((name, "区间不是步长整数倍"))
            continue
        count = span // stride
        rows = _encoded_rows(build, name, base, stride, count, encoder)
        if not rows:
            stats["skipped"].append((name, "没有译文"))
            continue
        need = max(len(raw) for raw in rows.values())
        new_stride = _choose_stride(stride, need)
        if new_stride is None:
            stats["skipped"].append((name, f"最长 {need}B 放得进 {stride}"))
            continue
        try:
            plan = plan_stride_rewrite(rom, base, stride, new_stride)
        except ValueError as exc:
            stats["skipped"].append((name, str(exc)))
            lines.append(f"; {name}: {exc}")
            continue
        if not plan.patches:
            stats["skipped"].append((name, "没有 K 等于旧步长的站点"))
            lines.append(f"; {name}: 没有可改的 index×{stride} 站点")
            continue

        ldrs: list[int] = []
        for patch in plan.patches:
            match = re.search(r"ldr 0x([0-9A-Fa-f]+)", patch.label)
            if not match:
                ldrs = []
                break
            ldrs.append(int(match.group(1), 16))
        if len(ldrs) != len(plan.patches):
            stats["skipped"].append((name, "移位指令没有对应的 ldr"))
            continue

        old_gba = GBA_BASE + base
        literals: list[int] = []
        bad_lit = False
        for ldr in ldrs:
            lit = parse_ldr_literal_target(rom, ldr)
            if lit is None or lit + 4 > len(rom):
                bad_lit = True
                break
            cur = struct.unpack_from("<I", rom, lit)[0]
            if cur != old_gba:
                bad_lit = True
                break
            literals.append(lit)
        if bad_lit:
            stats["skipped"].append((name, "站点字面量不是这张表的基址"))
            lines.append(f"; {name}: 字面量对不上基址，未写入")
            continue

        sim = bytearray(rom)
        for patch in plan.patches:
            sim[patch.offset:patch.offset + len(patch.data)] = patch.data
        # 只改一条移位，对 (i<<n)+i 这种倍数是错的。
        # 改完每个站点的 K 必须正好等于新步长，否则整张表不写。
        bad_k = 0
        for ldr in ldrs:
            got = solve_site_auto(bytes(sim), ldr, expect=new_stride)
            if got.stride != new_stride:
                bad_k += 1
        if bad_k:
            stats["skipped"].append((name, f"改完 {bad_k} 处 K 不是 {new_stride}"))
            lines.append(f"; {name}: 改移位后 K 不是 {new_stride}，未写入")
            continue

        blob = bytearray()
        for i in range(count):
            raw = rows.get(i)
            if raw is None:
                raw = bytes(rom[base + i * stride:base + i * stride + stride])
                if 0xFF in raw:
                    raw = raw[:raw.index(0xFF) + 1]
            fitted = _fit(raw, new_stride)
            if fitted is None:
                blob = bytearray()
                break
            blob += fitted
        if not blob:
            stats["skipped"].append((name, "译文切不开整字"))
            lines.append(f"; {name}: 译文长度不是整字，未写入")
            continue

        blob_size = len(blob)
        if cursor + blob_size > TABLE_AREA_END:
            stats["skipped"].append((name, "补丁表区域满了"))
            lines.append(f"; {name}: 0x{TABLE_AREA:07X} 区域放不下")
            continue
        new_base = cursor
        cursor = (cursor + blob_size + 3) & ~3
        new_gba = GBA_BASE + new_base
        bin_name = f"patch_table_{len(bins)}.bin"
        bins.append((bin_name, bytes(blob)))

        lines.append(
            f"; {name}: {count}×{stride} → {count}×{new_stride}  "
            f"@ 0x{new_gba:08X}  指令 {len(plan.patches)}  字面量 {len(set(literals))}"
        )
        for patch in plan.patches:
            org = GBA_BASE + patch.offset
            body = ", ".join(f"0x{b:02X}" for b in patch.data)
            lines.append(f".org 0x{org:08X}")
            lines.append(f"    .byte {body}    ; {patch.label}")
            lines.append("")
        for lit in sorted(set(literals)):
            word = struct.pack("<I", new_gba)
            body = ", ".join(f"0x{b:02X}" for b in word)
            lines.append(f".org 0x{GBA_BASE + lit:08X}")
            lines.append(f"    .byte {body}    ; {name} 基址 → 0x{new_gba:08X}")
            lines.append("")
        lines.append(f".org 0x{new_gba:08X}")
        lines.append(f"    .incbin \"gen/{bin_name}\"")
        lines.append("")
        stats["emitted"].append({
            "name": name,
            "old_stride": stride,
            "new_stride": new_stride,
            "count": count,
            "base": f"0x{new_gba:08X}",
            "insns": len(plan.patches),
            "literals": len(set(literals)),
        })

    if not stats["emitted"]:
        lines.append("; 这次没有通过校验的纯步长表。")
        lines.append("")
    return "\n".join(lines), bins, stats


def write_patch_table(
    rom_path: Path, texts_path: Path, build_path: Path, out_asm: Path, encoder=None
) -> dict:
    rom = Path(rom_path).read_bytes()
    text, bins, stats = plan_patch_table(rom, texts_path, build_path, encoder)
    out_asm.parent.mkdir(parents=True, exist_ok=True)
    out_asm.write_text(text, encoding="utf-8", newline="\n")
    for name, blob in bins:
        (out_asm.parent / name).write_bytes(blob)
    return stats
