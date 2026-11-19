# 创建、轮询与交付

### 第 1 步 — 明确需求

确认四件事：小程序类型（默认 `wechat_program`=微信小程序）、目标用户、核心页面/功能（含 tabBar 结构）、风格偏好。
信息不全时一次性问清，问题不超过 3 个；用户给一句话需求时，最多追问一轮，其余做合理假设并在交付时说明。

### 第 2 步 — 构造中文 prompt

六段式结构：小程序类型与目标 → 页面结构（含 tabBar/导航）→ 功能与交互 → 真实内容 → 视觉风格 → 适配要求。
禁止用一句话 prompt（如「做个小程序」）调用 API。
不要编造业务数据；数据缺失时在 prompt 中使用明显占位符（如 `[Your Logo]`），交付时提醒用户替换。

### 第 3 步 — 创建小程序

**直接用老接口**（微信小程序 `wechat_program` 走这条；2026-11-13 实测新版会拒，见下方说明）：

```
POST https://codetg.com/dev/skills/api/module/create.jss
Headers:
  Authorization: pt-xxx
  Content-Type: application/json
Body:
  {
    "type": "wechat_program",
    "prompt": "<中文提示词>",
    "image": ["<公共可访问的图片 URL>"]
  }
```

> ✅ **2026-11-13 实测结论**：新版接口 `POST /com/codetg/ai/facade/api/agent/dev/create.jss` 对 `type=wechat_program` **明确拒绝**，返回 `{"code":"unspported_type","msg":"Unsupported type=wechat_program"}`（注意平台把 unsupported 拼成了 unspported）。该接口目前只支持 `type=module`（Web 应用）。**微信小程序不要先试新版，直接调老接口 `module/create.jss`**，可省一次无效请求。

- 需要图片出现在页面上时，建议同时在 prompt 中明确「将图片显示到页面上」；无图传 `[]`
- 返回 `data: {dev_link, run_id, main_project_id}`，**记录 run_id（轮询用）和 main_project_id（增量修改用）**
- 小程序的 `dev_link` 形如 `https://codetg.com/user-dev/dashboard?url=<站点地址>&miniprogram_preview_url=/publish?projectid=<id>`，其中的 `miniprogram_preview_url` 是小程序预览/发布入口

如果接口返回 `code != "success"`，按错误码处理：

- 401 → ptKey 失效 → 走首次使用子流程
- 其他 → 把 `msg` 原样转给用户

### 第 4 步 — 轮询进度（实时播报大模型消息 · 禁止全程静默）

提交 create 后**立即播报**：「已提交生成，预计 1~3 分钟，开始实时播报大模型逐步产出」

执行环境允许时，每 10 秒查一轮（最多 50 轮）。单次执行时间不足时记录查询所需的项目和运行标识，后续继续查询。

**(1) status.jss**

```
POST https://codetg.com/dev/skills/api/agent/status.jss
Headers: Authorization: pt-xxx，Content-Type: application/json
Body: {"run_id": "<run_id>"}
→ data: {status, updated_at, model, error, main_project_id, project: {siteid, domain, projectid}}
```

新版状态接口可能对小程序返回 `data: null`。使用上面的 POST JSON 查询。

> 状态机：`queued` → `in_progress` → (`requires_action`) → `completed` / `success` / `failed`；`requires_action` 属中间态继续轮询；**`completed` 与 `success` 均视为成功**（新旧接口终态命名不同）
> 老接口终态返回的 `data.project` 里直接带 `appid`（形如 `wx…`）、`siteid`、`trial_qrcode_url`（`//pic.aier3.com//…` 补 `https:` 可直连下载）——创建完成即可先交付体验码，不必等主体绑定

**(2) messages/list.jss（拉本 run 新消息）**

```
POST https://codetg.com/com/codetg/ai/assistant/api/messages/list.jss
Headers: Authorization: pt-xxx，Content-Type: application/json
Body: {"main_project_id": "<main_project_id>","page":1,"page_size":50}
```

> `main_project_id` 优先使用创建时保存的值，缺失时从状态响应的 `data.main_project_id` 获取。只有 `projectid` 时继续查询状态，直到拿到 `main_project_id` 后再查询消息。
> 若该接口对小程序 run 不返回消息，降级为仅轮询 status 并按下方异常态播报

#### 增量识别（客户端维护 lastId）

`data[]` 字段不带 `after_id` / `nextAfterId`，**客户端维护 `lastId: str`**，按字符串字典序比较：

```python
new_msgs = [m for m in data if m["id"] > last_id]
last_id = max((m["id"] for m in data), default=last_id)
```

初始 `lastId = ""`，每轮更新为 `data[]` 中最大 id。

#### 按 run_id 过滤

`data[]` 混多 run 消息，必须过滤：

```python
current = [m for m in data if m["run_id"] == current_run_id]
```

#### 播报规则（按 AICP 真实 content 三态）

| content 形态                          | 播报模板                                                                |
| ----------------------------------- | ------------------------------------------------------------------- |
| `content: "<p>html</p>"` 非空字符串      | 💬 `{stripHtml(content)[:60]}…`                                     |
| `content: [{type, text}]` 非空数组      | 💬 `{text[:60]}…`                                                   |
| `content: ""` + `actions: [...]` 非空 | 🔧 `{actions[0].action} {actions[0].file_path}：{actions[0].remark}` |
| `role: "user"`                      | 跳过（用户自己说的话不回放）                                                      |
| `role: "assistant"` + 全空            | 跳过（无意义记录）                                                           |

#### 异常态播报

| 场景                         | 播报                    |
| -------------------------- | --------------------- |
| 连续 3 轮无新消息且 status 未变      | ⏸ 大模型在思考，已等 Xs        |
| 跨过 5 分钟（约 30 轮）            | 🟡 仍在生成中，已等 5 分钟      |
| status=completed 或 success | ✅ 生成完成 → 立即进入第 5 步    |
| status=failed              | ❌ {error 原文} → 询问是否重试 |

#### 状态保留（必须跨轮）

- `currentRunId: str`
- `mainProjectId: str`
- `lastId: str`（消息 ID，单调递增）
- `elapsedSec: int`
- `lastTickAt: timestamp`

LLM 在多轮工具调用间用对话上下文保留这些状态。

#### 禁止

- 客户端支持中途更新时一直等到终态才反馈
- 跳过 `lastId` 续传（会导致重复播报）
- 不按 `run_id` 过滤（会把别的 run 消息混进来）
- 把 user 角色消息当模型输出播报
- 把 actions 消息当文本输出播报（应播报为"操作/工具调用"）
- 生成完成前向用户宣称「已完成」

### 第 5 步 — 交付

- 终态成功 → 向用户返回 `dev_link`（平台开发控制台，含 `miniprogram_preview_url` 预览/发布入口）；新版接口若只返回 `domain`，则交付 `https://<domain>` 并说明预览入口需从平台控制台进入
- 若状态返回中含体验二维码地址（`trial_qrcode_url`，注意 URL 以 `//` 开头须补 `https:` 前缀），按[二维码交付规则](../SKILL.md#交付二维码)保存并展示 PNG
- 必返回字段：`run_id`、`main_project_id`（**留作第 7 步增量修改用，必须告知用户保存**）、`dev_link`/`domain`、`updated_at`
- 按[技能入口](../SKILL.md#选择流程)衔接体验码交付。已有体验码时直接交付。需要新建主体时，按用户的意愿进入[主体绑定流程](publish.md)。体验版扫码者需要体验权限。
