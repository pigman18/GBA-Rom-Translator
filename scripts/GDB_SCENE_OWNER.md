# 场景 tile 归属取证（`--preset scene-owner`）

> 姊妹文档：`scripts/GDB_CB_LOAD.md`（`--preset cb-load`）——同一个 GDB 通道，
> 专门看「官方往 cb2/cb3 装了什么参数」（S1→S2 衔接，2026-09-11 新增）。

## 目的

回答「屏上这批 tile 到底谁在写、谁在显示」：

- 每个启用 BG 层的 `charBase` / `screenBase` / size（= 它从哪个 charblock、哪个 screenblock 取数）
- 每层 tilemap 的**全量条目** → 它引用的 tile 号集合（同一 tile 被几格引用）
- 我们 v8/v9 账本：不可写位图占用 / 游标 / **ours 可回收位图** / 队列归属键 / 场景签名
- 把上面两方统一换算成**绝对 tile 号**后求交：
  - `BG引用 ∩ ours` = 我们写的 tile 正被显示（多串共用 ⇒ 后写的盖掉先写的）
  - `ours \ BG引用` = 我们写了但屏上没人引用（陈旧残留，**可回收**）
  - `BGx ∩ BGy` = 两个图层共用同一批 tile

---

## 前置条件（重要）

断点地址是 `game.bin` 里 hook 函数的地址，**每次重编 hook 都会变**。采集前先核对：

```bash
grep -n "v8_alloc_begin\|v8_alloc_tile" configs/POKEMON_RUBY_AXVJ00/hook/out/game.map
grep -n "name: V8Alloc$\|name: V8AllocBegin" -A 1 src/util/configs/POKEMON_RUBY_AXVJ00.yaml
```

两处地址必须一致（**V8AllocBegin=0x08801084 / V8Alloc=0x0880135c** @ 2026-09-11 v9.2 重编）。
**模拟器里必须跑与这份 `game.bin` 同源的 ROM**，否则断点会打在别的代码上。

---

## 采集步骤

### 1. 启动带 GDB stub 的 mGBA

```powershell
cd C:\code\GBA-Rom-Translator
& "tools\mGBA-0.10.5-win32\mGBA.exe" -g "roms\outputs\POKEMON_RUBY_AXVJ00_translated.gba"
```

`-g` = 监听 `127.0.0.1:2345`。窗口保持开着（此时游戏是暂停的，等 gdb 连上会自动继续）。

> ⚠ **每次重编 hook 后必须先重新打包 ROM**（`pack_no_llm.py`），再重开 mGBA 加载新 ROM ——
> 否则断点地址对不上。校验方法（ROM 内嵌 game.bin 应与本地编译产物同一 sha1）：
>
> ```bash
> sha1sum configs/POKEMON_RUBY_AXVJ00/hook/out/game.bin
> dd if=roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba bs=1 skip=$((0x800000)) count=9268 | sha1sum
> ```

### 2. 另开一个终端，挂埋点

```powershell
cd C:\code\GBA-Rom-Translator
C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe `
  src\util\gdb_patcher.py log --preset scene-owner `
  --log src/util/work/POKEMON_RUBY_AXVJ00/scene_owner.log
```

想同时看**逐字落在哪个 tile**，追加 `UpdateTilemap`（日志会长很多）：

```
--preset scene-owner --functions InitTextPrinter,V8AllocBegin,V8Alloc,UpdateTilemap
```

### 3. 进游戏到目标界面

在 mGBA 里操作到**领航员（PokéNav）训练家列表**那一屏，停住别动，等 5～10 秒
（脚本会跟着断点一条条打印 `[SCENE-OWNER]` 快照，内容变化才输出）。

### 4. Ctrl-C 定格

在跑脚本的那个终端按 `Ctrl-C`。脚本会**强制补一份终态快照**
（标题 `↓↓↓ 中断时终态`），这份是画面完全绘好之后的最终状态，最准。

### 5. 日志位置

```
src/util/work/POKEMON_RUBY_AXVJ00/scene_owner.log
```

日志是**追加**写的，每次采集前要么换 `--log` 路径，要么先删掉旧文件。

---

## 怎么读

一个快照长这样（示例）：

```
[SCENE-OWNER] DISPCNT=0x0F00 启用BG=[0, 1, 2, 3]
  BG0 CNT=0x1E01 prio=1 charBase=cb0(0x00000) screenBase=sb30(0x0600F000) size=32x32 ★=本窗写入的 tilemap
     条目=1024 引用tile0的空白槽=1020 引用唯一tile=3  相对范围=300..700
     绝对化引用集=300..301 700（3个）
     只看可见前20行=2 个；仅出现在不可见行(20~31)的陈旧引用=1 个（分配器活引用扫描会把它们也当『屏上在用』）
     ↳ 暗耗 tile（相对号）=700
     出现次数TOP=[(300, 2), (301, 1), (700, 1)]
  [OURS] 不可写位图 bm=3/1024 游标=0x012E last_tile=0x0000 phase=0 prow=0
         可回收位图 ours=5/768（tile 相对号 [256,1024)，v9.1 持久不淘汰）
         解码段 ours=[(256, 3), (300, 2)]
  [SIG] 判定依据=v9.2（BG0..3 CNT + mode；DISPCNT 已剔除）
        ROM 存=BGCNT 1F01 1B0C 1D0A 1E03 sent=0x5C00
        当前  =BGCNT 1F01 1B0C 1D0A 1E03 sent=0x5C00（DISPCNT=0x3F40 仅参考）
        ⇒ 一致（ours 有效，可回收）
  [V8Q] magic=0x5A3C（应 0x5A3C）归属 win=0x0202E658 tpl=0x081BB7E4
  [ARENA cb0] [256,1024) = 768 tile 结算：
     真·空闲=34  |  非空且活引用=44  |  非空且在账本非活=688  |  ★非空·无引用·无账本=2（v9.1 后应≈0）
  ★ BG引用(5个) ∩ ours(6个) = 4 个 → 256 300..302（4个）
  ○ ours \ BG引用 = 2 个 → 257..258（2个）
  ⊕ BG0 ∩ BG1 = 0 个 → （空）
  [本窗] 0x0202E658 tpl=0x081BB7B4 tile_base(win[0x16])=0x0001 tilemap(win[0x10])=0x0600F000 curx=0 cury=0
```

判读要点：

| 现象 | 含义 |
|---|---|
| `⊕ BG0 ∩ BG1` 非空 | 两个图层指向同一批 tile 号（各自 charBase 相同时才是真共用） |
| `★ 交集` 很大 | 我们分配的 tile 正被 BG 显示；若多条串共用 ⇒ 互相覆盖 |
| `[V8Q] 归属 tpl` 每条串都在变 | `(win,tpl)` 双键判定为「切换」⇒ 游标被置回首 256，各串从同一处重新领号 |
| **`[ARENA] ★非空·无引用·无账本` 大** | 这些 tile VRAM 非空、没人引用、也不在可回收位图里 ⇒ 被判「官方数据」永久锁死。先看 `[JUNK-HEX]` 判它是我们的旧字还是官方数据；再看 `[SIG]` 是否出现过「★不一致」（v9.2 前每次 DISPCNT 变动都会误清 ours） |
| `[SIG]` 显示「★不一致」 | v9.2 判定 = `BG0..3 CNT + mode`。**同场景内不该再出现不一致**；若频繁出现 ⇒ 该场景 BGxCNT 在抖 ⇒ ours 反复被清空 ⇒ 回收面归零（再收窄到只比 charBase 位）。注意 `DISPCNT` 已不参与判定，它单独打印只为参考|
| `[ARENA] ⇒ 本次 begin 后真正可领 = N tile` | **这才是池子的真实容量**（账本∩非空∩¬活引用）。N<100 ⇒ 本屏还会缺字；N 越大越好 |
| `[JUNK-HEX]` 抽样 | 32B/tile 内容指纹。**高半字节非零≈0 + 顶2行=0 + 底3行=0** ⇒ 这批 ★死数据是**我们自己的 8px 汉字**（回收面成立）；非零字节≈24~32 且高半字节也非零 ⇒ 是**官方图集／美术**（碰不得，只能换 charblock）|
| `ours` 段数远超 19 | **正常**（v9.1 位图无淘汰；旧 19 段是段表上限） |
| **`暗耗 tile` 数量大** | tilemap 第 20~31 行（屏幕外）残留旧表项，分配器的活引用扫描**扫全 1024 项** ⇒ 这些 tile 被误判「屏上在用」而永久跳过 ⇒ arena 被暗耗 |
| `charBase` 各层不同 | 绝对号要按 `cb×512 + 相对号` 换算，交集判定必须用绝对号 |

> `暗耗` 曾是主要嫌疑：可见区只占 32×32 表的前 20 行，
> 但 `v8_alloc_begin` 的 `v8_scan_entries(tilemap, 1024, bm)` 扫的是全表。
> 不过 2026-09-11 取证已判定主因是 **ours 认领记录被误清空**（不是暗耗）：
> v9.1 换成持久位图后，`v8_scene_sig_changed()` 把 DISPCNT 也比进去 ⇒ 进地图时
> （DISPCNT 0x0200→0x3F40，BGxCNT 全未变）把同一 UI 里刚写的 186 个认领整体抹掉 ⇒
> 641 次领号 0 成功。**v9.2 已把 DISPCNT 踢出判定**，只留 BGxCNT + mode。

---

## 相关代码

- 埋点实现：`src/util/gdb_patcher.py` → `_dump_scene_owner()` / `_bg_regs()` / `_bg_map_entries()`
- 监听点定义：`src/util/configs/POKEMON_RUBY_AXVJ00.yaml`（`gdb:` 段）
- 分配器：`configs/POKEMON_RUBY_AXVJ00/hook/src/text/tile_alloc.c`
