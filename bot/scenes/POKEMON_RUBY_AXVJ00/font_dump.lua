-- ============================================================================
-- font_dump.lua — 连续 dump VRAM/RAM（不依赖对话阶段判断）
--
-- 进野外后每 20 帧 dump 一次，跑够 30 秒即可拿到十几帧，
-- 期间脚本持续按 A 触发/推进对话。
--
-- 环境变量：BOT_OUTPUT（必填）
-- ============================================================================
local OUT = assert(os.getenv("BOT_OUTPUT"), "BOT_OUTPUT missing")
local frame = 0
local phase = "boot"
local last  = 0
local n     = 0
local next_dump = 0

local function rd16(a) return emu:read16(a) end
local function wr(path, data)
    local f = assert(io.open(path, "wb")); assert(f:write(data)); assert(f:close())
end
local function log(s)
    local f = assert(io.open(OUT .. "/trace.txt", "a")); f:write(s .. "\n"); f:close()
end

callbacks:add("frame", function()
    frame = frame + 1

    if phase == "boot" then
        if frame > 100 then
            emu:setKeys(0)
            if rd16(0x04000000) == 0x1741 and rd16(0x04000008) == 0x180B then
                emu:setKeys(1); phase = "title_wait"; log("title at " .. frame)
            end
        end
    elseif phase == "title_wait" then
        if frame % 30 == 0 then emu:setKeys(1) else emu:setKeys(0) end
        if rd16(0x04000000) == 0x3140 and rd16(0x04000008) == 0x1F08 then
            emu:setKeys(1); phase = "menu_wait"; log("mainmenu at " .. frame)
        end
    elseif phase == "menu_wait" then
        if frame % 30 == 0 then emu:setKeys(1) else emu:setKeys(0) end
        if rd16(0x04000000) == 0x7F60 then
            emu:setKeys(0); phase = "play"; last = frame; next_dump = frame
            log("overworld at " .. frame)
        end
    else
        -- play：每 60 帧按 8 帧 A，每 20 帧 dump
        if frame - last < 8 then
            emu:setKeys(1)
        else
            emu:setKeys(0)
            if frame - last > 60 then last = frame end
        end
        if frame >= next_dump and n < 30 then
            n = n + 1
            wr(string.format("%s/dump_%03d.vram.bin", OUT, n), emu:readRange(0x06000000, 0x18000))
            wr(string.format("%s/dump_%03d.ram.bin", OUT, n), emu:readRange(0x02020000, 0x20000))
            wr(string.format("%s/dump_%03d.io.bin", OUT, n), emu:readRange(0x04000000, 0x60))
            log(string.format("dump %03d frame=%d", n, frame))
            next_dump = frame + 20
        end
    end
end)
