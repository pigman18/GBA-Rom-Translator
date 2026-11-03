-- ============================================================================
-- fr_pair2.lua -- FireRed CN: dump text buffer + VRAM at the same frame
--
-- 修正（依据实测）：
--   1. 真文本缓冲的 code = (hi<<8)|lo，hi/lo 都应是"合理"值：
--      code < 0x0B00，且 hi <= 0x0A（字库只有 11 个 256 字块）
--   2. 逐个 0xF7 校验，不再只看"连续 3 个 0xF7"
--   3. 同时扫 IWRAM(0x03000000) 和 EWRAM(0x02000000)
-- ============================================================================
local OUT = os.getenv("BOT_SHOT_DIR") or "."
local frame = 0
local n = 0
local phase = "mash"
local last = 0
local function rd16(a) return emu:read16(a) end
local function log(s)
    local f = assert(io.open(OUT .. "/fr_pair2.txt", "a"))
    f:write(s .. "\n"); f:close()
end

local function scan(base, size, label)
    local data = emu:readRange(base, size)
    local hits = {}
    local i = 1
    while i < size - 9 do
        if data:byte(i) == 0xF7 then
            local hi = data:byte(i + 1)
            local lo = data:byte(i + 2)
            -- 合理 code：hi <= 0x0A（11 个块），且不是 0xFF
            if hi <= 0x0A then
                local j = i
                local codes = {}
                while j < size - 2 and data:byte(j) == 0xF7 do
                    local h = data:byte(j + 1)
                    local l = data:byte(j + 2)
                    if h > 0x0A then break end
                    codes[#codes + 1] = h * 256 + l
                    j = j + 3
                end
                if #codes >= 3 then
                    hits[#hits + 1] = { addr = base + i - 1, codes = codes }
                    i = j
                else
                    i = i + 1
                end
            else
                i = i + 1
            end
        else
            i = i + 1
        end
    end
    return hits
end

callbacks:add("frame", function()
    frame = frame + 1
    if phase == "mash" then
        if frame < 600 then
            if frame % 20 == 0 then emu:setKeys(1) else emu:setKeys(0) end
            return
        end
        emu:setKeys(0)
        phase = "cap"; last = frame
        log(string.format("start f=%d dispcnt=%04X", frame, rd16(0x04000000)))
        return
    end
    if frame - last > 30 and n < 20 then
        n = n + 1
        local base = string.format("%s/q_%03d", OUT, n)
        local f = assert(io.open(base .. ".vram.bin", "wb"))
        assert(f:write(emu:readRange(0x06000000, 0x18000))); f:close()
        local g = assert(io.open(base .. ".io.bin", "wb"))
        assert(g:write(emu:readRange(0x04000000, 0x60))); g:close()
        local h = assert(io.open(base .. ".pal.bin", "wb"))
        assert(h:write(emu:readRange(0x05000000, 0x400))); h:close()
        local r = assert(io.open(base .. ".iwram.bin", "wb"))
        assert(r:write(emu:readRange(0x03000000, 0x8000))); r:close()
        local e = assert(io.open(base .. ".ewram.bin", "wb"))
        assert(e:write(emu:readRange(0x02000000, 0x40000))); e:close()

        local a = scan(0x03000000, 0x8000, "iwram")
        local b = scan(0x02000000, 0x40000, "ewram")
        log(string.format("shot %d f=%d dispcnt=%04X iwram=%d ewram=%d",
            n, frame, rd16(0x04000000), #a, #b))
        for _, x in ipairs(a) do
            log(string.format("   I 0x%08X n=%d", x.addr, #x.codes))
        end
        for _, x in ipairs(b) do
            log(string.format("   E 0x%08X n=%d", x.addr, #x.codes))
        end
        last = frame
    end
end)
