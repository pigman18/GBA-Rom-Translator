/* PokeNav_TrainerEye_SkipListRow_hook — 进详情时跳过列表行重画。
 *
 * origin @ 0x080EC364 仅被详情进入态 case4（0x080F23FC）调用：
 * FormatListLine + 红条标题后仍 bl 本函数重画一行列表。
 * 日文 8px 随后被详情字盖住；中文 12px 残墨留在详情上。
 * 本钩直接返回（唯一调用面 = 进详情），列表滚动仍走 0x080EBD2C。
 */
void PokeNav_TrainerEye_SkipListRow_hook_C(void)
{
}
