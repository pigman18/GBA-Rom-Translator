#!/usr/bin/env python3
"""bot/verify.py — 字形级截图对比验收（2026-10-17 重写）

═══════════════════════════════════════════════════════════════════════════════
用户口径（逐条对应）
───────────────────────────────────────────────────────────────────────────────
  4) 对比截图：translated 相对 origin 已汉化 + **无撞 UI** + **无乱码** ⇒ 场景通过
  5) **像素级**：origin 中像素内不存在字形、而 translated 存在 ⇒ 判【乱码】拒绝
     并要求「精确到每个词每个像素」

═══════════════════════════════════════════════════════════════════════════════
为什么要重写（旧判据错在哪）
───────────────────────────────────────────────────────────────────────────────
旧实现 `garble_pixels()` 数的是「孤立墨点**个数**」，阈值 60。两个方向都不可靠：
  · 一个 12×12 的乱码字形会产生上百个墨点 ⇒ 任何一处乱码都直接爆阈值；
  · 一整片**正常**译文若笔画稀疏，也会被计入 ⇒ 假阳性。
它判的是**点数**，不是**字形**。

═══════════════════════════════════════════════════════════════════════════════
新判据：连通块 + 字形解剖
───────────────────────────────────────────────────────────────────────────────
把 translated 里「origin 没有墨」的像素聚成**连通块**，逐块判它的身份：

  ① 块的形状与密度
     · 汉字格：宽高比接近 1:1（或 1:2 全角），面积填充率落在人写字的合理区间
     · 碎片：面积过小、或退化成「宽≤2 且高≥6」的竖条残片（旧 ROM 的典型病灶）
     · 溢出：块越出它所在文字行的上下界（撞窗口边框）

  ② 块是否压在 origin 的 UI 上  ← 用户口径的「撞 UI」
     取 origin 在该块 bbox 内的墨迹，若占比高 ⇒ 译文盖到了原本的图形/边框

  ③ ★ 硬证据：块内是否出现 origin 全局都不存在的颜色
     这是「origin 像素内不存在字体而 translated 存在」最直接的机械判据 ——
     若某色在 origin 整幅图里一次都没出现过，却出现在 translated 的新增块里，
     说明该块是用**原版没有的墨色**画上去的，高度可疑（自造字形/调色板越界）。

  ④ 块与 origin 原有墨迹的接壤
     新增块若与 origin 已有墨迹**紧贴**（膨胀一圈内有交集），是正常的换字；
     若完全悬空于背景中且形状畸形，则更可能是乱码。

输出：per-frame verdict（pass / suspect / fail）+ 块级证据清单，
      并把每个可疑块的 bbox 与类别写进 verdict.json，供人眼直接定位。

退出码：pass=0、suspect=2、fail=1
═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

try:
    import numpy as np
    from PIL import Image
except ImportError as e:                                   # pragma: no cover
    print(f"[ERR] 需要 numpy + Pillow: {e}")
    raise SystemExit(3)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
# 基础：读图 / 背景 / 墨迹
# ═══════════════════════════════════════════════════════════════════════════

INK_THR = 90          # 离背景多远算「有墨」


def load_rgb(p: Path):
    """读 PNG 为 ndarray(H,W,3)。失败返回 None。"""
    if not p.is_file():
        return None
    try:
        with Image.open(p) as im:
            return np.asarray(im.convert("RGB")).astype(np.int32)
    except Exception:
        return None


def bg_color(arr: np.ndarray) -> np.ndarray:
    """背景色 = 量化后最高频的那个桶的真实均值。

    量化到 8 级再做众数，避免渐变/抖动把众数打散。
    """
    flat = arr.reshape(-1, 3)
    q = (flat // 32).astype(np.int32)
    key = q[:, 0] * 64 + q[:, 1] * 8 + q[:, 2]
    vals, counts = np.unique(key, return_counts=True)
    k = vals[counts.argmax()]
    return flat[key == k].mean(axis=0)


def ink_mask(arr: np.ndarray, bg: np.ndarray, thr: int = INK_THR) -> np.ndarray:
    """离背景足够远 ⇒ 有墨。返回 bool 数组。"""
    d = np.abs(arr - bg.astype(np.int32)).sum(axis=2)
    return d > thr


# ═══════════════════════════════════════════════════════════════════════════
# 连通块（8 邻域，逐字形级粒度）
# ═══════════════════════════════════════════════════════════════════════════

def components(mask: np.ndarray, min_px: int = 1):
    """BFS 求连通块。返回 [(size, y0, x0, y1, x1), ...] 按面积降序。

    用 8 邻域而不是 4 邻域：汉字的撇捺点常有对角相接，
    4 邻域会把一个完整的字拆成好几块，导致「碎片」误判。
    """
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out = []
    ys, xs = np.nonzero(mask)
    for sy, sx in zip(ys.tolist(), xs.tolist()):
        if seen[sy, sx]:
            continue
        stack = [(sy, sx)]
        seen[sy, sx] = True
        n = 0
        y0 = y1 = sy
        x0 = x1 = sx
        while stack:
            y, x = stack.pop()
            n += 1
            if y < y0: y0 = y
            if y > y1: y1 = y
            if x < x0: x0 = x
            if x > x1: x1 = x
            for dy in (-1, 0, 1):
                ny = y + dy
                if ny < 0 or ny >= h:
                    continue
                for dx in (-1, 0, 1):
                    if dy == 0 and dx == 0:
                        continue
                    nx = x + dx
                    if 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        if n >= min_px:
            out.append((n, y0, x0, y1, x1))
    out.sort(key=lambda t: -t[0])
    return out


def dilate(mask: np.ndarray, r: int = 1) -> np.ndarray:
    """形态学膨胀 r 圈（用于判断「新增块是否与原有墨迹接壤」）。"""
    out = mask.copy()
    for _ in range(r):
        shifted = out.copy()
        shifted[1:, :] |= out[:-1, :]
        shifted[:-1, :] |= out[1:, :]
        shifted[:, 1:] |= out[:, :-1]
        shifted[:, :-1] |= out[:, 1:]
        out = shifted
    return out


# ═══════════════════════════════════════════════════════════════════════════
# ★ 字形判据
# ═══════════════════════════════════════════════════════════════════════════

# 分类阈值（GBA 汉字格通常 12×12，假名格 8×8）
MIN_GLYPH_PX    = 8      # 小于此面积 ⇒ 碎片
TINY_PX         = 4      # 极小碎片
SLIVER_W        = 2      # 「竖条残片」宽阈值
SLIVER_H        = 6      # 「竖条残片」高阈值
FILL_MIN        = 0.06   # 字形填充率下限（太稀 = 散点）
FILL_MAX        = 0.92   # 填充率上限（太满 = 实心方块，不是字）

# ★ 块尺寸上限：单个字符格最大约 16×16（12px 汉字 + 阴影，留余量）。
#   超过这个尺寸的「新增连通块」不可能是字形 —— 它是**区域性的颜色差异**
#   （背景渐变、整块重绘、阴影过渡色不同），必须单独归类为 area，
#   绝不能拿它去触发「乱码」判据。
#   实测教训：options 场景曾有一个 bbox=[24,40,216,152]（193×113、304px）的块
#   被判成 new_color 乱码，其实只是整片背景的过渡色差异。
MAX_GLYPH_W     = 20
MAX_GLYPH_H     = 20

# 碎片必须**远离**任何真实字形块才算碎片；紧贴字形的是笔画边缘抗锯齿，
# 属于正常现象（实测 options 的 166 个「碎片」绝大多数就是这类）。
EDGE_ATTACH_R   = 2


def classify_block(blk, added: np.ndarray, o_ink: np.ndarray,
                   t_arr: np.ndarray, o_colors: set,
                   near_glyph: bool = False):
    """判定单个新增连通块的类别与证据。

    返回 (kind, notes)
      kind ∈ {"area", "glyph", "fragment", "sliver", "collision", "new_color"}
      判定顺序（宽 → 严）：
        0. 尺寸超限 ⇒ area（区域色差，不是字形，从这里就出局）
        1. 含 origin 全局不存在的颜色 ⇒ new_color（用户口径的硬乱码证据）
        2. bbox 内 origin 墨迹占比高 ⇒ collision（撞 UI）
        3. 宽≤2 高≥6 ⇒ sliver（竖条残片）
        4. 面积/填充率异常，**且不紧贴真实字形** ⇒ fragment
        5. 其余 ⇒ glyph
    """
    n, y0, x0, y1, x1 = blk
    bw = x1 - x0 + 1
    bh = y1 - y0 + 1
    bbox_px = bw * bh
    fill = n / float(bbox_px) if bbox_px else 0.0
    notes = []

    # ⓪ 尺寸超限 ⇒ 区域色差，不是字形。必须先判，否则整片背景差异会
    #    被当成乱码（实测踩过：193×113 的块触发 new_color 判 fail）。
    if bw > MAX_GLYPH_W or bh > MAX_GLYPH_H:
        notes.append(f"{bw}×{bh} 超出单字格上限（{MAX_GLYPH_W}×{MAX_GLYPH_H}），"
                     f"属区域色差")
        return "area", notes

    # ① ★ 硬证据：块内出现 origin 全局都没有的颜色
    block_colors = {tuple(c) for c in t_arr[y0:y1 + 1, x0:x1 + 1][
        added[y0:y1 + 1, x0:x1 + 1]].reshape(-1, 3).tolist()}
    novel = block_colors - o_colors
    if novel:
        notes.append("含 origin 全局不存在的颜色 "
                     + ",".join("#%02X%02X%02X" % c for c in sorted(novel)[:3]))
        return "new_color", notes

    # ② 撞 UI：块 bbox 内 origin 的墨迹占比高 ⇒ 译文压到了原有图形
    o_in_box = o_ink[y0:y1 + 1, x0:x1 + 1]
    o_ratio = o_in_box.sum() / float(bbox_px) if bbox_px else 0.0
    if o_ratio > 0.30:
        notes.append("bbox 内 origin 墨迹占比 %.0f%%" % (o_ratio * 100))
        return "collision", notes

    # ③ 竖条残片（旧 ROM 的典型病灶：字形边缘粘成窄条）
    if bw <= SLIVER_W and bh >= SLIVER_H:
        notes.append("宽%d×高%d 竖条残片" % (bw, bh))
        return "sliver", notes

    # ④ 碎片：太小，或填充率异常。
    #    ⚠⚠ 两个必须豁免的情形（都是实测踩坑后加的）：
    #      a) 紧贴真实字形块 ⇒ 笔画边缘的抗锯齿过渡像素，正常换字产物
    #      b) **纯直线段**（宽==1 或 高==1）⇒ 汉字的横画/竖画本身就只占
    #         1 像素宽。换字时旧笔画被替换、新笔画超出的部分，就会留下
    #         1×3、4×1、5×1 这样的规整细条。实测 options 的 109 个"碎片"
    #         清一色是这类（(1,1)×53、(2,1)×16、(1,2)×7、(1,3)×6、(4,1)×5…），
    #         全部是真笔画，不是乱码。
    #      真乱码碎片是「既小又不规则」的：2×2 散点、锯齿块、斑驳噪点。
    straight = (bw == 1 or bh == 1)
    bad = None
    if n < TINY_PX:
        bad = "面积仅 %d 像素" % n
    elif n < MIN_GLYPH_PX and fill < FILL_MIN:
        bad = "面积 %d、填充率 %.2f 过低" % (n, fill)
    elif fill > FILL_MAX and not straight:
        bad = "填充率 %.2f 过高（实心块，非字形）" % fill
    elif fill < FILL_MIN:
        bad = "填充率 %.2f 过低（散点）" % fill
    if bad is not None:
        if near_glyph or straight:
            notes.append(bad + ("；紧贴字形块" if near_glyph else "；为直线笔画段")
                         + "，判为正常笔画")
            return "stroke", notes
        notes.append(bad)
        return "fragment", notes

    return "glyph", notes


def glyph_analysis(o_arr, t_arr):
    """字形级分析主函数。

    ★ 关键修正（2026-10-17 实测踩坑）：
       不能只用「离背景远」来定义墨迹。汉化后文字变成另一种同样远离背景的
       颜色，两侧都会被判成「有墨」⇒ added=0，而相似度却只有 0.96，
       自相矛盾（selfcheck/menu_open 实测就是 added=0 但 4% 像素不同）。

       用户口径「origin 中像素内不存在字形而 translated 存在」的正确机械表述是：
         **translated 有墨、且该像素在 origin 里既没有墨、颜色也不相同**
       即：先按各自背景判墨，再要求 origin 该处「非墨」才计入新增。
       这样「同位置换了另一种墨色」会被正确识别为新增字形块，而不是被吞掉。
    """
    bg = bg_color(o_arr)
    o_ink = ink_mask(o_arr, bg)
    t_ink = ink_mask(t_arr, bg)

    # 逐像素颜色差异（任意通道差 > 24 视为不同）
    diff_mask = (np.abs(o_arr - t_arr).max(axis=2) > 24)

    # ★ 新增 = translated 有墨 & origin 该处非墨
    added = t_ink & ~o_ink
    # 丢失 = origin 有墨 & translated 该处非墨
    removed = o_ink & ~t_ink
    # 换字 = 两边都有墨但颜色变了（正常汉化的主要成分）
    retext = o_ink & t_ink & diff_mask

    # origin 里全局出现过的颜色（用于「原版没有的墨色」硬判据）
    o_colors = {tuple(c) for c in
                o_arr.reshape(-1, 3)[::3].tolist()}      # 采样加速

    blocks = components(added, min_px=1)

    # ★ 先跑一遍「粗判」圈出**真实字形块**（形状合理、尺寸在单字格内），
    #   再用它的膨胀图判定其它候选块是否只是笔画边缘（抗锯齿过渡像素）。
    #   这一步是必需的：实测 options 的 166 个「碎片」里绝大多数只是
    #   汉字笔画的边缘过渡色，不是乱码。
    glyph_mask = np.zeros(added.shape, dtype=bool)
    for blk in blocks:
        n, y0, x0, y1, x1 = blk
        bw, bh = x1 - x0 + 1, y1 - y0 + 1
        if bw > MAX_GLYPH_W or bh > MAX_GLYPH_H:
            continue
        if n < MIN_GLYPH_PX:
            continue
        glyph_mask[y0:y1 + 1, x0:x1 + 1] = True
    glyph_dil = dilate(glyph_mask, EDGE_ATTACH_R)

    o_ink_dil = dilate(o_ink, 1)

    kinds = Counter()
    items = []
    for blk in blocks:
        n, y0, x0, y1, x1 = blk
        near = bool(glyph_dil[y0:y1 + 1, x0:x1 + 1].any())
        kind, notes = classify_block(blk, added, o_ink, t_arr, o_colors, near)
        touch = bool(o_ink_dil[y0:y1 + 1, x0:x1 + 1].any())
        kinds[kind] += 1
        # 只有真正可疑的类别进清单；glyph / stroke / edge 都是正常的
        if kind not in ("glyph", "stroke", "edge"):
            items.append({
                "kind": kind,
                "bbox": [int(x0), int(y0), int(x1), int(y1)],
                "px": int(n),
                "touches_origin_ink": touch,
                "notes": notes,
            })
    items.sort(key=lambda x: (-x["px"]))

    return {
        "bg": "#%02X%02X%02X" % tuple(int(v) for v in bg),
        "changed_px": int(diff_mask.sum()),
        "added_px": int(added.sum()),
        "removed_px": int(removed.sum()),
        "retext_px": int(retext.sum()),
        "origin_ink_px": int(o_ink.sum()),
        "added_blocks": len(blocks),
        "kinds": dict(kinds),
        "suspicious": items,
        "suspicious_count": len(items),
    }


# ═══════════════════════════════════════════════════════════════════════════
# 单帧判定
# ═══════════════════════════════════════════════════════════════════════════

def similarity(o_arr, t_arr) -> float:
    return 1.0 - float((o_arr != t_arr).any(axis=2).sum()) / float(o_arr.shape[0] * o_arr.shape[1])


# ═══════════════════════════════════════════════════════════════════════════
# 硬判据：全黑 / 软复位 / 崩溃（2026-11-05 新增）
#
# 为什么必须单独判：旧判据只有「相似度 + 字形解剖」，一条整帧全黑的截图
# 会因为「没有新增块」而落到 suspect（"两侧像素完全相同，看不出汉化"），
# 被淹没在几十条同类噪声里。实测 pokemon_menu 第 50/51 帧整帧全黑
# （均值 < 8，仅 192 字节），在旧判据下只是两条 suspect —— 这正是用户
# 「随便一跑都是空白和模拟器闪退」却没人拦下来的原因。
# ═══════════════════════════════════════════════════════════════════════════

BLACK_MEAN   = 8      # 整帧平均亮度低于此值 ⇒ 全黑
BLACK_COLORS = 2      # 唯一色数 ≤ 此值 ⇒ 无内容（纯色帧）


def is_blank_frame(arr) -> tuple[bool, str]:
    """判定整帧是否为空（全黑 / 纯色）。

    返回 (是否空, 证据说明)。空帧在汉化验收里没有任何意义，
    必须直接 fail —— 它代表崩溃、软复位或渲染完全失效。
    """
    if arr is None:
        return True, "缺图"
    mean = float(arr.mean())
    flat = arr.reshape(-1, 3)
    ncolors = len(np.unique(flat[::7], axis=0))      # 采样加速
    if mean < BLACK_MEAN:
        return True, f"整帧全黑（均值 {mean:.1f} < {BLACK_MEAN}）"
    if ncolors <= BLACK_COLORS:
        return True, f"整帧纯色（唯一色 {ncolors} ≤ {BLACK_COLORS}）"
    return False, ""


def verdict_pair(o_png: Path, t_png: Path, *, scene_step: str = "") -> dict:
    """单帧判定。返回 {verdict, confidence, reasons, notes, metrics}。"""
    reasons = []
    notes_ok = []          # 正向证据，不参与 verdict 计算
    o = load_rgb(o_png)
    t = load_rgb(t_png)
    if o is None or t is None:
        return {"verdict": "fail", "confidence": 0.0,
                "reasons": [{"dim": "input", "level": "fail",
                             "msg": "缺少截图（origin 或 translated）"}],
                "metrics": {}}
    if o.shape != t.shape:
        return {"verdict": "fail", "confidence": 0.0,
                "reasons": [{"dim": "input", "level": "fail",
                             "msg": f"尺寸不一致 {o.shape} vs {t.shape}"}],
                "metrics": {}}

    sim = similarity(o, t)
    ga = glyph_analysis(o, t)
    metrics = {"scene_similarity": round(sim, 6), **ga}
    k = ga["kinds"]

    # ⓪ ★ 硬判据：整帧空白（全黑 / 纯色）
    #    必须先于所有其它判据 —— 空白帧没有字形可分析，
    #    后面的「无新增块 ⇒ suspect」会把它误降级成可疑。
    o_blank, o_why = is_blank_frame(o)
    t_blank, t_why = is_blank_frame(t)
    metrics["origin_blank"] = o_blank
    metrics["translated_blank"] = t_blank
    if t_blank and not o_blank:
        reasons.append({"dim": "g_black", "level": "fail",
                        "msg": f"translated {t_why}，origin 正常 ⇒ 渲染失效/崩溃/软复位"})
        return {"verdict": "fail", "confidence": 0.95, "reasons": reasons,
                "notes": notes_ok, "metrics": metrics}
    if t_blank and o_blank:
        # 两侧都空 ⇒ 这一帧本就没有画面内容，不能作为验收依据
        reasons.append({"dim": "g_black", "level": "suspect",
                        "msg": f"两侧均空白（{t_why}），本帧无画面可比"})
        return {"verdict": "suspect", "confidence": 0.55, "reasons": reasons,
                "notes": notes_ok, "metrics": metrics}

    # ① 两侧画面差异过大 ⇒ 不是同一画面（用户契约第 4 条的前提）
    #    ⚠ 阈值不能定太高：汉化本来就会重写整片文字区，
    #     实测设置界面（大量文字）相似度天然只有 0.77，属正常幅度。
    #     只有掉到 0.50 以下才说明结构不同（真的是两个画面）。
    if sim < 0.50:
        reasons.append({"dim": "s_scene", "level": "fail",
                        "msg": f"两侧画面差异过大（{sim:.3f} < 0.50），非同一场景"})
    elif sim < 0.35:
        reasons.append({"dim": "s_scene", "level": "suspect",
                        "msg": f"两侧画面差异异常大（{sim:.3f}）"})

    # ② ★ 乱码：用了 origin 全局不存在的墨色 ⇒ 直接 fail
    #    area（区域色差）已在 classify_block 里被排除，不参与此判据。
    if k.get("new_color"):
        reasons.append({"dim": "g_garble", "level": "fail",
                        "msg": f"{k['new_color']} 个字形块使用了 origin 全局不存在的颜色"
                               f"（自造字形/调色板越界），判【乱码】拒绝验收"})

    # ③ 竖条残片（旧 ROM 典型病灶）
    if k.get("sliver", 0) > 3:
        reasons.append({"dim": "g_garble", "level": "fail",
                        "msg": f"{k['sliver']} 处竖条残片（宽≤{SLIVER_W} 高≥{SLIVER_H}）"})
    elif k.get("sliver", 0) > 0:
        reasons.append({"dim": "g_garble", "level": "suspect",
                        "msg": f"{k['sliver']} 处竖条残片"})

    # ④ 碎片
    if k.get("fragment", 0) > 12:
        reasons.append({"dim": "g_garble", "level": "fail",
                        "msg": f"{k['fragment']} 个字形碎片（面积/填充率异常）"})
    elif k.get("fragment", 0) > 4:
        reasons.append({"dim": "g_garble", "level": "suspect",
                        "msg": f"{k['fragment']} 个字形碎片"})

    # ⑤ 撞 UI（用户口径第 4 条）
    #    中文换掉日文时新增块常与 origin 旧墨接壤；有明显换字量时降为 suspect。
    retext_px = int(ga.get("retext_px") or 0)
    text_delta = int(ga["added_px"]) + int(ga["removed_px"]) + retext_px
    collide_n = int(k.get("collision", 0) or 0)
    if collide_n > 2 and text_delta < 400:
        reasons.append({"dim": "g_collide", "level": "fail",
                        "msg": f"{collide_n} 个新增块压在 origin 已有图形上（撞 UI）"})
    elif collide_n > 0:
        msg = f"{collide_n} 个新增块与 origin 图形重叠"
        if text_delta >= 400:
            msg += f"（本帧换字约 {text_delta}px，降为提示）"
        reasons.append({"dim": "g_collide", "level": "suspect", "msg": msg})

    # ⑥ 汉化是否真的生效（用户契约的核心正向判据）
    #    origin 有明显墨迹却 0 像素变化 → 应译仍日 FAIL；
    #    无墨/几乎无墨帧保持 suspect（可能本就无文字）。
    changed_px = text_delta
    origin_ink = int(ga.get("origin_ink_px") or ga.get("o_ink_px") or 0)
    if changed_px == 0:
        # 仅对「应有可译 UI 文案」的步骤升 FAIL；过场/大地图墨迹多但未必有文案。
        step = str(scene_step or "").lower()
        expect_text = any(
            k in step
            for k in (
                "trainer", "bag", "menu", "name", "summary", "party",
                "dex", "mart", "shop", "battle", "talk", "msg", "dialog",
                "card", "option", "nav_item", "nav_on", "nav_home",
                "pokenav", "list", "desc",
            )
        )
        if origin_ink >= 200 and expect_text:
            reasons.append({
                "dim": "a_translated",
                "level": "fail",
                "msg": (
                    f"origin 有墨约 {origin_ink}px 但 translated 完全未变"
                    f"（应译仍日 step={step or '?'}）"
                ),
            })
        else:
            reasons.append({
                "dim": "a_translated",
                "level": "suspect",
                "msg": "两侧像素完全相同，本帧看不出汉化（可能本就无文字）",
            })
    elif retext_px > 0:
        notes_ok.append(f"{retext_px} 像素为同位置换字（汉化生效）")

    levels = {r["level"] for r in reasons}
    v = "fail" if "fail" in levels else ("suspect" if "suspect" in levels else "pass")
    conf = 0.85 if v in ("fail", "pass") else 0.55
    return {"verdict": v, "confidence": conf, "reasons": reasons,
            "notes": notes_ok, "metrics": metrics}


# ═══════════════════════════════════════════════════════════════════════════
# 场景级
# ═══════════════════════════════════════════════════════════════════════════

def _frame_arr(run_dir: Path, rel: str):
    return load_rgb(run_dir / rel)


def _detect_reset_and_crash(frames: list, manifest: dict) -> list:
    """跨帧判据：软复位 / 崩溃。

    必须在帧循环之后做 —— 单帧看不出「回到开场」或「之后永远黑」。

    判据：
      s_reset  translated 某一帧与 **同 run 的 origin 首帧** 高度相似，
               而它与自己的 origin 对应帧差异很大 ⇒ 汉化侧掉回开场/标题。
      s_crash  translated 从某帧起直到结束全部空白，而 origin 后续仍有内容
               ⇒ 模拟器崩溃或死循环（游戏没再推进）。
    """
    out = []
    pairs = manifest.get("pairs") or []
    if len(frames) < 2 or not pairs:
        return out
    base = Path(manifest.get("_run_dir") or ".")
    by_num = {p["number"]: p for p in pairs}

    first_o = _frame_arr(base, pairs[0]["origin"])
    if first_o is None:
        return out
    first_num = frames[0]["number"]

    # ── 软复位：某帧的 translated 与「开场首帧」几乎一样 ──────────────────
    RESET_SIM = 0.97
    for f in frames:
        pair = by_num.get(f["number"])
        if pair is None or f["number"] == first_num:
            continue
        t = _frame_arr(base, pair["translated"])
        o = _frame_arr(base, pair["origin"])
        if t is None or o is None or is_blank_frame(t)[0]:
            continue                      # 空白帧交给 s_crash / g_black
        sim_first = similarity(first_o, t)
        sim_own = similarity(o, t)
        if sim_first >= RESET_SIM and sim_own < 0.80:
            out.append({
                "frame": f["number"], "dim": "s_reset", "level": "fail",
                "msg": f"translated 与开场首帧相似度 {sim_first:.3f}（与本帧 origin 仅 "
                       f"{sim_own:.3f}）⇒ 疑似软复位回到开场/标题",
            })
            break

    # ── 崩溃：从某帧起永远空白 ────────────────────────────────────────────
    blanks = []
    for f in frames:
        pair = by_num.get(f["number"])
        t = _frame_arr(base, pair["translated"]) if pair else None
        blanks.append(bool(t is not None and is_blank_frame(t)[0]))
    if any(blanks):
        tail_start = None
        for i in range(len(blanks)):
            if blanks[i] and all(blanks[i:]):
                tail_start = i
                break
        if tail_start is not None:
            num = frames[tail_start]["number"]
            out.append({
                "frame": num, "dim": "s_crash", "level": "fail",
                "msg": f"translated 从第 {num} 帧起直到结束全部空白"
                       f"（连续 {len(blanks) - tail_start} 帧）⇒ 模拟器崩溃或死循环",
            })

    # ── 永久偏离：从某帧起相似度一直塌到 <0.50 ────────────────────────────
    #    实测 pokemon_menu：摘要页第 50/51 帧全黑，第 52 帧起回到野外，
    #    origin 仍停在摘要页 ⇒ 之后每一帧相似度都是 0.0。
    #    这不是「截图没对齐」，是游戏状态真的分叉了（软复位/崩溃/走错分支），
    #    旧判据只报「非同一场景」，容易被误读成采集问题。
    sims = []
    for f in frames:
        pair = by_num.get(f["number"])
        if pair is None:
            sims.append(None)
            continue
        o = _frame_arr(base, pair["origin"])
        t = _frame_arr(base, pair["translated"])
        sims.append(None if (o is None or t is None) else similarity(o, t))

    tail = None
    for i in range(len(sims)):
        rest = [s for s in sims[i:] if s is not None]
        if rest and all(s < 0.50 for s in rest) and len(rest) >= 2:
            tail = i
            break
    if tail is not None and tail > 0:
        num = frames[tail]["number"]
        out.append({
            "frame": num, "dim": "s_diverged", "level": "fail",
            "msg": f"画面从第 {num} 帧起永久偏离 origin（其后 {len(sims) - tail} 帧"
                   f"相似度全部 <0.50）⇒ 崩溃/软复位/走错分支，不是采集误差",
        })
    return out


def verify_run(run_dir: Path) -> dict:
    run_dir = Path(run_dir)
    manifest = {}
    mp = run_dir / "manifest.json"
    if mp.is_file():
        manifest = json.loads(mp.read_text(encoding="utf-8"))
    manifest["_run_dir"] = str(run_dir)

    roms = manifest.get("roms") or {}
    o_sha = (roms.get("origin") or {}).get("save_sha256")
    t_sha = (roms.get("translated") or {}).get("save_sha256")

    frames = []
    for p in manifest.get("pairs", []):
        res = verdict_pair(
            run_dir / p["origin"],
            run_dir / p["translated"],
            scene_step=str(p.get("scene_step") or ""),
        )
        res["number"] = p["number"]
        res["scene_step"] = p.get("scene_step")
        frames.append(res)

    scene_reasons = _detect_reset_and_crash(frames, manifest)
    if scene_reasons:
        for f in frames:
            hit = next((r for r in scene_reasons if r.get("frame") == f["number"]), None)
            if hit:
                f["reasons"].append({k: hit[k] for k in ("dim", "level", "msg")})
                f["verdict"] = "fail"

    verdicts = [f["verdict"] for f in frames]
    if not frames:
        scene = "fail"
    elif "fail" in verdicts:
        scene = "fail"
    elif "suspect" in verdicts:
        scene = "suspect"
    else:
        scene = "pass"

    if o_sha is not None and t_sha is not None and o_sha != t_sha:
        scene = "fail"
        scene_reasons.append({"dim": "s_scene", "level": "fail",
                              "msg": "两侧存档 SHA-256 不等，起点不同，对照不可信"})

    return {
        "schema": 2,
        "run_dir": str(run_dir),
        "verdict": scene,
        "counts": {v: verdicts.count(v) for v in ("pass", "suspect", "fail")},
        "frames": frames,
        "needs_user_review": [f["number"] for f in frames if f["verdict"] != "pass"],
        "scene_reasons": scene_reasons,
    }


def render_md(r: dict) -> str:
    L = ["# bot 字形级比对 verdict\n"]
    L.append(f"- run: `{r['run_dir']}`")
    L.append(f"- **场景判定: {r['verdict'].upper()}**")
    L.append("- 帧统计: " + " ".join(f"{k}={v}" for k, v in r["counts"].items()))
    L.append(f"- 待复核帧: {r['needs_user_review']}\n")
    if r["scene_reasons"]:
        L.append("## 场景级问题\n")
        for x in r["scene_reasons"]:
            L.append(f"- [{x['dim']}/{x['level']}] {x['msg']}")
        L.append("")
    L.append("| # | 步骤 | 判定 | 相似度 | 新增px | 丢失px | 字形 | 碎片 | 竖条 | 撞UI | 异色 |")
    L.append("|---|------|------|--------|--------|--------|------|------|------|------|------|")
    for f in r["frames"]:
        m = f["metrics"] or {}
        k = m.get("kinds") or {}
        L.append(f"| {f['number']:03d} | {f.get('scene_step') or ''} | "
                 f"{f['verdict'].upper()} | {m.get('scene_similarity')} | "
                 f"{m.get('added_px')} | {m.get('removed_px')} | "
                 f"{k.get('glyph', 0)} | {k.get('fragment', 0)} | "
                 f"{k.get('sliver', 0)} | {k.get('collision', 0)} | "
                 f"{k.get('new_color', 0)} |")
    L.append("")
    for f in r["frames"]:
        if f["verdict"] == "pass":
            continue
        L.append(f"### {f['number']:03d} {f.get('scene_step') or ''} — {f['verdict'].upper()}")
        for x in f["reasons"]:
            L.append(f"- [{x['dim']}/{x['level']}] {x['msg']}")
        sus = (f["metrics"] or {}).get("suspicious") or []
        for it in sus[:8]:
            L.append(f"  - `{it['kind']}` bbox={it['bbox']} px={it['px']} "
                     f"接壤={it['touches_origin_ink']} {'; '.join(it['notes'])}")
        if len(sus) > 8:
            L.append(f"  - …另有 {len(sus) - 8} 个可疑块，详见 verdict.json")
        L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    a = ap.parse_args()

    run_dir = Path(a.run_dir)
    if not run_dir.is_dir():
        raise SystemExit(f"[ERR] 目录不存在: {run_dir}")

    result = verify_run(run_dir)
    (run_dir / "verdict.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "verdict.md").write_text(render_md(result), encoding="utf-8")
    print(render_md(result))
    return {"pass": 0, "suspect": 2, "fail": 1}[result["verdict"]]


if __name__ == "__main__":
    raise SystemExit(main())
