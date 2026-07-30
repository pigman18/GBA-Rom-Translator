#!/usr/bin/env python3
"""
row_patcher.py - GBA ROM 图形导出导入工具

支持格式: 4bpp, 8bpp, 1bpp, palette, tilemap, raw
支持压缩: none, lz77, lz77_swap, auto
"""
import argparse
import json
import os
import struct
import sys
from pathlib import Path

from PIL import Image

# ─────────────────────────────────────────────
# LZ77 压缩解压
# ─────────────────────────────────────────────

def lz77_decompress(data: bytes, swap: bool = False) -> bytes:
    """
    解压 GBA LZ77 数据。

    swap=False: 标准 LZ77
        clen = (hi >> 4) + 3, coff = ((hi & 0xF) << 8) | lo + 1
    swap=True: Ruby JP 交换版
        clen = (lo >> 4) + 3, coff = ((lo & 0xF) << 8) | hi + 1
    """
    if len(data) < 4 or data[0] != 0x10:
        raise ValueError(f"不是 LZ77 数据 (首字节=0x{data[0]:02X}, 需要 0x10)")
    dst_size = data[1] | (data[2] << 8) | (data[3] << 16)
    dst = bytearray()
    src = 4
    while len(dst) < dst_size and src < len(data):
        flags = data[src]; src += 1
        for _ in range(8):
            if len(dst) >= dst_size:
                break
            if src >= len(data):
                break
            if flags & 0x80:
                if src + 1 >= len(data):
                    break
                if swap:
                    lo, hi = data[src], data[src + 1]
                    clen = ((lo >> 4) & 0xF) + 3
                    coff = (((lo & 0xF) << 8) | hi) + 1
                else:
                    lo, hi = data[src], data[src + 1]
                    clen = ((hi >> 4) & 0xF) + 3
                    coff = (((hi & 0xF) << 8) | lo) + 1
                src += 2
                if coff == 0 or len(dst) < coff:
                    raise ValueError(
                        f" LZ77 bad back-ref at dst={len(dst)}: "
                        f"coff={coff} clen={clen}"
                    )
                for _ in range(clen):
                    if len(dst) >= dst_size:
                        break
                    dst.append(dst[-coff])
            else:
                dst.append(data[src])
                src += 1
            flags <<= 1
    if len(dst) != dst_size:
        raise ValueError(
            f"LZ77 解压大小不匹配: 期望 {dst_size}, 得到 {len(dst)}"
        )
    return bytes(dst)


def lz77_compress(data: bytes, swap: bool = False) -> bytes:
    """
    LZ77 压缩。
    使用贪心前瞻匹配: 在已输出数据中查找最长匹配。
    最小匹配长度: 3 字节。
    """
    if not data:
        return struct.pack("<I", 0x10) + b"\x00\x00\x00"

    dst_size = len(data)
    compressed = bytearray()

    src = 0
    while src < dst_size:
        flag_pos = len(compressed)
        compressed.append(0)
        flags = 0

        for bit in range(8):
            if src >= dst_size:
                break

            best_len = 0
            best_dist = 0

            max_dist = min(src, 0xFFF)
            if max_dist > 0:
                search_start = src - max_dist
                window = data[search_start:src]

                for wpos in range(len(window)):
                    match_len = 0
                    while (match_len < 18 and
                           src + match_len < dst_size and
                           wpos + match_len < len(window) and
                           window[wpos + match_len] == data[src + match_len]):
                        match_len += 1
                    if match_len >= 3 and match_len > best_len:
                        best_len = match_len
                        best_dist = src - (search_start + wpos)

            if best_len >= 3:
                flags |= (0x80 >> bit)
                length_field = best_len - 3
                dist_field = best_dist - 1
                if swap:
                    lo = ((length_field & 0xF) << 4) | ((dist_field >> 8) & 0xF)
                    hi = dist_field & 0xFF
                else:
                    lo = dist_field & 0xFF
                    hi = ((length_field & 0xF) << 4) | ((dist_field >> 8) & 0xF)
                compressed.append(lo)
                compressed.append(hi)
                src += best_len
            else:
                compressed.append(data[src])
                src += 1

        compressed[flag_pos] = flags

    header = struct.pack("<I", 0x10 | (dst_size << 8))
    return header + bytes(compressed)


def find_lz77_size(data: bytes, offset: int) -> int:
    """从 LZ77 数据头计算实际压缩数据大小（包含 header）。"""
    if offset >= len(data) or data[offset] != 0x10:
        return 0
    dst_size = data[offset + 1] | (data[offset + 2] << 8) | (data[offset + 3] << 16)
    src = offset + 4
    written = 0
    while written < dst_size and src < len(data):
        flags = data[src]; src += 1
        for bit in range(8):
            if written >= dst_size:
                break
            if flags & (0x80 >> bit):
                if src + 1 >= len(data):
                    return src + 1 - offset
                lo, hi = data[src], data[src + 1]
                clen = ((lo >> 4) & 0xF) + 3
                coff = (((lo & 0xF) << 8) | hi) + 1
                src += 2
                for _ in range(clen):
                    if written >= dst_size:
                        break
                    written += 1
            else:
                src += 1
                written += 1
    return src - offset


# ─────────────────────────────────────────────
# 4bpp / 8bpp / 1bpp tile 编解码
# ─────────────────────────────────────────────

def decode_tiles(data: bytes, bpp: int, width_tiles: int, height_tiles: int,
                 count: int = 1, palette=None) -> list[Image.Image]:
    """
    将 raw tile 数据解码为 PNG 列表。

    bpp: 1, 4, 8
    每个 sprite 的尺寸 = (width_tiles * 8, height_tiles * 8) 像素
    """
    images = []
    tile_size = {1: 8, 4: 32, 6: 64, 8: 64}[bpp]
    pixels_per_byte = {1: 8, 4: 2, 8: 1}[bpp]
    sprite_w = width_tiles * 8
    sprite_h = height_tiles * 8
    tiles_per_sprite = width_tiles * height_tiles
    bytes_per_sprite = tiles_per_sprite * tile_size

    for i in range(count):
        offset = i * bytes_per_sprite
        if offset + bytes_per_sprite > len(data):
            break
        img = Image.new("RGBA", (sprite_w, sprite_h), (0, 0, 0, 0))
        tile_idx = 0
        for ty in range(0, sprite_h, 8):
            for tx in range(0, sprite_w, 8):
                tile_data = data[offset + tile_idx * tile_size:
                                 offset + (tile_idx + 1) * tile_size]
                if bpp == 4:
                    _decode_tile_4bpp(img, tile_data, tx, ty, palette)
                elif bpp == 8:
                    _decode_tile_8bpp(img, tile_data, tx, ty, palette)
                elif bpp == 1:
                    _decode_tile_1bpp(img, tile_data, tx, ty)
                tile_idx += 1
        images.append(img)
    return images


def _decode_tile_4bpp(img, tile_data, tx, ty, palette):
    for row in range(8):
        for col in range(0, 8, 2):
            b = tile_data[row * 4 + col // 2]
            px0 = b & 0xF
            px1 = (b >> 4) & 0xF
            if palette and px0 < len(palette):
                r, g, b_ = palette[px0]
                if px0 > 0 or (r, g, b_) != (0, 0, 0):
                    img.putpixel((tx + col, ty + row), (r, g, b_, 255 if px0 > 0 else 0))
            if palette and px1 < len(palette):
                r, g, b_ = palette[px1]
                if px1 > 0 or (r, g, b_) != (0, 0, 0):
                    img.putpixel((tx + col + 1, ty + row), (r, g, b_, 255 if px1 > 0 else 0))


def _decode_tile_8bpp(img, tile_data, tx, ty, palette):
    for row in range(8):
        for col in range(8):
            idx = tile_data[row * 8 + col]
            if palette and idx < len(palette) and idx > 0:
                r, g, b_ = palette[idx]
                img.putpixel((tx + col, ty + row), (r, g, b_, 255))


def _decode_tile_1bpp(img, tile_data, tx, ty):
    for row in range(8):
        b = tile_data[row]
        for col in range(8):
            if b & (0x80 >> col):
                img.putpixel((tx + col, ty + row), (255, 255, 255, 255))


def encode_tiles_4bpp(images: list[Image.Image], width_tiles: int,
                      height_tiles: int) -> bytes:
    """将 PNG 列表编码为 4bpp raw tile 数据。"""
    result = bytearray()
    for img in images:
        for ty in range(0, img.height, 8):
            for tx in range(0, img.width, 8):
                for row in range(8):
                    byte = 0
                    for col in range(0, 8, 2):
                        p0 = img.getpixel((tx + col, ty + row))
                        p1 = img.getpixel((tx + col + 1, ty + row))
                        idx0 = p0[3] > 0 if len(p0) == 4 else True
                        idx1 = p1[3] > 0 if len(p1) == 4 else True
                        byte = (idx1 << 4) | idx0
                        result.append(byte)
    return bytes(result)


def encode_tiles_4bpp_from_raw(images: list[Image.Image], width_tiles: int,
                               height_tiles: int, palette: list) -> bytes:
    """
    将 PNG 列表编码为 4bpp raw tile 数据，使用 palette 索引匹配。
    找不到匹配颜色时回退到最接近的颜色。
    """
    result = bytearray()
    for img in images:
        for ty in range(0, img.height, 8):
            for tx in range(0, img.width, 8):
                for row in range(8):
                    byte = 0
                    for col in range(0, 8, 2):
                        p0 = img.getpixel((tx + col, ty + row))
                        p1 = img.getpixel((tx + col + 1, ty + row))
                        idx0 = _find_nearest_color(p0[:3], palette) if p0[3] > 0 else 0
                        idx1 = _find_nearest_color(p1[:3], palette) if p1[3] > 0 else 0
                        byte = ((idx1 & 0xF) << 4) | (idx0 & 0xF)
                        result.append(byte)
    return bytes(result)


def _find_nearest_color(rgb, palette):
    best_idx = 0
    best_dist = float("inf")
    for i, (r, g, b) in enumerate(palette):
        dist = (rgb[0] - r) ** 2 + (rgb[1] - g) ** 2 + (rgb[2] - b) ** 2
        if dist < best_dist:
            best_dist = dist
            best_idx = i
            if dist == 0:
                break
    return best_idx


# ─────────────────────────────────────────────
# Palette 处理
# ─────────────────────────────────────────────

def decode_palette_gba555(data: bytes, bank_count: int = 3,
                          colors_per_bank: int = 16) -> list[list[tuple]]:
    """解码 GBA555 调色板。返回 bank 列表，每个 bank 是 RGB 元组列表。"""
    banks = []
    for b in range(bank_count):
        bank = []
        for c in range(colors_per_bank):
            offset = (b * colors_per_bank + c) * 2
            if offset + 2 > len(data):
                break
            val = struct.unpack("<H", data[offset:offset + 2])[0]
            r = (val & 0x1F) << 3
            g = ((val >> 5) & 0x1F) << 3
            b_ = ((val >> 10) & 0x1F) << 3
            bank.append((r, g, b_))
        banks.append(bank)
    return banks


def encode_palette_gba555(banks: list[list[tuple]]) -> bytes:
    """将 RGB 调色板编码为 GBA555 字节。"""
    result = bytearray()
    for bank in banks:
        for r, g, b in bank:
            val = ((r >> 3) & 0x1F) | (((g >> 3) & 0x1F) << 5) | (((b >> 3) & 0x1F) << 10)
            result.extend(struct.pack("<H", val))
    return bytes(result)


def palette_to_rgb_list(data: bytes, bank_count: int = 3,
                        colors_per_bank: int = 16) -> list[tuple]:
    """将 GBA555 调色板展平为单一 RGB 列表。"""
    banks = decode_palette_gba555(data, bank_count, colors_per_bank)
    flat = []
    for bank in banks:
        flat.extend(bank)
    return flat


def render_palette_image(palette: list[tuple], colors_per_row: int = 16,
                         cell_size: int = 16) -> Image.Image:
    """将调色板渲染为可视化 PNG。"""
    n = len(palette)
    if n == 0:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    rows = (n + colors_per_row - 1) // colors_per_row
    w = max(colors_per_row * cell_size, 1)
    h = max(rows * cell_size, 1)
    img = Image.new("RGB", (w, h), (128, 128, 128))
    for i, (r, g, b) in enumerate(palette):
        x = (i % colors_per_row) * cell_size
        y = (i // colors_per_row) * cell_size
        for dy in range(cell_size):
            for dx in range(cell_size):
                img.putpixel((x + dx, y + dy), (r, g, b))
    return img


# ─────────────────────────────────────────────
# ROM 工具
# ─────────────────────────────────────────────

def gba_address_to_offset(addr: int) -> int:
    """GBA 地址 → 文件偏移。如果 addr < 0x08000000，视为文件偏移直接返回。"""
    if addr < 0x08000000:
        return addr
    return addr - 0x08000000


def offset_to_gba_address(off: int) -> int:
    return off + 0x08000000


def _normalize_gba_addr(addr_str: str) -> int:
    """将用户输入的地址统一为 GBA 地址。文件偏移自动加 0x08000000。"""
    val = int(addr_str, 16)
    if val < 0x08000000:
        val += 0x08000000
    return val


def detect_lz77(rom: bytes, offset: int) -> str:
    """检测 LZ77 类型: 'lz77', 'lz77_swap', 或 'none'。"""
    if offset >= len(rom) or rom[offset] != 0x10:
        return "none"
    dst_size = rom[offset + 1] | (rom[offset + 2] << 8) | (rom[offset + 3] << 16)
    if dst_size == 0 or dst_size > 0x100000:
        return "none"

    for swap in [False, True]:
        try:
            result = lz77_decompress(rom[offset:offset + 0x100000], swap=swap)
            if len(result) == dst_size:
                return "lz77_swap" if swap else "lz77"
        except Exception:
            continue
    return "none"


def find_free_space(rom: bytearray, needed: int, start: int = 0x09000000,
                    fill: int = 0xFF) -> int:
    """
    在 ROM 中查找空闲空间。默认从扩展区开始。
    如果 start 超出 ROM 范围，返回 start（调用者负责扩展 ROM）。
    返回 GBA 地址，找不到返回 -1。
    """
    start_off = gba_address_to_offset(start) if start >= 0x08000000 else start
    if start_off >= len(rom):
        return start

    run_start = -1
    for i in range(start_off, len(rom)):
        if rom[i] == fill:
            if run_start == -1:
                run_start = i
            if i - run_start + 1 >= needed:
                return offset_to_gba_address(run_start)
        else:
            run_start = -1

    free_end = len(rom)
    free_needed = free_end - start_off
    if free_needed >= needed:
        return start
    return offset_to_gba_address(free_end)


def scan_pointer_sources(rom: bytes, target_offset: int,
                         max_scan: int = 0x100000) -> list[int]:
    """
    扫描 ROM 中所有指向 target_offset 的指针。
    返回 GBA 地址列表。
    """
    target_gba = offset_to_gba_address(target_offset)
    target_bytes = struct.pack("<I", target_gba)
    sources = []
    scan_end = min(len(rom), target_offset + max_scan)
    for i in range(0, scan_end - 3, 4):
        if rom[i:i + 4] == target_bytes:
            sources.append(offset_to_gba_address(i))
    return sources


def patch_pointer(rom: bytearray, ptr_offset: int, new_gba_addr: int):
    """覆写 ROM 中的指针值。"""
    rom[ptr_offset:ptr_offset + 4] = struct.pack("<I", new_gba_addr)


def _get_rom_id(rom_path: Path) -> str:
    """从 ROM 文件名提取 romId (去掉扩展名)。"""
    return rom_path.stem


def _get_export_dir(rom_path: Path) -> Path:
    """获取导出目录: works/{romId}/tiles"""
    rom_id = _get_rom_id(rom_path)
    script_dir = Path(__file__).parent
    return script_dir / "works" / rom_id / "tiles"


# ─────────────────────────────────────────────
# Probe (自动检测参数)
# ─────────────────────────────────────────────

_KNOWN_SPRITE_SIZES_4BPP = [
    (8, 8, 32), (16, 8, 64), (16, 16, 128),
    (32, 16, 256), (32, 32, 512), (64, 32, 1024), (64, 64, 2048),
]


def _parse_hex_string(hex_str: str) -> bytes:
    """解析 hex 字符串，支持空格、0x 前缀、换行。"""
    cleaned = hex_str.replace(" ", "").replace("\n", "").replace("\r", "")
    cleaned = cleaned.replace("0x", "").replace("0X", "")
    if len(cleaned) % 2 != 0:
        raise ValueError(f"Hex 字符串长度必须为偶数，当前: {len(cleaned)}")
    if len(cleaned) < 8:
        raise ValueError(f"Hex 字符串至少 8 个字符，当前: {len(cleaned)}")
    return bytes.fromhex(cleaned)


def _find_lz77_backwards(rom: bytes, target_offset: int,
                         max_search: int = 0x10000) -> list:
    """
    从 target_offset 向低地址搜索 LZ77 块。
    返回 [(offset, compressed_size, decompressed_size), ...]
    """
    results = []
    start = max(0, target_offset - max_search)

    for off in range(target_offset, start - 1, -1):
        if off < 0 or rom[off] != 0x10:
            continue
        # 检查 header 中的 size 是否合理
        if off + 4 > len(rom):
            continue
        dst_size = rom[off + 1] | (rom[off + 2] << 8) | (rom[off + 3] << 16)
        if dst_size == 0 or dst_size > 0x100000:
            continue

        # 尝试解压 (先 swap, 后 standard)
        for swap in [True, False]:
            try:
                dec = lz77_decompress(rom[off:], swap=swap)
                if dec and len(dec) == dst_size:
                    # 检查是否覆盖目标位置
                    if target_offset - off < len(dec):
                        comp_size = find_lz77_size(rom, off)
                        comp = "lz77_swap" if swap else "lz77"
                        results.append((off, comp_size, dst_size, comp))
                        break
            except Exception:
                continue

    return results


def _detect_bpp(data: bytes) -> int:
    """分析 nibble 分布判断 4bpp 或 8bpp。"""
    if len(data) < 32:
        return 4
    indices = set()
    for b in data[:256]:
        indices.add((b >> 4) & 0xF)
        indices.add(b & 0xF)
    if len(indices) > 8:
        return 8
    return 4


def _infer_sprite_size(decomp_size: int, bpp: int = 4):
    """根据解压大小推断 sprite 尺寸和数量。优先选数量在 1-50 的合理尺寸。"""
    candidates = []
    if bpp == 4:
        for w, h, bps in _KNOWN_SPRITE_SIZES_4BPP:
            if decomp_size % bps == 0:
                count = decomp_size // bps
                if 1 <= count <= 200:
                    candidates.append((w, h, count, bps))
    else:
        for w, h, bps in _KNOWN_SPRITE_SIZES_4BPP:
            bps_8bpp = bps * 2
            if decomp_size % bps_8bpp == 0:
                count = decomp_size // bps_8bpp
                if 1 <= count <= 200:
                    candidates.append((w, h, count, bps_8bpp))

    if not candidates:
        return 8, 8, max(1, decomp_size // 32)

    # 优先选数量在 1-50 的，且 sprite 尺寸较大的
    reasonable = [c for c in candidates if 1 <= c[2] <= 50]
    if reasonable:
        # 选 bytes_per_sprite 最大的 (即 sprite 尺寸最大的)
        best = max(reasonable, key=lambda x: x[3])
    else:
        # 回退: 选第一个
        best = candidates[0]

    return best[0], best[1], best[2]


def _is_valid_gba555(data: bytes) -> bool:
    """检查数据是否像 GBA555 调色板。"""
    if len(data) < 32 or len(data) % 2 != 0:
        return False
    for i in range(0, len(data), 2):
        val = data[i] | (data[i + 1] << 8)
        if val > 0x7FFF:
            return False
    return True


def _find_palette_near(rom: bytes, target_offset: int,
                       search_range: int = 0x20000) -> tuple:
    """搜索目标地址附近的 palette。返回 (offset, banks, compression)。"""
    pal_sizes = [96, 64, 32, 128, 160, 192]
    candidates = []
    start = max(0, target_offset - search_range)
    end = min(len(rom), target_offset + search_range)

    for off in range(start, end - 4):
        # 检查 LZ77 压缩的 palette
        if rom[off] == 0x10:
            dst_size = rom[off + 1] | (rom[off + 2] << 8) | (rom[off + 3] << 16)
            if dst_size in pal_sizes:
                for swap in [False, True]:
                    try:
                        dec = lz77_decompress(rom[off:], swap=swap)
                        if dec and len(dec) == dst_size and _is_valid_gba555(dec):
                            comp = "lz77_swap" if swap else "lz77"
                            candidates.append((off, dst_size, comp))
                            break
                    except Exception:
                        continue
        # 检查未压缩的 palette (直接 GBA555 数据)
        elif off + 32 <= end:
            chunk = rom[off:off + 96] if off + 96 <= len(rom) else rom[off:]
            if len(chunk) >= 32 and _is_valid_gba555(chunk):
                # 检查是否像 palette (第一个颜色通常是 0x0000)
                if chunk[0] == 0 and chunk[1] == 0:
                    candidates.append((off, len(chunk) // 2, "none"))

    if not candidates:
        return None, 0, None

    # 优先级: 96 bytes (3 banks) > 64 > 32 > 其他, 同 size 按距离排序
    def palette_priority(item):
        size = item[1]
        dist = abs(item[0] - target_offset)
        if size == 96:
            return (0, dist)
        elif size == 64:
            return (1, dist)
        elif size == 32:
            return (2, dist)
        else:
            return (3 - size // 100, dist)

    candidates.sort(key=palette_priority)
    best = candidates[0]
    return best[0], best[1] // 32, best[2]


# LZ77 解压缓存: {offset: (decompressed_bytes, swap)}
_lz77_cache: dict = {}


def probe_data(rom: bytes, search_data: bytes) -> list:
    """
    用二进制数据在 ROM 中搜索，返回所有匹配的分析结果。
    支持直接匹配和在 LZ77 解压数据中搜索子串。
    使用缓存避免重复解压。
    """
    matches = []

    # 1. 先尝试直接搜索
    for i in range(len(rom) - len(search_data) + 1):
        if rom[i:i + len(search_data)] == search_data:
            matches.append((i, None, None))  # (offset, decomp_data, sub_offset)

    # 2. 如果直接搜索没找到，在 LZ77 解压数据中搜索
    if not matches and len(search_data) >= 16:
        print("直接搜索未找到，在 LZ77 解压数据中搜索...")
        # 优化: 只扫描对齐的 LZ77 块 (4字节对齐)，且跳过太小的块
        min_dst = len(search_data)
        count = 0
        for off in range(0, len(rom) - 4, 4):  # 4字节对齐
            if rom[off] != 0x10:
                continue
            dst_size = rom[off + 1] | (rom[off + 2] << 8) | (rom[off + 3] << 16)
            if dst_size < min_dst or dst_size > 0x80000:
                continue
            # 尝试解压 (先查缓存)
            for swap in [False, True]:
                cache_key = (off, swap)
                if cache_key in _lz77_cache:
                    dec = _lz77_cache[cache_key]
                else:
                    try:
                        dec = lz77_decompress(rom[off:], swap=swap)
                        if dec and len(dec) == dst_size:
                            _lz77_cache[cache_key] = dec
                        else:
                            dec = None
                    except Exception:
                        dec = None
                if dec and len(dec) == dst_size:
                    # 搜索完整数据
                    sub_idx = dec.find(search_data)
                    if sub_idx >= 0:
                        matches.append((off, dec, sub_idx))
                        count += 1
                        if count >= 3:
                            break
                    else:
                        # 找第一个非零字节作为搜索起点
                        sig_start = 0
                        for k in range(len(search_data)):
                            if search_data[k] != 0:
                                sig_start = k
                                break
                        # 搜索签名部分 (跳过前导零)
                        sig_len = min(256, len(search_data) - sig_start)
                        if sig_len >= 16:
                            sig = search_data[sig_start:sig_start + sig_len]
                            sub_idx = dec.find(sig)
                            if sub_idx >= 0:
                                matches.append((off, dec, sub_idx - sig_start))
                                count += 1
                                if count >= 3:
                                    break
            if count >= 3:
                break
        if count == 0:
            print(f"  (扫描了 {len(range(0, len(rom) - 4, 4))} 个对齐位置)")

    # 3. 分析每个匹配
    results = []
    for match_offset, decomp_data, sub_offset in matches:
        if decomp_data is not None:
            # 在 LZ77 解压数据中找到的匹配
            data_offset = match_offset
            swap = True  # Ruby JP 使用 lz77_swap
            comp_size = find_lz77_size(rom, data_offset)
            decomp_size = len(decomp_data)

            bpp = _detect_bpp(decomp_data)
            w, h, count = _infer_sprite_size(decomp_size, bpp)
            pal_off, pal_banks, pal_comp = _find_palette_near(rom, data_offset)
            ptrs = scan_pointer_sources(rom, data_offset)

            results.append({
                "match_offset": match_offset,
                "match_in_decomp": sub_offset,
                "data_offset": data_offset,
                "address": offset_to_gba_address(data_offset),
                "compression": "lz77_swap",
                "compressed_size": comp_size,
                "decompressed_size": decomp_size,
                "bpp": bpp,
                "sprite_width": w,
                "sprite_height": h,
                "sprite_count": count,
                "palette_addr": offset_to_gba_address(pal_off) if pal_off else None,
                "palette_banks": pal_banks,
                "palette_compression": pal_comp,
                "pointer_sources": ptrs,
            })
        else:
            # 直接在 ROM 中找到的匹配
            lz77_blocks = _find_lz77_backwards(rom, match_offset)

            if lz77_blocks:
                best = min(lz77_blocks, key=lambda x: abs(x[0] - match_offset))
                data_offset, comp_size, decomp_size, compression = best
                swap = compression == "lz77_swap"
                decomp = lz77_decompress(rom[data_offset:], swap=swap)

                bpp = _detect_bpp(decomp)
                w, h, count = _infer_sprite_size(decomp_size, bpp)
                pal_off, pal_banks, pal_comp = _find_palette_near(rom, data_offset)
                ptrs = scan_pointer_sources(rom, data_offset)

                results.append({
                    "match_offset": match_offset,
                    "match_in_decomp": None,
                    "data_offset": data_offset,
                    "address": offset_to_gba_address(data_offset),
                    "compression": compression,
                    "compressed_size": comp_size,
                    "decompressed_size": decomp_size,
                    "bpp": bpp,
                    "sprite_width": w,
                    "sprite_height": h,
                    "sprite_count": count,
                    "palette_addr": offset_to_gba_address(pal_off) if pal_off else None,
                    "palette_banks": pal_banks,
                    "palette_compression": pal_comp,
                    "pointer_sources": ptrs,
                })
            else:
                results.append({
                    "match_offset": match_offset,
                    "match_in_decomp": None,
                    "data_offset": match_offset,
                    "address": offset_to_gba_address(match_offset),
                    "compression": "none",
                    "compressed_size": 0,
                    "decompressed_size": 0,
                    "bpp": 4,
                    "sprite_width": 0,
                    "sprite_height": 0,
                    "sprite_count": 0,
                    "palette_addr": None,
                    "palette_banks": 0,
                    "palette_compression": None,
                    "pointer_sources": [],
                })

    return results


# ─────────────────────────────────────────────
# Export 命令
# ─────────────────────────────────────────────

def cmd_export(args):
    rom_path = Path(args.rom)
    rom = rom_path.read_bytes()
    addr = _normalize_gba_addr(args.address) if isinstance(args.address, str) else args.address
    offset = gba_address_to_offset(addr)
    bpp = int(args.format.replace("bpp", "")) if "bpp" in args.format else 0

    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = _get_export_dir(rom_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    meta_dir = output_dir / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    prefix = f"0x{addr:08X}"

    # ── 检测/设置压缩 ──
    compression = args.compression
    if compression == "auto":
        compression = detect_lz77(rom, offset)
        print(f"自动检测压缩: {compression}")

    # ── 解压 ──
    raw_data = None
    if compression == "lz77" or compression == "lz77_swap":
        swap = compression == "lz77_swap"
        raw_data = lz77_decompress(rom[offset:], swap=swap)
        print(f"解压: {len(raw_data)} bytes")
    elif compression == "none":
        size = int(args.raw_size) if args.raw_size else 0
        if size > 0:
            raw_data = rom[offset:offset + size]
        else:
            raw_data = rom[offset:offset + 0x10000]
            print("警告: 未指定 --raw-size，读取前 64KB")

    if raw_data is None:
        print("错误: 无法读取数据")
        sys.exit(1)

    # ── 加载调色板 ──
    palette_flat = None
    palette_banks = None
    palette_path = None
    if args.palette:
        pal_addr = _normalize_gba_addr(args.palette) if isinstance(args.palette, str) else args.palette
        pal_offset = gba_address_to_offset(pal_addr)
        # 检测 palette 是否压缩
        pal_comp = detect_lz77(rom, pal_offset)
        if pal_comp in ("lz77", "lz77_swap"):
            pal_swap = pal_comp == "lz77_swap"
            pal_data = lz77_decompress(rom[pal_offset:], swap=pal_swap)
            print(f"调色板解压: {len(pal_data)} bytes ({pal_comp})")
        else:
            pal_data = rom[pal_offset:pal_offset + 96]
        palette_banks = decode_palette_gba555(pal_data, bank_count=3)
        palette_flat = palette_to_rgb_list(pal_data, bank_count=3)
        # 保存调色板可视化
        palette_path = meta_dir / f"{prefix}_palette.png"
        pal_img = render_palette_image(palette_flat)
        pal_img.save(palette_path)
        print(f"调色板: {palette_path}")
    elif bpp in (4, 8):
        print("警告: 未指定调色板 (--palette)，使用默认灰度调色板")
        # 生成默认灰度调色板
        palette_flat = [(i * 17, i * 17, i * 17) for i in range(16)]
        palette_banks = [palette_flat[:16]]

    # ── 解析 sprite 参数 ──
    sprite_w, sprite_h = [int(x) for x in args.sprite_size.split("x")]
    tile_w, tile_h = sprite_w // 8, sprite_h // 8
    count = int(args.count)
    tiles_per_sprite = tile_w * tile_h

    # ── 切分 sprite 并保存 ──
    images = decode_tiles(raw_data, bpp, tile_w, tile_h,
                          count=count, palette=palette_flat)
    for i, img in enumerate(images):
        png_path = output_dir / f"{prefix}_{i:02d}.png"
        img.save(png_path)

    print(f"导出 {count} 个 sprite → {output_dir}")

    # ── 扫描指针源 ──
    pointer_sources = []
    if args.pointers:
        for ptr_str in args.pointers:
            ptr_addr = _normalize_gba_addr(ptr_str) if isinstance(ptr_str, str) else ptr_str
            ptr_off = gba_address_to_offset(ptr_addr)
            # 读取该指针当前值
            if ptr_off + 4 <= len(rom):
                current_val = struct.unpack("<I", rom[ptr_off:ptr_off + 4])[0]
                pointer_sources.append({
                    "address": f"0x{ptr_addr:08X}",
                    "current_value": f"0x{current_val:08X}",
                    "label": "",
                })
    elif not args.no_scan:
        # 自动扫描
        pointer_sources_addrs = scan_pointer_sources(rom, offset)
        for ptr_addr in pointer_sources_addrs:
            pointer_sources.append({
                "address": f"0x{ptr_addr:08X}",
                "label": "",
            })
        if pointer_sources:
            print(f"自动扫描到 {len(pointer_sources)} 个指针源")

    # ── 生成 meta.json ──
    meta = {
        "name": args.name or prefix,
        "rom_address": f"0x{addr:08X}",
        "format": args.format,
        "compression": compression,
        "raw_size": len(raw_data),
        "sprite_size_px": [sprite_w, sprite_h],
        "sprite_count": count,
        "tile_size_px": [8, 8],
        "tiles_per_sprite": tiles_per_sprite,
        "tile_order": "row_major",
        "palette": {
            "rom_address": f"0x{_normalize_gba_addr(args.palette):08X}" if args.palette else None,
            "format": "gbapal555",
            "bank_count": 3,
            "colors_per_bank": 16,
        } if args.palette else None,
        "pointer_sources": pointer_sources,
        "sprites": [
            {"index": i, "file": f"{prefix}_{i:02d}.png"}
            for i in range(count)
        ],
    }

    meta_path = meta_dir / f"{prefix}_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    print(f"元数据: {meta_path}")


# ─────────────────────────────────────────────
# Import 命令
# ─────────────────────────────────────────────

def cmd_import(args):
    tiles_dir = Path(args.tiles_dir)
    rom_path = Path(args.rom)
    rom = bytearray(rom_path.read_bytes())
    output_path = Path(args.output) if args.output else rom_path.with_name(
        rom_path.stem + "_patched" + rom_path.suffix)

    # 扫描所有 meta.json (优先 tiles/meta/，回退 tiles/)
    meta_search_dir = tiles_dir / "meta" if (tiles_dir / "meta").is_dir() else tiles_dir
    meta_files = sorted(meta_search_dir.glob("*_meta.json"))
    if not meta_files:
        print(f"错误: {meta_search_dir} 下未找到 *_meta.json")
        sys.exit(1)

    print(f"找到 {len(meta_files)} 个元数据文件")

    for meta_path in meta_files:
        meta = json.loads(meta_path.read_text())
        prefix = meta["rom_address"]
        addr = int(meta["rom_address"], 16)
        offset = gba_address_to_offset(addr)
        bpp = int(meta["format"].replace("bpp", "")) if "bpp" in meta["format"] else 0
        sprite_w, sprite_h = meta["sprite_size_px"]
        count = meta["sprite_count"]
        tile_w, tile_h = sprite_w // 8, sprite_h // 8

        print(f"\n处理 {prefix} ({meta['format']}, {count} sprites)")

        # ── 加载调色板 ──
        palette_flat = None
        palette_banks = None
        if meta.get("palette") and meta["palette"].get("rom_address"):
            pal_addr = int(meta["palette"]["rom_address"], 16)
            pal_offset = gba_address_to_offset(pal_addr)
            pal_comp = detect_lz77(rom, pal_offset)
            if pal_comp in ("lz77", "lz77_swap"):
                pal_swap = pal_comp == "lz77_swap"
                pal_data = lz77_decompress(bytes(rom[pal_offset:]), swap=pal_swap)
            else:
                pal_data = bytes(rom[pal_offset:pal_offset + 96])
            palette_flat = palette_to_rgb_list(pal_data, bank_count=3)
            palette_banks = decode_palette_gba555(pal_data, bank_count=3)

        # ── 读取所有 sprite ──
        all_raw = bytearray()
        for i in range(count):
            # 优先读 .raw，没有则读 .png
            raw_file = tiles_dir / f"{prefix}_{i:02d}.raw"
            png_file = tiles_dir / f"{prefix}_{i:02d}.png"

            if raw_file.exists():
                sprite_data = raw_file.read_bytes()
                all_raw.extend(sprite_data)
            elif png_file.exists():
                img = Image.open(png_file).convert("RGBA")
                if bpp == 4:
                    sprite_data = encode_tiles_4bpp_from_raw(
                        [img], tile_w, tile_h, palette_flat or [])
                else:
                    sprite_data = encode_tiles_4bpp([img], tile_w, tile_h)
                all_raw.extend(sprite_data)
            else:
                print(f"警告: 找不到 {prefix}_{i:02d}.raw 或 .png，跳过")
                continue

        print(f"读取 {count} 个 sprite，共 {len(all_raw)} bytes")

        # ── LZ77 压缩 ──
        compression = meta["compression"]
        if compression == "lz77" or compression == "lz77_swap":
            swap = compression == "lz77_swap"
            compressed = lz77_compress(bytes(all_raw), swap=swap)
            print(f"压缩: {len(all_raw)} → {len(compressed)} bytes")
        elif compression == "none":
            compressed = bytes(all_raw)
        else:
            print(f"错误: 未知压缩格式 '{compression}'")
            sys.exit(1)

        # ── 检查原数据大小 ──
        original_compressed_size = meta["raw_size"]
        if rom[offset] == 0x10:
            # 从 LZ77 header 读取原始压缩大小
            original_compressed_size = find_lz77_size(rom, offset)
        else:
            original_compressed_size = meta["raw_size"]

        # ── 写入新数据 ──
        if len(compressed) <= original_compressed_size:
            # 新数据比原来小（或相同），原地写入
            write_offset = offset
            # 如果比原来小，用 00 填充剩余
            rom[write_offset:write_offset + len(compressed)] = compressed
            if len(compressed) < original_compressed_size:
                rom[write_offset + len(compressed):
                     write_offset + original_compressed_size] = \
                    b"\x00" * (original_compressed_size - len(compressed))
            print(f"原地写入: offset=0x{write_offset:08X}")
        else:
            # 新数据更大，需要找空闲区
            free_addr = find_free_space(rom, len(compressed))
            if free_addr < 0:
                print("错误: 未找到足够空闲空间")
                sys.exit(1)
            free_offset = gba_address_to_offset(free_addr)
            # 扩展 ROM 以容纳新数据
            needed_end = free_offset + len(compressed)
            if needed_end > len(rom):
                rom.extend(b"\x00" * (needed_end - len(rom)))
            rom[free_offset:free_offset + len(compressed)] = compressed
            write_offset = free_offset
            print(f"新数据写入空闲区: 0x{free_addr:08X} ({len(compressed)} bytes)")

            # ── 更新所有指针 ──
            for ptr_info in meta.get("pointer_sources", []):
                ptr_addr = int(ptr_info["address"], 16)
                ptr_off = gba_address_to_offset(ptr_addr)
                patch_pointer(rom, ptr_off, free_addr)
                print(f"  指针更新: 0x{ptr_addr:08X} → 0x{free_addr:08X}")

    # ── 保存 ──
    output_path.write_bytes(rom)
    print(f"\n输出: {output_path} ({len(rom)} bytes)")


# ─────────────────────────────────────────────
# Probe 命令
# ─────────────────────────────────────────────

def cmd_probe(args):
    rom_path = Path(args.rom)
    rom = rom_path.read_bytes()

    # 读取搜索数据: --bin, --hex, 或 --hex-file
    if args.bin:
        bin_path = Path(args.bin)
        if not bin_path.exists():
            print(f"错误: 文件不存在 {bin_path}")
            sys.exit(1)
        search_data = bin_path.read_bytes()
        print(f"搜索 bin: {bin_path.name} ({len(search_data)} bytes)")
    elif args.hex:
        search_data = _parse_hex_string(args.hex)
        print(f"搜索 hex: {args.hex[:40]}{'...' if len(args.hex) > 40 else ''}")
    elif args.hex_file:
        hex_file = Path(args.hex_file)
        if not hex_file.exists():
            print(f"错误: 文件不存在 {hex_file}")
            sys.exit(1)
        hex_str = hex_file.read_text().replace("\n", "").replace("\r", "").replace(" ", "")
        search_data = _parse_hex_string(hex_str)
        print(f"搜索 hex-file: {hex_file.name} ({len(search_data)} bytes)")
    else:
        print("错误: 需要 --bin, --hex, 或 --hex-file 参数")
        sys.exit(1)

    print(f"ROM 大小: {len(rom)} bytes\n")

    results = probe_data(rom, search_data)

    if not results:
        print("未找到匹配!")
        sys.exit(1)

    print(f"找到 {len(results)} 个匹配\n")

    for i, result in enumerate(results):
        match_offset = result["match_offset"]
        data_offset = result["data_offset"]
        compression = result["compression"]
        comp_size = result["compressed_size"]
        decomp_size = result["decompressed_size"]
        bpp = result["bpp"]
        w = result["sprite_width"]
        h = result["sprite_height"]
        count = result["sprite_count"]
        pal_off = result["palette_addr"]
        pal_banks = result["palette_banks"]
        pal_comp = result["palette_compression"]
        ptrs = result["pointer_sources"]
        match_in_decomp = result.get("match_in_decomp")

        # 使用手动指定的调色板覆盖自动检测结果
        if args.palette:
            pal_off = _normalize_gba_addr(args.palette)
            pal_banks = 3
            pal_comp = "manual"

        print(f"{'=' * 50}")
        print(f"[{i + 1}] 文件偏移: 0x{match_offset:06X}")
        print(f"{'=' * 50}")
        print(f"数据位置: 0x{data_offset:06X} (GBA 0x{offset_to_gba_address(data_offset):08X})")
        if match_in_decomp is not None:
            print(f"匹配位置: 解压数据偏移 +0x{match_in_decomp:X}")
        print(f"压缩: {compression} ({comp_size} → {decomp_size} bytes)")
        print(f"格式: {bpp}bpp")
        print(f"Sprite: {w}x{h} × {count}")
        if pal_off:
            print(f"调色板: 0x{pal_off:08X} ({pal_banks} banks, {pal_comp})")
        else:
            print(f"调色板: 未找到! (需要手动指定 --palette)")
        if ptrs:
            ptr_str = ", ".join(f"0x{p:08X}" for p in ptrs)
            print(f"指针源: {ptr_str}")

        # 生成建议命令
        addr_hex = f"0x{offset_to_gba_address(data_offset):08X}"
        cmd = (
            f"python row_patcher.py export {rom_path} {addr_hex} "
            f"--format {bpp}bpp --sprite-size {w}x{h} --count {count} "
            f"--compression {compression}"
        )
        if pal_off:
            cmd += f" --palette 0x{pal_off:08X}"
        if ptrs:
            ptr_args = " ".join(f"0x{p:08X}" for p in ptrs)
            cmd += f" --pointers {ptr_args}"
        print(f"\n建议命令:\n  {cmd}")

        print()


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="GBA ROM 图形导出导入工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 导出 type icons (输出到 works/{romId}/tiles/)
  python row_patcher.py export rom.gba 0x087EE9C8 \\
    --format 4bpp --sprite-size 32x16 --count 23 \\
    --compression lz77_swap --palette 0x087EF450

  # 导入修改后的 sprite
  python row_patcher.py import rom.gba tiles/ -o output.gba

  # 用 hex 字符串搜索并自动检测参数
  python row_patcher.py probe rom.gba --hex "000000009099999989888888"
        """,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── export ──
    p_export = sub.add_parser("export", help="导出 ROM 图形为 PNG")
    p_export.add_argument("rom", help="ROM 文件路径")
    p_export.add_argument("address", help="数据起始 GBA 地址 (如 0x087EE9C8)")
    p_export.add_argument("--format", default="4bpp",
                          choices=["1bpp", "4bpp", "8bpp", "palette", "tilemap", "raw"],
                          help="数据格式 (默认: 4bpp)")
    p_export.add_argument("--sprite-size", default="8x8",
                          help="单个 sprite 像素尺寸 (如 32x16)")
    p_export.add_argument("--count", type=int, default=1, help="sprite 数量")
    p_export.add_argument("--compression", default="auto",
                          choices=["none", "lz77", "lz77_swap", "auto"],
                          help="压缩格式 (默认: auto)")
    p_export.add_argument("--raw-size", help="原始数据大小 (bytes, 仅 none 压缩时使用)")
    p_export.add_argument("--palette", help="调色板 GBA 地址")
    p_export.add_argument("--pointers", nargs="*", help="指针源 GBA 地址列表")
    p_export.add_argument("--no-scan", action="store_true",
                          help="禁用自动指针扫描")
    p_export.add_argument("--name", help="数据名称 (默认用地址)")
    p_export.add_argument("-o", "--output", help="输出目录 (默认: works/{romId}/tiles)")

    # ── import ──
    p_import = sub.add_parser("import", help="将 PNG 导入回 ROM")
    p_import.add_argument("rom", help="ROM 文件路径")
    p_import.add_argument("tiles_dir", help="tiles 目录路径")
    p_import.add_argument("-o", "--output", help="输出 ROM 路径 (默认: xxx_patched.gba)")

    # ── probe ──
    p_probe = sub.add_parser("probe", help="在 ROM 中搜索数据并自动检测参数")
    p_probe.add_argument("rom", help="ROM 文件路径")
    p_probe.add_argument("--bin", help="mgba 导出的 .bin 文件路径")
    p_probe.add_argument("--hex", help="要搜索的 hex 字符串 (支持空格分隔)")
    p_probe.add_argument("--hex-file", help="包含 hex 字符串的文件路径")
    p_probe.add_argument("--palette", help="手动指定调色板 GBA 地址")

    args = parser.parse_args()

    if args.command == "export":
        cmd_export(args)
    elif args.command == "import":
        cmd_import(args)
    elif args.command == "probe":
        cmd_probe(args)


if __name__ == "__main__":
    main()
