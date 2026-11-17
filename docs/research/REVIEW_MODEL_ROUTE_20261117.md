# 审图子代理模型路由（2026-11-17 确立，17:45 更新）

## 结论：当前可用路由

```
provider: qoder
model:    gfmodel          # 显示名 GLM-5.3-Flash · x0.10
```

**2026-11-17 17:45 实测**：`qoder/gfmodel` 读图正常、可全帧审图（105 对全部过目，产出
`pass=105 fail=0 suspect=0` 报告，并独立确认招式表第二行四招全出）。

## 已失效路由（不要再试）

| 路由 | 状态 |
|---|---|
| `dshgw/workbuddy/glm-5.3-flash` | ❌ 2026-11-17 17:00 后连续失败（账号积分耗尽） |
| `doubao/person-glm-5-3-flash-261111` | ❌ 同上，子代理无收尾消息即退出 |
| `trae/glm-5.3-flash` | ❌ 同上 |
| `opencode-free/glm-5.3-flash-free` | ❌ 读图失败，回 `{"vision_ok":false}`（免费额度/不收图） |

失效特征：子代理**无 closing message 直接 failed**，或回 `vision_ok:false` 且招式名为空串。
遇到这两种表现立刻换路由，不要重试同一条。

## 原始实测对比（2026-11-17 上午，同一张 origin/080.png）

| 路由 | 命中 | 响应时间 | 结论 |
|---|---|---|---|
| **`workbuddy/glm-5.3-flash`** | **6/7** | **5–46 s** | ✅ 当时可用（现已失效） |
| `glm-5.3-flash`（裸名） | 1/5 | 12–180 s | ❌ 多轮收不到图 |
| `trae/glm-5.3-flash` | 2/4 | 63–180 s | ❌ 频繁 180 s 超时 |
| `nuoda/glm-5.3-flash` | 0/1 | — | ❌ 网关 401 Invalid token |
| `opencode-free/glm-5.3-flash-free` | 0/1 | — | ❌ 免费额度耗尽 / 不收图 |

裸名 `glm-5.3-flash` 与 `trae/glm-5.3-flash` 都会在多数轮次回「图片被省略/未收到」，属**多模态丢图**，不能用于审图。

## 子代理调用写法（当前）

```
subagent(
    description="审图",
    provider="qoder",
    model="gfmodel",
    prompt="<按 bot/SKILL.md 审图>",
)
```

## 配置改动（已落盘，需重启 DSH 生效）

`~/.dsh/profiles/desktop/cordis.patch.yml`（备份 `cordis.patch.yml.bak_20261117`）：

1. `llm-pi-ai.config.providers` 新增 `dshgw` 段（缩进 6 空格，与 `nuoda` 同级）：
   ```yaml
   dshgw:
     displayName: DSH Local Gateway (8787)
     apiKeyEnv: DSH_GW_API_KEY
     api: openai-completions
     baseURL: http://127.0.0.1:8787/v1
     defaultContextWindow: 200000
     defaultMaxTokens: 32768
     models:
       - id: workbuddy/glm-5.3-flash
         name: 审图 · glm-5.3-flash (workbuddy, 支持读图)
         contextWindow: 200000
         maxTokens: 32768
         input: [ text, image ]
   ```
2. `subagent-model-selection-settings.config.allowedModels` 首项插入 `{provider: dshgw, model: workbuddy/glm-5.3-flash}`。

`~/.dsh/.credentials.yaml`（备份 `.bak_20261117`）新增：
```yaml
DSH_GW_API_KEY: sk-dsh-o-rllIuMuh2gPlOdm_DUc3bFj_X2S71W
```

## 关键约束：必须新开会话

DSH 的 `SubagentModelSelectionConfig` 只在 `agent/created` 且 `target.firstLiveSeq === 0` 时追加
`subagent/model-selection-policy` 事件。**已运行的会话永远拿不到策略**，`subagent(provider, model)`
会被 `assertAllowedModelSelection` 拒绝：

```
child LLM route "dshgw/workbuddy/glm-5.3-flash" is not allowed for this Session;
without a recorded model-selection policy, explicit selection is limited to the parent route
```

⇒ 重启 DSH 后**新建会话**，策略即自动写入，子智能体可直接指定上述路由。

## 子智能体调用写法

```python
subagent(
    description="审图",
    provider="dshgw",
    model="workbuddy/glm-5.3-flash",
    prompt="<按 bot/SKILL.md 审图>",
)
```

## 未改动项

- 未追加任何事件到运行中的会话日志（用户选择新开会话，不改历史）。
- `nuoda` provider 保留原样（其 key 已失效但未被引用）。
- 回滚：还原两个 `.bak_20261117` 文件即可。
