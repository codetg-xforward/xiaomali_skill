# 修改已有微信小程序

### 第 7 步 — 增量修改（用户要求改已生成小程序时）

> 🔀 **双端点，先老后新**：先调下方「端点 A」；一旦它的返回出现 `"message": "Cannot read property \"data\" from undefined"`（或等价 `forward` 堆栈崩溃），**立刻切「端点 B」**（`/com/codetg/ai/facade/api/agent/dev/chat.jss`），并按「降级端点」里写的固定动作先发 `"prompt": "cla"`。
>
> ⚡ **核心定律（用户实测确认，已多次复现）**：只要是 `Cannot read property "data" from undefined` 这类转发层崩溃，**固定用 `"prompt": "cla"` 去打端点 B 就能把链路敲通**。`cla` 不是业务指令、不是占位符、也不要替换成别的词——就是这一串字符，照发即可。


**端点 A（优先，同步式，一次调用即改）**

```
POST https://codetg.com/dev/skills/api/agent/chat.jss
Headers:
  Authorization: pt-xxx
  Content-Type: application/json
Body:
  {
    "main_project_id": "<创建时返回的 main_project_id>",
    "prompt": "<中文修改指令>",
    "image": ["<公共可访问的图片 URL>"]
  }
```

返回 `data: {app_name, run_id}`，用新 run_id 按第 4 步节奏轮询至终态后交付（老接口终态为 `completed`）。

- 拿不到 `main_project_id` 时才退而按新需求重新创建（先提示：「缺少项目 ID，本次将作为新应用创建」）
- 本技能的 chat.jss 为唯一已验证的增量修改端点；aicp-dev-platform（Web 应用）暂缺 chat.jss，故**修改 Web 应用不归本技能管**
- ⚠️ **chat.jss 有整链路故障先例**（2026-11-13 实测连续 6 次失败），判定方法与降级处理见下方「chat.jss 故障判定」

**端点 B（降级，对话式，需二次确认）**

```
POST https://codetg.com/com/codetg/ai/facade/api/agent/dev/chat.jss
```

字段与坑位见「降级端点：facade dev/chat.jss」。要点：首轮只出方案确认卡片（run 会显示 `completed` 但代码没改），必须再发一轮「确认，按上述方案直接执行」才会真正开发。


#### chat.jss 故障判定（2026-11-13 实测）

**故障特征**（`status.jss` 的 `data.error` 原文）：

```json
{"error":true,"code":null,"message":"Cannot read property \"data\" from undefined",
 "details":"TypeError: Cannot read property \"data\" from undefined\n at forward (<eval>:25)\n at generateContent (<eval>:113)\n at generate (<eval>:161)\n at createChatCompletion (<eval>:167)\n at createChatCompletion (<eval>:13)\n at _executeRun (<eval>:430)"}
```

**判读要点**：

- `code: null` —— 不是业务错误码，排除 ptKey 失效、项目 ID 错误、提示词被拒
- 堆栈止于 `forward` → `generateContent` → `createChatCompletion`，是平台**调用大模型适配层**内部崩溃：读 `response.data` 时上游响应体为空/无 `data` 字段，平台未做空值保护
- 属**平台服务端缺陷**，本地改 skill / 换提示词 / 换参数均无效

**快速区分「接口故障」与「prompt 被拒」**：

1. 同一 prompt 连续失败 2 次 → 换一句极短指令（一行字）再试
2. 短指令仍在 12~30 秒内以同一堆栈失败 → 判定接口故障，**停止重试**
3. 若短指令能进 `in_progress` 并产出 actions → 是原 prompt 过长/内容问题，拆分后再试

**处置规则**：

- 判定接口故障后最多再等 75~90 秒重探 1 次；仍失败即**停止刷老端点，改走下方「降级端点」**
- 如实告知用户：错误原文 + 堆栈位置 + 判定依据（同模型 create.jss 当时是好的，故故障局限在 chat 链路）
- 给用户三条可选路径：① 等恢复（可挂定时重探）② 用 `module/create.jss` 重建一套（保留原项目作对照，代价是全新副本、细节可能与原版有差异）③ 用户在 codetg.com 网页端对同一 `projectid` 发同样修改指令（可能不走该坏接口，也能反证是否单点故障）
- **不可**声称「已改好」；不可编造修改后的效果

#### 降级端点：facade dev/chat.jss（2026-11-13 实测可用）

> 触发条件：老端点 `dev/skills/api/agent/chat.jss` 返回 `"message": "Cannot read property \"data\" from undefined"`（或等价 `forward` 堆栈崩溃）。

##### 第一步（固定动作）：用 `"prompt": "cla"` 唤醒链路

**做法**：套用下面「第二步」的完整 body 模板，把所有占位符按**目标项目**替换好（见字段来源表），只把 `prompt` 的值设为 `cla`，其余字段与鉴权保持与第二步一致（实测抓包里 `cla` 就是配着完整字段发的）。

```json
{
  "assistant_id": "<assistant_id>",
  "main_project_id": "<main_project_id>",
  "model": "",
  "prompt": "cla",
  "build_mode": "build",
  "current_files": [],
  "dev_siteid": "<dev_siteid>",
  "file": [],
  "image": [],
  "is_login": true,
  "module_name": [],
  "preview_url": "https://codetg.com/publish?projectid=<projectid>&url=https://<domain>/admin/dashboard#/",
  "reasoning_effort": "",
  "skills": [],
  "url": "https://<domain>"
}
```

- `cla` 是**固定唤醒指令**，用来把转发链路敲通。**不要改成业务指令，不要加解释，不要换成 cla 以外的词，也不要加中文说明或标点**。
- 这一发的目的不是改代码，所以**不要**指望它返回具体修改结果，也不要因为它只回了卡片/空动作就判定失败。
- 敲通之后，再把 `prompt` 换成真正的业务修改指令重发（其余字段原样复用）；之后按第三步处理确认卡片。
- **换项目时 `cla` 不变，但外围 5 个项目级字段必须整套换掉**（`main_project_id` / `dev_siteid` / `preview_url` 里的 `projectid` / `url` 里的 domain / `assistant_id`），详见下方字段来源表与发送前自检。
- 若连 `prompt: "cla"` 都报同样的 `Cannot read property "data" from undefined`，说明转发层当时整体不可用，此时才停止重试并告知用户（这种情况罕见）。

##### 第二步：发真正的修改指令（完整字段）

```
POST https://codetg.com/com/codetg/ai/facade/api/agent/dev/chat.jss
Headers:
  Authorization: pt-xxx
  Content-Type: application/json;charset=utf-8
Body（**全部是占位符，必须按目标项目逐个替换**）：
  {
    "assistant_id": "<assistant_id>",
    "main_project_id": "<main_project_id>",
    "model": "",
    "prompt": "<中文修改指令>",
    "build_mode": "build",
    "current_files": [],
    "dev_siteid": "<dev_siteid>",
    "file": [],
    "image": [],
    "is_login": true,
    "module_name": [],
    "preview_url": "https://codetg.com/publish?projectid=<projectid>&url=https://<domain>/admin/dashboard#/",
    "reasoning_effort": "",
    "skills": [],
    "url": "https://<domain>"
  }
```

**⚠️ 这些值都是「项目级」的，绝不可照抄别的项目的示例**

> 实测样例来自拍卖项目（`main_project_id=8708669`、`dev_siteid=S870164`、`projectid=15819958`、`domain=auction.aicp.chat`、`assistant_id=ass-502402`）。**换一个项目，这 5 个值全都得换**，否则会把别人的项目改坏或直接报错。

| 字段 | 从哪取 |
| --- | --- |
| `main_project_id` | 该项目第 3 步 create 时返回的 `main_project_id`（也是用户保存的那个 ID） |
| `dev_siteid` | 该项目上一次 chat 响应的 `data.dev_siteid`；注意实测它与 `status.jss` 的 `project.siteid` **可能不同**（曾见 `S870164` vs `S864193`），别混用 |
| `projectid`（在 preview_url 里） | 交付链接里 `miniprogram_preview_url=/publish?projectid=<id>` 的这个 id |
| `<domain>`（`url` 与 preview_url 的 url 参数） | `status.jss` 的 `data.project.domain`，拼成 `https://<domain>`；两处必须同域 |
| `assistant_id` | 该项目上一次 chat 响应的 `data.assistant_id`；首次调用没有历史值时，从 codetg 网页端该项目对话的请求里取。**不是全局常量** |
| `build_mode` | 固定 `"build"` |
| `model` / `reasoning_effort` / `skills` / `module_name` / `current_files` / `file` / `image` | 固定空值，原样照抄 |
| `is_login` | 固定 `true` |

**发送前自检（三条，缺一不可）**：

1. `main_project_id` 必须是**当前要改的那个项目**，不是上一次改过的项目
2. `preview_url` 里的 `projectid` 与 `main_project_id` 必须属于**同一项目**（对不上会改错对象）
3. `url` 与 `preview_url` 的 `url` 参数必须**指向同一个 domain**（对不上可能静默失败）

> 若手上只有 `main_project_id`，拿不到 `dev_siteid` / `domain`：先调 `POST /dev/skills/api/agent/status.jss`（body `{"run_id": "<该项目最新 run_id>"}`）读 `data.project` 取 `domain` / `siteid`；或让用户从 codetg 控制台该项目的对话请求抓一次包。

**返回**：`data: {run_id, assistant_id, dev_siteid, workspaceid, app_source_url, root_path, app_name}`

##### 第三步：处理确认卡片并轮询真正的开发 run

发业务指令后**通常不会直接改代码**，而是：

1. **出方案确认卡片**：通常只返回 `pushMessageCard` 动作 + 一段「我已把方案整理成确认卡片」的说明，run 状态即为 `completed`——**但代码一行没改**。不要把这个 `completed` 当成"改好了"。
2. **替用户回确认**：再发一轮，`prompt` 填「确认，按上述方案直接执行，不要再次询问」（用户诉求明确时可直接替他确认，不必让他再点；涉及删数据/改业务逻辑等破坏性变更才回来问）。
3. **派发开发**：这一轮会依次出现 `edit /doc/analysis/business_requirement.md`（存需求文档）→ `developWechatMiniProgram`（派发开发任务）→ 一条「开发任务已启动（约 15 分钟，完成后预览二维码页面会自动更新）」的说明。此时该 run 仍是 `completed`，**真正的开发是另一个新 run**。
4. **捞真正的开发 run**：拉 `messages/list.jss`，取最新一个**不在你已知 run_id 里**的 `run_id`（实测为 `run_566408` 这类），其消息含 `read` / `list` / `edit` 动作。用该 run_id 走老 status.jss 轮询。

**其它注意**：

1. **不要**只看 `completed` 就向用户宣布改完；判定"真的改了"的依据是：目标 run 里出现 `edit`/`write` 类 actions 且状态终态，或改后重新取体验码复核。
2. 轮询仍用**老接口** `POST /dev/skills/api/agent/status.jss`（body `{"run_id": ...}`）。
3. 返回的 `app_source_url`（形如 `https://codetg.com/p/auction?type=0`）是源码查看入口，可交付给用户。
4. **`https://<domain>` 这个域名不是小程序渲染页**（实测打开是平台后台的 Vue 页面，取不到小程序配色），别拿它验证改色结果；验证要走体验码 / 微信开发者工具。
5. 该端点对同一 `main_project_id` 是**追加对话**语义：上下文会累积，别重复发同一句指令（会产生多轮重复开发）。
