# 配置包阶段说明

权威示例见 [`POKEMON_RUBY_AXVJ00/docs/PROFILE_FIELDS.md`](../POKEMON_RUBY_AXVJ00/docs/PROFILE_FIELDS.md)。

```text
configs/<game_id>/
  translate/
    modules.json            # dump 复制：addr_bands + offset/end
    modules.inject.json     # read / write.type / write.stride / line_width
```

- 名表 **offset/end** 在 dump；**count** 由 `(end-offset+1)/unit` 推导，不写 inject。
- `read.type`：`fixed_table` / `struct_table` / `ptr_table`。
- `write.type`：`auto` / `menu_grid` / `footer_grid` / `linear_alloc` / `local_slot`（中文写入行为）。
- `write.stride`：中文扩表行宽（原 `chs_stride`）。
