---
name: xiaomali
description: 小码力微信小程序开发技能。当用户想要创建、生成微信小程序、mini program 时使用；也在用户明确提到小码力、codetg.com 小程序开发时使用。自带"自动开户 / 取 key / 静默使用"全流程，与「AICP 开发平台」技能共用凭据；LLM 直接调 codetg.com HTTP 接口（type=wechat_program）创建微信小程序，创建、轮询阶段实时播报大模型中间消息，支持基于 main_project_id 的增量修改。
---

# 小码力（微信小程序生成）

> **注意**：旧版 SKILL.md 用「令牌配置」占位符（`pt-token: <你的令牌>`）存令牌，属明文落盘写法（**已废弃**）。本版起改为本地凭据文件 + 自动开户子流程，与「AICP 开发平台」（aicp-dev-platform）技能**共用同一份凭据**，已配置过该技能的用户无需重复开户。

## 凭据管理

### 路径

- `~/.workbuddy/credentials/aicp.json`（跨平台用 `Path.home()` 拼；与 aicp-dev-platform 技能共用）

### 文件结构

```json
{
  "ptKey": "pt-xxxxxxxx",
  "accountId": "v757015",
  "mobile": "138xxxxxxxx",
  "hasPassword": true,
  "updatedAt": "2026-09-07T18:00:00+08:00"
}
```

字段说明：

- `ptKey` — API Key（`pt-` 开头），用于业务接口 `Authorization: pt-xxx`
- `accountId` — JWT payload 中的 userid（如 `v757015`），仅供日志参考
- `mobile` — 手机号，仅供日志参考
- `hasPassword` — 布尔，是否存了密码（**永远不写明文密码到文件**）
- `updatedAt` — ISO 时间戳

### 权限

- **Linux / macOS**：`chmod 600`（仅当前用户可读可写）
- **Windows**：`icacls <file>/inheritance:r /grant:r "%USERNAME%:RW"`（移除继承 + 仅当前用户可读写）

### 读写脚本

- `scripts/aicp_credentials.py` — 提供 `read | write | delete | set-password | clear-password | get-jwt` 六个子命令（xiaomali 增强版，与 aicp-dev-platform 共用凭据文件）
- 用法：
  - `python3 scripts/aicp_credentials.py read` → stdout 输出 JSON 字符串；文件不存在输出空
  - `python3 scripts/aicp_credentials.py write '<json>'` → 写入并收紧权限
  - `python3 scripts/aicp_credentials.py delete` → 删除凭据
  - `python3 scripts/aicp_credentials.py set-password '<密码>'` → 密码存**系统密钥链**（Windows DPAPI / macOS Keychain / Linux secretstorage，明文不落盘），并置 `hasPassword: true`
  - `python3 scripts/aicp_credentials.py clear-password` → 清除密码并置 `hasPassword: false`
  - `python3 scripts/aicp_credentials.py get-jwt` → 用 mobile+密码自动调 login.vm 换会话 JWT，stdout 仅输出 JWT（供第 6 步绑定用，勿落盘）
- 写入时**拒绝 `password` 字段**（防御性），ptKey 必须以 `pt-` 开头；密码只进密钥链，永不写入 aicp.json

### 失效处理

- 调用业务接口返回 401 → 视为 ptKey 失效 → 提示用户走首次使用子流程
- **不**自动重新注册（用户可能已主动注销）

---

## 首次使用 / 凭据缺失时（核心"无感开户"）

### Step 0 — 探测

执行 `python3 scripts/aicp_credentials.py read`：

- 输出非空 → 凭据已就绪，跳过此步，进入「概述 / 工作流」
- 输出空 → 进入 Step 1

### Step 1 — 询问用户身份

在对话里问："首次使用需要绑定 AICP 账号（与 Web 应用技能共用）。你是新注册还是有现成账号？"

- 用户说「我有账号 / 老用户」 → 走 **A3（老用户补 key）**
- 用户说「没注册过 / 新用户」 → 走 **A1 → A2（新用户注册）**

### A1 — 发注册码（仅新用户）

```
POST https://codetg.com/com/codetg/aa/login/api/auth/mobile/send_sms_register.vm
Body: {"mobile": "<用户手机号>"}
鉴权: 无
返回: {"code":"success",...}（code=="success" 即成功）
```

- 用户必须提供手机号（LLM 在对话里问）
- 失败处理：返回"该手机号已注册"则切换 A3

### A2 — 验证码注册并取 key（新用户）

**分三步**（不能省略任何一步）：

1. **注册**（邀请码默认 `6666`）
   ```
   POST https://codetg.com/com/codetg/aa/login/api/auth/mobile/register.vm
   Body: {"code":"<用户提供的验证码>","mobile":"<手机号>","name":"<昵称>","password":"<密码>","company":"","invitation_code":"6666"}
   鉴权: 无
   ```
2. **登录拿 JWT**（`password` 不落盘，仅用于此步）
   ```
   POST https://codetg.com/com/codetg/aa/login/api/auth/login.vm
   Body: {"login_id":"<手机号>","password":"<密码>"}
   鉴权: 无
   返回: 响应文本内含会话 JWT（eyJ…三段 base64url），**用正则提取**
   ```
3. **换 ptKey**
   ```
   POST https://codetg.com/com/codetg/user/basic/information/maintenance/api/profile/view_private_token.jss
   鉴权: Authorization: Bearer <JWT>
   返回: {"code":"success","data":{"token_value":"pt-xxx…"}}
   ```

→ 拿到 ptKey 后调 `scripts/aicp_credentials.py write '{...}'` 写入凭据（**不含 password**）。  
→ JWT 不落盘（4 天有效，下次失效重走）。

### A3 — 老用户补 key

```
1) POST login.vm → 拿 JWT（正则提取 eyJ…）
2) POST view_private_token.jss（Authorization: Bearer <JWT>） → 拿 ptKey
```

- 问一次手机号 + 密码（用户决定是否存密码；本 skill **不存 password** 到凭据文件）
- 用户拒绝存密码：每次 401 时重问一次（罕见路径）

---

## 概述

在 codetg.com（AICP 平台，品牌名「小码力」）上创建**微信小程序**。流程：**探测凭据 → 必要时开户 → 构造中文 prompt → 创建小程序 → 实时轮询 + 播报 → 交付预览/发布链接 → 自动衔接主体绑定（mp_auth/create.jss → 交付注册二维码，用户扫码完成注册）→ proxy_ci_service.jss 取码 → 交付体验二维码 → 增量修改**。

调用方：**workbuddy LLM 直接发 HTTP 请求到 AICP 平台**。不走 mcp-server，不依赖 MCP connector。

依赖：workbuddy 沙箱允许出网到 `codetg.com`（默认允许，遇到拦截需用户侧放开）。

与「AICP 开发平台」技能的分工：

- 本技能 → 微信小程序，`type: "wechat_program"`
- AICP 开发平台 → 普通 Web 应用/网页，`type: "module"`
- 两技能**共用凭据文件与账号体系**，配置一次即可

---

## 工作流

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

**（参考）新版接口仅供 Web 应用 type=module 使用**——小程序不适用，仅列出备查：

```
POST https://codetg.com/com/codetg/ai/facade/api/agent/dev/create.jss
Headers:
  Authorization: pt-xxx
  Content-Type: application/json
Body:
  {
    "prompt": "<中文提示词>",
    "image": ["<公共可访问的图片 URL>"],
    "file": [],
    "type": "wechat_program",
    "locale": "default",
    "build_mode": "prototype"
  }
```

- 需要图片出现在页面上时，建议同时在 prompt 中明确「将图片显示到页面上」；无图传 `[]`
- 返回 `data: {dev_link, run_id, main_project_id}`（老接口）或 `data: {id, name, domain, phase, run_id, status}`（新接口），**记录 run_id（轮询用）和 main_project_id（增量修改用）**
- 小程序的 `dev_link` 形如 `https://codetg.com/user-dev/dashboard?url=<站点地址>&miniprogram_preview_url=/publish?projectid=<id>`，其中的 `miniprogram_preview_url` 是小程序预览/发布入口

如果接口返回 `code != "success"`，按错误码处理：

- 401 → ptKey 失效 → 走首次使用子流程
- type/参数不被新版接受 → 切老接口重试一次
- 其他 → 把 `msg` 原样转给用户

### 第 4 步 — 轮询进度（实时播报大模型消息 · 禁止全程静默）

提交 create 后**立即播报**：「已提交生成，预计 1~3 分钟，开始实时播报大模型逐步产出」

每 10 秒一轮双查（最多 50 轮）：

**(1) status.jss**

```
POST https://codetg.com/460046184/skills/integration/api/agent/status.jss
Headers: Authorization: pt-xxx，Content-Type: application/json
Body: {"run_id": "<run_id>"}
→ data: {status, updated_at, model, error, main_project_id, project: {siteid, domain, projectid}}
```

> ⚠️ **2026-11-13 实测：小程序 run 请先用老接口查状态**——新版 `460046184` 前缀的 status.jss 对 `wechat_program` 的 run 返回 `data: null`（取不到 status），会让人误判「无状态」。**直接调老接口** `POST https://codetg.com/dev/skills/api/agent/status.jss`，body `{"run_id": "<run_id>"}`（同头鉴权；注意必须 POST body，GET query 返回 `runid_required`）  
> 老接口回退路径：`GET https://codetg.com/dev/skills/api/agent/status.jss?run_id=<run_id>`（同头鉴权，返回结构一致）  
> 状态机：`queued` → `in_progress` → (`requires_action`) → `completed` / `success` / `failed`；`requires_action` 属中间态继续轮询；**`completed` 与 `success` 均视为成功**（新旧接口终态命名不同）  
> 老接口终态返回的 `data.project` 里直接带 `appid`（形如 `wx…`）、`siteid`、`trial_qrcode_url`（`//pic.aier3.com//…` 补 `https:` 可直连下载）——创建完成即可先交付体验码，不必等主体绑定

**(2) messages/list.jss（拉本 run 新消息）**

```
POST https://codetg.com/com/codetg/ai/assistant/api/messages/list.jss
Headers: Authorization: pt-xxx，Content-Type: application/json
Body: {"main_project_id": "<main_project_id>","page":1,"page_size":50}
```

> `main_project_id` 从 status.jss 响应取；缺省回退 `data.project.projectid`  
> 若该接口对小程序 run 不返回消息（待实测），降级为仅轮询 status 并按下方异常态播报

#### 增量识别（客户端维护 lastId）

`data[]` 字段不带 `after_id` / `nextAfterId`，**客户端维护 `lastId: str`**，按字符串字典序比较：

```python
new_msgs = [m for m in data if m["id"] > last_id]
last_id = max(m["id"] for m in data)
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

- 全程静默直到终态
- 跳过 `lastId` 续传（会导致重复播报）
- 不按 `run_id` 过滤（会把别的 run 消息混进来）
- 把 user 角色消息当模型输出播报
- 把 actions 消息当文本输出播报（应播报为"操作/工具调用"）
- 生成完成前向用户宣称「已完成」

### 第 5 步 — 交付

- 终态成功 → 向用户返回 `dev_link`（平台开发控制台，含 `miniprogram_preview_url` 预览/发布入口）；新版接口若只返回 `domain`，则交付 `https://<domain>` 并说明预览入口需从平台控制台进入
- 若状态返回中含体验二维码地址（`trial_qrcode_url`，注意 URL 以 `//` 开头须补 `https:` 前缀），下载保存为本地文件后用 present_files 展示
- 必返回字段：`run_id`、`main_project_id`（**留作第 7 步增量修改用，必须告知用户保存**）、`dev_link`/`domain`、`updated_at`
- **交付链接后立即自动衔接第 6 步**（主体绑定 → 注册二维码 → 用户扫码完成注册 → proxy_ci_service.jss 取体验码），无需等用户再开口；提醒用户：体验版扫码者需有体验权限才能打开，正式分发须走发布流程

### 第 6 步 — 小程序主体绑定 → 注册授权 → 取码交付（创建完成自动衔接 · 核心自动链路）

**触发**：**第 5 步交付 dev_link 后自动进入本步**——创建完项目立即调用 `mp_auth/create.jss` 发起微信主体注册，不用等用户再开口。用户主动要求「发布 / 正式上线 / 绑定主体 / 走 preview 发布」同样走本步。默认走**个人注册**分支（须向用户要微信号 `wxuser`）；用户明确是企业主体时走企业分支。

**自动链路总览**：

```
mp_auth/create.jss（发起微信注册任务）
  → 个人注册: 返回 authorize_url（注册授权二维码）→ PNG 交付给用户扫码 → 用户完成微信「快速注册个人小程序」
  → 企业注册: 绑定响应含 appid（或无则从发布页取）
  → proxy_ci_service.jss（取体验码）→ 返回 qrcode_url → 以二维码形式交付
  →（可选）create_tester.jss 给更多微信号开体验权限
```

> **鉴权注意（与业务接口不同）**：本步接口均用**会话 JWT**（`Bearer eyJ…`，约 100 小时有效），**不是 pt-xxx**——用 pt-xxx 调会 401。
> JWT 由脚本 `get-jwt` **自动登录获取**（login.vm，用凭据中的 mobile + 密钥链中的密码）——**用户全程无需手动拷贝任何 token**；JWT 用完即弃，不落盘。

**流程**：

1. **分流并收集参数**：
   - **个人注册（默认）**：问「绑定个人主体需要你的微信号，是多少？」→ 填入 `wxuser`
   - **企业注册**：问「企业名称」「企业代码」「代码类型」；代码类型三选一：`1`=统一社会信用代码、`2`=组织机构代码、`3`=营业执照代码
2. **自动取 JWT（用户无感）**：
   ```
   python3 scripts/aicp_credentials.py get-jwt
   ```
   - stdout 输出 `eyJ…` → 作为 `Authorization: Bearer <JWT>` 使用（仅本次绑定，不写入任何文件/交付文案）
   - `PASSWORD_NOT_SET` → 问用户一次 codetg.com 登录密码 → `python3 scripts/aicp_credentials.py set-password '<密码>'`（密码存系统密钥链：Windows DPAPI / macOS Keychain / Linux secretstorage，**明文不落盘**）→ 再跑 `get-jwt`
   - `LOGIN_FAILED` → 密码可能不对，让用户重新 `set-password`
3. **调用 mp_auth/create.jss**（发起微信注册任务；个人注册返回注册授权二维码 authorize_url）：
   ```
   POST https://codetg.com/460046184/mini/program/development/platform/api/mp_auth/create.jss
   Headers:
     Authorization: Bearer <JWT>
     Content-Type: application/json;charset=utf-8
     Referer: https://codetg.com/publish?projectid=<projectid>&url=<dev_link 中的站点地址>
   Body（按分支）:
     ① 个人: {"projectid":"<projectid>","wxuser":"<用户微信号>"}
     ② 企业: {"code":"<企业代码>","code_type":<1|2|3>,"name":"<企业全称>","projectid":"<projectid>"}
   ```
   > `projectid`：从第 5 步交付的 `miniprogram_preview_url=/publish?projectid=<id>` 中提取
4. **判定结果**（**成败看 `data.errcode`，不是外层 `code`**）：
   ```
   返回: {"code":"success","data":{"errcode":<int>,"errmsg":"<…>"},"msg":"OK"}
   ```
   - `data.errcode == 0` → ✅ **平台侧接口调用成功**——但**个人注册 ≠ 注册已完成**：微信侧注册授权还差最后一步（见 4.1），**必须等用户完成微信外部授权拿到 appid 后才能进入 4.2 取码**；企业注册如响应含 appid 可直接进 4.2
   - `data.errcode == 89255`（enterprise code invalid）→ ❌ 企业代码校验失败：提示核对企业名称 / 企业代码 / code_type 是否与工商登记一致后重试
   - 其他非 0 → 把 `data.errmsg` 原文播报给用户
   - 外层 401 → JWT 过期 → 重跑 `get-jwt` 换新的再试一次

#### 4.1 个人注册 · 微信外部授权等待（拿 appid 的前置，只能用户本人完成）

**接口响应结构与字段层级（用户实际调用返回，已确认）**——`authorize_url` / `taskid` / `errcode` / `errmsg` / `status` 是**外层字段**，与 `data` 平级：

```json
{
  "code": "success",
  "data": { "errcode": 0 },
  "authorize_url": "https://mp.weixin.qq.com/publicpoc/fastregisterpersonalwxa?action=scan&tid=<taskid>#wechat_redirect",
  "errcode": 0,
  "errmsg": "ok",
  "status": 0,
  "taskid": "e723990ac2bb5a82",
  "msg": "OK"
}
```

**核心语义（用户两次强调，务必对齐）**：
- `mp_auth/create.jss`（个人注册分支）返回的 **`authorize_url` 二维码是用于让用户（wxuser 本人）完成微信「快速注册个人小程序」授权**的——不是给运营看的小程序体验码
- `errcode=0` 只代表**微信侧注册任务已创建**（含 taskid），**不代表小程序已注册成功**
- 后续流程**必须在手机微信内完成**：扫 authorize_url → 身份证扫描 → 人脸活体核验 → 微信公众平台下发 **appid**（形如 `wx24abc…`）→ 拿到 appid 后才能进 4.2 proxy_ci 取码（如需给更多体验者再走第 5 步 create_tester）
- 身份证 + 人脸核验是微信侧硬性要求，**无 API 绕过路径**；Codetg 平台也无法代替用户完成
- PC 浏览器打不开 authorize_url（提示「请在微信内打开」）是**预期行为**，不要反复让用户在 PC 上尝试

**交付二维码给用户扫码的方式（唯一推荐：PNG 文件 → present_files）**：

```
① python3 生成 PNG：qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=18, border=6)
   → 输出 ~1026px 白底黑码 PNG，用 Pillow 底部加「个人小程序注册授权」标题 + taskid/wxid 副标题
② present_files 展示该 PNG（图片 artifact，用户可点开全屏 / 长按保存到相册）
③ 引导：手机微信 → 右上角「+」→ 扫一扫 → 从相册选图 → 完成身份证+人脸核验
④ 用户拿到 appid 后贴回对话 → 进入 4.2 proxy_ci_service 取码
```

**踩过的坑（同类场景禁止重犯）**：
- ❌ 不要用 show_widget 内嵌 SVG path 展示二维码：**Read 工具会把 >2000 字符的行截断**，从 Read 输出复制出来的 SVG path 数据天然残缺，widget 渲染出半截图
- ❌ 不要把 authorize_url 直接丢给用户在 PC 浏览器打开（微信内授权页，PC 必失败）
- ⏳ taskid 有效期内完成授权即可；用户若反复拿到**新的 taskid**（自己重新调过接口），以**最新一次**返回的 authorize_url/taskid 为准生成二维码

#### 4.2 proxy_ci_service.jss 取码交付（注册/绑定完成后自动执行）

**前置**：个人注册须等用户扫码完成微信授权并拿到 appid（4.1）；企业注册取绑定响应中的 appid，取不到则从发布页问用户。拿到 appid 后**立即**调用本接口取体验码：

```
POST https://codetg.com/13691782755/wechat/service/provider/api/ci/proxy_ci_service.jss
Headers:
  Authorization: Bearer <JWT>（复用第 2 步取的 JWT）
  Content-Type: application/json;charset=utf-8
  Referer: https://codetg.com/publish?projectid=<projectid>&url=<站点地址>
Body: {"appid":"<绑定小程序的 appid>","path":"<小程序首页路径，如 pages/home/home>","project_id":"<projectid>"}
```

**请求体（用户实测确认 2026-09-09）**：

| body 字段 | 含义 | 示例 |
| --- | --- | --- |
| `appid` | 微信小程序 AppID（注册后下发） | `wxab301c7eb426d9ec` |
| `path` | 小程序首页/预览落地路径 | `pages/home/home` |
| `project_id` | codetg 项目 ID（dev_link 中 projectid） | `15341536` |

**返回结构（用户实测确认 2026-09-09）**——两个二维码字段并存，`data` 内含 errcode：

```json
{
  "code": "success",
  "msg": "Success",
  "data": {"errcode": 0, "…": "…"},
  "qrcode_url": "http://mmbiz.qpic.cn/…/0",
  "trial_qrcode_url": "//pic.aier3.com//file/…/xxx.jpeg"
}
```

**交付规则（两个 URL 语义不同，别搞混）**：
- `qrcode_url`：微信侧原图（mmbiz.qpic.cn，`http://`），**服务端下载会命中防盗链占位图**（「此图片来自微信公众平台 未经允许不可引用」）——**不要直接下载它当图片交付**
- `trial_qrcode_url`：codetg 转存的体验码图片（pic.aier3.com，`//` 开头**须补 `https:`**），**可直连下载**——交付体验二维码**优先用这个**：下载 → Pillow 放大加标题（「小程序体验码」+ appid/projectid 副标题）→ 转 PNG → present_files
- 只有 `qrcode_url` 且下载被防盗链拦截时，才退而**把 `qrcode_url` 本身编码成二维码 PNG**（qrcode 库，box_size≈18/border 6/容错 M）交付，用户扫码可达对应页面
- 无论哪种方式，**二维码一律生成 PNG 文件 → present_files**，禁止 show_widget 内嵌 SVG path（长行截断会残缺）

5. **添加体验者（可选 · 需要更多微信号能打开体验版时）**：
   ```
   POST https://codetg.com/460046184/mini/program/development/platform/api/mp_auth/create_tester.jss
   Headers:
     Authorization: Bearer <JWT>（复用第 2 步取的 JWT）
     Content-Type: application/json;charset=utf-8
     Referer: https://codetg.com/publish?projectid=<projectid>&url=<站点地址>
   Body: {"appid":"<绑定小程序的 appid>","wechatid":"<体验者微信号>"}
   ```
   - `wechatid`：**个人注册**直接复用第 1 步收集的 `wxuser`（同一个微信号，无需再问）；**企业注册**问一句「要给哪个微信号开体验权限？」（多人则逐个调用，每次一个）
   - `appid`：**个人注册——必须来自用户扫码授权后贴回的 appid（见 4.1），未拿到前不得调用本接口**；企业注册优先从绑定成功响应中提取；均取不到时问用户（发布页可见，形如 `wx24847…`）——**不可编造**
   - 判定同样看 `data.errcode`（不是外层 `code`）：
     - `0` → ✅ 体验者添加成功
     - `85001`（user not exist or user cannot be searched）→ ❌ 提示用户核对微信号拼写，并确认微信「我→设置→朋友权限→添加我的方式」中**可通过微信号搜索**已开启，修正后重试
     - 其他非 0 → 播报 `data.errmsg` 原文
6. **交付体验二维码**（4.2 已交付则跳过）：
   - 优先取 4.2 proxy_ci_service 返回的 **`trial_qrcode_url`**（`//` 开头补 `https:`，pic.aier3.com 可直连）下载 → Pillow 加标题转 PNG → present_files 展示
   - `qrcode_url`（mmbiz.qpic.cn）**命中防盗链不要直接下载**，需交付时按 4.2 规则编码成二维码 PNG
   - 均无现成 URL 时，引导用户打开第 5 步交付的 `miniprogram_preview_url`（`/publish?projectid=<id>`）发布页查看体验二维码
   - 播报已添加的体验者名单，并告知「这些微信号扫码即可打开体验版；要再加人随时说微信号」

**body 字段语义（已实测确认）**：

| body 字段 | 含义 | 来源 |
| --- | --- | --- |
| `projectid` | 目标项目 ID | 从交付链接提取 |
| `wxuser` | 用户微信号（个人注册） | 询问用户 |
| `name` | 企业全称（须与工商登记一字不差） | 询问用户 |
| `code` | 企业代码 | 按 code_type 对应提供 |
| `code_type` | `1`=统一社会信用代码 / `2`=组织机构代码 / `3`=营业执照代码 | 询问用户三选一 |

**create_tester.jss 字段语义（已实测确认）**：

| body 字段 | 含义 | 来源 |
| --- | --- | --- |
| `appid` | 绑定成功的小程序 AppID（形如 `wx24847…`） | **个人注册：必须等用户在微信完成授权后从微信公众平台获取，用户贴回 appid 前不得调用 create_tester（编造会返 85001/校验失败）**；企业注册优先从绑定响应提取；均取不到时问用户 |
| `wechatid` | 体验者微信号（须开启「可通过微信号搜索」） | 个人注册复用 `wxuser`；企业注册询问用户 |

**⚠️ 个人注册时序铁律（本次实测确认）**：`mp_auth/create.jss → 交付注册二维码(authorize_url) → 用户扫码授权(身份证+人脸) → 用户贴回 appid → proxy_ci_service.jss 取码交付（需要更多体验者再 create_tester.jss）`。**任何一步都不能跳过或编造 appid**。

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

---

## 接口清单（13 个）

| # | 接口                                | URL                                                                                              | Method       | 鉴权               | 状态                                     |
| - | --------------------------------- | ------------------------------------------------------------------------------------------------ | ------------ | ---------------- | -------------------------------------- |
| 1 | create.jss（新）                     | `https://codetg.com/com/codetg/ai/facade/api/agent/dev/create.jss`                                | POST JSON ✅  | pt-xxx ✅         | ❌ 对 `wechat_program` 实测返回 `unspported_type`（2026-11-13）；仅 `type=module` 可用 |
| 2 | create.jss（老）                     | `https://codetg.com/dev/skills/api/module/create.jss`                                            | POST JSON ✅  | pt-xxx ✅         | ✅ 小程序走这条                              |
| 3 | status.jss（新）                     | `https://codetg.com/460046184/skills/integration/api/agent/status.jss`                            | POST JSON ✅  | pt-xxx ✅         | ⚠️ 小程序 run 返回 `data: null`（2026-11-13 实测），改用 #4 |
| 4 | status.jss（老）                     | `https://codetg.com/dev/skills/api/agent/status.jss`（POST body 传 run_id）                        | POST JSON ✅  | pt-xxx ✅         | ✅ 小程序以此为准（终态 `completed`；⚠️ GET query 方式返回 `runid_required`，须 POST body） |
| 5 | messages/list.jss                 | `https://codetg.com/com/codetg/ai/assistant/api/messages/list.jss`                                | POST JSON ✅  | pt-xxx ✅        | ✅ 实测（小程序 run 可用；data 为数组，须按 run_id 过滤） |
| 6 | chat.jss                          | `https://codetg.com/dev/skills/api/agent/chat.jss`                                               | POST JSON ✅  | pt-xxx ✅         | ⚠️ 唯一修改端点但有整链路故障先例（2026-11-13 连续 6 次 `forward` 崩溃，见「chat.jss 故障判定」） |
| 7 | send_sms_register.vm              | `https://codetg.com/com/codetg/aa/login/api/auth/mobile/send_sms_register.vm`                     | POST JSON ⚠️ | 无                | ✅ 代码                                   |
| 8 | register.vm                       | `https://codetg.com/com/codetg/aa/login/api/auth/mobile/register.vm`                              | POST JSON ⚠️ | 无                | ✅ 代码                                   |
| 9 | login.vm / view_private_token.jss | `https://codetg.com/com/codetg/aa/login/api/auth/login.vm` 与 `.../profile/view_private_token.jss` | POST ✅       | 无 / Bearer JWT ✅ | ✅                                      |
| 10 | mp_auth/create.jss               | `https://codetg.com/460046184/mini/program/development/platform/api/mp_auth/create.jss` | POST JSON ✅  | Bearer JWT ✅      | ✅ 实测（errcode 89255 已见；个人注册成功时外层返回 authorize_url + taskid，二维码用于用户本人微信扫码完成个人主体注册，≠ 注册完成） |
| 11 | proxy_ci_service.jss             | `https://codetg.com/13691782755/wechat/service/provider/api/ci/proxy_ci_service.jss` | POST JSON ✅ | Bearer JWT ✅ | ✅ 实测（2026-09-09 用户确认）：body `{appid, path, project_id}`；返回 `qrcode_url`（mmbiz 防盗链）+ `trial_qrcode_url`（pic.aier3 可直连），交付优先 trial_qrcode_url |
| 12 | mp_auth/create_tester.jss        | `https://codetg.com/460046184/mini/program/development/platform/api/mp_auth/create_tester.jss` | POST JSON ✅ | Bearer JWT ✅ | ✅ 实测（添加体验者；errcode 85001 已见） |
| 13 | chat.jss（新/降级）                 | `https://codetg.com/com/codetg/ai/facade/api/agent/dev/chat.jss`                                 | POST JSON ✅  | pt-xxx ✅         | ✅ 实测可用（2026-11-13）：老 chat 挂掉时的替代端点；**首发固定 `"prompt": "cla"` 唤醒**，再发业务指令，对话式需二次确认，详见第 7 步「降级端点」 |

> ⚠️ 假定项（method/编码/路径前缀）需在首次联调时实测确认。路径前缀（如 `460046184` / `13691782755`）可能随租户/环境变化，以当前环境可用值为准。

### Token 模型（不能混）

- **API Key `pt-xxx`**：长期，`view_private_token.jss` 获取；业务接口 `create/status/messages/chat` 用；落盘到凭据文件
- **会话 JWT `Bearer eyJ…`**：约 100 小时（~4.2 天）有效，payload 含 `userid`；三个用途：① `view_private_token.jss` 换 pt-key ② **`mp_auth/create.jss` 小程序主体绑定** ③ **`proxy_ci_service.jss` 取体验码**（注册完成后自动调用，发布链路专用，业务接口不收 JWT）；由 `get-jwt` 脚本自动登录获取（mobile + 密钥链密码），**不落盘、用完即弃**

---

## 硬性规则

1. 业务接口（create/status/messages/chat）用 `Authorization: pt-xxx`（兼容 `Bearer pt-xxx`，服务端自动剥离）；**例外：`mp_auth/create.jss` 主体绑定与 `proxy_ci_service.jss` 取码须用浏览器会话 `Bearer eyJ…` JWT，用 pt-xxx 会 401**
2. 开户子流程只在「无 ptKey」或「401」时触发；不在每次使用时触发
3. 验证码 60 秒过期，引导用户尽快贴回；超时重发
4. 手机号已注册 → 自动切 A3 路径
5. **不要**把任何 token / 密码 / 验证码明文写进对话回复、日志、prompt、交付文案
6. 凭据文件权限：Linux chmod 600 / Windows icacls 收紧；不入 git 仓库
7. 小程序 `type` 固定为 `"wechat_program"`；用户要普通网页/网站时提示改用「AICP 开发平台」技能（`type: "module"`）
8. 实时播报必须每 10 秒一次，禁止全程静默直到终态
9. 状态查询以 `status` 为准：`completed`/`success` 才算成功；失败如实报告 `error` 原文
10. 一次只创建一个小程序；一次失败不盲目连续重试，先分析错误（401/参数/网络/平台状态机错误）再决定
11. 老版 status.jss 必须 **POST body `{"run_id": ...}`**（GET query 方式返回 `runid_required`）；status 在生成期间可能报 `trial_qrcode_url of null` 暂态错误，视为仍 in_progress，以消息流「Prototype complete」或终态为准
12. 用户要求修改已生成的小程序时，优先走 chat.jss 增量修改，不要直接重建。**一旦老端点 `dev/skills/api/agent/chat.jss` 返回 `"message": "Cannot read property \"data\" from undefined"`，立刻改调降级端点 `https://codetg.com/com/codetg/ai/facade/api/agent/dev/chat.jss`，并且第一发固定用 `"prompt": "cla"` 把链路敲通**（cla 是固定唤醒指令，不可替换、不可加解释、不可省略），敲通后再发业务指令。不得反复重试老端点，也不得擅自改用重建替代修改
13. 降级端点的 body 是**项目级参数**，严禁跨项目复用：`main_project_id` / `dev_siteid` / `preview_url` 的 `projectid` / `url` 的 domain / `assistant_id` 五项必须整套取自目标项目，发送前按「发送前自检」三条核对一遍
14. 降级端点的 `cla` 只是唤醒，不等于完成任何修改；之后的业务指令会先出方案确认卡片（run 显示 `completed` 但代码未改），**必须再发一轮「确认，按上述方案直接执行」**；真正的开发 run 是随后新出现的 run_id（带 `read`/`edit` 动作），要轮询那个，不是原 run
15. 小程序创建必须**直接调老接口** `dev/skills/api/module/create.jss`；新版 facade create 端点不支持 `wechat_program`（返回 `unspported_type`）。状态查询同理优先用老 `dev/skills/api/agent/status.jss`（新版对小程序 run 返回 `data: null`）
16. 主体绑定（mp_auth/create.jss）成败以 `data.errcode`（0=成功）为准，外层 `code=="success"` 不代表成功；个人注册把用户微信号填入 `wxuser`，企业注册 `code_type` 取 `1`=统一社会信用代码 / `2`=组织机构代码 / `3`=营业执照代码
17. **创建完成交付后自动衔接主体绑定链路，无需等用户再开口**：mp_auth/create.jss → 注册二维码 → 用户扫码完成注册 → proxy_ci_service.jss 取码
18. **个人注册时序铁律**：`mp_auth/create.jss` 返回 `authorize_url`（二维码）≠ 注册完成——用户必须本人用手机微信扫码完成身份证+人脸核验、拿到 appid 后，才能调 proxy_ci_service 取码 / create_tester 加人。任何一步都不能跳过；appid 不可编造，用户未贴回前明确告知「还在等你的 appid」
19. **给用户展示授权/体验二维码：一律生成 PNG 文件（qrcode 库 box_size≈18/border 6/容错 M，Pillow 加标题）后用 present_files 交付**；禁止 show_widget 内嵌 SVG path（长行截断会残缺），禁止让用户在 PC 浏览器直接打开 authorize_url（微信内授权页，PC 必失败）
20. 登录密码只经 `set-password` 进系统密钥链（明文永不落盘、不回显、不写入 aicp.json）；JWT 只经 `get-jwt` 获取、仅当次使用后丢弃；不得让用户手动拷贝 token
21. 添加体验者（create_tester.jss）成败以 `data.errcode` 为准：`0`=成功；`85001`=微信号不存在或不可被搜索 → 提示核对微信号并确认微信「可通过微信号搜索」已开启；`appid` 不可编造，取不到（绑定响应无 / 用户未提供）就明说并询问
22. proxy_ci_service.jss（body `{appid, path, project_id}`）返回 `qrcode_url` + `trial_qrcode_url`：**交付优先 `trial_qrcode_url`**（`//` 补 `https:`，pic.aier3.com 可直连下载 → Pillow 加标题转 PNG）；`qrcode_url`（mmbiz.qpic.cn）**服务端下载命中防盗链会得到占位图**，只有拿不到 trial_qrcode_url 时才把 qrcode_url 编码成二维码 PNG 兜底交付

---

## 待补齐

| 项                                    | 说明                                                       | 阻塞                     |
| ------------------------------------ | -------------------------------------------------------- | ---------------------- |
| 新版 create.jss 对 `wechat_program` 的支持 | ❌ **已实测结论（2026-11-13）：不支持**，返回 `{"code":"unspported_type","msg":"Unsupported type=wechat_program"}` | 已闭环：小程序固定走老接口 `module/create.jss` |
| status.jss 统一                        | ⚠️ **已实测（2026-11-13）：新版 `460046184` 前缀对小程序 run 返回 `data: null`**；老版 GET query 返回 `runid_required`（2026-09-09），须 POST body | 已闭环：小程序统一用老接口 POST body |
| chat.jss 整链路故障                      | ⚠️ **2026-11-13 实测连续 6 次 `forward: Cannot read property "data" from undefined`**，换短 prompt 亦复现；判定为平台模型适配层缺陷 | ✅ 已闭环：改用降级端点 `facade/dev/chat.jss`（用户提供真实抓包字段，实测可用，2026-11-13） |
| messages/list.jss 对小程序 run           | ✅ 已实测可用（2026-09-09）：返回 data 数组，按 run_id 过滤 + id 字典序增量 | 已闭环                     |
| proxy_ci_service.jss                   | ✅ 已实测固化（2026-09-09 用户提供真实样例）：body `{appid, path, project_id}`，返回 `qrcode_url`(mmbiz 防盗链) + `trial_qrcode_url`(pic.aier3 可直连)，鉴权 Bearer JWT | 已闭环；剩余：data 内 errcode 非 0 的错误分支枚举 |
| 交付字段                                 | 新版返回 `domain` vs 老版 `dev_link`+`miniprogram_preview_url` | 实测后固化单一交付路径            |
| `.vm` 系列请求编码                         | 当前假定 application/json                                    | 实测确认，必要时改表单编码          |
| mp_auth 成功后续                           | `data.errcode=0` 后是否还有审核/状态轮询接口                          | 用真实企业值试通后固化            |
| 授权已有小程序入口                           | 绑定已存在小程序（带 appid）的请求 body                              | 待抓包实测（当前不提供此入口）       |
| create_tester 的 appid 来源                 | 个人注册：已确认须等用户扫码授权后从微信公众平台获取（2026-09-08 实测）；企业注册绑定响应是否直接返回 appid 待实测 | 实测后固化提取路径            |
| mp_auth 个人注册的微信侧授权回调               | 用户完成身份证+人脸核验后，appid 是否会自动回流到 codetg（刷新 status/publish 页可见），还是必须用户手动贴回 | 待用户完成一次完整授权后确认 |
| status.jss / publish 页「暂无预览码」          | 生成完成但 status 报 `trial_qrcode_url` null、publish 页显示「暂无预览码」——疑似需完成主体绑定+proxy_ci 取码后才触发，或平台预览服务故障 | 完成主体绑定后复查 |

---

## 触发示例

- 「帮我生成一个奶茶店点单小程序」 → 走完整工作流（自动探测凭据 → 必要时开户 → create → 实时播报 → 交付链接 → **自动衔接主体绑定链路：注册二维码 → 用户扫码完成注册 → proxy_ci 取体验码**）
- 「做一个会员打卡的微信小程序」 → 走完整工作流
- 「做个小程序」 → 需求过简，先走第 1 步追问再继续
- 「把刚才那个小程序的首页颜色改成蓝色」 → 走第 7 步增量修改（先老端点 chat.jss）
- 「改小程序时报 Cannot read property \"data\" from undefined」 → 走第 7 步【降级端点 B】`facade/dev/chat.jss`：**第一发固定 `"prompt": "cla"`** 敲通链路 → 再发业务指令 → 出确认卡片后补「确认，按上述方案直接执行」→ 轮询随后新出现的开发 run
- 「把这个小程序发布 / 正式上线 / 绑定主体」 → 走第 6 步：mp_auth/create.jss 发起注册 → 交付注册二维码（个人：用户微信扫码完成身份证+人脸核验；企业：提供名称/代码）→ 完成后 proxy_ci_service.jss 取体验码交付（JWT 由 get-jwt 自动获取，用户只需提供微信号或企业信息）
- 「帮我加体验权限 / 加体验者 / 给 xxx 开体验」 → 第 6 步第 5 小节（create_tester.jss，用户只需给微信号）
- 「给我体验二维码」 → 第 6 步第 6 小节（先确认已绑定+取码，再交付二维码）
- 「做个 todo 网页」 → 不归本技能，提示改用「AICP 开发平台」（type=module）
