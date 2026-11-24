; =============================================================================
; battle 域 hook 订址桩
; -----------------------------------------------------------------------------
; ★ 2026-11-24：P03 / P10 已全部撤销，恢复 origin 行为。
;
; 【撤销记录 —— 实测证据，不要重走】
;
; ■ P03「HP 条昵称遮罩 CpuSet 长度 32B → 24B」（原 0x08041760 / 0x08042620 /
;   0x08042C38 三处池 .word 0x04000006）—— **已撤销，保持原版 0x04000008**。
;   理由（静态反汇编 + 像素实测）：
;     1. 三个血条名字函数的 CpuSet 步进都是 `lsls rX, rY, #6` = 64B = 2 个 tile，
;        源固定 32B（GetHealthboxElementGfxPtr(0x2B)）。砍到 24B 会让 tile1
;        只写 3/4 —— 字模本身就不完整，不是「保护汉字上半」。
;     2. elem 0x2B 实测（日版 ROM 0x0868F140）：
;           行0-1 00000000 透明
;           行2   66666666  ┐
;           行3   77777777  │ 血条框底色渐变
;           行4   33333333  │
;           行5-7 22222222  ┘
;        它是「擦除格子的底色条」，不是空格字形。
;     3. 像素实测（battle_move_anim 20261124T093454 / 020.png）：
;        拷 24B 时名字只余 6 行墨迹；恢复 32B 后 8 行 —— 24B 确实在切残字模。
;
; ■ P10「战斗血条名字改用 species 查新表」（原计划 hook 0x08042430 GetMonData）
;   —— **已撤销**。理由：0x0804242E `mov r2, sp` 的 sp 是 sub_80451A0 的局部
;   nickname[10]（pokeruby src/battle_interface.c:1497），只有 10 字节，
;   写 12B 中文名会溢出压坏相邻局部变量。真正的显示串 dst 是
;   0x08042440 `StringCopy(gDisplayedStringBattle + 3, nickname)` 的目标。
;
; 【BUG-12 真实根因（已由权威源码 + 反汇编 + 像素三方确认）】
;   pokeruby src/battle_interface.c:1545-1616 sub_80451A0():
;     ① RenderTextHandleBold(ptr, gDisplayedStringBattle)   ← 我们的 12px 引擎
;     ② if (GetMonData(pkmn, MON_DATA_LANGUAGE) == 1 && !isEgg) {
;          while (*p != EOS) {
;            if (*p == EXT_CTRL_CODE_BEGIN) p += GetExtCtrlCodeLength(p[1]) + 1;
;            else { CpuCopy32(GetHealthboxElementGfxPtr(0x2B),
;                             ptr + 0x40 * i, 32); i++; p++; }
;          }
;        }
;        for (; i < 7; i++) 补空格
;   中文名 F7 00 hi lo（4B/字）在第 ② 段被当成 4 个独立字节 ⇒ 1 个汉字吃掉
;   4 次 i++，3 汉字 = 12 次 >> 上限 7 ⇒ 只画出前 7 块，后面被截断。
;
;   三个平行实现的循环次数来源不同（全部反汇编实测）：
;     Alt1 0x080415A0  pool 0x08041760   cmp r5,r8
;     Alt2 0x08042408  pool 0x08042620   bl StringLength → r8 = len-6（按字节数）
;     Main 0x08042B14  pool 0x08042C38   movs r1,#7 → r8 = 7（固定 7）
;   ⇒ 只有 Alt2 会随中文变长而越界；Main 恒 7 次会截断；三个都要处理。
;
; 【修法（2026-11-24 实施，两个 hook）】
;   hook A  0x08042440  StringCopy(dst=gDSB+3, src=nickname)
;           → 换成「species 查中文名表写完整名」，绕开 nickname[10] 截断。
;   hook B  0x08042536  → 跳过 0x08042536..0x080425A6 整段 0x2B 覆盖，
;           直接到 0x080425A8（第二段 EWRAM→VRAM 拷贝，那一段是需要的）。
;   逻辑见 src/battle/NickFullName_entry.s。
; =============================================================================

; hook A：0x08042440 → 0x081B5060（距 1.45MB，bl 可达）
.org 0x08042440
    bl NickFullName_Tramp

.org 0x081B5060
NickFullName_Tramp:
    ldr r3, =(NickFullName_Hook | 1)
    bx  r3
.pool

; hook B：0x08042536 → 0x081B5070（距 1.45MB）
;   ★ 覆盖 0x08042536..0x08042538（movs r5,#3 / movs r7,#0 / cmp r7,r8 之前）
;   只覆盖 4 字节，保留 0x0804253A 起的 cmp/bcs（虽然被跳过，但保持字节完整性）
.org 0x08042536
    bl NickSkipTiler_Tramp

.org 0x081B5070
NickSkipTiler_Tramp:
    ldr r3, =(NickSkipTiler_Hook | 1)
    bx  r3
.pool

; hook C：0x080425CC  第二段循环次数 r8 改为「ceil(字数 x 9 / 8)」
;
; 原版 r8 = StringLength(buf+3) - 6。对日文 6 字节名 = 0，对中文就崩了：
;   长翅鸥 = fc0202 + 3x(f7 00 hi lo) + fc010b + b5 + ff = 20B
;   r8 = 20-6 = 14  =>  14 x 64B = 896B  写进只有 384B 的名字区
;   => 越界覆盖 HP 条/框体装饰（实机：上方出现整块白斑）
;
; 正确值：每字 9px，单元 = 8px 宽，所以
;   1字=2  2字=3  3字=4  4字=5  5字=6  6字=7
; 即 r8 = ceil(字数 x 9 / 8)，且硬上限 6（名字区 0x180 = 6 单元）。
; 名字区最多放 5 个汉字（5x9=45px -> ceil(45/8)=6）。
;
; 每轮仍按原版 64B 步进（r5=0..r8-1），渲染侧 p0/p1 的咬合逻辑负责
; 让相邻字共享边界单元（见 PrintNextChar_hook.c 的 grid_emit buffered 分支）。
.org 0x080425CC
    bl NickCopyCells_Tramp

.org 0x081B5080
NickCopyCells_Tramp:
    ldr r3, =(NickCopyCells_Hook | 1)
    bx  r3
.pool

; =============================================================================
; hook D：0x0804264A  敌方路径（备用）的 r8 定型 —— BUG-12 真根因
; -----------------------------------------------------------------------------
; 0x080425B8  bl GetBattlerSide / cmp r0,#0 / bne 0x0804262C
;   ⇒ 敌方 side=1 永远走备用路径 0x0804262C，其循环入口是 0x0804264A。
;   hook C 只补了主路径 0x080425CC（我方专用），备用路径的 r8 一直是
;   原版 StringLength(gDSB)-6 = 14（中文 3 字 20B），导致：
;     ① 14x64B=896B 写进 384B 名字区 ⇒ 越界读出血条框绿色渐变（绿色涂块）；
;     ② 备用路径 up=+1..+14 / dn=+9..+22 区间重叠 ⇒ 后半程 up 覆盖前半程 dn
;        ⇒ 汉字下半截全丢（破碎残字）。
; 修法：备用路径同样接管 r8 = ceil(字数*9/8)，硬限 6。
;   0x0804264A: 00 25 45 45 = movs r5,#0 ; cmp r5,r8（覆盖 4B，返回后重放）
;   返回地址 0x0804264E = bge.n ⇒ 跳 0x0804264F（bx 清 bit0 落回 0x0804264E）
; =============================================================================
.org 0x0804264A
    bl NickCopyCellsAlt_Tramp

.org 0x081B5088
NickCopyCellsAlt_Tramp:
    ldr r3, =(NickCopyCellsAlt_Hook | 1)
    bx  r3
.pool

; =============================================================================
; [P12] 遭遇文本「野生的XXX」：用 species 查新表写完整名
; -----------------------------------------------------------------------------
; 0x0811C7AA = bl GetMonData(mon, 2, sp)，是 FD 03（物种名占位符）的展开点。
; 源 nickname[10] 装不下 3 汉字 → 第 3 字只有半个，后面是越界残渣。
; 本 hook 换成「species → 新表 0x1EB0AF4」，完整名自带 FF，
; 后续 0x0811C7B0 的 StringCopyN 遇 FF 即停，不会截断。
;
; 0x0811C7AA → 0x08800000 距 7.2MB，超 bl 的 ±4MB，两级跳：
;   bl 到 0x081B504C（距 0.6MB）→ ldr/bx 到 game.bin
; 0x081B504C 在原版 355B 连续 0x00 空洞内，未被任何 .org 占用。
; =============================================================================

.org 0x0811C776
    bl NickSlot_Tramp

.org 0x081B504C
NickSlot_Tramp:
    ldr r3, =(NickSlot_Hook | 1)
    bx  r3
.pool
