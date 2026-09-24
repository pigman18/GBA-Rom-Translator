-- ============================================================================
-- mgba_autodrive.lua —— mGBA 内置 Lua 输入驱动（规则 mgba-script-input-only.mdc 认可的方式）
--
-- 用法：把 qt.ini 的 [scripting] lastScript 指到本文件，mGBA 启动时自动加载。
-- 通过 emu:setKeys(mask) 喂按键（mask 与 KEYINPUT 按下位一致：
--   A=1 B=2 SELECT=4 START=8 RIGHT=16 LEFT=32 UP=64 DOWN=128 R=256 L=512）
--
-- 时间表由同目录的 .tmp/drive_plan.lua 提供（避免每次改脚本本体）：
--   SCHEDULE  = { {startFrame, endFrame, mask}, ... }
--   SHOTS     = { {frame, path}, ... }
--   END_FRAME = number
-- 若 .tmp/drive_plan.lua 不存在，就用内置的「只写探针文件」模式。
-- ============================================================================

local PROBE = "C:\\code\\GBA-Rom-Translator\\.tmp\\lua_probe.txt"

local function probe(msg)
    local f = io.open(PROBE, "a")
    if f then
        f:write(msg .. "\n")
        f:close()
    end
end

probe("lua_autodrive loaded, frame=" .. tostring(emu:currentFrame()))

local SCHEDULE, SHOTS, END_FRAME = {}, {}, nil
local ok, plan = pcall(dofile, "C:\\code\\GBA-Rom-Translator\\.tmp\\drive_plan.lua")
if ok and type(plan) == "table" then
    SCHEDULE = plan.schedule or {}
    SHOTS = plan.shots or {}
    END_FRAME = plan.end_frame
    probe("plan loaded: " .. #SCHEDULE .. " entries, end=" .. tostring(END_FRAME))
else
    probe("plan NOT loaded: " .. tostring(plan))
end

local frame = 0
local shots_done = {}

callbacks:add("frame", function()
    frame = frame + 1

    local mask = 0
    for _, s in ipairs(SCHEDULE) do
        if frame >= s[1] and frame <= s[2] then
            mask = mask | s[3]
        end
    end
    emu:setKeys(mask)

    for i, sh in ipairs(SHOTS) do
        if frame == sh[1] and not shots_done[i] then
            shots_done[i] = true
            local o = emu:screenshot(sh[2])
            probe("shot frame=" .. frame .. " -> " .. tostring(sh[2]) .. " ok=" .. tostring(o))
        end
    end

    if END_FRAME and frame >= END_FRAME then
        emu:setKeys(0)
        probe("reached END_FRAME=" .. END_FRAME .. ", holding")
        callbacks:clear("frame")
    end
end)
