# GDB 抓崩溃现场 —— 操作说明

## 目标
放技能/换人黑屏时，PC 跑飞（如 0x04002DEA）。要定位根因，需要抓崩溃瞬间的
**PC / LR / SP** 寄存器 + 崩溃地址附近的调用信息。

## 你需要做的事（只做一次连接）

### 第 1 步：启动 mGBA + GDB server
```powershell
cd C:\code\GBA-Rom-Translator
& "tools\mGBA-0.10.5-win32\mgba-sdl.exe" -g "roms\outputs\POKEMON_RUBY_AXVJ00_translated.gba"
```
`-g` 启动 GDB stub，监听 **localhost:2345**。

（注意：把 ROM 路径换成你实际测的那个 ROM）

### 第 2 步：保持 mGBA 窗口，去游戏里操作到黑屏
（脚本连着会让游戏自动 continue 运行，你正常遇敌→选技能→触发黑屏）

### 第 3 步：黑屏/崩溃发生后告诉我
我这边会通过 cmd.txt 下发 `interrupt` + `info registers` 等命令，抓取崩溃现场。

---

## 我这边做的事

我运行（一次性）：
```powershell
cd C:\code\GBA-Rom-Translator\scripts
arm-none-eabi-gdb -batch -x gdb_loop.py
```
脚本会：
1. 连接 mGBA（localhost:2345）
2. 自动 continue 让游戏跑
3. 反复轮询 cmd.txt，我追加命令 + `__DONE__` 就执行，结果写到 out.txt

## 文件约定
- `cmd.txt`  我追加 GDB 命令（每行一条），末尾加 `__DONE__` 触发
- `out.txt`  执行结果（我读取）
- `cursor.txt` 内部游标（自动）
