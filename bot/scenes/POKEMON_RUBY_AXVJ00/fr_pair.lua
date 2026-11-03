-- ============================================================================
-- fr_pair.lua -- FireRed CN: dump text RAM buffer + VRAM at the same instant
--
-- 目的（规则 3：bot 内存实证，不猜）：
--   同一帧同时拿到
--     A. RAM 里的文本 code 序列（0xF7 hi lo ...）
--     B. VRAM 里渲染出的字形位图
--   离线用整行 OCR（可靠）对齐 → code -> 汉字 精确映射
-- ============================================================================
local OUT = os.getenv("BOT_SHOT_DIR") or "."
local frame = 0
local n = 0
local phase = "mash"
local last = 0
local function rd16(a) return emu:read16(a) end
local function log(s)
    local f = assert(io.open(OUT .. "/fr_pair.txt", "a"))
    f:write(s .. "\n"); f:close()
end

-- 在 IWRAM 里找连续出现 >=3 个 0xF7 的起始地址
local function find_text_bufs()
    local base, size = 0x03000000, 0x8000
    local data = emu:readRange(base, size)
    local hits = {}
    local i = 1
    while i < size - 9 do
        if data:byte(i) == 0xF7 and data:byte(i + 3) == 0xF7 and data:byte(i + 6) == 0xF7 then
            -- 收集该段
            local j = i
            local cnt = 0
            while j < size - 2 and data:byte(j) == 0xF7 do
                cnt = cnt + 1
                j = j + 3
            end
            if cnt >= 3 then
                hits[#hits + 1] = { addr = base + i - 1, codes = cnt }
                i = j
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
        log(string.format("start capture f=%d dispcnt=%04X", frame, rd16(0x04000000)))
        return
    end
    if frame - last > 30 and n < 20 then
        n = n + 1
        local base = string.format("%s/p_%03d", OUT, n)
        local f = assert(io.open(base .. ".vram.bin", "wb"))
        assert(f:write(emu:readRange(0x06000000, 0x18000))); f:close()
        local g = assert(io.open(base .. ".io.bin", "wb"))
        assert(g:write(emu:readRange(0x04000000, 0x60))); g:close()
        local h = assert(io.open(base .. ".pal.bin", "wb"))
        assert(h:write(emu:readRange(0x05000000, 0x400))); h:close()
        local r = assert(io.open(base .. ".iwram.bin", "wb"))
        assert(r:write(emu:readRange(0x03000000, 0x8000))); r:close()

        local bufs = find_text_bufs()
        log(string.format("shot %d f=%d dispcnt=%04X bufcount=%d", n, frame,
            rd16(0x04000000), #bufs))
        for _, b in ipairs(bufs) do
            log(string.format("   buf 0x%08X codes=%d", b.addr, b.codes))
        end
        last = frame
    end
end)
