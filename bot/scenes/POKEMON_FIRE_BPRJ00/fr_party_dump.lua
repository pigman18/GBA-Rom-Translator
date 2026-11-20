-- ============================================================================
-- fr_party_dump.lua — 进队伍界面后 dump EWRAM/VRAM + 截图
--
-- 目的：验证「火红队伍名字渲染时，内存里的串是 F7 还是日文」。
--
-- 时序沿用 303_gdb_pc_fix.py 里已验证可进队伍界面的驱动：
--   标题(0x9F40) → A → 主菜单(0x3140) → UP → A → 存档确认(0x7F60)
--   → 连按 B 退掉 11 次 → START 开菜单 → DOWN → A 进队伍
-- 进队伍后 dc 实测 0x1740。
--
-- 产物（BOT_OUT 目录）：
--   party.png / party.ewram.bin / party.iwram.bin / party.vram.bin / party.pal.bin
-- ============================================================================
local OUTP = os.getenv("BOT_OUT") or "."
local K = { A = 1, B = 2, START = 8, UP = 64, DOWN = 128 }

local function setk(m) emu:setKeys(m) end
local function rd16(a)
    local ok, v = pcall(function() return emu:read16(a) end)
    if ok then return v end
    return 0
end

local logf = assert(io.open(OUTP .. "/party.log", "w"))
local function log(s) logf:write(s .. "\n"); logf:flush() end

local function wr(path, data)
    local f = assert(io.open(OUTP .. "/" .. path, "wb"))
    f:write(data)
    f:close()
end

local function dump(tag)
    wr(tag .. ".ewram.bin", emu:readRange(0x02000000, 0x40000))
    wr(tag .. ".iwram.bin", emu:readRange(0x03000000, 0x8000))
    wr(tag .. ".vram.bin",  emu:readRange(0x06000000, 0x18000))
    wr(tag .. ".pal.bin",   emu:readRange(0x05000000, 0x400))
    log("[DUMP] " .. tag .. " f=" .. emu:currentFrame())
end

local phase, hold, wait, dc_n, bn = "await_title", 0, 0, 0, 0

local function dc_is(want, k)
    local dc = rd16(0x04000000)
    if dc == want then dc_n = dc_n + 1 else dc_n = 0 end
    return dc_n >= (k or 8)
end

callbacks:add("frame", function()
    local f = emu:currentFrame()
    if hold > 0 then hold = hold - 1; if hold == 0 then setk(0) end; return end
    if wait > 0 then wait = wait - 1; return end

    if phase == "await_title" then
        if dc_is(0x9F40, 10) then phase = "a1"; hold = 16; setk(K.A) end
        return
    end
    if phase == "a1" then phase = "await_menu"; return end
    if phase == "await_menu" then
        if dc_is(0x3140, 8) then phase = "up"; hold = 10; setk(K.UP); wait = 25 end
        return
    end
    if phase == "up" then phase = "a2"; hold = 16; setk(K.A); wait = 80; return end
    if phase == "a2" then
        if dc_is(0x7F60, 20) then phase = "press_b"; bn = 0 end
        return
    end
    if phase == "press_b" then
        bn = bn + 1
        if bn > 11 then phase = "open"; hold = 16; setk(K.START); wait = 90; return end
        setk(K.B); hold = 10; wait = 40
        return
    end
    if phase == "open" then phase = "down"; hold = 16; setk(K.DOWN); wait = 40; return end
    if phase == "down" then phase = "enter"; hold = 16; setk(K.A); wait = 260; return end
    if phase == "enter" then
        log("[PARTY] dc=" .. string.format("%04X", rd16(0x04000000)) .. " f=" .. f)
        emu:screenshot(OUTP .. "/party.png")
        dump("party")
        wait = 60
        phase = "party2"
        return
    end
    if phase == "party2" then
        dump("party2")
        emu:screenshot(OUTP .. "/party2.png")
        log("[DONE] f=" .. f)
        phase = "idle"
        return
    end
end)
