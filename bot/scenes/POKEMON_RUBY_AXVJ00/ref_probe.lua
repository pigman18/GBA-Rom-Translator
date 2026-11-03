-- ref_probe.lua -- FireRed guide pages: press A only, advance steadily
local OUT = os.getenv("REF_OUT") or "."
local frame = 0
local phase = "boot"
local last = 0
local KEY_A = 1
local function rd16(a) return emu:read16(a) end
local function log(s)
    local f = assert(io.open(OUT .. "/ref_trace.txt", "a"))
    f:write(s .. "\n"); f:close()
end
callbacks:add("frame", function()
    frame = frame + 1
    if phase == "boot" then
        if frame > 150 then
            emu:setKeys(0)
            local d = rd16(0x04000000)
            if d ~= 0x0000 and d ~= 0x0080 then
                emu:setKeys(KEY_A); phase = "pa"; last = frame
                log(string.format("first-nonblank f=%d dispcnt=%04X", frame, d))
            end
        end
    elseif phase == "pa" then
        if frame - last < 12 then emu:setKeys(KEY_A) else
            emu:setKeys(0); phase = "wait"; last = frame end
    elseif phase == "wait" then
        emu:setKeys(0)
        if frame - last > 300 then
            emu:setKeys(KEY_A); phase = "pa2"; last = frame
            log(string.format("A2 f=%d d=%04X", frame, rd16(0x04000000)))
        end
    elseif phase == "pa2" then
        if frame - last < 12 then emu:setKeys(KEY_A) else
            emu:setKeys(0); phase = "wait2"; last = frame end
    elseif phase == "wait2" then
        emu:setKeys(0)
        if frame - last > 600 then
            emu:setKeys(KEY_A); phase = "adv"; last = frame
            log(string.format("adv-start f=%d", frame))
        end
    else
        -- adv: press A 12 frames every 120 frames, never B
        local n = frame - last
        if n < 12 then
            emu:setKeys(KEY_A)
        else
            emu:setKeys(0)
            if n > 120 then last = frame end
        end
        if frame % 240 == 0 then
            log(string.format("adv f=%d dispcnt=%04X bg0=%04X", frame, rd16(0x04000000), rd16(0x04000008)))
        end
    end
end)
