/* ============================================================================
 * diag_log.c — 字形落点追踪实现（对应 include/diag_log.h 的布局说明）
 *
 * 🔴 零行为影响：只写自己的 EWRAM 采样块，不碰 VRAM / tilemap / 引擎字段。
 * ==========================================================================*/
#include "diag_log.h"
#include "game.h"

#if CHS_TRACE

#define TR_MAGIC     0x32584441u   /* 'A','D','X','2' */
#define TR_WORDS     2048u         /* 8192 B */
#define TR_HDR       8u
#define TR_TBL_W     8u
#define TR_TBL_N     24u
#define TR_REC_W     5u
#define TR_RING_W    (TR_HDR + TR_TBL_W * TR_TBL_N)              /* 200 */
/* 环形条数**必须是 2 的幂**：freestanding 链接器没有 __aeabi_uidivmod，
 * 取模要换成 & (N-1)。 */
#define TR_RING_N    256u

static volatile uint32_t *tr(void)
{
    return (volatile uint32_t *)(uintptr_t)ADDR_TRACE;
}

static void tr_init(void)
{
    volatile uint32_t *r = tr();
    uint32_t i;

    if (r[0] == TR_MAGIC)
        return;
    for (i = 0u; i < TR_WORDS; i++)
        r[i] = 0u;
    r[0] = TR_MAGIC;
}

void trace_glyph(uint32_t win, uint32_t tpl, uint16_t tb, uint16_t off,
                 uint8_t cx, uint8_t cy, uint8_t ctx, uint8_t cty,
                 uint16_t t0, uint16_t t1, uint16_t prev,
                 uint8_t phase, uint8_t adv,
                 uint8_t tm, uint8_t ch)
{
    volatile uint32_t *r = tr();
    uint32_t i, idx, off_w, rec[TR_REC_W];

    tr_init();
    r[1] = r[1] + 1u;

    /* ---- 窗口表：登记 (win, tpl, tileData, map) 四元组 ---- */
    idx = 0xFFFFFFFFu;
    for (i = 0u; i < TR_TBL_N; i++) {
        off_w = TR_HDR + i * TR_TBL_W;
        if (r[off_w] == win) {
            idx = i;
            r[off_w + 4u] = r[off_w + 4u] + 1u;
            break;
        }
        if (r[off_w] == 0u && idx == 0xFFFFFFFFu)
            idx = i;
    }
    if (idx < TR_TBL_N) {
        off_w = TR_HDR + idx * TR_TBL_W;
        if (r[off_w] == 0u) {
            r[off_w]      = win ? win : 1u;
            r[off_w + 1u] = tpl;
            r[off_w + 2u] = tpl ? *(volatile uint32_t *)(uintptr_t)
                                  (tpl + TPL_TILE_DATA) : 0u;
            r[off_w + 3u] = tpl ? *(volatile uint32_t *)(uintptr_t)
                                  (tpl + TPL_TILEMAP) : 0u;
            r[off_w + 4u] = 1u;
            r[off_w + 5u] = tb;
            r[off_w + 6u] = (uint32_t)cx | ((uint32_t)cy << 8);
            r[3] = r[3] + 1u;
        }
    }

    /* ---- 环形记录（连续重复去重） ---- */
    rec[0] = win;
    rec[1] = (uint32_t)cx | ((uint32_t)cy << 8)
             | ((uint32_t)ctx << 16) | ((uint32_t)cty << 24);
    rec[2] = (uint32_t)tb | ((uint32_t)(off & 0x0Fu) << 12)
             | ((uint32_t)prev << 16);
    rec[3] = (uint32_t)t0 | ((uint32_t)t1 << 16);
    rec[4] = (uint32_t)phase | ((uint32_t)adv << 8)
             | ((uint32_t)tm << 16) | ((uint32_t)ch << 24);

    {
        uint32_t w = r[2] ? ((r[2] - 1u) & (TR_RING_N - 1u)) : 0u;
        volatile uint32_t *last = r + TR_RING_W + w * TR_REC_W;
        uint32_t same = 1u;

        if (r[2] != 0u) {
            for (i = 0u; i < TR_REC_W; i++) {
                if (last[i] != rec[i]) {
                    same = 0u;
                    break;
                }
            }
        }
        if (r[2] != 0u && same) {
            r[4] = r[4] + 1u;
            return;
        }
        w = r[2] & (TR_RING_N - 1u);
        last = r + TR_RING_W + w * TR_REC_W;
        for (i = 0u; i < TR_REC_W; i++)
            last[i] = rec[i];
        r[2] = r[2] + 1u;
    }
}

#else

/* 关闭时留一个空翻译单元，避免 ANSI-C 空文件告警 */
typedef int chs_trace_disabled_t;

#endif /* CHS_TRACE */
