-- 采集脚本：跑汉化版火红，进入对话文本画面，dump VRAM/EWRAM/PAL
-- 用法: mGBA.exe --script capture.lua rom.gba
-- 输出到 work/BPRJ/caps/

local OUT = "C:/code/Rom-Translator/work/BPRJ/caps/"

local function wr(path, data)
    local f = io.open(path, "wb")
    if not f then console:error("open fail " .. path); return end
    f:write(data)
    f:close()
end

local function num(n) return string.format("%04d", n) end

local frame = 0
local shots = 0
local plan = {
    -- 帧号 -> 动作标签
}
-- 每 120 帧按一次 A，持续推进对话；每 600 帧 dump 一次
callbacks:add("frame", function()
    frame = frame + 1
    if frame < 300 then return end

    -- 每 120 帧按一次 A（推进文本）
    if frame % 120 == 0 then
        emu:setKeys(0)  -- 先松开
    end
    if frame % 120 == 30 then
        emu:setKeys(1)  -- A 键
    end
    if frame % 120 == 45 then
        emu:setKeys(0)
    end

    -- 每 600 帧 dump
    if frame % 600 == 0 and shots < 20 then
        shots = shots + 1
        local tag = OUT .. num(shots)
        emu:screenshot(tag .. ".png")
        wr(tag .. ".vram.bin", emu:readRange(0x06000000, 0x18000))
        wr(tag .. ".pal.bin",  emu:readRange(0x05000000, 0x400))
        wr(tag .. ".io.bin",   emu:readRange(0x04000000, 0x60))
        wr(tag .. ".ewram.bin", emu:readRange(0x02000000, 0x40000))
        console:log(string.format("[CAP] %d f=%d", shots, frame))
    end

    if frame > 13000 then
        console:log("done")
        emu:exit()
    end
end)
