/*
 * PartyMenuDoPrintMonNickname_hook.c — 队伍界面宝可梦名改查中文表（BUG-13）
 *
 * ═══ 权威依据：pokeruby 源码 ═══
 * tools/pokeruby/src/party_menu.c:2567
 *   void PartyMenuDoPrintMonNickname(u8 monIndex, int b, const u8 *nameBuffer)
 *   { CpuFastFill(0, gTileBufferPtr, 0x400);
 *     Text_InitWindow8004E3C(&gWindowTemplate_81E6CAC, gTileBufferPtr, nameBuffer);
 *     CpuFastCopy(gTileBufferPtr, OBJ_VRAM1 + (monIndex * 0x400), 0x200); }
 * tools/pokeruby/src/text.c:3717
 *   Text_InitWindow8004E3C(tpl, tileData, const u8 *text)  ← text 是 const
 *
 * ═══ AXVJ 地址（GDB 实测）═══
 *   PartyMenuDoPrintMonNickname = 0x0806B288
 *   入口实测 12 次（6 只 × 2 次重绘）：
 *     r0 = monIndex (0..5), r1 = 0, r2 = nameBuffer(0x03007DC8)
 *   0x0806B2AA 处 r2=0x03007DC8 经 adds r1,r2,#0 传给 Text_InitWindow
 *
 * ═══ 设计：零副作用 ═══
 * 只用 r2 指向的 nameBuffer 内容反查，不调 GetMonData、不改 r0/r1。
 *
 * ═══ 为什么长度不成问题 ═══
 * Text_InitWindow8004E3C 的 text 是 const，只存进 win->text，
 * 之后由 PrintNextChar 逐字节解析 —— 而文本引擎已被 PrintNextChar_hook.c
 * 整体接管，按 F7 00 hi lo 解析，与源缓冲大小无关
 * ⇒ 换成 ROM 中文表条目后完全绕过 nameBuffer[12] 限制，
 *   4~5 字名也能完整显示（用户 2026-11-23 明确指示）。
 *
 * ═══ 存档 ═══
 * 完全不碰 nickname → 串回日版不乱码（与 P10/P12 同一原则）。
 *
 * ═══ 已证伪的旧路线（别再走）═══
 * ① hook 0x0803B11C（日文表 species*6）：GDB 命中 0 次。
 * ② PrintNextChar 字符流换源：WIN_STATE 到不了 END → 输入回调停摆。
 * ③ Text_InitWindow(0x08002C68) 入口：通用函数每场景 160 次 → 开始菜单卡死。
 * ④ 让 GetMonNickname 返回中文指针：调用者忽略返回值（实测）。
 * ⑤ 在 0x0806B2E4 改 r2：停摆。
 * ⑥ 本函数里调 GetMonData 算 species：队伍界面全黑。
 */
#include <stdint.h>

#define JP_SPECIES_TABLE   0x081CA354u
#define CN_SPECIES_TABLE   0x09EB0AF4u
#define SPECIES_COUNT      412u
#define JP_NAME_STRIDE     6u
#define CN_NAME_STRIDE     24u

/* 用 nameBuffer 里的日文物种名反查中文表条目地址；未命中返回 0。 */
uint32_t PartyName_LookupJp(const uint8_t *p)
{
    const uint8_t *jp = (const uint8_t *)(uintptr_t)JP_SPECIES_TABLE;
    unsigned sp;

    if (!p)
        return 0u;
    if (p[0] == 0xFFu || p[0] >= 0xF0u)   /* 空串 / 控制码 / 已是中文 */
        return 0u;

    for (sp = 1u; sp < SPECIES_COUNT; ++sp) {
        const uint8_t *cand = jp + sp * JP_NAME_STRIDE;
        unsigned i = 0u;

        for (; i < JP_NAME_STRIDE; ++i) {
            if (cand[i] != p[i])
                break;
            if (cand[i] == 0xFFu)          /* 连 FF 一起对上才算命中 */
                return CN_SPECIES_TABLE + sp * CN_NAME_STRIDE;
        }
    }
    return 0u;
}
