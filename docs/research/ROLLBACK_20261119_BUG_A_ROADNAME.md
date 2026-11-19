# ROLLBACK · 2026-11-19 · BUG-A 训练家详情道路名空白

> 记录两次失败补丁的 diff、症状帧、截图证据。按 `METHOD_WHY_SLOW_20261118.md` §1.2 规约落档。
> 结论：**BUG-A 未修复，工作区已回滚到 HEAD `f5ab01c` 基线，产物 ROM 需重打包回基线。**

## 根因（三重证据确认，非推测）

1. **反汇编**：`PrintLocation@0x080EB9C0` 读 `flag = blk[0x87CE]`；`cmp#0/cmp#1` 均不匹配（实测 flag=2）→ `b 0x80EBA32; pop{bx}` 直接返回。
2. **GDB 运行时**：`PC=0x80EB9CC r0=flag=0x00000002 r1=0x000087CE r2=blk=0x02000000 LR=0x08801D68`（LR 在 hook 区，证明是 DetailEnter hook 触发）。log: `navigator/20261119T101329_362460/translated/gdb_probe.log`。
3. **RAM dump**（ROM `8be7b0fe`，f130）：`blk+0x878C` = 说明串「身体保持健康」；f077（列表页）= 「118号道路」(`a2 a2 a9 f7...`)。

**关键机制**：`blk+0x878C` 是 `FormatListLine_hook` 的列表行缓冲（职业名+训练家名），不是地点串源。原版 `PrintLocation` flag=0 分支（`0x80EB9E0`）用 `sel` 取地点编号，经 `bl 0x80EF8AC`（`ConvertIntToDecimalString` + 后缀）**运行时生成**地点串写入 `blk+0x878C` 再打印。flag=2 时整段跳过。origin 进详情不重打，靠进领航员时打印的旧字模存活；汉化 hook 的 `init(LEFT_WIN)+scrub_list_arena()` 毁掉旧字模 → 全空。

**决定性新事实**：进详情时（f130 RAM）`sel@0x8772=0`、`blk[0x8942 + sel*4]` 地点编号表**已全清零**。因此 `flag=0` 分支即使执行，也只能生成「0番」——即**地点编号数据在进详情时已失效，重打路径本就不可用**。这是 origin 用 flag=2 跳过重打、靠旧字模存活的原因。

## 失败补丁 v1：直接 `Menu_PrintText(blk+0x878C, 1, 6)`

- **diff**：DetailEnter_hook.c 加 `menu_print_text_t` + `ADDR_MENU_PRINT_TEXT=0x0806F16C`，把第108行 `PrintLocation()` 替换为 `Menu_PrintText(blk+OFF_LIST_LINE=blk+0x878C, 1, 6)`。
- **build**：OK，game.bin 8892B；ROM SHA `99ae350f25b7cd73258820a892956c12b880f143358e6feaf31c271430b25f20`。
- **症状帧**：`navigator/20261119T101958_519658/translated/130.png` 左栏地点框显示「**香薰姐姐**」（训练家名残值），且文字溢出边框（撞UI）。墨量 0→253 但内容错误。
- **证伪原因**：`blk+0x878C` 是列表行缓冲，`Menu_PrintText` 延迟渲染时该缓冲已被覆写为训练家名。

## 失败补丁 v2：临时置 `flag=0` 调 `PrintLocation` 再恢复

- **diff**：第108行改为 `{ pflag=blk+0x87CE; saved=*pflag; *pflag=0; PrintLocation(); *pflag=saved; }`。
- **build**：OK，game.bin 8892B；ROM SHA `23b85ca4fbd39296f4db5d43ebc76b6e823793f047cfb4919e1f9498e0e61c94`。
- **症状帧**：`navigator/20261119T102545_852045/translated/130.png` 左栏显示「**0番**」+ 残字。
- **证伪原因**：进详情时地点编号表已清零（见决定性新事实），flag=0 分支生成「0番どうろ」。

## 下一步方向（未实施，需用户确认）

重打路径源数据已失效，两条重打假设均证伪。剩余方向：

1. **保住旧字模**（贴合 origin）：不让 `DetailEnter_hook` 的 `init(LEFT_WIN)+scrub_list_arena()` 毁掉列表页打印的地点字模。需确认 scrub 范围 `[tb+2, 0x1F0)` 是否波及地点 tile（窗 0x25 与列表窗 0x2F 是否同 charblock）。
2. **换数据源重打**：在 `blk` 内找进详情后未被覆盖的地点串来源，或改写 `0x80EF8AC` 的地点编号输入为正确的地图 location（`SaveBlock1.location`，bot prove 显示 `loc=0:33` = Route118）。
3. 上述都需先 GDB 精确定位，不得再凭反汇编碎片猜测。

## 证据日志

- GDB 探针点已加入 `src/util/configs/POKEMON_RUBY_AXVJ00.yaml`：`TE_PrintLocation_flag@0x080EB9CC`、`TE_PrintText_call@0x080EBA2A`（均 default:false，无害保留）。
- evidence_gate 已用真实证据登记并通过 R1-R4；两次失败已 `--falsify` 记录。
