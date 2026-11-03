-- ============================================================================
-- fr_menu.lua -- FireRed CN: boot with save, mash A to overworld, press START,
-- capture VRAM frames of the menu screen (for font identification)
-- ============================================================================
local OUT = os.getenv("BOT_SHOT_DIR") or "."
local frame = 0
local n = 0
local phase = "mash"
local last = 0
local function rd16(a) return emu:read16(a) end
local function log(s)
    local f = assert(io.open(OUT .. "/fr_trace.txt", "a"))
    f:write(s .. "\n"); f:close()
end
callbacks:add("frame", function()
    frame = frame + 1
    if phase == "mash" then
        if frame < 600 then
            if frame % 20 == 0 then emu:setKeys(1) else emu:setKeys(0) end
            return
        end
        emu:setKeys(0)
        phase = "start"; last = frame
        log(string.format("press START f=%d dispcnt=%04X", frame, rd16(0x04000000)))
    elseif phase == "start" then
        if frame - last < 10 then emu:setKeys(0x08) else
            emu:setKeys(0); phase = "cap"; last = frame
        end
    else
        -- capture: every 30 frames, PNG + VRAM + io + pal, up to 12 shots
        if frame - last > 30 and n < 12 then
            n = n + 1
            local base = string.format("%s/m_%03d", OUT, n)
            emu:screenshot(base .. ".png")
            local f = assert(io.open(base .. ".vram.bin", "wb"))
            assert(f:write(emu:readRange(0x06000000, 0x18000))); f:close()
            local g = assert(io.open(base .. ".io.bin", "wb"))
            assert(g:write(emu:readRange(0x04000000, 0x60))); g:close()
            local h = assert(io.open(base .. ".pal.bin", "wb"))
            assert(h:write(emu:readRange(0x05000000, 0x400))); h:close()
            log(string.format("shot %d f=%d dispcnt=%04X bg0=%04X", n, frame,
                rd16(0x04000000), rd16(0x04000008)))
            last = frame
        end
    end
end)
