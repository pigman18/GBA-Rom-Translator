-- ============================================================================
-- font_probe.lua — GDB 调试用探针（对话态常驻版）
--
-- 目的：让游戏**尽早进入对话并持续重绘**，这样 gdb 在 boot-wait 之后
--       下写观察点时，背景已加载完，下一次命中就是字模写入。
--
-- 时序（帧）：
--   0-120     等标题
--   标题      A
--   主菜单    A（读档）
--   野外      等 90 帧 → 按 A 触发对话
--   之后      每 60 帧按一次 A 推进文本，持续重绘
--
-- 用法：mGBA.exe -g --script font_probe.lua rom.gba
-- ============================================================================
local frame = 0
local phase = "boot"
local last  = 0

local function rd16(a) return emu:read16(a) end

callbacks:add("frame", function()
    frame = frame + 1

    if phase == "boot" then
        if frame > 120 then
            emu:setKeys(0)
            if rd16(0x04000000) == 0x1741 and rd16(0x04000008) == 0x180B then
                emu:setKeys(1); phase = "title_wait"
            end
        end

    elseif phase == "title_wait" then
        if frame % 30 == 0 then emu:setKeys(1) else emu:setKeys(0) end
        if rd16(0x04000000) == 0x3140 and rd16(0x04000008) == 0x1F08 then
            emu:setKeys(1); phase = "menu_wait"
        end

    elseif phase == "menu_wait" then
        if frame % 30 == 0 then emu:setKeys(1) else emu:setKeys(0) end
        if rd16(0x04000000) == 0x7F60 then
            emu:setKeys(0); phase = "overworld"; last = frame
        end

    elseif phase == "overworld" then
        emu:setKeys(0)
        if frame - last > 90 then
            emu:setKeys(1); phase = "talk_press"; last = frame
        end

    elseif phase == "talk_press" then
        if frame - last < 10 then emu:setKeys(1) else
            emu:setKeys(0); phase = "talk_advance"; last = frame
        end

    elseif phase == "talk_advance" then
        -- 每 60 帧按 8 帧 A，持续推进文本
        if frame - last < 8 then
            emu:setKeys(1)
        else
            emu:setKeys(0)
            if frame - last > 60 then last = frame end
        end
    end
end)
