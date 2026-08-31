/* ============================================================================
 * blend_glyph_harness.c — 宿主对拍 harness（clang/gcc 编译本机执行）
 *
 * 命令：
 *   selftest <N> <seed>
 *       N 个随机用例：blend_glyph_1bpp vs vendored 官方
 *       refpr_draw_tile_unshadowed（reference/pokeruby/draw_glyph_tile.c，
 *       用 -I tests/host 的 shim 头编译）逐位对拍，覆盖全部
 *       (width 0..8 × startPixel 0..7) × textMode {0,2}。全等输出
 *       "SELFTEST OK"，否则打印首个差异并 exit 1。
 *
 *   eval
 *       从 stdin 逐行读用例，逐行输出结果（tests/test_blend_glyph.py 的
 *       Python 参考实现对拍走这条通道）：
 *       输入: <fmt> <width> <sp> <bg> <fg> <d0..d7 hex8> <s0..s7 hex8> <rows hex>
 *             fmt=1: rows 8 字节(1bpp)；fmt=2: rows 16 字节(2bpp)
 *       输出: <adv> <d0..d7 hex8> <s0..s7 hex8>
 * ==========================================================================*/
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#include "text_render.h" /* shim：结构体仅服务 vendored 官方文件 */

/* blend_glyph.h 用 <>/"" 都行，这里直接带路径声明（避免 typedef 冲突） */
#include "../../work/POKEMON_RUBY_AXVJ00/build/include/blend_glyph.h"

/* vendored 官方原语（独立 TU 编译） */
int32_t refpr_draw_tile_unshadowed(struct GlyphBuffer *gb,
                                   struct GlyphTileInfo *glyphTileInfo);

static uint32_t rng_state;
static uint32_t dst_seed[8], spill_seed[8];
static uint8_t rows[8];
static uint8_t cols2[2];

static int fail(const char *tag, int width, int sp, int mode, int r, int which)
{
    printf("SELFTEST FAIL %s w=%d sp=%d mode=%d row=%d word=%d\n",
           tag, width, sp, mode, r, which);
    printf("  dst_seed:");
    for (r = 0; r < 8; r++) printf(" %08x", dst_seed[r]);
    printf("\n  spill_seed:");
    for (r = 0; r < 8; r++) printf(" %08x", spill_seed[r]);
    printf("\n  rows:");
    for (r = 0; r < 8; r++) printf(" %02x", rows[r]);
    printf("\n  cols2: %u %u\n", cols2[0], cols2[1]);
    return 1;
}

static uint32_t rnd(void)
{
    rng_state ^= rng_state << 13;
    rng_state ^= rng_state >> 17;
    rng_state ^= rng_state << 5;
    return rng_state;
}

static int run_selftest(long n, uint32_t seed)
{
    uint32_t buf[32];
    uint32_t cols16[16];
    struct GlyphBuffer gb;
    struct GlyphTileInfo info;
    long i;
    int width, sp, mode, r, bad = 0;

    rng_state = seed ? seed : 0x1234567u;

    for (i = 0; i < n && !bad; i++) {
        uint32_t ref_out[8], ref_spill[8];
        uint32_t my_out[8], my_spill[8];
        uint32_t exp_adv, got_adv;

        width = (int)(rnd() % 9u);
        sp = (int)(rnd() % 8u);
        mode = (int)(rnd() % 2u);

        for (r = 0; r < 8; r++) {
            dst_seed[r] = rnd();
            spill_seed[r] = rnd();
            rows[r] = (uint8_t)rnd();
        }
        cols2[0] = (uint8_t)(rnd() % 16u);
        cols2[1] = (uint8_t)(rnd() % 16u);
        memset(cols16, 0, sizeof(cols16));
        cols16[0] = cols2[0];
        cols16[15] = cols2[1];

        /* 官方副本 */
        memset(buf, 0, sizeof(buf));
        for (r = 0; r < 8; r++) {
            buf[r] = dst_seed[r];
            if (mode == 0)
                buf[16 + r] = spill_seed[r];
            else
                buf[8 + r] = spill_seed[r];
        }
        info.dest = buf;
        info.src = rows;
        memcpy(info.colors, cols16, sizeof(cols16));
        info.width = (uint8_t)width;
        info.startPixel = (uint8_t)sp;
        info.textMode = (uint8_t)(mode ? 2u : 0u);
        exp_adv = (uint32_t)refpr_draw_tile_unshadowed(&gb, &info);
        memcpy(ref_out, buf, 32);
        if (mode == 0)
            memcpy(ref_spill, buf + 16, 32);
        else
            memcpy(ref_spill, buf + 8, 32);

        /* 我方副本 */
        memset(buf, 0, sizeof(buf));
        for (r = 0; r < 8; r++) {
            buf[r] = dst_seed[r];
            if (mode == 0)
                buf[16 + r] = spill_seed[r];
            else
                buf[8 + r] = spill_seed[r];
        }
        got_adv = blend_glyph_1bpp(buf, (mode == 0) ? buf + 16 : buf + 8,
                                   rows, (uint32_t)width, (uint32_t)sp,
                                   cols2);
        memcpy(my_out, buf, 32);
        if (mode == 0)
            memcpy(my_spill, buf + 16, 32);
        else
            memcpy(my_spill, buf + 8, 32);

        if (exp_adv != got_adv)
            bad = fail("adv", width, sp, mode, 0, (int)exp_adv ^ (int)got_adv);

        for (r = 0; r < 8 && !bad; r++) {
            if (ref_out[r] != my_out[r])
                bad = fail("dst", width, sp, mode, r, r);
            if (ref_spill[r] != my_spill[r])
                bad = fail("spill", width, sp, mode, r, r);
        }
    }

    if (!bad)
        printf("SELFTEST OK (%ld cases, 1bpp vs official, mode0+mode2)\n", n);
    return bad;
}

static uint32_t parse_hex8(const char *s)
{
    uint32_t v = 0;
    int i;

    for (i = 0; i < 8; i++) {
        char c = s[i];
        uint32_t d;

        if (c >= '0' && c <= '9') d = (uint32_t)(c - '0');
        else if (c >= 'a' && c <= 'f') d = (uint32_t)(c - 'a' + 10);
        else if (c >= 'A' && c <= 'F') d = (uint32_t)(c - 'A' + 10);
        else d = 0;
        v = (v << 4) | d;
    }
    return v;
}

static int hexval(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

static int run_eval(void)
{
    char line[2048];

    while (fgets(line, sizeof(line), stdin)) {
        char *p = line;
        char *tok[128];
        int ntok = 0;
        int fmt, width, sp, bg, fg, r;
        uint32_t dst[8], spill[8];
        uint8_t rows[32];
        uint8_t cols16[16];
        uint32_t adv;

        while (*p == ' ' || *p == '\t') p++;
        if (*p == '\n' || *p == '#' || *p == '\0')
            continue;

        tok[ntok++] = p;
        while (*p && *p != '\n') {
            if (*p == ' ' || *p == '\t') {
                *p = '\0';
                p++;
                while (*p == ' ' || *p == '\t') p++;
                if (*p && *p != '\n')
                    tok[ntok++] = p;
            } else {
                p++;
            }
        }
        if (ntok < 1)
            continue;

        fmt = atoi(tok[0]);
        width = atoi(tok[1]);
        sp = atoi(tok[2]);
        bg = atoi(tok[3]);
        fg = atoi(tok[4]);

        for (r = 0; r < 8; r++)
            dst[r] = parse_hex8(tok[5 + r]);
        for (r = 0; r < 8; r++)
            spill[r] = parse_hex8(tok[13 + r]);

        {
            int nrows = (fmt == 4) ? 32 : ((fmt == 2) ? 16 : 8);
            int t;

            for (t = 0; t < nrows; t++)
                rows[t] = (uint8_t)hexval(tok[21 + t][0]) * 16u
                        + (uint8_t)hexval(tok[21 + t][1]);
        }

        cols16[0] = (uint8_t)bg;
        cols16[1] = (uint8_t)fg;
        cols16[2] = (uint8_t)fg;
        cols16[3] = (uint8_t)fg;

        if (fmt == 4) {
            /* colors[16] 由行尾附加段提供（真实 LUT 形态：0=bg/14/15=fg 等）*/
            int nrows = 32;
            int t;

            for (t = 0; t < 16; t++)
                cols16[t] = (uint8_t)atoi(tok[21 + nrows + t]);
            adv = blend_glyph_4bpp(dst, spill, rows, (uint32_t)width,
                                   (uint32_t)sp, cols16);
        } else if (fmt == 2) {
            adv = blend_glyph_2bpp(dst, spill, rows, (uint32_t)width,
                                   (uint32_t)sp, cols16);
        } else {
            adv = blend_glyph_1bpp(dst, spill, rows, (uint32_t)width,
                                   (uint32_t)sp, cols16);
        }

        printf("%u", adv);
        for (r = 0; r < 8; r++)
            printf(" %08x", dst[r]);
        for (r = 0; r < 8; r++)
            printf(" %08x", spill[r]);
        printf("\n");
        fflush(stdout);
    }
    return 0;
}

int main(int argc, char **argv)
{
    if (argc >= 2 && strcmp(argv[1], "selftest") == 0)
        return run_selftest(argc >= 3 ? atol(argv[2]) : 1000,
                            argc >= 4 ? (uint32_t)strtoul(argv[3], 0, 0)
                                      : 0x1234567u);
    if (argc >= 2 && strcmp(argv[1], "eval") == 0)
        return run_eval();

    fprintf(stderr, "usage: %s selftest <N> <seed> | eval\n", argv[0]);
    return 2;
}
