# Plan: probe 命令 (hex 字符串搜索)

## 目标
通过 hex 字符串在 ROM 中搜索，自动定位数据并检测所有导出参数。

## 用法
```bash
# 输入从 mgba 复制的 hex 字符串
python row_patcher.py probe ROM.gba --hex "00000000909999998988888888888888"

# 支持带空格的 hex
python row_patcher.py probe ROM.gba --hex "00 00 00 00 90 99 99 99 89 88 88 88"
```

## 输出示例
```
=== Probe: 在 ROM 中找到 16 bytes 匹配 ===

位置: 文件偏移 0x7EE9C8 (GBA 0x087EE9C8)
压缩: lz77_swap (2693 → 5888 bytes)
格式: 4bpp
Sprite: 32x16 × 23
调色板: 0x087EF450 (3 banks, lz77_swap)
指针源: 0x0839747C

建议命令:
  python row_patcher.py export ROM.gba 0x087EE9C8 \
    --format 4bpp --sprite-size 32x16 --count 23 \
    --compression lz77_swap --palette 0x087EF450
```

## 搜索策略

### 1. 正向搜索 (在 ROM 中找 hex 字符串)
```python
hex_str = "000000009099999989888888"
search_bytes = bytes.fromhex(hex_str.replace(" ", ""))
matches = []
for i in range(len(rom) - len(search_bytes)):
    if rom[i:i+len(search_bytes)] == search_bytes:
        matches.append(i)
```

### 2. 定位 LZ77 数据块
找到匹配后，**向低地址搜索**找 LZ77 header (0x10):
```python
for back in range(match_offset, max(0, match_offset - 0x10000), -1):
    if rom[back] == 0x10:
        # 验证: 解压后是否覆盖 match_offset
        try:
            dec = lz77_decompress(rom[back:], swap=True)
            if dec and (match_offset - back) < len(dec):
                # 找到! 这是包含目标数据的 LZ77 块
                data_offset = back
                break
        except:
            continue
```

### 3. 分析找到的数据块
- 检测压缩格式 (standard/swap)
- 获取解压大小
- 推断 bpp、sprite 尺寸
- 搜索附近 palette
- 扫描指针源

## 输入验证

- hex 字符串最少 8 bytes (避免误匹配)
- 自动忽略空格、前缀 `0x`、换行符
- 如果找到多个匹配，全部列出，让用户选择

## 多匹配处理

```
=== 找到 3 个匹配 ===

  [1] 偏移 0x7EE9C8 (LZ77, 5888B) ← 推荐
  [2] 偏移 0x357575 (非压缩数据)
  [3] 偏移 0x5A3C00 (LZ77, 1024B)

使用哪个? (输入序号, 默认 1):
```

## 涉及文件

| 文件 | 改动 |
|------|------|
| `row_patcher.py` | 新增 `probe_hex()`, `find_lz77_back()`, `cmd_probe()`, CLI 参数 |
| `README.md` | 补充 probe 用法 |

## 验证
```bash
python row_patcher.py probe ROM.gba --hex "000000009099999989888888888888888888F88E"
# 应找到 0x7EE9C8, 输出完整 export 命令
```
