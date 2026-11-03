-- ============================================================================
-- fr_text.lua -- FireRed CN: boot -> mash A through intro -> capture frames
-- 用于抓取「操作说明」文字页的 VRAM（小字体实证）
-- ============================================================================
local OUT = os.getenv("BOT_SHOT_DIR") or "."
local frame = 0
local n = 0
local function rd16(a) return emu:read16(a) end
local function log(s)
    local f = assert(io.open(OUT .. "/fr_trace.txt", "a"))
    f:write(s .. "\n"); f:close()
end
callbacks:add("frame", function()
    frame = frame + 1
    if frame < 300 then
        if frame % 20 == 0 then emu:setKeys(1) else emu:setKeys(0) end
        return
    end
    -- 300 帧后：每 40 帧按 8 帧 A 并拍一帧
    local k = (frame - 300) % 40
    if k < 8 then
        emu:setKeys(1)
    else
        emu:setKeys(0)
        if k == 20 and n < 24 then
            n = n + 1
            local base = string.format("%s/fr_%03d", OUT, n)
            local f = assert(io.open(base .. ".vram.bin", "wb"))
            assert(f:write(emu:readRange(0x06000000, 0x18000))); f:close()
            local g = assert(io.open(base .. ".io.bin", "wb"))
            assert(g:write(emu:readRange(0x04000000, 0x60))); g:close()
            local h = assert(io.open(base .. ".pal.bin", "wb"))
            assert(h:write(emu:readRange(0x05000000, 0x400))); h:close()
            local r = assert(io.open(base .. ".iwram.bin", "wb"))
            assert(r:write(emu:readRange(0x03000000, 0x8000))); r:close()
            log(string.format("shot %d f=%d dispcnt=%04X", n, frame, rd16(0x04000000)))
        end
    end
end)
