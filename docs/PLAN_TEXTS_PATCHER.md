# 方案：util/texts_patcher + 统一 YAML 配置（第 1 步）

## 配置文件

路径：[`src/util/configs/POKEMON_RUBY_AXVJ00.yaml`](../src/util/configs/POKEMON_RUBY_AXVJ00.yaml)

```yaml
game_id: POKEMON_RUBY_AXVJ00
game_code: AXVJ

texts:
  modules:
    - id: 属性名
      type: stride
      start: "0x1cbb0c"
      end: "0x1cbb65"
      read:
        stride: 5
      # …

# tiles:   # 预留
```

- 无 `_meta`
- 入口：`texts.modules`
- `game_id` / 单个 `game_code`

## 脚本

[`src/util/texts_patcher.py`](../src/util/texts_patcher.py)

```text
python src/util/texts_patcher.py export <rom.gba>
  [--config src/util/configs/<game_id>.yaml]
  [-o work/<game_id>/translate/texts.json]
```

- `id` = `{game_code.lower()}_` + md5(address+hex)[:12]（与原 `axvj_`+hash 同构）
- 默认输出：`configs/<game_id>/translate/texts.json`
- 单模块：`--module 物种名` → `texts_物种名.json`
- `modules`：**对象** `{模块id: {type,start,end,…}}`（不再是 id 列表）
- entries 字段顺序：id → module → address → byte_length → original → …
- 不含 `_axvj_module` / `category`

## 依赖

`pyproject.toml` 已加 `PyYAML>=6.0`
