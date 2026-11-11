#!/usr/bin/env python3
"""gba_ppu.py — 离线重放 GBA PPU（用 bot 采集的运行时快照渲染 240x160）

## 这个文件解决什么问题

`tiles_patcher.py` 的导出是**静态**的：从 ROM 里 LZ77 解压出 tile 数据，
再套一个**人猜的**调色板 + **人猜的**拼合方式（yaml 里的 `palette` /
`bank_list` / `compose`）。猜错就导出一堆配色错误、拼合错位的图
（`docs/TILES_CANDIDATES_AXVJ.md` 已经记录过：横幅那条 pal 就是错的）。

bot 采集的 `NNN.{vram,pal,oam,io}.bin` 是**同一帧的真实硬件状态**。
用这套快照按 GBA 硬件规则重放 PPU，得到的就是**屏幕上真实渲染的那一帧**。
这是把「导出图和 bot 实际渲染一致」从口号变成可验证事实的唯一办法：
重放结果与 bot 存的 `NNN.png` 逐像素比对，一致率达标才算成立。

## 硬件规则（mode 0/1/2 文本 BG + OBJ）

| 寄存器 | 位域 |
|---|---|
| DISPCNT | 0-2 mode / 4 页 / 5 OAM 1D / 6 OBJ 直通 / 7 force-blank / 8-11 BG0-3 on / 12 OBJ on / 13-15 WIN0,WIN1,OBJWIN on |
| BGxCNT | 0-1 pri / 2-3 charBase / 6 mosaic / 7 8bpp / 8-12 screenBase / 13 wrap / 14-15 size |
| tilemap entry | 0-9 tile / 10 hflip / 11 vflip / 12-15 palbank(4bpp) |
| OAM attr0 | 0-7 y / 8-9 rot-scale / 10-11 (objmode in 12-13) / 12-13 mode / 14 mosaic / 15 8bpp |
| OAM attr1 | 0-8 x / 12-13 flip / 14-15 size |
| OAM attr2 | 0-9 tile / 10-11 pri / 12-15 palbank |

## ⚠ 只写寄存器的硬限制（实测，不是猜测）

GBA 的 `BGxHOFS/BGxVOFS(0x10-0x1F)`、`WIN0H/WIN0V/WIN1H/WIN1V(0x40-0x47)`、
`MOSAIC(0x4C)`、`BLDCNT/BLDALPHA/BLDY(0x50-0x55)` **全部是只写寄存器**，
总线读回来是 open bus。实测 `work/POKEMON_RUBY_AXVJ00/bot/bag/.../001.io.bin`：

    0x04000010..0x04000046 全是 0x1C10（垃圾）
    0x0400004C MOSAIC      0x1C10（Pokemon 从不用马赛克，必是垃圾）
    0x04000054 BLDY        0x1C10（同上）
    0x04000006 VCOUNT      0x00CF=207（>159，也在屏幕外）

所以离线重放**拿不到**卷动/窗口边界/混合参数。本模块的对策：

  · 卷动默认 0，可用 `scroll` 参数显式覆盖（UI/菜单/战斗/对话场景卷动就是 0）
  · 窗口边界默认全屏（即「窗口不裁剪」），可用 `wins` 覆盖
  · 混合默认关闭，可用 `blend` 覆盖
  · 渲染结果带 `trace` 说明本次用了哪些假设 ⇒ 一致率不达标时能立刻看出
    是哪个假设错了，而不是瞎猜

## 用法

    from util.gba_ppu import Snapshot, render
    snap = Snapshot.load(side_dir, "001")
    img = render(snap)            # -> ndarray(H,W,3) uint8
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

SCREEN_W, SCREEN_H = 240, 160


# ─────────────────────────────────────────────────────────────
# 快照
# ─────────────────────────────────────────────────────────────

@dataclass
class Snapshot:
    """bot 采集的单帧硬件状态。"""

    vram: bytes                      # 0x06000000 + 0x18000 (96KB，BG 64K + OBJ 32K)
    pal: bytes                       # 0x05000000 + 0x400 (512 色 CGRAM)
    oam: bytes                       # 0x07000000 + 0x400 (128 项 × 8B)
    io: bytes                        # 0x04000000 + 0x60
    name: str = ""

    @classmethod
    def load(cls, side_dir, number) -> "Snapshot":
        d = Path(side_dir)
        n = str(number)
        return cls(
            vram=(d / f"{n}.vram.bin").read_bytes(),
            pal=(d / f"{n}.pal.bin").read_bytes(),
            oam=(d / f"{n}.oam.bin").read_bytes(),
            io=(d / f"{n}.io.bin").read_bytes(),
            name=n,
        )

    # -- 寄存器读（IO 区 0x00-0x0F 可信，之后不可信）------------------
    def io16(self, off: int) -> int:
        return struct.unpack_from("<H", self.io, off)[0]

    @property
    def dispcnt(self) -> int:
        return self.io16(0x00)

    def bgcnt(self, bg: int) -> int:
        return self.io16(0x08 + bg * 2)

    @property
    def mode(self) -> int:
        return self.dispcnt & 0x07

    @property
    def obj_1d(self) -> bool:
        """OBJ 图块映射是否 1D。

        ⚠ 是 **bit6**，不是 bit5。GBATEK 的 DISPCNT：
          bit5 = HBlank Interval Free（与 tile 映射无关）
          bit6 = OBJ Character Mapping (0=2D, 1=1D)
        实测 `0x1740`（背包界面）bit6=1 ⇒ 1D；按 bit5 判断会误判成 2D，
        结果 64x64 的背包精灵整块错位（diff 5.34% 全部集中在这一块）。
        """
        return bool(self.dispcnt & 0x40)

    @property
    def force_blank(self) -> bool:
        return bool(self.dispcnt & 0x80)

    def bg_on(self, bg: int) -> bool:
        return bool(self.dispcnt & (0x100 << bg))

    @property
    def obj_on(self) -> bool:
        return bool(self.dispcnt & 0x1000)

    def bg_palette(self, bank: int = 0) -> np.ndarray:
        """CGRAM 里某个 16 色 bank 的 RGB（4bpp BG 用 bank0）。"""
        return cgram_to_rgb(self.pal, bank * 16, 16)

    def obj_palette(self, bank: int) -> np.ndarray:
        return cgram_to_rgb(self.pal, 0x100 + bank * 16, 16)


def cgram_to_rgb(pal: bytes, first_color: int, count: int) -> np.ndarray:
    """GBA555 → RGB888。

    mGBA 的 5→8 位扩展是 `(v << 3) | (v >> 2)`（0x1F → 0xFF），
    不是 tiles_patcher 用的纯 `v << 3`（0x1F → 0xF8）。差 7 会导致
    「看起来对但像素不等」，比对一致率时会被判成不一致。
    """
    out = np.zeros((count, 3), dtype=np.uint8)
    for i in range(count):
        v = struct.unpack_from("<H", pal, (first_color + i) * 2)[0]
        r = v & 0x1F
        g = (v >> 5) & 0x1F
        b = (v >> 10) & 0x1F
        out[i] = ((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2))
    return out


# ─────────────────────────────────────────────────────────────
# tile 解码
# ─────────────────────────────────────────────────────────────

def decode_tile_4bpp(data: bytes, off: int) -> np.ndarray:
    """8x8 4bpp → (8,8) uint8 索引（0-15）。"""
    out = np.empty((8, 8), dtype=np.uint8)
    base = off
    for y in range(8):
        for x in range(0, 8, 2):
            b = data[base + y * 4 + x // 2]
            out[y, x] = b & 0xF
            out[y, x + 1] = (b >> 4) & 0xF
    return out


def decode_tile_8bpp(data: bytes, off: int) -> np.ndarray:
    """8x8 8bpp → (8,8) uint8 索引（0-255）。"""
    return np.frombuffer(data, dtype=np.uint8, count=64, offset=off).reshape(8, 8).copy()


# ─────────────────────────────────────────────────────────────
# BG 文本层
# ─────────────────────────────────────────────────────────────

_TEXT_SIZES = {0: (256, 256), 1: (512, 256), 2: (256, 512), 3: (512, 512)}


def bg_text_layer(snap: Snapshot, bg: int,
                  scroll=(0, 0)) -> tuple[np.ndarray, np.ndarray]:
    """渲染 mode 0/1 的文本 BG 层。

    返回 (rgb(H,W,3), mask(H,W)) —— mask=True 表示该像素是透明色 0
    （BG 层透出下层，不是黑色）。
    """
    cnt = snap.bgcnt(bg)
    char_base = 0x0000 + ((cnt >> 2) & 3) * 0x4000
    screen_base = 0x0000 + ((cnt >> 8) & 0x1F) * 0x800
    bpp8 = bool(cnt & 0x80)
    size = (cnt >> 14) & 3
    mw, mh = _TEXT_SIZES[size]
    palbank0 = snap.bg_palette(0)
    full_pal = cgram_to_rgb(snap.pal, 0, 256)

    hx, vy = scroll
    img = np.zeros((SCREEN_H, SCREEN_W, 3), dtype=np.uint8)
    mask = np.ones((SCREEN_H, SCREEN_W), dtype=bool)

    # 屏幕像素 → map 内坐标（卷动 0 时就是本身）
    xs = (np.arange(SCREEN_W) + hx) % mw
    ys = (np.arange(SCREEN_H) + vy) % mh
    gx, gy = np.meshgrid(xs, ys)

    # 256x256 一个 map 块，每块 32x32 项；512 宽的 map 由 2 个块横向拼
    blk_x = gx // 256
    blk_y = gy // 256
    in_x = gx % 256
    in_y = gy % 256
    entry_off = (screen_base
                 + blk_x * 0x800
                 + blk_y * (0x800 if mw > 256 else 0)
                 + (in_y // 8) * 64
                 + (in_x // 8) * 2)

    # 逐像素取 tile 项（向量化 gather）
    entries = np.frombuffer(snap.vram, dtype="<u2", count=len(snap.vram) // 2)
    e = entries[entry_off // 2]
    tile_no = (e & 0x3FF).astype(np.int32)
    hflip = ((e >> 10) & 1).astype(bool)
    vflip = ((e >> 11) & 1).astype(bool)
    palbank = ((e >> 12) & 0xF).astype(np.int32)

    px = in_x % 8
    py = in_y % 8
    px = np.where(hflip, 7 - px, px)
    py = np.where(vflip, 7 - py, py)

    if bpp8:
        stride = 64
        off = char_base + tile_no * stride
        flat = np.frombuffer(snap.vram, dtype=np.uint8)
        idx = flat[off + py * 8 + px]
        rgb = full_pal[idx]
    else:
        stride = 32
        off = char_base + tile_no * stride
        flat = np.frombuffer(snap.vram, dtype=np.uint8)
        # 4bpp: 每字节 2 像素，低半 = 偶数列
        byte = flat[off + py * 4 + px // 2]
        idx = np.where(px % 2 == 0, byte & 0xF, (byte >> 4) & 0xF).astype(np.uint8)
        # ★ 4bpp 的调色板 bank 来自 tilemap entry 的 bit12-15，
        #   不是固定 bank0。漏掉这步会让整层颜色全错（实测 BG0 命中率 0%）。
        rgb = full_pal[idx + palbank * 16]

    img[:] = rgb
    mask = idx == 0
    return img, mask


# ─────────────────────────────────────────────────────────────
# OBJ 层
# ─────────────────────────────────────────────────────────────

_OBJ_SIZES = {0: (1, 1), 1: (2, 1), 2: (1, 2), 3: (2, 2)}   # 单位 8px


def _obj_dim(shape: int, size: int) -> tuple[int, int]:
    """OAM shape(0-2) × size(0-3) → (w_tiles, h_tiles)。"""
    table = {
        0: [(1, 1), (2, 2), (4, 4), (8, 8)],     # square
        1: [(2, 1), (4, 1), (4, 2), (8, 4)],     # horizontal
        2: [(1, 2), (1, 4), (2, 4), (4, 8)],     # vertical
    }
    return table[shape][size]


def _obj_tile_step(one_d: bool, bpp8: bool, wt: int, ty: int, tx: int) -> int:
    """计算 sprite 内第 (tx,ty) 个 8x8 块相对 tile_no 的偏移。

    ★ 实测结论（2026-11-11，标题画面 7 个 OBJ 逐块反查）：
      OAM 的 tile 号字段对 8bpp 来说**已经是槽位号**（一个 8bpp tile 占
      两个 32B 槽，tile 号就是那个 32B 槽的序号），所以 1D 映射下
      步长恒为 1，**不要**因为 8bpp 就 ×2。
      实测：步长 1 → 标题 logo 45.3%；步长 2 → 掉到 0.6%。

      2D 映射：每行固定 32 个槽位（与 bpp 无关）。
    """
    if one_d:
        return ty * wt + tx
    return ty * 32 + tx


@dataclass
class ObjSprite:
    """一个已解出的 OBJ，带它在屏幕上的位置与像素。"""

    index: int
    x: int
    y: int
    w: int
    h: int
    priority: int
    palbank: int
    hflip: bool
    vflip: bool
    bpp8: bool
    tile_no: int
    rgb: np.ndarray                  # (h,w,3)
    mask: np.ndarray                 # (h,w) True=透明
    affine: bool = False
    mode: int = 0                    # 0 正常 / 1 半透明 / 2 obj window
    mosaic: bool = False


def parse_oam(snap: Snapshot) -> list[ObjSprite]:
    """解析 OAM 里所有启用的 OBJ，从 VRAM OBJ 区切出像素并上色。

    这是「导出精灵图和屏幕一致」的关键：tile 号 + 调色板 bank + 翻转
    **全部来自运行时 OAM**，不是人猜的。
    """
    out: list[ObjSprite] = []
    obj_vram_base = 0x10000                 # VRAM 内 OBJ 区起点 0x06010000
    flat = np.frombuffer(snap.vram, dtype=np.uint8)

    for i in range(128):
        a0, a1, a2 = struct.unpack_from("<HHH", snap.oam, i * 8)
        # attr0 bit8 = rot/scale 使能；bit9 在非仿射模式下是 disable，
        # 在仿射模式下是 double-size。别混。
        affine = bool(a0 & 0x100)
        if not affine and (a0 & 0x200):
            continue                        # 非仿射 + disable ⇒ 不显示
        shape = (a0 >> 14) & 3
        if shape == 3:
            continue                        # shape=3 禁止
        size = (a1 >> 14) & 3
        wt, ht = _obj_dim(shape, size)
        w, h = wt * 8, ht * 8

        bpp8 = bool(a0 & 0x2000)
        mode = (a0 >> 10) & 3
        if mode == 3:
            continue
        mosaic = bool(a0 & 0x1000)

        # 坐标：X/Y 是 9 位有符号（-256..255）
        x = a1 & 0x1FF
        if x >= 256:
            x -= 512
        y = a0 & 0xFF
        if y >= 160:
            y -= 256

        # 完全在屏幕外 ⇒ 硬件不画（OAM 里 128 项通常只有个位数可见）
        if x >= SCREEN_W or y >= SCREEN_H or x + w <= 0 or y + h <= 0:
            continue

        tile_no = a2 & 0x3FF
        pri = (a2 >> 10) & 3
        palbank = (a2 >> 12) & 0xF

        hflip = bool(a1 & 0x1000) and not affine
        vflip = bool(a1 & 0x2000) and not affine

        # 切像素
        rgb = np.zeros((h, w, 3), dtype=np.uint8)
        mask = np.ones((h, w), dtype=bool)
        if bpp8:
            pal = cgram_to_rgb(snap.pal, 0x100, 256)
            for ty in range(ht):
                for tx in range(wt):
                    tno = tile_no + _obj_tile_step(snap.obj_1d, bpp8, wt, ty, tx)
                    off = obj_vram_base + (tno & 0x3FF) * 64
                    if off + 64 > len(flat):
                        continue
                    t = flat[off:off + 64].reshape(8, 8)
                    sub = rgb[ty * 8:(ty + 1) * 8, tx * 8:(tx + 1) * 8]
                    m = mask[ty * 8:(ty + 1) * 8, tx * 8:(tx + 1) * 8]
                    sub[:] = pal[t]
                    m[:] = t == 0
        else:
            pal = cgram_to_rgb(snap.pal, 0x100 + palbank * 16, 16)
            for ty in range(ht):
                for tx in range(wt):
                    tno = tile_no + _obj_tile_step(snap.obj_1d, bpp8, wt, ty, tx)
                    off = obj_vram_base + (tno & 0x3FF) * 32
                    if off + 32 > len(flat):
                        continue
                    t = decode_tile_4bpp(flat, off)
                    sub = rgb[ty * 8:(ty + 1) * 8, tx * 8:(tx + 1) * 8]
                    m = mask[ty * 8:(ty + 1) * 8, tx * 8:(tx + 1) * 8]
                    sub[:] = pal[t]
                    m[:] = t == 0

        if hflip:
            rgb = rgb[:, ::-1]
            mask = mask[:, ::-1]
        if vflip:
            rgb = rgb[::-1]
            mask = mask[::-1]

        out.append(ObjSprite(
            index=i, x=x, y=y, w=w, h=h, priority=pri, palbank=palbank,
            hflip=hflip, vflip=vflip, bpp8=bpp8, tile_no=tile_no,
            rgb=rgb, mask=mask, affine=affine, mode=mode, mosaic=mosaic,
        ))
    return out


# ─────────────────────────────────────────────────────────────
# 合成
# ─────────────────────────────────────────────────────────────

@dataclass
class RenderTrace:
    """本次重放用了哪些假设 —— 一致率不达标时用来定位。"""

    mode: int = 0
    bg_layers: list = field(default_factory=list)
    obj_count: int = 0
    assumptions: list = field(default_factory=list)

    def __str__(self) -> str:
        s = [f"mode={self.mode}",
             f"BG={self.bg_layers}",
             f"OBJ={self.obj_count}"]
        if self.assumptions:
            s.append("假设: " + "; ".join(self.assumptions))
        return " | ".join(s)


@dataclass
class BlendSpec:
    """亮度衰减 / 混合参数（BLDCNT/BLDALPHA/BLDY 全部只写不可读，必须外部给）。

    GBA 硬件规则（GBATEK）：
      亮度衰减（mode 1 且 BLDY 控制）：out = c - c*evy/16   （变暗）
                                      out = c + (31-c)*evy/16 （变亮，EVY 高位）
      alpha 混合（mode 1 且 BLDALPHA）：out = (c1*eva + c2*evb) / 16

    实测（title_menu 主菜单帧）：EVY=9 ⇒ ref/canvas 中位数 0.5643 ≈ 9/16，
    说明菜单界面用「亮度衰减 9/16」把 BG0 压暗，而 WIN0 内的菜单条不衰减。
    """

    evy: int = 0                    # 0-16，亮度衰减强度
    evy_up: bool = False            # True = 变亮
    eva: int = 0                    # alpha 混合系数（第一目标）
    evb: int = 0                    # alpha 混合系数（第二目标）
    alpha: bool = False             # True = 走 alpha 混合而不是亮度衰减
    outside_window_only: bool = True  # 只对窗口外生效（Pokemon 的常规用法）

    def apply(self, canvas: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """对 mask=True 的像素做混合/衰减。"""
        out = canvas.copy()
        sel = mask
        if not sel.any():
            return out
        c = out[sel].astype(np.int16)
        if self.alpha and (self.eva or self.evb):
            # 单目标 alpha：与黑色混合 = 乘 eva/16
            k = self.eva / 16.0
            out[sel] = np.clip(np.round(c * k), 0, 255).astype(np.uint8)
            return out
        if self.evy == 0:
            return out
        e = self.evy / 16.0
        if self.evy_up:
            out[sel] = np.clip(np.round(c + (255 - c) * e), 0, 255).astype(np.uint8)
        else:
            out[sel] = np.clip(np.round(c - c * e), 0, 255).astype(np.uint8)
        return out


def render(snap: Snapshot, *, scroll=None, backdrop=None,
           blend: Optional[BlendSpec] = None,
           window: Optional[tuple] = None,
           trace: Optional[RenderTrace] = None) -> np.ndarray:
    """按快照重放 240x160 帧。

    scroll: {bg: (hx, vy)}，缺省全 0（只写寄存器读不到，见模块 docstring）
    blend:  BlendSpec，缺省不衰减（BLD 只写不可读，必须外部给）
    window: WIN0 矩形 (x0, y0, x1, y1)，缺省 None = 无窗口（全屏都算窗口外）
    """
    tr = trace if trace is not None else RenderTrace()
    tr.mode = snap.mode
    if snap.force_blank:
        tr.assumptions.append("force-blank ⇒ 全白")
        return np.full((SCREEN_H, SCREEN_W, 3), 255, dtype=np.uint8)

    scroll = scroll or {}
    tr.assumptions.append("BGxHOFS/VOFS 只写不可读 ⇒ 默认 0")
    tr.assumptions.append("窗口边界不可读 ⇒ 按全屏（不裁剪）")
    tr.assumptions.append("BLDCNT/BLDALPHA/BLDY 不可读 ⇒ 关闭混合")

    # 背景色（CGRAM 0）
    bd = cgram_to_rgb(snap.pal, 0, 1)[0]
    canvas = np.zeros((SCREEN_H, SCREEN_W, 3), dtype=np.uint8)
    canvas[:] = bd

    # ── BG 层：按优先级合成（数字小 = 靠前）──
    layers = []
    for bg in range(4):
        if not snap.bg_on(bg):
            continue
        cnt = snap.bgcnt(bg)
        pri = cnt & 3
        if snap.mode in (0, 1) and (bg < 2 or snap.mode == 0):
            img, mask = bg_text_layer(snap, bg, scroll.get(bg, (0, 0)))
            layers.append((pri, bg, img, mask))
            tr.bg_layers.append(f"BG{bg}(text,pri{pri})")
        else:
            # mode 1 的 BG2 / mode 2 的 BG2-3 是仿射层；需要 PA/PB/PC/PD，
            # 同样只写不可读。此处标记未实现，交给上层决定。
            tr.bg_layers.append(f"BG{bg}(affine,未实现)")
            tr.assumptions.append(f"BG{bg} 仿射层未实现")

    # ── OBJ ──
    objs = parse_oam(snap) if snap.obj_on else []
    tr.obj_count = len(objs)
    if objs:
        tr.assumptions.append("OBJ 半透明/objwindow 未做混合（按正常绘制）")

    # 合成顺序：所有 BG 与 OBJ 一起按 priority 从低到高画（4 最高/最靠后）
    items = []
    for pri, bg, img, mask in layers:
        items.append((pri, 0, bg, img, mask))         # 0=BG 先于同 pri 的 OBJ
    for o in objs:
        items.append((o.priority, 1, o.index, o.rgb, o.mask))
    items.sort(key=lambda t: (-t[0], t[1]))

    for _pri, kind, _idx, img, mask in items:
        if kind == 0:
            canvas[~mask] = img[~mask]
        else:
            o = next(x for x in objs if x.index == _idx)
            _blit_obj(canvas, o)

    # ── 亮度衰减 / alpha 混合 ──
    if blend is not None and (blend.evy or blend.alpha):
        if blend.outside_window_only and window is not None:
            x0, y0, x1, y1 = window
            sel = np.ones((SCREEN_H, SCREEN_W), dtype=bool)
            sel[max(0, y0):max(0, y1), max(0, x0):max(0, x1)] = False
        else:
            sel = np.ones((SCREEN_H, SCREEN_W), dtype=bool)
        canvas = blend.apply(canvas, sel)
        tr.assumptions.append(
            f"BLD 手动: evy={blend.evy} alpha={blend.alpha} "
            f"win={window}")

    return canvas


def _blit_obj(canvas: np.ndarray, o: ObjSprite) -> None:
    """把 OBJ 贴到画布，处理出屏裁剪。"""
    x0, y0 = o.x, o.y
    sx0, sy0 = max(0, -x0), max(0, -y0)
    dx0, dy0 = max(0, x0), max(0, y0)
    w = min(o.w - sx0, SCREEN_W - dx0)
    h = min(o.h - sy0, SCREEN_H - dy0)
    if w <= 0 or h <= 0:
        return
    sub_rgb = o.rgb[sy0:sy0 + h, sx0:sx0 + w]
    sub_mask = o.mask[sy0:sy0 + h, sx0:sx0 + w]
    region = canvas[dy0:dy0 + h, dx0:dx0 + w]
    region[~sub_mask] = sub_rgb[~sub_mask]


# ─────────────────────────────────────────────────────────────
# 校验：重放 vs bot 截图
# ─────────────────────────────────────────────────────────────

def compare(img: np.ndarray, png_path) -> dict:
    """逐像素比对重放结果与 bot 截图的 PNG。

    返回 {"total", "match", "ratio", "max_diff"}。
    """
    from PIL import Image

    ref = np.asarray(Image.open(png_path).convert("RGB"))
    if ref.shape != img.shape:
        return {"total": 0, "match": 0, "ratio": 0.0, "max_diff": -1,
                "error": f"尺寸不符: {ref.shape} vs {img.shape}"}
    diff = np.abs(ref.astype(np.int16) - img.astype(np.int16))
    per_px = diff.max(axis=2)
    match = int((per_px == 0).sum())
    total = per_px.size
    return {
        "total": total,
        "match": match,
        "ratio": match / total if total else 0.0,
        "max_diff": int(per_px.max()),
    }
