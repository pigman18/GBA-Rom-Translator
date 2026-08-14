# AXVJ 图块候选表（LZ77 静态扫描）与 presets 生成指引

> 生成：2026-08-14。工具：`src/util/_scan_tiles.py`（全 ROM LZ77 块扫描）。ROM：`roms/origin/POKEMON_RUBY_AXVJ00.gba`。
> 目的：为「其他待汉化图标能不能通过静态分析也加 presets 导出」提供实证候选与落地方案。

## 结论（TL;DR)

**能，但静态分析只能到「候选 + 大部分参数」，不是零人工。**

- 普通图集（如属性图标 `0x087EE9C8`）**可全自动**转成一条 `tiles.presets`：地址/压缩/bpp/尺寸/count/调色板/指针/bank 表全部由 `probe_data` / `_scan_tiles` 静态推出且与真值一致。
- **compose 类**（标题 Logo `0x0836D268`、横幅 `0x0836EC6C`）静态只能看到 tile 表，**推不出 `compose` 的拼接结构**（`tilemap_address/width/height/left/right`），必须人工补。
- 调色板启发式**会误判**（横幅那条 pal 就是错的），需人眼核对。
- 「哪些块算待汉化图标」本身**没有自动边界**——需结合已知 UI 地址带 / 屏幕残留（`docs/PENDING_TEXT_JP.md`）人工圈定。

## 扫描产物

- 全量 LZ77 候选表：`scan_out.txt`（仓库根，UTF-16，1763 行）。
- 解析脚本：`tools_scan_filter.py`（读取 `scan_out.txt`，列出全部非 64×64 地图瓦片的候选）。

全 ROM 共扫到 **1763 个 LZ77 块**，其中 676 个非 `64×64` 地图瓦片。真正「图标」需要从这 676 个里结合信号筛选。

## 锚点验证（已知 3 个已汉化图标，静态分析对照真值）

| GBA 地址 | 用途 | 静态推断 | 真值(meta) | 可自动 preset？ |
|----------|------|----------|------------|-----------------|
| `0x087EE9C8` | 属性图标 | 4bpp 32x16 ×23, pal=0x087EF450, ptr=0x0839747C | 完全相同 | ✅ 全自动 |
| `0x0836D268` | 标题 Logo | 8bpp 16x16 ×39（tile 表） | 需 compose logo (tilemap) | ⚠️ 需补 compose |
| `0x0836EC6C` | 标题横幅 | 4bpp 64x32 ×3, **pal=0x0836EC6A 误判** | compose banner | ⚠️ 需补 compose + 手核 pal |

## 高价值「UI 图标集」候选（结构上最像待汉化图标）

> 判定信号：多帧小尺寸块（非 64×64 地图），集中在同一地址带、共用一板调色板。

| GBA 地址 | 形状 | 帧数 | 解压字节 | 调色板 | 备注 |
|----------|------|------|----------|--------|------|
| `0x081EEB48` | 8bpp 8x8 | 159 | 5088 | 0x081EEB46 | 大型 8bpp 图标集 |
| `0x081EF53C` | 4bpp 8x8 | 498 | 15936 | 0x081EF53A | **巨型 4bpp 图集类**（~500 帧）|
| `0x081F8204` | 4bpp 32x32 | 27 | 13824 | 0x081F8202 | 32×32 组图标 |
| `0x081F1A...` 一带 | 8bpp 8x8 多组 | 100~500 | — | — | 大型零散字形/图标池 |
| `0x0820C510` | 4bpp 32x16 | 39 | 9984 | 0x0820C50E | 与属性图标同形参（39 帧）|
| `0x0837CB34` | 4bpp 32x16 | 19 | 4864 | 0x0837CB32 | 同形参 |
| `0x083CDCC8` 一带 | 8bpp 8x8 | 3~37 | 360~1200 | 0x083DCCC* | **战斗 FC 四键字形**（见下）|

### 与 `PENDING_TEXT_JP.md` §4「疑图块」的交叉

PENDING 登记「战斗右下四键仍全日文，可能是图块字」。静态扫描在文件偏移 `0x3DCCxx`（GBA `0x083DCCC8` 一带）找到一组 `8bpp 8x8` / `4bpp 8x8` 小图块（帧数 3/11/15/37），**正是疑似「たたかう/バッグ/ポケモン/にげる」四键字形**。这类图块用 `cmd_probe`（喂该特征）即可全自动导出为 preset。

> 注意：`0x3862xx`（选宠类别字乱码）区域**没有 LZ77 块命中**——印证 PENDING 判断：那是定宽结构槽而非 LZ 图，不能走 tiles 管线。

## 如何把一个候选转成 `tiles.presets`

`tiles.presets` 项字段与 `apply_tiles_preset_to_args` 一一对应：

```yaml
tiles:
  presets:
    - id: battle_fc_buttons        # 短横线名
      address: 0x083DCCC8          # = meta.rom_address
      format: 8bpp                 # = meta.format
      compression: lz77_swap       # = meta.compression
      sprite_size: 8x8             # = meta.sprite_size_px
      count: 11                    # = meta.sprite_count
      palette: 0x083DCCC2          # = meta.palette.rom_address
      palette_size: 96
      # 属性图标类的按帧调色板 bank（若 probe 检出 bank 表）：
      # bank_list: 0,0,1,1,0,...
      # compose 类额外补：
      # compose:
      #   type: logo|banner
      #   tilemap_address: 0x...
      #   width / height  (logo)
      #   left / right: {width,height}  (banner)
      # 有指针被改时：
      # pointers: [0x0839747C, 0x...]
```

导出（写回流水线 tiles 目录）：

```bash
python tiles_patcher.py export roms/origin/POKEMON_RUBY_AXVJ00.gba --preset <id> \
  -o configs/POKEMON_RUBY_AXVJ00/tiles
# 或全部：
python tiles_patcher.py export roms/origin/POKEMON_RUBY_AXVJ00.gba --all \
  -o configs/POKEMON_RUBY_AXVJ00/tiles
```

导入（build/字库之后，由 Meowth tile 阶段调用）：

```bash
python tiles_patcher.py import roms/origin/POKEMON_RUBY_AXVJ00.gba \
  configs/POKEMON_RUBY_AXVJ00/tiles -a 0x09200000
```

## 局限性（为什么不是「一键全自动」）

1. **参数推断是启发式**：`_infer_sprite_size` 只认 `_KNOWN_SPRITE_SIZES_4BPP` 六种标准尺寸，非整倍数会回退 `8x8` 且 count 错；调色板近视 `±0x20000`，找不到会全 ROM 回退 LZ77 扫屏——易命中错误板（横幅即实证）。
2. **compose 无法自动**：banner/logo 横跨 tile 表 + tilemap，`probe` 看不到 `compose` 结构，必须人工。
3. **「待汉化」无自动判据**：map sheet / 文字字形 / 头像 / 图标混在一起，静态无法分辨哪个是「要汉化的 UI 图标」；需结合已知 UI 地址带、屏幕残留、或导出 PNG 人眼核对（可借 `--all` 批量出 PNG 再核对）。
4. **图块正文案源是本 ROM 有日文字形的字形块**：真正的战斗四键若已是字形引用（FC 串），可能根本不该走 tile 管线，而应走文本（PENDING §4 也是「先看 rebuild 后 FC 是否生效再决定是否挖图」）。

## 推荐落地流程

1. `_scan_tiles.py` 已跑 → `scan_out.txt` 全量候选。（本步骤已做）
2. 用 `tools_scan_filter.py` 过滤出非地图瓦片的候选。
3. 结合 `PENDING_TEXT_JP.md` §4 + 已知 UI 地址带，圈定 5–15 个「疑似待汉化图标」。
4. 对每个用 `cmd_probe`（喂特征字节）得到建议 export 命令 → 复核调色板与 compose → 写成 `tiles.presets` 项。
5. `--all` 一次导出 PNG -> 人眼核对挑出真图标 -> 编辑 PNG -> 流水线 import。
