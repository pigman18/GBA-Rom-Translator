"""把一帧按 BG0-3 / OBJ 分别渲染出来，用于判断某段 UI 来自哪一层。"""
import argparse
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, r"C:\code\GBA-Rom-Translator\src")
from util.gba_ppu import Snapshot, bg_text_layer, parse_oam, render

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("origin", help="bot 回放 origin 目录")
    ap.add_argument("frame", help="帧号，如 015")
    ap.add_argument("out")
    a = ap.parse_args()

    snap = Snapshot.load(a.origin, a.frame)
    out = Image.fromarray(render(snap))
    out.save(f"{a.out}_full.png")

    dispcnt = int.from_bytes(snap.io[0:2], "little")
    for i in range(4):
        if not (dispcnt >> (8 + i)) & 1:
            continue
        layer = bg_text_layer(snap, i)
        if layer is None:
            continue
        rgb, mask = layer
        arr = np.zeros((160, 240, 4), np.uint8)
        h = min(160, rgb.shape[0]); w = min(240, rgb.shape[1])
        arr[:h, :w, :3] = rgb[:h, :w]
        arr[:h, :w, 3] = np.where(mask[:h, :w], 0, 255)
        Image.fromarray(arr).save(f"{a.out}_bg{i}.png")

    objs = parse_oam(snap)
    if objs:
        arr = np.zeros((160, 240, 4), np.uint8)
        for ob in objs:
            spr, mask = ob.rgb, ob.mask
            h, w = spr.shape[:2]
            y, x = ob.y, ob.x
            if y + h < 0 or x + w < 0 or y > 160 or x > 240:
                continue
            ys, xs = max(0, y), max(0, x)
            ye, xe = min(160, y + h), min(240, x + w)
            if ye <= ys or xe <= xs:
                continue
            arr[ys:ye, xs:xe, :3] = spr[ys - y:ye - y, xs - x:xe - x]
            arr[ys:ye, xs:xe, 3] = np.where(
                mask[ys - y:ye - y, xs - x:xe - x], 0, 255)
        Image.fromarray(arr).save(f"{a.out}_obj.png")

    print(f"dispcnt=0x{dispcnt:04X} objs={len(objs)} -> {a.out}_*.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
