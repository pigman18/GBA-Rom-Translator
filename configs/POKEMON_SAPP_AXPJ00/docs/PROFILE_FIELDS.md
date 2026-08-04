# modules.inject.json（write.op）

- `write.type=op` + `write.op` → `F9 <op> hi lo`，op 须在 **0x01..0x7E**
- 默认短语：`F9 80 hi lo`（不配 write.op；表内为 F9 00+PCS 流）
- `F9 00` = 侧载；裸 `FA..FF` = PCS，禁止作通道
