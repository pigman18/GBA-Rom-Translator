# DONT — 禁止事项

## 禁止将游戏特异性逻辑硬编码到 .py 文件中

### 规则
游戏名称（如 `"ruby_jp"`、`"POKEMON_RUBY_AXVJ00"`、`"firered"`）或任何游戏专属标识**不得出现在 `.py` 代码中**作为条件判断。

### 正确做法
所有游戏特异性差异必须通过 `.json` 配置文件的 **feature flag** 表达。

```json
// configs/pokemon_ruby_jp.json
{
  "features": {
    "seed_translate": true,       // 是否应用离线 seed 翻译
    "module_filter": true,        // 是否按模块过滤条目
    "name_tables": true,          // 是否注入宽化名称表
    "lz_scan": true,              // 是否在注入前扫描 LZ 段
    "gfx_ptr_restore": true       // 是否恢复被误改的 gfx 指针
  }
}
```

代码只按 feature key 查询：
```python
cfg = load_game_config(game_id)
features = cfg.get("features", {})
if features.get("seed_translate"):
    ...
```

### 例外
- `game_backends/` 下的 Backend ID 定义（唯一注册标识，非条件判断）
- CLI 中的 `"unknown"` / `"firered"` 默认值（通用消歧逻辑）

### 后果
每加一个新游戏，只需添加或修改一个 `.json` 文件，**代码一行不动**。任何违反此规则的修改将被拒绝。
