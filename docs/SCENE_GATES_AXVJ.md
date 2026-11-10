# AXVJ 布局特例（text_scene）

只做一件事：少数界面不能跟原生 tm/font 走，用 `screen_*(win)` 认出来，在 **linear / floor / remap / mode2** 四处早期处理。

```c
static int screen_summary(TextPrinter *win)
{
    return tpl == 0x081BB5BC;
}
```

| 认窗 | 典型效应 |
|------|----------|
| `screen_battle` | Linear、不 remap、不抬 floor |
| `screen_summary` | 禁 MENU_BAND；remap UI+B（无▶） |
| `screen_shop_desc` | 强制 Linear + floor |
| `screen_shop_bag` | Linear + floor；AXVJ 列表 `TILE_BASE` 常 `<0x80`（非文档 `0x8A+14*row`） |
| `screen_bottom_msg` | 像素 Y≥0x68，或 tile Y 15..18（但排除背包名列：`tb<0x80` 且 left≠7/9，否则末行「丝×1巾」） |
| `screen_party_footer` | Mode2 y/band |
| `screen_menu_mode2` | font3+cb0/2 → Mode2 |

没有政策结构体、没有调度表。新增界面 = 加一个 `screen_*`，在对应效应函数里加一行 `if`。
