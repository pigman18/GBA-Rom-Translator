/* 由 scripts/gen_tm1_slots.py 生成 —— 勿手改 */
/*
 * 选中态（红色）汉字槽。当前为**空表**，原因：
 *   PTR 段只用于标签列，而标签不吃高亮（DrawOptionMenuChoice_hook
 *   只包装候选字符串，标签不走它 ⇒ ADDR_OPT_FG_COLOR 恒为 0）；
 *   候选列走 DYN，选中色只是换个前景色重画一遍，**不占额外 tile**。
 * 若将来 PTR 段要放会高亮的文本：把脚本里 need_sel 改成 True
 * 重新生成（会再吃掉 41*4 个 tile，需确认空间够）。
 *
 * ⚠ 若非空，本表必须与 kOptChsSlots **下标一一对应**。
 *   选中槽若按“组内第几个字”共用一小撮槽（旧实现），光标一移动
 *   就会顶掉旧选中行仍在引用的那批槽 → 文字替换。必须 per-glyph。
 */
static const struct { uint16_t glyph; uint16_t slot; } kOptChsSelSlots[1] = {
    { 0xFFFFu, 0x0000u },   /* 哨兵：glyph 0xFFFF 永不命中 */
};
