# BUG-3 根因：训练家详情道路名不重打（2026-11-18）

## 现象

领航员 → 训练家之眼 → 详情页，左侧道路名框空白。
origin 显示「118ばん どうろ」，translated 无字。

## 实测数据

| 项 | origin | translated |
|---|---|---|
| 框内文字区墨量（x10-104, y50-64） | 182 px | 0（102 px 全在边框） |
| 有墨行 | y=44–53（文字）+ 57/58/69/70（边框） | 只有 57/58/69/70（边框） |
| 文字实际像素行 | y=43..53 → tilemap 行 5–6 | 无 |

## 根因链

### 1. 原版 `PrintLocation @0x080EB9C0` 按 flag 分支

反汇编（`0x080EB9C0`）：

```asm
80eb9c2: ldr r0,[pc,#20]   @ 0x083B4BAC  → 取 blk 指针
80eb9c4: ldr r2,[r0]
80eb9c6: ldr r1,[pc,#20]   @ 0x000087CE  → flag 偏移
80eb9c8: adds r0,r2,r1
80eb9ca: ldrb r0,[r0,#0]   @ flag = blk[0x87CE]
80eb9cc: cmp r0,#0
80eb9ce: beq 0x80eb9e0     @ flag=0 → 分支 A
80eb9d0: cmp r0,#1
80eb9d2: beq 0x80eba08     @ flag=1 → 分支 B
80eb9d4: b   0x80eba32     @ flag=其它 → **直接 pop/bx 返回，什么都不打**
```

### 2. 实测 flag = 2（两侧相同）

| ROM | `blk[0x87CE]` |
|---|---|
| origin | **2** |
| translated | **2** |

⇒ 原版在 flag=2 时**也不重打**。origin 能显示，是因为
**列表页打过、进详情时字模还在 VRAM 里存活**（代码注释也这么写：
「进详情 origin 不重打地点，靠旧字模存活」）。

### 3. 中文共块后旧字模被毁

我们的 12px 网格按屏幕位置分配 tile（`tile = TB+2+band*62+2*col`），
列表页和详情页共用同一 TB（实测都是 `0x0001`），所以：
- 列表页打的字模落在 TB+2+band*62+...
- 进详情后 `blank(0,9,11,16)` + 右栏重绘，覆盖了列表页的 arena
- 道路名对应的旧字模被销毁 → 屏上空白

### 4. hook 的补救无效

`PokeNav_TrainerEye_DetailEnter_hook.c:108` 试图补救：

```c
init(LEFT_WIN);
blank(LEFT_L=0, LEFT_T=9, LEFT_R=11, LEFT_B=16);
((void_fn_t)(ADDR_TE_PRINT_LOCATION | 1u))();   /* 想重打地点 */
```

但 `PrintLocation` 在 flag=2 时**直接返回**，这一行等于空操作。

### 5. 地点字符串数据本身是好的

`blk + 0x878C` 实测（translated 帧 130）：

```
+878c: 00 f7 00 0b cb f7 00 0c e6 f7 00 01 60 f7 00 02 58 ...
        ^^ 首字节 0x00，之后是完整 F7 中文串
```

⇒ **数据没坏，只是没被打印。**

## 修法（待实施）

不走 `PrintLocation` 的 flag 分支，在 hook 里自己把 `blk+0x878D` 的串
用 `Menu_PrintText(str, left=1, top=6)` 打出来。

关键约束：
- 原版调用参数是 `left=1, top=6`（反汇编 `0x80eba2a: movs r1,#1` / `0x80eba2c: movs r2,#6`）
- 窗口是 `LEFT_WIN = 0x25`
- 必须**先 `init(LEFT_WIN)`**（原版 `0x80eba1c: movs r0,#0x25` + `bl 0x806f158`）
- 串起点是 `blk + 0x878D`（跳过首字节 0x00），或按原版逻辑解析索引表

**风险**：`0x878D` 起的串长度未知，需先测出 FF 终止符位置。

## 下一步（最小验证）

1. 在 hook 里加 `Menu_PrintText(blk+0x878D, 1, 6)` 试验
2. bot 采 `navigator`，量框内文字墨量（目标 182）
3. 通过则整理提交；不通过则记录失败原因
