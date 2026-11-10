# FireRed compose lock (Phase 0) — **H1 FAIL**

> ROM: `roms/translated/宝可梦火红日版汉化2.2.gba`  
> Dumps: `work/_probe/ewram/d*.f7table.bin` (all **zero** at `0x0203F2C0`)  
> Analyzer: `scripts/research/firered/compose_lock_p0.py`  
> Superseding authority: [`FIRERED_FONT_GDB_FINAL.md`](FIRERED_FONT_GDB_FINAL.md) (GDB breakpoints on glyph fetch)

## Verdict

**H1 COMPOSE FAIL — do not port “expand to vanilla PCS → FontFunc” to AXVJ.**

| Claim (early encoding doc) | Reality (GDB + ROM) |
|---|---|
| Chinese = `F7` → `TABLE[hi]` → **original JP PCS string** → FontFunc | **False.** Chinese uses a **dedicated 12×13 bitmap font** |
| “No Han bitmaps in ROM” | **False.** Pages under `0x08B6C000` / table `0x08B74000` (汉化新增；原版全 `FF`) |
| EWRAM `0x0203F2C0` is the live compose TABLE | **Empty** in all 6 dumps (`d1`–`d6` f7table nonzero=0). Literals still point there, but it is not a filled PCS-pointer table at render time |

### GDB lock (from FIRERED_FONT_GDB_FINAL)

- Fetch fn: `0x081DB3EE` (汉化新增), width **12**, height **13**
- Page table: `0x08B74000` (11 entries, `hi ∈ [0x00,0x0A]`)
- Address: `PAGES[hi] + (lo >> 3) * 512 + (code & 7) * 32`
- Codepoints: ~2816 (content ~2385)
- ASCII/digits remain separate 8×12 vanilla path — not “compose Han from kana”

### Live dump (this Phase 0)

```
d1..d6.f7table.bin @ 0x0203F2C0: all 256 u32 = 0
literal 0x081DB6D8 / 0x081DB85C = 0x0203F2C0 (unchanged)
EWRAM scan: no long run of ROM pointers → FF-terminated JP text suitable as compose dict
F7 triples in text band still look like F7 hi lo (e.g. f7 00 35) — they index the **bitmap** path, not FontFunc PCS expand
```

### ROM spot-check (this run)

Page table `@0x08B74000` present in ZH ROM (11 entries); default page `@0x08B6C000` has dense nonzero payload (not empty / not JP string table).

## lo consumption (R-2)

Under the **bitmap** model: `F7 hi lo` is a 12-bit-ish glyph index (`hi` = page, `lo` = code in page), consumed by `0x081DB3EE` via the formula above — **not** “hi selects a PCS string, lo is a second compose stage.”

## Gate for Phase 1+

**Closed.** Plan rule: *If H1 fails: stop and report; do not force AXVJ.*

- Do **not** implement AXVJ compose codec / Han→PCS dictionary / FontFunc-only expand.
- Do **not** delete CHS blit on the basis of FireRed “compose.”
- Correct FireRed-like direction (separate effort): **12×13 (or ~12 advance) glyph font + official-ish layout**, not PCS assembly. See GDB final + `FIRERED_GLYPH_GEOMETRY.md` metrics; that is **not** this compose plan.

## What early FIRERED_RENDER_ENCODING got wrong

§1.3 “中文 = 索引 → 原版单字节片段，不是新字模” was inferred from transcoder disasm + empty ROM bitmap search. GDB glyph-fetch breakpoints later proved a **new** Han font. Treat encoding doc §1.3 as **superseded** by `FIRERED_FONT_GDB_FINAL.md`.
