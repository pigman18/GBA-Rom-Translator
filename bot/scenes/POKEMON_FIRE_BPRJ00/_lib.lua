-- ============================================================================
-- _lib.lua — POKEMON_FIRE_BPRJ00 场景共用构建器
--
-- 火红 phase-1：冷启动标题 → 主菜单，不读档。
-- 验收见 bot/SKILL.md（origin vs translated 看图）。
-- ============================================================================

local M = {}

function M.new()
    local S = {}
    local api = {
        S = S,
        tap = function(k, n, w)
            S[#S + 1] = { act = k, n = n or 4 }
            if w then S[#S + 1] = { act = "wait", n = w } end
            return api
        end,
        wait = function(n) S[#S + 1] = { act = "wait", n = n }; return api end,
        shot = function(name)
            S[#S + 1] = { act = "shot", n = 0, name = name }
            return api
        end,
        await = function(opt)
            opt = opt or {}
            assert(opt.dispcnt, "await 需要 dispcnt（DISPCNT 实测值）")
            S[#S + 1] = {
                act = "await",
                n = opt.timeout or 3000,
                addr = 0x04000000, value = opt.dispcnt,
                addr2 = opt.bg0 and 0x04000008 or nil, value2 = opt.bg0,
                tag = opt.tag or "await",
            }
            return api
        end,
        -- 读档场景必须调用：在 EWRAM 里搜存档身份字节，证明这份 .sav 真的被加载。
        -- 不调用时 run.py 会拒绝产出截图（"本侧对照无效"）。
        prove = function()
            S[#S + 1] = { act = "prove" }
            return api
        end,
    }
    return api
end

return M
