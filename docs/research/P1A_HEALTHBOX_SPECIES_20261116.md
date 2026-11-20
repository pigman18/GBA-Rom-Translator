# P1a′/P1b：血条种名中文显示（2026-11-16）

范围：血条名字的**展示**。不动昵称槽（6B）、不动 `GetSpeciesName`、不动 F7 协议、不动译文。
基线：`refactor/drop-f980-slt2` @ `5f37bd5`。

**结论：P1b 已生效。** 血条名字区现在能显示完整中文种名（12px 字形），并保留原 8px 路径。

---

## 1. 先验证再改：0x0811CA64 不是展示站点

`bot/run.py --gdb` 在 `battle_species_name`（Route118 存档）实测：

| 探针 | 地址 | 命中 | 结论 |
|---|---|---|---|
| `BattleSpeciesNameDst` | `0x0811CA60`（原计划站点） | **0 次** | 整场遇敌+台词+菜单都没走这条分支 |
| `GetSpeciesNameEntry` | `0x0803B11C` | **1 次** | 唯一调用者 `LR=0x08037D0A` = CreateBoxMon；dest=`0x03007D10`（栈） |
| `HealthboxMaskAlt2` | `0x08042408` | **3 次** | 真正的血条名刷新函数 `UpdateNickInHealthbox` |
| `TextEngineEntry` | `0x08800000` | 120 次 | 扩展区 ROM 断点可用 |

血条链路：

```text
UpdateNickInHealthbox @0x08042408
  GetMonData(mon, 2, sp)   @0x08042430   ; 结构昵称 6B
  StringTruncate5(sp)      @0x08042434 → 0x0804290（movs r4,#5） ; 再截 5B
  StringCopy(buf+3, sp)    @0x0804243E
  RenderTextHandleBold     @0x08042432   ; textMode 2 打到 gfx 缓冲
  0x04253A 循环            ; 逐**字节**把 8px 字块写进缓冲
  0x0425A8 循环            ; 按 r8（字节数-6）把每格 32B 拷进 VRAM
```

## 2. 实现（两个钩子）

### 2.1 名字串（P1a′）

`HealthboxNameCopy_C(dst, mon)`：
- `GetMonData(mon, 11)` 取 species → 名表 `0x09EB0AF4 + sp*24`；
- 默认名判定：昵称前 6B == 名表前 6B，**或**昵称里没有 F7 token（旧存档日文默认名）；
- 默认 → 写名表全文（≤23B + FF）；自定义中文昵称 → 保持原 5B + FF。

拼串缓冲从 `0x0202362C`（20B 槽，5 字名溢出）改指私有 32B `0x0203E020`。

### 2.2 绘字循环（P1b）

`HealthboxNameGlyphs_C(dst, str)` 取代 `0x042538` 起的逐字节循环：
- `F7 00 hi lo` → 取 `0x09000000 + gidx*128` 的 12x12 墨迹，画进 **2 个连续 8x16 字格**（16px 宽），`cell += 2`；
- 其它字节 → 原 `0x08040EF8(byte)` 的 8px 字块，`cell += 1`；
- **返回实际格数**，跳板写回 `r8` —— 否则 0x0425A8 的 VRAM 拷贝仍按「字节数-6」循环，会把名字区后面的缓冲垃圾一起拷进 VRAM。

| 文件 | 改动 |
|---|---|
| `hook/src/battle/UpdateNickInHealthbox_hook.c` | 新增 `HealthboxNameCopy_C` / `HealthboxNameGlyphs_C`（含 12px 字形绘制） |
| `hook/src/battle/UpdateNickInHealthbox_entry.s` | 新增 `HealthboxNameCopy_Entry`（回 0x08042448）/ `HealthboxNameGlyphs_Entry`（回 0x080425A8，并写 r8） |
| `hook/src/battle/hooks_origin.s` | `0x0804243E` 起 10B、`0x08042538` 起 8B 换成 `ldr r1,=(塔|1); bx r1; .pool`；池 `0x08042494`/`0x08042568` → `0x0203E020` |
| `hook/build.bat` + `hook/Makefile` | 符号白名单加两个塔 |
| `hook/game_addrs.asm` + `include/game.h` | `GetMonData 0x08039F24`、`HealthboxTile8 0x08040EF8`、`SpeciesNameTable 0x09EB0AF4`、`HealthboxNameBuf 0x0203E020` |

## 3. 三个必须记住的坑

1. **armips 不要手写 `.dh`/`.word` 做 PC 相对字面量**：实机 `r3=0` → `bx 0` → 开机 LOGO 重启。必须用 `ldr r1,=(符号|1); bx r1; .pool`，且站点最好选 4 字节对齐地址（0x042538 而不是 0x04253A）。
2. **`python -m meowth build` 不重编 hook C**：只复制 `hook/out/game.bin`。改 C/汇编后必须先跑 `configs/POKEMON_RUBY_AXVJ00/hook/build.bat`。
3. **`GetMonData` 值型字段走返回值 r0**，不写 dst；`species = GetMonData(mon, 11, 0) & 0xFFFF`。

## 4. 验收

- 钩子命中：`HealthboxNameCopyEntry` / `HealthboxNameGlyphsEntry` 各命中 3 次（battler 0/1 + 一次刷新）。
- 名字串：RAM `0x0203E020 = FC 02 02 | F7 00 05 7D F7 00 0E CF F7 00 05 91 | FC 01 0B B5 | FF` → **火焰鸡**（3 字）。
- 画面：字库直接导出的 12x12「火焰鸡」与游戏内名字区逐字对比，笔画骨架一致（游戏侧多了血条 UI 的描边/调色），三个字完整。
- 场景 `battle_species_name` 122 帧跑通，无黑屏/重启。
- 对照图：`work/_p1a_probe/p1b_compare.png`（改前基线 / 改后 / 日文原版）。
  注：两次 run 的野生遭遇由狩猎 RNG 决定，**不保证同一只**；改前那张是 ジグザグマ（蛇纹熊）的破碎中文名，改后那张是 火焰鸡。

## 5. 已知限制 / 下一步

- 血条名字区按 6 个 8px 格宽（48px）布局：3 个 12px 汉字正好占满；**4~5 字名会顶到框边**，需要另案（缩字距 / 换 Small 8px 字库 / 加宽血条框几何）。
- 12px 字形没有原版 8px 字块的阴影层（`0x0425F6` 的第二段 CpuSet 只拷下半格）；如需要可再补一层阴影。
- 开场句「野生的××跳出来了」走另一条串展开，未在本次范围。

## 6. 复现

```text
cd configs\POKEMON_RUBY_AXVJ00\hook
build.bat

cd C:\code\GBA-Rom-Translator
$env:PYTHONPATH="$PWD\src"
python -m meowth build roms/origin/POKEMON_RUBY_AXVJ00.gba `
  --translations work/POKEMON_RUBY_AXVJ00/translate.build.json `
  -o roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba --source ja --target zh-Hans

python bot/run.py POKEMON_RUBY_AXVJ00 battle_species_name `
  --save bot/scenes/POKEMON_RUBY_AXVJ00/saves/Route118_68-7.sav
```

诊断探针（`src/util/configs/POKEMON_RUBY_AXVJ00.yaml`，均 `default: false`）：
`BattleSpeciesNameDst` / `GetSpeciesNameEntry` / `PartyNickCopyLoop` / `NickCopyLoop` / `HealthboxMaskAlt2`
/ `HealthboxPatchSite` / `HealthboxBxSite` / `HealthboxResume` / `HealthboxNameCopyEntry` / `HealthboxNameCopyC`
/ `HealthboxNameGlyphsEntry` / `RenderTextHandleBold` / `TextEngineEntry`。其中 `HealthboxPatchSite/BxSite/Resume` 仅排查用，可删。