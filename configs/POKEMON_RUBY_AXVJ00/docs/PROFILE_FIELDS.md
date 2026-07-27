# modules.inject.json（write.op）

- `write.type=op` + `write.op` → `F9 <op> hi lo`，op 须在 **0x01..0x7E**
- 默认短语：`F9 7F hi lo`（不配 write.op）
- `F9 00` = 侧载；裸 `FA..FF` = PCS，禁止作通道
