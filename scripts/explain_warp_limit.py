#!/usr/bin/env python3
"""说明「直接触发白屏」为什么不可靠，并给出真正可行的判断。

── 现状（2026-11-03 已实测的事实）──────────────────────────────────────
✅ `lastHealLocation`（SaveBlock1+0x1C）写入 **能保住**
   实测：写 `00 21 ff 00 44 07`（Route118 0:33 x68 y7）后，
   角色走出商店门，值依然是 `00 21 ff 00 44 07`，没被覆盖。
✅ 它是 `DoWhiteOut()` 唯一的目标来源（源码）：
     Overworld_SetWarpDestToLastHealLoc();   /* = gSaveBlock1.lastHealLocation */
     WarpIntoMap();
✅ `WarpIntoMap` 全文件只有三处调用：白屏 / 传送术 / 秘密基地。

❌ 但「触发白屏」这一步，纯写内存做不到：
   · `DoWhiteOut` 是函数（0x08050648），mGBA Lua 没有函数调用接口
   · 硬塞 `sScriptContext1` 容易把脚本状态机弄坏（结构 0x74 字节、
     含状态/栈/指针，猜错一个字段就是死机或软锁）
   · 全员濒死需要改**加密后的**队伍 HP —— `gPlayerParty` 里读出来是
     密文（实测 gPlayerParty+0 是 `8d 89 8c 89 ...`），
     改之前要先按 Gen3 的 XOR 方案解密，改完再加密回去，
     还要重算 4 个校验子（checkword）—— 这是 PKHeX 级别的工作量

── 结论 ────────────────────────────────────────────────────────────────
「金手指传送」在**美版**上成立（网传 02031F84 那套码就是美版的），
在**日版 AXVJ** 上不成立：
  · 那套地址在 AXVJ 落在 gPokemonStorage 内部（实测，
    scripts/check_warpcode_origin.py 有书面证据）
  · 日版真正的 warp 变量 gWarpDestination 只有白屏/传送术/秘密基地会读，
    而这三条都由游戏自己发起

所以「跳到新场景」目前只有**走位**这一条实路。
这不是"没试出来"，而是被源码和地址归属两头夹住的结果。

用法：python scripts/explain_warp_limit.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot" / "tools"))


def main() -> int:
    print(__doc__)

    # 附：把已实测的三条路径结论复述一遍（防止后来人再试一遍）
    print("已试并证伪的路径：")
    print("  1. 改 SaveBlock1.location (+0x04)        → 被 gWarpDestination 覆盖")
    print("  2. 提前改 gWarpDestination (0x020297F8)  → 值保住但没人读（走门不读它）")
    print("  3. 改 SaveBlock1.pos (+0x00)             → 值变、画面不跟随")
    print("  4. 网传 02031F84 / 020322E4             → 落在 PC 箱子数据内，非 warp 变量")
    print("  5. lastHealLocation (+0x1C)              → ✅ 能写入并保住，但触发白屏做不到")
    print()
    print("下一步若仍要攻传送，唯一有希望的方向：")
    print("  实现 Gen3 队伍的 XOR 解密/加密 + checkword 重算，")
    print("  把全队 HP 改成 0，再主动触发一场战斗 → 白屏 → 走 lastHealLocation。")
    print("  工作量：等同于一个小型 PKHeX（约 200 行 + 大量验证）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
