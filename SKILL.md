---
name: xiaomali
description: 通过 codetg.com 创建、查询或修改微信小程序、网页、落地页或 H5，并交付预览链接或体验二维码。用户提到小码力或 codetg.com，或要求用该平台绑定微信小程序主体、获取体验码时使用。
metadata:
  version: "1.1.0"
  display_name: "小码力"
  display_name_en: "xiaomali"
  title: "小码力 / xiaomali"
  description_zh: "小码力（codetg.com）生成技能：按用户提供的需求，在 codetg.com 上创建微信小程序或网页 / 落地页 / H5，创建与轮询阶段实时播报进度，完成后交付预览链接与体验二维码，并支持基于 main_project_id 的增量修改。账号注册可在技能内完成（`send-code` + `register`，须用户明确同意且验证码由本人提供）；主体绑定、扫码核验、页面确认等需现场身份的操作仍由用户在网页端完成。触发词：做个小程序、生成小程序、做个网页、落地页、官网、改样式、要体验码、小码力、codetg。"
  description_en: "Xiaomali (codetg.com) generation skill: with a requirement provided by the user, create a WeChat Mini Program or a web page / landing page / H5 on codetg.com, stream progress while creating and polling, then deliver a preview link and trial QR code; supports incremental edits via main_project_id. Account sign-up can be driven in-skill via SMS verification (send-code + register) once the user explicitly agrees and supplies the code; subject binding, QR verification and on-page confirmations still require the user in the web console. Triggers: build a mini program, build a web page or landing page, change style, get trial QR code, xiaomali, codetg."
  category: development
  tags: "微信小程序, 小程序生成, codetg, code generation"
---

# 小码力

## 运行环境

从本文件所在目录解析 `scripts/` 下的脚本。使用当前环境中的 Python 3.10+，Windows 示例使用 `python`，macOS / Linux 可使用 `python3`。执行环境需能访问 codetg.com。生成或处理二维码 PNG 时需 `qrcode` 和 Pillow，Linux 本地保存密码另需可访问的 Secret Service 和 SecretStorage。

向用户交付授权二维码或体验码时，用当前客户端支持的图片附件或本地 PNG 展示能力。在 Codex 桌面端可以使用带文件绝对路径的 Markdown 图片。二维码应可打开或保存，生成后检查图像完整。读取报错截图时，使用当前会话的附件或本地图片读取能力。

## 凭据与授权

先运行 `python scripts/aicp_credentials.py paths` 查看凭据模式和有效缓存位置。默认凭据目录为 `~/.xiaomali/credentials/`，旧 WorkBuddy 凭据可原地复用。显式目录与环境变量的用法见 [README.md](README.md)。

调用 `read`、`get-pt-key` 或 `get-jwt` 时，将完整凭据保留在发出 HTTP 请求的进程内。使用 `status` 或脱敏输出汇报凭据状态。

本技能**仅在用户明确同意时协助注册账号**（短信验证码须由用户本人提供）。凭据分三类，用途互不混用；账号密码**仅用于换取会话 JWT 与 pt-key**（同一条链：`login.vm` → `view_private_token.jss`），不直接参与任何业务请求。

> 本地密码存入系统密钥链，用于换取会话 JWT 或按用户要求注册。托管环境从运行环境的密钥配置获取凭据。

### 账号密码

- **存储**：在终端运行 python scripts/aicp_credentials.py set-password 后隐藏输入，或通过安全输入通道以 set-password --stdin 读取。Windows 使用 DPAPI，macOS 使用 Keychain，Linux 使用 Secret Service。托管执行从 AICP_LOGIN_PASSWORD 读取。
- **账号信息**：本地 aicp.json 使用 mobile、accountId、ptKey、hasPassword、updatedAt 字段。
- **来源**：在终端设置一次登录密码，后续由系统密钥链复用。
- **清除**：clear-password 清除密钥链口令和 JWT 缓存，delete 删除账号信息文件。
- **边界**：密码仅用于向 codetg.com 的 login.vm 登录或向 register.vm 注册。对话回复、请求提示词和日志中只展示脱敏信息。

### 开户流程（首次使用）

**先问一次身份**：「你之前在 codetg.com 注册过吗？」
- 注册过 → 走 **B. 老用户**（三步）
- 没有 → 走 **A. 新用户**（两步 + 一次填码），注册成功后自动接 B 的第 3 步

#### A. 新用户注册（`send-code` → 用户报码 → `register`）

```bash
python scripts/aicp_credentials.py set-account '<手机号>'    # 1. 先落手机号
python scripts/aicp_credentials.py set-password     # 2. 密码进系统密钥链
python scripts/aicp_credentials.py send-code --json         # 3. 下发短信验证码
#   → 停下来问用户收到的验证码，拿到后立刻执行第 4 步（验证码有时效）
python scripts/aicp_credentials.py register --code '<验证码>' --json   # 4. 建号 + 换 key
```

第 4 步内部串完三件事：`register.vm` 建号 → `login.vm` 换 JWT → `view_private_token.jss` 换 pt-key，**一步写回 `aicp.json`**，不必再单独跑 `get-pt-key`。

实测要点（2026-11-23 真机验证）：

| 事项 | 结论 |
|---|---|
| `send_sms_register.vm` 成功判定 | ⚠️ **外层 `code` 恒为 `"success"`**，真实结果在 `data.success`（bool）与 `data.send_status_list[0].code == "Ok"`。只看外层 `code` 会把失败误报成已发送 —— 脚本已按 `data.success is True` 判定 |
| 号码非法 | 返回 `data.success: false` + `code: "InvalidParameterValue.IncorrectPhoneNumber"`，**不扣费** |
| 号码合法 | **真的下发短信并计费**（返回 `fee: 1`）→ 同一次开户只发一次，禁止循环重试 |
| `register.vm` 字段 | `{name, company:"", mobile, invitation_code:"6666", code, password}`，六个字段缺一不可 |
| 邀请码 | 固定 `6666`，可用 `--invitation-code` 覆盖 |
| 密码传递 | 从密钥链读出，**只存在于请求体**，不落盘、不回显；未设密码时先报 `PASSWORD_NOT_SET` |
| 验证码错误 | 服务端返回 `{"code":"code_is_invalid","msg":"验证码错误"}` → 脚本映射为 `CODE_INVALID` |

> **代注册的边界**：仅当用户**明确表示「没有账号、要注册」**时才走 A 路径。用户没说，不得擅自替其开户；**不得替用户编造手机号**（随手填的号会真实发出短信并计费）。

#### B. 老用户补 key（三步）

```bash
python scripts/aicp_credentials.py set-account '<手机号>'    # 1. 只写手机号，不需要 pt-key
python scripts/aicp_credentials.py set-password     # 2. 密码进系统密钥链
python scripts/aicp_credentials.py get-pt-key --json        # 3. 自动换出 pt-key 并写入 aicp.json
```

第 3 步内部就是 **账号密码 → JWT → pt-key** 这条链：

```
POST login.vm                                 Body: {"login_id":"<手机号>","password":"<密码>"}
  → 响应体 / Set-Cookie 中正则提取会话 JWT
POST view_private_token.jss                   Authorization: Bearer <JWT>
  → {"code":"success","data":{"token_value":"pt-xxx…"}}  → 写入 aicp.json 的 ptKey
```

开户之后先用 read 复用已有 API Key，缺失时用 get-pt-key，绑定或取码时再用 get-jwt。

#### 失败处理

| 错误码 | 来源接口 | 含义 | 动作 |
|---|---|---|---|
| `SMS_FAILED` | `send_sms_register.vm` | 号码格式非法等 | 原样转述 `data.send_status_list[0]` 的 `code` + `message`，核对号码 |
| `CODE_INVALID` | `register.vm` | 验证码错误或过期（`code_is_invalid`） | 重新 `send-code` 后**立刻**填新码，别让用户翻旧短信 |
| `MOBILE_EXISTS` | `register.vm` / `send-code` | 该号已注册 | 不重试注册，直接切 B 路径 |
| `REGISTER_FAILED` | `register.vm` | 其他错误 | 转述 `code` + `msg`，不自动重试 |
| `PASSWORD_NOT_SET` | — | 密钥链无密码 | 补跑 `set-password` |
| LOGIN_FAILED | login.vm | 凭据或网络异常 | 根据脱敏错误核对凭据或网络，由用户确认后再试 |
| `PT_KEY_FAILED` | `view_private_token.jss` | 换 key 接口报错 | `jwt_token_invalid` 时脚本已自动重登重试一次；仍失败则回退「用户手动贴 pt-key」 |

### API Key（`pt-` 开头）— 业务接口

- **来源**：先用 read 读取有效配置。优先级为 AICP_PT_KEY、旧变量 CODETG_PT_KEY、本地 aicp.json。缺少 API Key 时，get-pt-key 用账号密码换 JWT 再获取 API Key，并在本地模式下保存。
- **使用范围**：仅作为业务接口（`create` / `status` / `messages` / `chat`）的 `Authorization: pt-<key>` 请求头
- **生命周期**：只在内存中传给请求头，**不写入交付文案与日志**；`aicp.json` 中的副本由用户可随时删除
- **校验与脱敏**：环境提供的 API Key 可用 `python scripts/codetg_token.py check` 检查格式，或用 `python scripts/codetg_token.py mask` 显示脱敏值。通过标准输入提供 API Key 时，在子命令后加 `-`。
- **失效处理**：本地保存的 API Key 返回 401 时可用 get-pt-key --refresh 重取一次。环境变量提供的 API Key 需在运行环境的密钥配置中更新。

### 会话 JWT（仅主体绑定 / 取码接口使用）

- **适用范围**：`mp_auth/create.jss`、`proxy_ci_service.jss`、`get_auth_list.jss`（这三个接口不收 `pt-` key）
- **获取优先级（三级，逐级降级）**：
  1. **读缓存** — 本地路径由 paths 返回的 jwtCache 提供，含 jwt、obtainedAt 和 mobileHash，有效期 90 小时。托管模式跳过缓存。
  2. **自动登录** — python scripts/aicp_credentials.py get-jwt --json。脚本使用本地手机号和密钥链密码，或托管环境的 AICP_MOBILE 和 AICP_LOGIN_PASSWORD 登录。本地模式可用 --no-cache 禁用本次缓存。
  3. **手动贴（兜底，永久保留）** — 请用户在浏览器登录后从开发者工具复制 `Authorization` 头
- **`--json` 返回**：`{jwt, source: "cache"|"login", obtainedAt, expiresAt, ageSeconds, jwtMasked}`
- **错误处理**：
  | 错误码 | 含义 | 动作 |
  |---|---|---|
  | CRED_MISSING | 缺少手机号 | 本地用 set-account 配置，托管环境设置 AICP_MOBILE |
  | PASSWORD_NOT_SET | 缺少密码 | 本地在终端运行 set-password，托管环境设置 AICP_LOGIN_PASSWORD |
  | LOGIN_FAILED | 凭据或网络异常 | 展示脱敏错误，核对账号或网络后再试 |
- **不在代码里解析 JWT payload**（不读 `exp`/`userid`），过期判定只用本地 `obtainedAt` + 90h 策略 TTL
- **展示**：任何时候只输出 `jwtMasked`（形如 `eyJh********`），禁输完整 JWT

### 用户没有账号时

两条路，优先走第一条：

1. **技能内自动注册**（推荐，用户明确要求注册时）：走「开户流程 A」——`set-account` → `set-password` → `send-code` → 用户报验证码 → `register`，全程不用开浏览器，也不用去后台复制 API Key。
2. **用户自行网页注册**：浏览器打开 https://codetg.com 完成注册，回来走「开户流程 B」三步。

两条路都会自动换出 `pt-` key。**没得到用户明确同意前，不得替他开户**，也不得替他编造手机号。

### 数据边界

- 主动请求仅限 `codetg.com`：业务接口 + `login.vm`（登录）+ `*.jss` 平台接口；交付用的图片按接口返回的 URL 原样使用
- 用户提供的图片 / 截图仅用于当次任务识别，不上传到其它服务
- 本地文件包括 aicp.json、Windows 的 aicp_password.bin、JWT 缓存和 AppID 缓存。通过 paths 获取有效路径。
- 托管模式仅使用环境凭据。paths 在此模式返回空缓存路径，AppID 查询直接以平台接口结果为准。
- 不读取系统或浏览器中保存的登录状态（cookie / localStorage 一概不碰），不修改文件 ACL 之外的系统设置

---

## 概述

在 codetg.com（品牌名「小码力」）上创建**微信小程序或网页**。流程：**探测本地凭据（缺失则开户并自动换取 pt-key，见「开户流程」） → 构造中文 prompt → 创建小程序（新接口 `type: wechat_mini`）→ 实时轮询 + 播报 → 交付：`status.project.appid` 有值就直接下体验码，无值先调 `get_auth_list.jss` 查账号已绑定 appid（多为已有；1 条直接取码，多条让用户选，不自动挑），仍无才引导用户本人在页面完成主体注册（mp_auth/create.jss → 注册二维码 → 用户扫码 → proxy_ci_service.jss 取码）→ 增量修改 → 用户要后端时用一句话提示词让它自建后端与管理后台（详见第 7.5 步），**后端是异步子 run，且完成后必须交付「平台查看入口 + 新体验码 + 落库凭证」三样（详见 7.5.1 / 7.5.2）** → 核对后台菜单是否已注册到 `admin/ui/admin_function.json`（详见第 7.6 步）→ 长上下文时小步指令（详见第 8 步）→ 用户发报错截图时先图转文字再提交（详见第 9 步）**。

通过当前客户端的 HTTP 请求能力直接调用 codetg.com。

支持的产出类型：

- 微信小程序 → 新接口 `type: "wechat_mini"` / 老接口 `type: "wechat_program"`
- 网页 / 网站 / 落地页 / H5 → 新接口 `type: "web"` / 老接口 `type: "module"`
- 两类**共用同一套凭据与账号体系**，配置一次即可

---

## 工作流

### 第 1 步 — 明确需求

确认四件事：小程序类型（默认微信小程序，新接口 `wechat_mini`）、目标用户、核心页面/功能（含 tabBar 结构）、风格偏好。
信息不全时一次性问清，问题不超过 3 个；用户给一句话需求时，最多追问一轮，其余做合理假设并在交付时说明。

### 第 2 步 — 构造中文 prompt

六段式结构：小程序类型与目标 → 页面结构（含 tabBar/导航）→ 功能与交互 → 真实内容 → 视觉风格 → 适配要求。
禁止用一句话 prompt（如「做个小程序」）调用 API。
不要编造业务数据；数据缺失时在 prompt 中使用明显占位符（如 `[Your Logo]`），交付时提醒用户替换。

### 第 3 步 — 创建小程序

**优先新版接口**（小程序与网页同一个 create，仅 type 不同）：

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
    "type": "wechat_mini",
    "locale": "default",
    "build_mode": "prototype",
    "skills": []
  }
```

> ⚠️ **type 枚举（2026-11-19 实测，此前文档写错）**：新版接口小程序必须传 `wechat_mini`，传 `wechat_program` 直接返回 `{"code":"unspported_type","msg":"Unsupported type=wechat_program"}`；普通网页传 `web`（老文档写 `module` 也是错的）。入参与出参命名不一致——**入参 `wechat_mini`，返回体里 `biz_type` 仍叫 `wechat_program`、`type: 0`**。
>
> ⚠️ **`build_mode` 语义**：`prototype` = 直接产出可预览原型（本技能默认用这个）；`plan` = 只出设计方案，实测 18 秒结束、`phase: "design"`、`messages/list.jss` 返回 0 条消息，**不产出可跑代码**，不要用于交付。

**回退老接口**（新版返回非法 type / 参数错误时）：

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

- 需要图片出现在页面上时，建议同时在 prompt 中明确「将图片显示到页面上」；无图传 `[]`
- **返回结构（2026-11-19 实测，两版完全不同）**：
  - 老接口 → `data: {dev_link, run_id, main_project_id}`，`main_project_id` 可直接用于 `chat.jss`
  - 新接口 → 完整字段为：
    ```json
    {"path":"test500035","biz_type":"wechat_program","icon":"mdi-clipboard-check",
     "name":"测试小程序","locale":"zh-CN-CN","workspace_count":1,"status":1,
     "creator":"v000000","type":0,"create_time":"2026-11-19 17:01:20",
     "id":15820068,"domain":"<create 返回的站点域名>","phase":"design",
     "template_workspaceid":8697084,"dev_workspaceid":1000002,"run_id":"run_XXXXXX"}
    ```
  - ⚠️ 新接口**不返回 `dev_link`、不返回 `main_project_id`**，须自行推导：
    - `id`（如 `15820068`）就是 `projectid` → 发布页 `?projectid=<id>`、`proxy_ci_service` 的 `project_id`
    - **`main_project_id` = `dev_workspaceid`**（已用 `status.jss` 反查验证：拿 `1000002` 打 status 返回的正是该 run 的 `main_project_id: "1000002"`）→ 增量修改 `chat.jss` 用这个，不是 `id`
    - `domain` = create 返回的站点域名（形如 `<随机串>.<站点域名>`），注意 `status.jss` 里的 `project.domain` 反而是 `codetg.com`（不可靠），一律以 create 返回的 `domain` 为准
    - `dev_link` 可拼：`https://codetg.com/user-dev/dashboard?url=https://<domain>&miniprogram_preview_url=/publish?projectid=<id>`
    - `phase`（创建时为 `design`）不等于终态，终态看 `status.jss` 的 `status`
- 小程序的 `dev_link` 形如 `https://codetg.com/user-dev/dashboard?url=<站点地址>&miniprogram_preview_url=/publish?projectid=<id>`，其中的 `miniprogram_preview_url` 是小程序预览/发布入口

如果接口返回 `code != "success"`，按错误码处理：

- 401 → 按「API Key」的失效处理更新凭据，拿到有效凭据后再重试。
- type/参数不被新版接受 → 切老接口重试一次
- 其他 → 把 `msg` 原样转给用户

### 第 4 步 — 轮询进度（实时播报大模型消息 · 禁止全程不播报）

提交 create 后**立即播报**：「已提交生成，预计 1~3 分钟，开始实时播报大模型逐步产出」

每 10 秒一轮双查（最多 50 轮）：

**(1) status.jss**

```
POST https://codetg.com/460046184/skills/integration/api/agent/status.jss
Headers: Authorization: pt-xxx，Content-Type: application/json
Body: {"run_id": "<run_id>"}
→ data: {status, updated_at, model, error, main_project_id, project: {siteid, domain, appid, biz_type, trial_qrcode_url}}
```

实测完整返回（新接口 run，已绑定 appid 的项目）：

```json
{"msg":"Success","code":"success","data":{
  "status":"completed","updated_at":"2026-11-19 17:01:38",
  "model":"deepseek:deepseek-flash","error":"null","main_project_id":"1000002",
  "project":{"domain":"codetg.com","appid":"wx0000000000000000","siteid":"S000000",
             "biz_type":"wechat_program",
             "trial_qrcode_url":"//接口返回的图片域名//file/.../xxx.jpeg"}}}
```

> 🔑 **`project` 对象是整个交付链路的关键开关**（2026-11-19 实测）：
> - `project.appid` 非空 → 该项目**已有小程序码记录**，`project.trial_qrcode_url` 直接可交付，无需再调 proxy_ci
> - `project` 为 `null` → 接口直接抛 `{"code":"failed","msg":"Cannot get property \"trial_qrcode_url\" of null"}`。**这不是生成失败**，只代表该项目还没有小程序码记录
> - ⚠️ **`project` 为 null 的真实成因（2026-11-19 验证）**：新建项目从提交到「原型已完成」期间 `project` 都是 null，这很正常；但如果**原型完成后仍然 null**，说明 run **卡在 `requires_action` 待确认卡片**上没走完最后一步。此时请**用户在页面上查看并确认该卡片**，确认后 `project` 通常立即出现并携带 `appid` + `trial_qrcode_url`（详见下文 `requires_action` 处理）。所以 `project` 不是「发布才有」，而是「run 真正走完才有」
> - AppID 在账号下可复用。项目侧没有码时，先查 get_auth_list.jss，按第 5 步处理。

> 老接口回退路径：`POST https://codetg.com/dev/skills/api/agent/status.jss`，Body `{"run_id": "<run_id>"}`（同头鉴权，返回结构一致；**必须 POST body 传参，GET query 方式会返 `runid_required`**）
> 状态机：`queued` → `in_progress` → (`requires_action`) → `completed` / `success` / `failed`；`requires_action` 属中间态继续轮询；**`completed` 与 `success` 均视为成功**（新旧接口终态命名不同）

> ⚠️ **`requires_action`（待确认卡片）的处理（2026-11-20 修订）**：平台在原型完成后可能弹出一张「是否需要云端后台？」类卡片，run 停在 `requires_action`，页面显示「等待您的确认」。此时：
>
> 1. **必须由用户本人在页面上查看并确认**。技能不代为作答，禁止发送「直接结束 / 跳过确认」类替代 prompt 越过该卡片
> 2. 技能只负责播报并给出入口：「任务正在等待你的确认，请在页面上的卡片中做出选择」+ 页面地址（`dev_link` 或 `https://codetg.com/publish?projectid=<projectid>`）；卡片内容以页面显示为准，API 读不到时如实说明
> 3. 用户确认后再继续轮询 `status.jss`，此时 `project` 通常会补齐 `appid` 与 `trial_qrcode_url`
> 4. 若用户表示「页面上没有卡片 / 无法操作」，如实报告为阻塞状态，不要凭空断言生成失败或平台故障
>

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

#### 播报规则（按平台真实 content 三态）

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
| status=failed              | ❌ {error 原文} → **若为 `Cannot read property "data" from undefined` 走第 8 步（拆步或从项目记录接续），不要原样重试**；其余情况询问是否重试 |

#### 状态保留（必须跨轮）

- `currentRunId: str`
- `mainProjectId: str`
- `lastId: str`（消息 ID，单调递增）
- `elapsedSec: int`
- `lastTickAt: timestamp`

LLM 在多轮工具调用间用对话上下文保留这些状态。

#### 禁止

- 全程不播报直到终态
- 跳过 `lastId` 续传（会导致重复播报）
- 不按 `run_id` 过滤（会把别的 run 消息混进来）
- 把 user 角色消息当模型输出播报
- 把 actions 消息当文本输出播报（应播报为"操作/工具调用"）
- 生成完成前向用户宣称「已完成」

### 第 5 步 — 交付

**先看 `status.jss` 的 `data.project` 对象，按有无 `appid` 分四条路**：

> ⚡ **强制前置（2026-11-20 修复，针对「用户明明绑过小程序却拿不到 appid」）**：`project` 为空时，**必须**先调 `get_auth_list.jss` 查账号已绑定的 appid 列表，**禁止**只看本地缓存就判定「用户没有 appid」。
>
> **缓存空 ≠ 账号没绑过**。换设备、重装技能、清过缓存、换浏览器会话，都会让本地缓存丢失，而账号侧的微信授权一直有效。实测有用户账号下已绑多个小程序，本地缓存却是空的 —— 旧逻辑会把他当成新用户推去注册，这是本 bug 的根因。

> **前置动作（推荐第一步）**：原型完成后 `status` 若仍报 `trial_qrcode_url of null`，先按第 4 步的 `requires_action` 处理方式**请用户在页面上确认待确认卡片**，用户确认后再重查 `status` —— 多数情况下这时它已经带出 `project.appid` + `trial_qrcode_url`，可直接走路径 A。

| 分支 | 判定 | 动作 |
|---|---|---|
| **A · status 已带码** | `data.project` 非 null 且 `project.trial_qrcode_url` 非空 | 下载 `project.trial_qrcode_url`（`//` 补 `https:`）→ Pillow 加标题转 PNG 并交付。跳过第 6 步 |
| **B0 · 账号侧已绑定**（命中率最高，首选） | `get_auth_list.jss` 返回的 `data` **非空** | **1 条 → 直接用；≥2 条 → 先请用户明确选择**（见「路径 B0」标准问法，**禁止**按 `project_id`/`is_default`/顺序自动挑）→ 写缓存 → 调 `proxy_ci_service.jss` 取码。**已绑过小程序的用户全走这条，不需要注册** |
| **B1 · 本地缓存兜底** | 账号查询遇到网络或平台异常，且本地有当前项目的历史 AppID | 可用相同项目 ID 的缓存 AppID 试取体验码。鉴权失败时先修复鉴权。 |
| **C · 确实没有** | get_auth_list.jss 成功返回空列表 | 如需体验码或发布，按第 6 步引导用户绑定。 |

#### 路径 B0 · 查账号已绑定的 appid 列表（`get_auth_list.jss`，2026-11-20 实测）

**取 appid 的第一入口，优先级高于本地缓存。** 判断用户「有没有小程序」以本接口返回为准，不以 `project.appid` 或缓存为准。

- **URL**：`https://codetg.com/<租户路径段>/wechat/service/provider/api/authorization/get_auth_list.jss`
- **鉴权**：`Bearer <JWT>` 必填（由 `get-jwt` 自动获取，失败才由用户从浏览器复制；**此接口不收 pt-xxx**）
- **传参**：`projectid`（**全小写、无下划线**），**可选**。实测三种写法：`{"projectid":"<id>"}`（body）、`?projectid=<id>`（query）、`{"project_id":...}` 都能拿到数据；差别只在 `is_default` 会不会被算出来

```
POST .../authorization/get_auth_list.jss
Body: {"projectid":"<create 返回的 projectid / id>"}
# 拿不准 projectid 是否有效时，直接发空 body {} —— 一样返回完整列表（只是没有 is_default）
```

> ⚠️ **传了不存在的 projectid 会整次失败**（实测）：`{"projectid":"99999999"}` → `code: failed`、`data: null`，`msg` 为 `Cannot get property "biz_type" of null`。所以**只在 create/status 确认过这个 projectid 真实存在时才传**，否则发空 body。
> `is_default` 指向的是**账号默认小程序**，实测与传入的 `projectid` 无必然对应（传 1000005，被标默认的仍是 1000004 那个）—— **别只信 `is_default`**，按下方取值规则走。

> 🛑 **鉴权失败也是 HTTP 200**（实测）：不带 `Authorization` → `code: jwt_token_invalid`，`msg` 为 `Authorization not setting, token required!`。**判断成功必须看 `code == "success"` 且 `data` 是数组**，不能只看 HTTP 状态码 —— 否则会把 401 当成「账号下没有小程序」，又退回逼用户注册的老坑。

- **返回**：`data` 是**账号下全部已授权小程序**的数组（不只当前项目；`projectid` 只决定哪条被标为默认）：

| 字段 | 含义 | 注意 |
|---|---|---|
| `appid` | 小程序 AppID | `wx` 开头，取码就传它 |
| `mp_name` | 小程序名称 | **可能为空字符串**（新建未命名）→ 展示时用 appid 代称，**不要**当成无效条目丢掉 |
| `head_img` | 头像 | `wx.qlogo.cn`，可能为空 |
| `principal_name` | 主体名称 | `个人` 或企业全称，用于向用户确认「是不是这个」 |
| `qrcode_url` | 该小程序自己的码图 | 平台图片域名或 mmbiz，**仅展示用，不是你要交付的体验码** |
| `project_id` | 归属项目 id | 与请求 `projectid` 相同的即当前项目自己的绑定 |
| `is_default` | 账号默认小程序 | **仅用于排序与标注**，不作选取依据（是否默认是账号级，与当前 project 无必然对应） |

- **实测返回样例**（2026-11-20，账号下 7 条，节选 2 条，主体名已脱敏）：

```json
{"msg":"Success","code":"success","data":[
  {"appid":"wx0000000000000000","mp_name":"示例小程序（企业）","principal_name":"深圳某某科技有限公司",
   "project_id":"1000004","is_default":true,
   "head_img":"http://wx.qlogo.cn/mmopen/...","qrcode_url":"https://接口返回的图片域名//file/.../0.jpg"},
  {"appid":"wx0000000000000000","mp_name":"示例小程序（个人）","principal_name":"个人",
   "project_id":"1000005","is_default":false,
   "head_img":"http://wx.qlogo.cn/mmopen/...","qrcode_url":"http://mmbiz.qpic.cn/..."}]}
```

**取值规则（2026-11-20 修订：一律让用户选，禁止自动挑）**

> 🛑 **禁止「默认选一个」**：`project_id` 匹配、`is_default`、数组顺序**只用来排展示顺序**（最可能的排前面），**不能代替用户决策**。旧版「`project_id` → `is_default` → 第一条」的自动取值逻辑已废弃。

| `data` 条数 | 动作 |
|---|---|
| **1 条** | 无需选择，直接用；交付时点名「用的是「<mp_name>」（主体：<principal_name>）」 |
| **≥ 2 条** | **必须让用户选**；用户选定前**禁止**调 `proxy_ci_service.jss`、禁止写缓存 |

**≥ 2 条时的标准问法（照这个来，别自创）**：

1. 先用一句话说清情况，不夹技术词：
   > 「你账号下绑了 3 个小程序，体验码要用其中一个来出。你想用哪个？」
2. 列出小程序名称和主体，请用户明确选择。客户端支持选项时可用单选，其他情况下列出编号。
   - 名称为空时可显示 AppID 后 6 位，用主体和 AppID 尾号区分重名项。
   - 可标注「上次用过」「当前项目」「账号默认」，由用户决定。
   - 客户端有选项数量限制时，在对话里列出完整候选列表。
3. 用户选定 → 写缓存 → 调 `proxy_ci_service.jss` 取码
4. 用户回「随便 / 都行 / 你看着办」→ **仍不自动挑**，把候选第一条复述成一句确认：「那我用「示例小程序（企业）」，可以吗？」拿到明确「可以」再取码
5. 用户不回、或只说「先看页面」→ 不取码、不写缓存，先交付 `dev_link`，留一句「体验码等你选好小程序再出」。**禁止**为了「把流程走完」自己挑一个

> ⚠️ **码归属必须讲清楚**：appid 是账号级通用的，取码能成功，但**码指向的是用户选中的那个小程序**，页面内容是当前项目。交付时补一句：「这个码落在「<mp_name>」（主体：<principal_name>），扫开是你刚生成的新页面。」—— **选择发生在入口处（见上方标准问法），不是取完码再告知。**

**写缓存**：使用 paths 返回的 appidCache，仅在路径非空时写入。缓存文件统一用 xiaomali_appid.json。

```json
{"appid":"wx…","mp_name":"…","project_id":"…","source":"get_auth_list","updatedAt":"<ISO8601>"}
```

> 每次取码先查 get_auth_list.jss。缓存只在网络或平台异常时为同一个项目兜底。账号查询成功返回空列表时以服务端为准。

#### 路径 B · 账号级 appid 复用取码（2026-11-19 完整跑通）

已绑定的一个 appid 对账号下**所有**项目通用，一次取得、长期复用：

1. **取 appid**：按「路径 B0」调 `get_auth_list.jss` 拿账号已绑定列表（首选）；**列表 ≥2 条一律让用户选，禁止自动挑**；1 条直接用；符合路径 B1 时可使用同项目缓存。**两者都拿不到才问用户，不可编造**
2. **取码**：`proxy_ci_service.jss`（Bearer JWT）
   ```
   Body: {"appid":"<已确认的 appid>","path":"pages/index/index","project_id":"<create 返回的 id>"}
   → data: {qrcode_url, trial_qrcode_url}
   ```
   实测成功样例（project `1000003` + 账号 appid `wx0000000000000000`）：
   ```json
   {"msg":"Success","code":"success","data":{
     "qrcode_url":"https://接口返回的图片域名//file/.../0.jpg",
     "trial_qrcode_url":"//接口返回的图片域名//file/.../xxx.jpeg"}}
   ```
3. **交付**：`qrcode_url` 此时也在平台图片域名下、可直连（返回的是**圆形微信小程序码**，比 trial 的方形码好看，优先用）；若为 `mmbiz.qpic.cn` 则命中防盗链，改下 `trial_qrcode_url`
4. `path` 传首页路径（默认 `pages/index/index`，有 tabBar 时用首个 tab 的路径）

> 结论：**在账号已绑定 appid 的情况下，生成 → 取码 可一次闭环完成**，无需再走主体注册。只有 `get_auth_list` 明确返回 `data: []`（账号一次都没绑过）（路径 C）时，才必须走第 6 步。

- 终态成功 → 向用户返回 `dev_link`（老接口直接给；新接口按第 3 步公式用 `id`/`domain` 拼），含 `miniprogram_preview_url` 预览/发布入口
- 新接口若 `domain` 字段异常（status 里可能返回 `codetg.com`），以 create 返回的 `domain` 为准
- 必返回字段：`run_id`、`main_project_id`（新接口 = `dev_workspaceid`；**留作第 7 步增量修改用，必须告知用户保存**）、`projectid`（新接口 = `id`）、`dev_link`/`domain`、`updated_at`、`appid`（路径 A/B 已取得时一并告知）
- 交付体验码后仍告知用户：扫码者需有体验权限才能打开，正式分发须走发布流程；要给更多微信号开权限走第 6 步第 5 小节 `create_tester.jss`（appid 用路径 A/B 取得的那个）
- 只有路径 C 才需要「交付链接后自动衔接第 6 步」

### 第 6 步 — 小程序主体绑定 → 用户扫码授权 → 取码交付（仅在账号下无已绑定小程序时进入）

**触发**：第 5 步交付 `dev_link` 后进入本步。**但进来第一件事不是注册，是查**：

1. 先按第 5 步「路径 B0」调 `get_auth_list.jss`
2. 返回 `data` **非空** → 1 条直接用、**≥2 条先让用户选**（见第 5 步标准问法），选定后出码交付，**本步到此结束，不要发起注册**（这是绝大多数老用户的真实路径）
3. 返回 `data: []` → 才按下方链路发起 `mp_auth/create.jss`

用户主动要求「发布 / 正式上线 / 绑定主体 / 走 preview 发布」时，同样**先查列表**。注册默认走**个人注册**分支（须向用户要微信号 `wxuser`）；用户明确是企业主体时走企业分支。

**流程总览**

```
get_auth_list.jss（① 先查账号已绑定小程序 —— 必做，不做就别往下走）
  ├─ data 非空（老用户，最常见）→ 选 appid → proxy_ci_service.jss 取码 → 交付【结束，不注册】
  └─ data: []（真新用户）↓
mp_auth/create.jss（② 发起微信注册任务）
  → 个人注册: 返回 authorize_url（注册授权二维码）→ PNG 交付给用户扫码 → 用户完成微信「快速注册个人小程序」
  → 企业注册: 绑定响应含 appid（或无则从发布页取）
  → proxy_ci_service.jss（③ 取体验码）→ 返回 qrcode_url → 以二维码形式交付
  →（可选）create_tester.jss 给更多微信号开体验权限
```

> **鉴权注意（与业务接口不同）**：本步接口均用**会话 JWT**（`Bearer eyJ…`，约 100 小时有效），**不是 pt-xxx**——用 pt-xxx 调会 401。
> 用 `python scripts/aicp_credentials.py get-jwt` 按「凭据与授权」获取 JWT。脚本在本地模式下复用 90 小时缓存，在托管模式下从环境凭据登录。自动登录失败时，可由用户在浏览器手动获取 `Authorization` 头。

#### 入口分流 —— 确认「真的没有 appid」后才引导注册（必做，不许跳过）

> 🛑 **判定前必须先调 `get_auth_list.jss`**（见第 5 步「路径 B0」）。
> 仅凭「`project.appid` 为空 + 本地无缓存」就判定「用户没有 appid」**是错的** —— 这正是换设备 / 重装 / 清缓存后把老用户误当新用户、逼人重复注册的根因。
> **顺序**：`get_auth_list` 返回非空 → 直接取码（B0，不走本节）；返回 `data: []` → 才进本节。

**判定「确实没有 appid」的权威依据**（按优先级）：

| 判定依据 | 具体表现 | 权重 |
|---|---|---|
| **账号侧无**（权威） | `get_auth_list.jss` 返回 `data: []` —— 账号下一个小程序都没绑过 | **以此为准** |
| 账号侧有（反向判据） | `get_auth_list.jss` 返回 `data` 非空 | **直接走 B0，不进本节** |
| 项目侧无（辅助） | `status.jss` 的 `data.project` 为 null，或 `project.appid` 为空 | **不能单独作为判据**（`project` 为 null 是常态） |
| 本地无缓存（辅助） | paths 没有返回 appidCache，或对应文件不存在 | 账号是否已绑定，以 get_auth_list.jss 为准 |
| 用户明说 | 「我没有 appid」「没注册过小程序」「不知道怎么弄」「这个要去哪弄」 | 仍要先查 `get_auth_list` 复核 |

**引导四条原则**：

1. **主动开口，不等用户问**。原型生成完、链接交付完，紧接着就把「下一步要注册小程序」说清楚
2. **说人话，不甩接口名**。用户不需要知道 `mp_auth/create.jss`，只需要知道「扫个码 + 身份证 + 人脸核验」
3. **一次只给一个动作**。别同时抛「要微信号 + 扫码 + 贴 appid」三件事，用户会懵
4. **讲清代价与选择**：只**看页面**可以不注册（`dev_link` 直接能开）；要**体验码**（别人扫码试用）或**发布上线**，就必须有 appid

**标准引导话术（可直接说给用户听）**：

| 场景 | 话术 |
|---|---|
| 首次提示要注册 | 「页面已经能打开了。不过你要的**体验码**（别人扫码就能试用那种）得先有一个小程序 appid。我帮你发起微信的「快速注册个人小程序」——你手机微信扫个码、做下身份证和人脸核验就行，免费，一两分钟。」 |
| 要微信号 | 「注册要用你的微信号当管理员，你的微信号是多少？（只用于绑定这个主体，不做别的用途）」 |
| 发注册二维码 | 「用手机微信扫这张码 → 按提示完成身份证扫描 + 人脸核验 → 微信会给你一个 `wx` 开头的 appid，把它发我就行，后面我自动出体验码。」 |
| 用户嫌麻烦 / 不想注册 | 「那这次先给你**页面链接**，直接点开就能看效果。等以后要正式发布、或者想让别人扫码试用，再回来找我注册，一样很快。」 |
| 用户已自己注册过小程序 / 绑过小程序 | 「**不用重新注册**。我先查一下你账号下绑过哪几个小程序，能查到就直接用它的 appid 出体验码。」（→ 调 `get_auth_list.jss`，非空即走 B0；**查到多条就把 `mp_name` + `principal_name` 逐条列出，并请用户明确选择，不许自动挑**；**只有返回 `data: []` 才说「账号下没有绑定记录」**） |
| 查到多个小程序 | 「你账号下绑了这几个，用哪个出码？① 示例小程序A（企业，默认）② 示例小程序B（个人）③ …」→ 用户选定后用该 `appid` 取码 |
| 注册卡住 / 扫码报错 | 「把报错截图发我，我逐字看一下是哪一步卡了。」（拿到截图走第 9 步图转文字流程） |

**注册通道（仅服务真正的新用户）**：`mp_auth/create.jss`（个人注册 → `authorize_url` → 用户手机微信完成授权 → 微信下发 appid）。

**已有小程序的用户不走本通道**：先查 `get_auth_list.jss`（第 5 步路径 B0），查到就直接用 —— 这就是「用已有小程序」的正路，**不需要任何绑定接口**。本通道只在 `get_auth_list` 返回 `data: []` 时使用。

**流程**：

1. **分流并收集参数**：
   - **个人注册（默认）**：问「绑定个人主体需要你的微信号，是多少？」→ 填入 `wxuser`
   - **企业注册**：问「企业名称」「企业代码」「代码类型」；代码类型三选一：`1`=统一社会信用代码、`2`=组织机构代码、`3`=营业执照代码
2. **取得会话 JWT（三级降级：先自动，后手动）**：
   - 先跑 `python scripts/aicp_credentials.py get-jwt --json`，取返回里的 `jwt` 字段。**成功就不要再打扰用户**：
     - `source` 为 `cache`（命中缓存）或 `login`（刚登录）→ 直接用
     - `CRED_MISSING` → 走「开户流程」收手机号 + 密码 + `pt-` key，再重跑
     - `PASSWORD_NOT_SET` → 问一次密码 → `set-password` → 重跑
     - `LOGIN_FAILED` → 把服务端 `msg` 原样转述（例如 `账户不存在`），让用户确认账号；确认后仍失败才降级手动
   - **手动兜底（仅自动登录失败时）**：请用户在浏览器登录 codetg.com，打开开发者工具 → Network，复制任一 `*.jss` 请求的 `Authorization` 请求头（形如 `Bearer eyJ…`）贴回
   - JWT 只进请求头，**不写入交付文案、不写进 prompt**；缓存由脚本管理，90h 后自动重登
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
   - 外层 401 → JWT 过期 → 请用户重新复制一次 `Authorization` 头后重试

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
- 身份证 + 人脸核验是微信侧硬性要求，**无自动化替代路径**；Codetg 平台也无法代替用户完成
- PC 浏览器打不开 authorize_url（提示「请在微信内打开」）是**预期行为**，不要反复让用户在 PC 上尝试

**授权二维码交付**

```
① 使用 Python 生成 PNG：qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=18, border=6)
   → 输出 ~1026px 白底黑码 PNG，用 Pillow 底部加「个人小程序注册授权」标题 + taskid/wxid 副标题
② 用当前客户端的图片交付方式展示生成的 PNG。
③ 引导：手机微信 → 右上角「+」→ 扫一扫 → 从相册选图 → 完成身份证+人脸核验
④ 用户拿到 appid 后贴回对话 → 进入 4.2 proxy_ci_service 取码
```

**踩过的坑（同类场景禁止重犯）**：
- 交付可保存的 PNG 文件，供用户在手机微信里扫码。
- ❌ 不要把 authorize_url 直接丢给用户在 PC 浏览器打开（微信内授权页，PC 必失败）
- ⏳ taskid 有效期内完成授权即可；用户若反复拿到**新的 taskid**（自己重新调过接口），以**最新一次**返回的 authorize_url/taskid 为准生成二维码

#### 4.2 proxy_ci_service.jss 取码交付（注册/绑定完成后自动执行）

**前置**：个人注册须等用户扫码完成微信授权并拿到 appid（4.1）；企业注册取绑定响应中的 appid，取不到则从发布页问用户。拿到 appid 后**立即**调用本接口取体验码：

```
POST https://codetg.com/<租户路径段>/wechat/service/provider/api/ci/proxy_ci_service.jss
Headers:
  Authorization: Bearer <JWT>（复用第 2 步取的 JWT）
  Content-Type: application/json;charset=utf-8
  Referer: https://codetg.com/publish?projectid=<projectid>&url=<站点地址>
Body: {"appid":"<绑定小程序的 appid>","path":"<小程序首页路径，如 pages/home/home>","project_id":"<projectid>"}
```

**请求体（用户实测确认 2026-09-09）**：

| body 字段 | 含义 | 示例 |
| --- | --- | --- |
| `appid` | 微信小程序 AppID（注册后下发） | `wx0000000000000000` |
| `path` | 小程序首页/预览落地路径 | `pages/home/home` |
| `project_id` | codetg 项目 ID（dev_link 中 projectid） | `15341536` |

**返回结构（用户实测确认 2026-09-09）**——两个二维码字段并存，`data` 内含 errcode：

```json
{
  "code": "success",
  "msg": "Success",
  "data": {"errcode": 0, "…": "…"},
  "qrcode_url": "http://mmbiz.qpic.cn/…/0",
  "trial_qrcode_url": "//接口返回的图片域名//file/…/xxx.jpeg"
}
```

**交付规则（两个 URL 语义不同，别搞混）**：
- `qrcode_url`：微信侧原图（mmbiz.qpic.cn，`http://`），**服务端下载会命中防盗链占位图**（「此图片来自微信公众平台 未经允许不可引用」）——**不要直接下载它当图片交付**
- `trial_qrcode_url`：codetg 转存的体验码图片（接口返回的图片域名，`//` 开头**须补 `https:`**），**可直连下载**——交付体验二维码**优先用这个**：下载 → Pillow 放大加标题（「小程序体验码」+ appid/projectid 副标题）→ 转 PNG 并交付
- 只有 `qrcode_url` 且下载被防盗链拦截时，才退而**把 `qrcode_url` 本身编码成二维码 PNG**（qrcode 库，box_size≈18/border 6/容错 M）交付，用户扫码可达对应页面
- 使用当前客户端展示生成的二维码 PNG。

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
   - 优先取 4.2 proxy_ci_service 返回的 **`trial_qrcode_url`**（`//` 开头补 `https:`，接口返回的图片域名 可直连）下载 → Pillow 加标题转 PNG 并交付
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

**首选新端点（facade，与 create 同命名空间 · 2026-11-20 实测通过）**：

```
POST https://codetg.com/com/codetg/ai/facade/api/agent/dev/chat.jss
Headers:
  Authorization: pt-xxx
  Content-Type: application/json
Body（最小可用集，三个字段就够）:
  {
    "main_project_id": "<创建时返回的 main_project_id>",
    "prompt": "<中文修改指令>",
    "url": "<站点地址，即 https:// + create 返回的 domain>"
  }
```

- ✅ **实测确认（2026-11-20）**：只传上述三字段即成功；`assistant_id` **不需要传**（服务端自返回，且与网页端取到的值不同，说明非项目级固定）；`dev_siteid` 不传则为 `null`；不需要 `is_login` / cookie，`pt-xxx` 直连即可
- ❌ **`url` 是必需项**：缺它会返回 `{"code":"failed","msg":"java.net.MalformedURLException in <eval> at line number 532"}`，报错信息完全不提 url，极易误判
- 其余字段（`model` / `mode` / `build_mode` / `reasoning_effort` / `file` / `module_name` / `skills` / `current_files` / `preview_url` / `dev_siteid`）**均为可选**，不传走默认
- 返回（比老端点多 5 个字段）：
  ```json
  {"msg":"Success","code":"success","data":{
    "app_name":"云栖谷景区预约",
    "app_source_url":"https://codetg.com/p/yunqigu?type=0",
    "root_path":"/","code":"success","run_id":"run_XXXXXX",
    "assistant_id":"ass-501702","dev_siteid":null,"workspaceid":"8708846"}}
  ```
  - `workspaceid` **等于 `main_project_id`**（第三次印证：`dev_workspaceid` / status 反查 / 本字段）
  - `app_source_url` 是短链形式的站点地址（比 dashboard 长链干净）
  - `dev_siteid` 与 `status.jss` 的 `project.siteid` **不是同一个 id**（实测 `S870327` vs `S000000`），不要互相替代

**回退老端点（已验证长期可用，字段最简）**：

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

返回 `data: {app_name, run_id}`，用新 run_id 按第 4 步节奏轮询至终态后交付（两版终态均为 `completed`，消息流共用同一个 `messages/list.jss`，`run_id` 连续递增）。

- 拿不到 `main_project_id` 时才退而按新需求重新创建（先提示：「缺少项目 ID，本次将作为新应用创建」）
- 网页项目同样走 chat.jss 做增量修改（facade 新接口，body 传 `main_project_id` + `prompt` + `url`）；若平台返回不支持，如实说明并停下，不要引导用户另装技能
- ⚠️ **增量修改是本技能最容易踩上下文上限的环节**（项目代码已膨胀）。写 prompt 前先自检：这段指令是否 > 300 字？是否一次要做多件事？若是，先拆步或直接读第 8 步

---

### 第 7.5 步 — 后端开发（用户确认原型后再做）

**触发**：用户看过前端原型、明确表示要后端 / 登录 / 数据库 / 管理后台。

**提示词就一句，不要拆步、不要写六段式**（写复杂反而会让它分心去做你没要的东西）：

```
开始开发后端。只用你自带的后端框架，不要引入任何第三方服务或自建服务器。
后端和管理后台一起开发。
```

需要它给出验收证据时，再加一句：

```
做完告诉我后台入口地址，并说明数据是否真的落库（给一条真实记录）。
```

> 指令发在原项目的 `chat.jss`（`main_project_id` + `url`）。它会自己把后端模块（domain/api/model + `ini.mod` + `i.db`）和管理后台一起建好；**管理后台它通常会自动另建一个项目并绑定好**，不需要你说明放哪、也不用指定目录或表结构。

**三条铁律**

1. **框架白名单**：只允许它自带的后端框架（jss 模块：`domain` / `api` / `model` + `ini.mod` 注册 + `i.db`）。禁止第三方后端、外部数据库、云函数、自建服务器或 NPM 服务。
2. **不指定项目归属与目录**：后端和管理后台由它自己决定建在哪、是否另起项目。管理后台通常会是独立项目、由它自动创建并绑定，**不要显式要求"不要新建项目"，也不要指定 `/admin/ui/` 之类的目录**——指定了反而会让它绕路（实测会让它在原项目里硬塞，撞上构建期 workspace 解析问题）。
3. **无库不伪造**：数据库实例由平台分配，模型不能自己造。实测到下列任一现象即判定「平台未给该项目分配数据库实例」，**如实告诉用户去控制台开通，禁止用 mock / 内存 / 文件模拟持久化**，也不要在无库状态下反复改代码。

**失败现象 → 判定 → 动作**

| 现象（实测） | 含义 | 动作 |
|---|---|---|
| `i.db` 为 null、`current_schema` 为 `""`、`total_record` 为 `-1` | 项目没有数据库实例 | 让用户去控制台开通；开通后回一句「数据库已开通，建表并验收」 |
| `insertMockData` 返回 `module_not_exist` | 模块未注册 / DB 侧无模块记录 | 让它先 `importModule` 再重试 |
| `Cannot get property "workspaceid" of null`（`getModuleInfoByFilePath`） | 构建会话解析不到 workspace，常见于 `/com/codetg/...` 模块目录读写 | 让它换到能正常读写的路径（通常项目根），别动已跑通的代码 |
| admin 接口返回 `{"code":"failed","msg":null}` | 多为表不存在（同「无数据库实例」） | 先解决数据库，不要改查询代码 |
| 后端接口 404 / `file_not_found` 但 `workspaceid` 正常 | 路径写错或模块没 import | 让它 `importModule` 并核对路径 |

**验收由我方做，不让模型自证**：用 curl 打它给的接口，看 `log_ok` 是否 true、admin 列表是否有真实记录；后台页面用 HTTP 200 + 页面标题/关键文案判断，不轻信「已完成」。

**验收必查四项（2026-11-25 实测，四项全过才算后端可用）**

| 检查 | 怎么打 | 通过标准 |
|---|---|---|
| C 端主接口 | `POST <模块>/api/mall/menu.jss`（按实际命名） | `code=success`，且返回真实门店与商品条数；`shop_not_found` 说明种子没落库 |
| 后台列表接口 | `POST <模块>/admin/api/order/order_list.jss` | 返回 `total_record` 与真实行；报 `Cannot read property "instance" from undefined` 见下方「`var i` 遮蔽」 |
| 播种幂等 | `POST <模块>/api/setup/seed_demo.jss` 连打两次 | 第一次有插入数，第二次全 0；`totals` 由 `select count(*)` 实测 |
| 后台页面 | `GET` 菜单里的 `.vuetify` 地址 | 返回 HTML（含 `GLOBAL` / `Vue`）；返回 `{"code":"failed","msg":null}` 说明页面不存在 |

#### 7.5.1 后端是异步子 run：`chat.jss` 的 run 完成 ≠ 活干完了

实测（2026-11-25）：`chat.jss` 返回 `run_XXXXXX`，**20 秒内就 `completed`**，消息只有一句「后端已开始生成，通常 10–20 分钟」。真正的开发 agent 跑在**另一个 run_id**（本例 `run_XXXXXX`，`model: deepseek:deepseek-flash`，实测耗时 44 分钟）。

正确处理：

1. `chat.jss` 拿到 `run_id` 后**不要**只用它过滤消息；改用 `messages/list.jss`（传 `main_project_id`）**不按 run 过滤**拉全量，找 `role=assistant` 且带 `developWechatMiniProgramBackend` 动作的那几条，**它们所在的 run_id 才是真执行体**（本例为 `run_XXXXXX`，与派发 run 不同）
2. 拿该 run_id 打 `status.jss` 循环跟踪，直到 `completed`；期间 `status.updated_at` 持续刷新 = 还活着
3. 全程按第 4 步节奏播报它干了什么（建模块 / 建表 / 写 `place_order` / 建 admin 页面），否则用户会以为卡死

#### 7.5.2 后端完成后必须交付三样东西

做完后端，用户最需要的是「去哪看、看什么、怎么验」，缺一样都等于没交付：

1. **平台侧查看入口（必给）**：`https://codetg.com/user-dev/dashboard?url=https://<domain>`，说明「后端模块、数据表、运营后台都在平台里」，并告诉它后台菜单是否已可见（不可见则指向 7.6）
2. **重新出一张体验码（仅小程序，必给）**：后端上线后小程序代码已从本地 mock 切到真实接口，**必须重新取码交付，不能让用户继续扫旧图**。取码方式同第 5 步路径 A（`status.jss` 的 `project.trial_qrcode_url` → 下载 → Pillow 加标题 → 交付 PNG），标题写「<项目名> · 已接后端」，与原型版二维码区分开
   - 网页项目没有体验码，只交付站点地址 + 后台地址
3. **一条真实落库凭证**：订单号 / 记录条数 / 时间戳，用来证明数据进了库而不是留在缓存

> 同时必须如实说明**种子数据的来源**：当前环境 `insertMockData` 常被 `dev_siteid_required` 拦住，生成器会把演示数据放到 `setup/setup.jss` —— 但该文件是平台只读生成文件（`file_is_readonly`），末尾是 service 对象，**POST 它只会被 conform 成 `NULL` 且异常被 `safe()` 静默吞掉**，数据一行都不会进。正确做法是让它另建 `api/setup/seed_demo.jss` 幂等播种接口，并把「以该接口为唯一播种入口」写进交付说明。

---

### 第 7.6 步 — 后台菜单注册（后台页面能打开 ≠ 后台能用）

**症状**：平台后台侧边栏只有「微信配置 / 用户基本信息维护 / 用户权限」，看不到任何业务菜单；但 `.vuetify` 页面单独访问完全正常。

**根因**：平台**只扫描** `<模块>/admin/ui/admin_function.json` 来生成侧边栏。生成器常把菜单写到 `setup/admin_function.json`（平台不扫 `setup/`），页面就成了孤立页 —— 有页面、没入口。

**正确文件与格式**（2026-11-25 实测）：

`<模块>/admin/ui/admin_function.json`

```json
[
  {
    "name": "示例项目",
    "icon": "mdi-cup-outline",
    "menus": [
      {
        "component_name": "mall-dashboard",
        "name": "经营看板",
        "url": "/<站点前缀>/<模块路径>/admin/ui/analytics/mall-dashboard.vuetify"
      }
    ]
  }
]
```

- `component_name` 必须与页面模板里的组件 id 一致，否则点进去白屏
- `url` 用 **`.vuetify`** 后缀（不是 `.html`），且必须带站点前缀（形如 `/<站点前缀>/...`）；去掉前缀会 `file_not_found`
- 一个业务一个组，组内按页面顺序排，建议 8~10 项内

**验证三条（缺一不可）**

1. `GET <模块>/admin/ui/admin_function.json` → 返回 `{"content":"<字符串化 JSON>",...}`，`content` 里项数 = 页面数
2. 逐个 `GET` 菜单 `url`：**返回 HTML 才算存在**。不存在的页面返回 `{"code":"failed","msg":null}`（**不是 404，HTTP 200 也会骗你**）
3. 让用户强刷（Ctrl+F5）或重登后台；仍不显示则进「用户权限」把新组勾给当前角色（菜单按 RBAC 下发到角色）

> ❌ **`var menu={}` 不能当判断依据**：站点 `/index.html` 和 `/u/login` 里都是 `var menu={}`，那是 SPA 占位符，登录后由运行时接口填充。拿它判「菜单没注册」必然误诊。

---

### 第 8 步 — 长上下文项目的拆步与接续

**症状**：`status.jss` 返回 `failed`，`error` 为 `Cannot read property "data" from undefined`（栈里常见 `forward` / `generateContent`）；同一句长指令连续重试仍是同样失败；换成十几个字的短指令立刻 `completed`。

**根因**：不是平台故障，也不是指令写错。项目经多轮改造后，服务端拼接给大模型的上下文（项目全部代码 + 历史对话 + 本次指令）已逼近上游模型请求上限，任何"稍长"的 prompt 都会把请求撑爆；上游返回体为空 → 平台侧读 `resp.data` 得到 `undefined` → 抛这个错。所以**指令越长越必失败，原样重试无效**。

**执行铁律（按级别顺序降级，不要跳级）**：

| 级别 | 做法 | 说明 |
|---|---|---|
| **L1 拆步**（默认） | 把大需求拆成 3~6 条独立指令，**单条控制在 300 字内**，一次只做一件事（如：先只统一数据层引用 → 再只补核销记录 → 最后只跑自检） | 上一轮 completed 后再发下一条，不要并行 |
| **L2 精简** | 删掉「请先通读项目」「完整自检所有页面」这类大范围动词；用「请只做一件事：…」开头，结尾加「完成后简短列出改了哪些文件」 | 最占 token 的常是**范围描述**而非目标本身 |
| **L3 短探针** | 先发一句 20 字内指令（如「回复一句话：当前接口是否可用？」）验证服务活性 | 用于区分病因：短指令成功 = 上下文撑爆；短指令也失败 = 上游真故障，等 5~10 分钟再试 |
| **L4 新会话接续** | 若客户端会话上下文过长，记录项目标识、进度和待办，在新会话接续 | 服务端仍然失败时，保留错误与 run ID 以供定位 |

**新会话接续时记录这些信息**

1. 重新加载本技能（`Skill: xiaomali`），读凭据
2. 交代固定 ID：`main_project_id`、`projectid`、`domain`、`appid`、体验码路径
3. 用一句话说清项目现状（如「景区门票预约小程序，9 页面，后端已上云，7 张表」）
4. 只交代**未完成的那一件事**，不要罗列全部历史
5. 再按 L1 小步发指令

**禁止**：

- ❌ 把此失败报成「平台崩了，稍后重试」——根因是上下文超限，不拆步重试必然复现
- ❌ 原样重发同一条长指令（`run_XXXXXX` 长自检、`run_XXXXXX` 长复述均如此连续失败）
- 新会话先用已记录的项目 ID 核对目标，再发送下一条修改指令。
- ❌ 把整份历史对话 / 日志 / 代码贴回 prompt 当"恢复上下文"——等于再把上下文撑爆一次

---

### 第 9 步 — 用户发来报错截图时的处理（图转文字 → 短指令 → 修复）

用户（尤其真机试用后）最常直接甩一张报错截图，配一句「修一下」。**绝不能把图原样丢给平台，也不能说「报错了帮我看看」**——必须先把图里的信息转成结构化文字，再拼成满足第 8 步 L1 标准的短指令。

**为什么必须转文字**：① `chat.jss` 的 `image` 字段只接受**公网可访问 URL**，手机截图/剪贴板图是本地文件，传不上去；② 图片对定位问题几乎没有约束力，真正有用的是报错原文、错误码、出现位置；③ 文字版能被平台侧大模型精确搜索代码。

#### 9.1 从会话附件提取报错原文

一次性把以下 5 项抠全，缺哪项就在指令里说明「截图未显示」：

| # | 提取项 | 要求 |
|---|---|---|
| 1 | **报错原文** | 逐字照抄，含大小写、括号、引号、反引号、变量名（如 `(i.tickets \|\| []).map is not a function`），不要"翻译"成中文描述 |
| 2 | **错误码 / 响应体** | 有 `{"code":"xxx","msg":...}` 就整段抄；有 `[jwt_token_invalid]` 这类方括号码也照抄 |
| 3 | **触发位置** | 哪个页面、什么操作之后出现、有无弹窗标题（如「错误」「提示」） |
| 4 | **同屏其他提示** | 如「网络开小差了，请重试」「重试」按钮、空状态文案——这些能区分"接口挂了"和"渲染挂了" |
| 5 | **环境线索** | 真机 / 开发者工具、是否有导航栏（判断是否已进入页面） |

#### 9.2 组指令（严格三段式，总长 ≤300 字）

```
【真机报错】<页面> 出现 <报错原文逐字>，<同屏提示/按钮>，<现象：列表不显示/无法提交>。

【判断】<一句话根因推测>。

请只做一件事：<单点修复动作>。只改 <限定范围>，不动 UI 和样式。完成后简短列出改了哪些文件。
```

- 「判断」可以错，但**必须给出**——它决定了模型第一轮往哪查，能省掉一半读文件轮次
- 一次只报**一个**错。截图里有多条错误时，按「先阻塞流程的那条」排序，逐条发

#### 9.3 常见报错 → 排查方向（照此写「判断」和「修复动作」）

| 报错原文特征 | 常见根因 | 指令里该要求什么 |
|---|---|---|
| `jwt_token_invalid` / `401` / `unauthorized` | 请求没带有效登录态；token 存了脏值；登录请求自身带坏 token | 排查 token 存取一致性、失效重登、登录与业务请求的先后顺序 |
| `xxx is not a function`（`.map` / `.filter` / `.forEach`） | 字段不是数组，`\|\| []` 兜不住「非空但非数组」的形态 | **在数据层出口（`utils/api/scenic.js`）统一归一化，不要逐页面打补丁**；同时全局搜 `(x \|\| []).map(` 与 `: x \|\| []` 逐点替换，并要求它列出全部改动文件——单点修完必然还会在别的页面复现 |
| `Cannot read property 'x' of undefined/null` | 接口字段缺失或嵌套层级不符预期 | 先核对真实返回结构，再加可选链 + 默认值 |
| `网络开小差了` / `request:fail` / `timeout` | 请求域名未加白名单、接口路径前缀错、超时过短 | 核对 request 合法域名、接口真实路径、超时与重试 |
| `stock_insufficient` / 库存类提示 | 库存未初始化，或并发扣减条件不满足 | 核对初始化与条件更新（`remaining >= ?`） |
| **点击无反应 / 选中态不生效 / 按钮永久禁用（无报错）** | 主键字段名或类型与前端不一致，`dataset.id` 取到空串；或跨类型 `===` 永假；或必填校验漏项 | 核对接口真实主键（如 `session_id` / `code`）；`bindtap` 用 `data-index` 兜底定位；选中态改由数据字段（如 `is_active`）驱动；统一转字符串比较 |
| `Cannot read property "instance" from undefined` / `..."db" from undefined`（后台或接口 500） | 后端 jss 里 `for (var i in rows)` 遮蔽了平台函数库 `i`，`i.instance()` / `i.db` 变 undefined | 让它把**全部**循环变量从 `i` 改名（`row_index` / `s` / `k`），并全量搜 `var i ` / `var i in`——这类遮蔽往往同时存在于多文件（`admin/domain/*`、`domain/mall/order_list.jss`、`order_detail.jss` 的 `build_steps`），只改报错那一处必然复发 |
| `shop_not_found` / 列表永远空但无报错 | 种子数据没落库；`setup/setup.jss` 是只读生成文件，POST 只会返回 `NULL` 且异常被 `safe()` 吞掉 | 要求另建幂等播种接口（`api/setup/seed_demo.jss`），按业务键判存在、可重复调用，并回报插入数与库内总数 |
| 页面白屏 / 什么都不显示且无报错 | 首屏 `setData` 前抛错、数据未 `await`、组件属性类型不符 | 加 try-catch 与 loading 态，先保证不白屏 |

#### 9.4 提交后必做

1. 用 `chat.jss` 提交 → 拿 `run_id` → 按第 4 步节奏轮询播报
2. 终态后读全文，向用户回报四件事：**我发给它的原文** / **它查出的真实根因** / **改了哪些文件** / **用户现在要做什么**
3. 「用户要做什么」要具体到动作：例如「杀掉小程序重进，**不要点「重试」**」——重试往往只是重跑同一条已崩的渲染逻辑
4. 若根因具通用价值（如本次 `|| []` 兜不住非数组），主动问用户是否要固化进本技能

**禁止**：

- ❌ 只回一句「收到，我让平台修一下」而不提取报错原文
- ❌ 把「页面报错了」当 prompt（模型只能盲猜，通常要来回 3~5 轮）
- ❌ 把多张截图的多个错误塞进一条指令（违反第 8 步 L1）
- ❌ 把本地截图路径/本地 URL 填进 `image` 字段（平台取不到，会被忽略）
- ❌ 修完后只说「已修复」而不交代用户需要执行的动作

---

## 接口清单（15 个，含 login.vm / view_private_token.jss / send_sms_register.vm / register.vm）

| # | 接口                                | URL                                                                                              | Method       | 鉴权               | 状态                                     |
| - | --------------------------------- | ------------------------------------------------------------------------------------------------ | ------------ | ---------------- | -------------------------------------- |
| 1 | create.jss（新）                     | `https://codetg.com/com/codetg/ai/facade/api/agent/dev/create.jss`                                | POST JSON ✅  | pt-xxx ✅         | ✅ 实测：`type` 必须 `wechat_mini`（`wechat_program` 报 `unspported_type`），`build_mode: prototype`，带 `skills: []`；不返回 dev_link/main_project_id，`main_project_id = dev_workspaceid` |
| 2 | create.jss（老）                     | `https://codetg.com/dev/skills/api/module/create.jss`                                            | POST JSON ✅  | pt-xxx ✅         | ✅                                      |
| 3 | status.jss（新）                     | `https://codetg.com/460046184/skills/integration/api/agent/status.jss`                            | POST JSON ✅  | pt-xxx ✅         | ✅（前缀 460046184 可能随环境变 ⚠️；终态 `success`） |
| 4 | status.jss（老）                     | `https://codetg.com/dev/skills/api/agent/status.jss`（POST body 传 run_id）                        | POST JSON ✅  | pt-xxx ✅         | ✅（终态 `completed`；⚠️ GET query 方式返回 `runid_required`，须 POST body） |
| 5 | messages/list.jss                 | `https://codetg.com/com/codetg/ai/assistant/api/messages/list.jss`                                | POST JSON ✅  | pt-xxx ✅        | ✅ 实测（小程序 run 可用；data 为数组，须按 run_id 过滤） |
| 6 | chat.jss                          | `https://codetg.com/dev/skills/api/agent/chat.jss`                                               | POST JSON ✅  | pt-xxx ✅         | ✅                                      |
| 7 | mp_auth/create.jss               | `https://codetg.com/460046184/mini/program/development/platform/api/mp_auth/create.jss` | POST JSON ✅  | Bearer JWT ✅      | ✅ 实测（errcode 89255 已见；个人注册成功时外层返回 authorize_url + taskid，二维码用于用户本人微信扫码完成个人主体注册，≠ 注册完成） |
| 8 | proxy_ci_service.jss             | `https://codetg.com/<租户路径段>/wechat/service/provider/api/ci/proxy_ci_service.jss` | POST JSON ✅ | Bearer JWT ✅ | ✅ 实测（2026-09-09 用户确认）：body `{appid, path, project_id}`；返回 `qrcode_url`（mmbiz 防盗链）+ `trial_qrcode_url`（可直连），交付优先 trial_qrcode_url |
| 9 | mp_auth/create_tester.jss        | `https://codetg.com/460046184/mini/program/development/platform/api/mp_auth/create_tester.jss` | POST JSON ✅ | Bearer JWT ✅ | ✅ 实测（添加体验者；errcode 85001 已见） |
| 10 | chat.jss（新/facade） | `https://codetg.com/com/codetg/ai/facade/api/agent/dev/chat.jss` | POST JSON ✅ | pt-xxx ✅ | ✅ 实测 2026-11-20：**仅需 `main_project_id`+`prompt`+`url` 三字段**；缺 `url` 报 `java.net.MalformedURLException`（报错不提 url）；`assistant_id` 不用传（服务端返回，与网页端值不同）；无需 `is_login`/cookie；返回多出 `app_source_url`/`dev_siteid`/`workspaceid` |
| 11 | get_auth_list.jss（**新增**） | `https://codetg.com/<租户路径段>/wechat/service/provider/api/authorization/get_auth_list.jss` | POST JSON ✅ | Bearer JWT ✅ | ✅ 实测 2026-11-20：body `{projectid}`（小写、可选；不传也返回全量，传不存在的 id 会 `Cannot get property "biz_type" of null`）→ `data` 为账号下**全部**已授权小程序数组（7 条实测），字段 `appid/mp_name/head_img/principal_name/qrcode_url/project_id/is_default`；`mp_name` 可为空；**错误也是 HTTP 200，须看 `code`**；取 appid 的第一入口 |
| 12 | login.vm | `https://codetg.com/com/codetg/aa/login/api/auth/login.vm` | POST JSON ✅ | 无 | ✅ 实测 2026-11-23：body `{login_id, password}`，JWT 在响应体或 `Set-Cookie` 中，正则提取；账号不存在时返回 `{"code":"account_not_exist","msg":"账户不存在"}` |
| 13 | view_private_token.jss | `https://codetg.com/com/codetg/user/basic/information/maintenance/api/profile/view_private_token.jss` | POST JSON ✅ | Bearer JWT ✅ | ⚠️ 接口存活已验证（伪造 JWT → HTTP 200 + `jwt_token_invalid`）；成功返回 `{"code":"success","data":{"token_value":"pt-…"}}`，待真实账号端到端确认。**鉴权失败也是 HTTP 200，须看 `code`** |
| 14 | send_sms_register.vm | `https://codetg.com/com/codetg/aa/login/api/auth/mobile/send_sms_register.vm` | POST JSON ✅ | 无 | ✅ 实测 2026-11-23：body `{mobile}`；⚠️ **外层 `code` 恒为 `"success"`，真实结果看 `data.success`（bool）+ `data.send_status_list[0].code`**；成功示例 `{"data":{"success":true,"request_id":"…","send_status_list":[{"code":"Ok","fee":1,"phone_number":"+86…","message":"send success","serial_no":"…"}]}}`；号码非法 → `data.success:false` + `InvalidParameterValue.IncorrectPhoneNumber`（不扣费） |
| 15 | register.vm | `https://codetg.com/com/codetg/aa/login/api/auth/mobile/register.vm` | POST JSON ✅ | 无 | ✅ 实测 2026-11-23：body `{name, company:"", mobile, invitation_code:"6666", code, password}`；验证码错 → `{"code":"code_is_invalid","msg":"验证码错误"}`；成功返回 `code=="success"` |

> ⚠️ 假定项（method/编码/路径前缀）需在首次联调时实测确认。路径前缀（`codetg.com/` 之后的第一段，形如一串数字）**因租户/环境而异**，本文件中的数字段仅为示例；若接口 404，从 status.jss 的响应、发布页 URL 或上一成功接口的路径中读取真实前缀，不要硬编码。

### Token 模型（不能混）

- **API Key `pt-xxx`**：长期有效，由用户在自己账号内生成并提供；业务接口 `create/status/messages/chat` 使用；**仅在当次任务内存中使用，不落盘**
- **会话 JWT `Bearer eyJ…`**：约 100 小时（~4.2 天）有效，payload 含 `userid`；用途：① `mp_auth/create.jss` 小程序主体绑定 ② `proxy_ci_service.jss` / `get_auth_list.jss` 取码与查询（业务接口不收 JWT）；**由 `get-jwt` 用 mobile + 密钥链密码自动登录换取，缓存 90h 复用；仅在自动登录失败时才请用户手动贴**
- **账号密码**：只存系统密钥链（Windows DPAPI / macOS Keychain / Linux secretstorage），只用于 `login.vm` 换 JWT，明文不落盘、不回显

---

## 硬性规则

1. 业务接口（create/status/messages/chat）用 `Authorization: pt-xxx`（兼容 `Bearer pt-xxx`，服务端自动剥离）；**例外：`mp_auth/create.jss` 主体绑定、`proxy_ci_service.jss` 取码、`get_auth_list.jss` 查询须用会话 JWT `Bearer eyJ…`（`get-jwt` 自动获取，失败才手动贴），用 pt-xxx 会 401**
2. API Key 优先使用环境或已保存配置，缺失时按「凭据与授权」获取。用户明确要求注册后才调用 send-code 和 register，同一次开户只发一次短信。
3. 微信主体绑定、扫码核验和网页上的待确认卡片由用户本人完成。codetg.com 短信注册按规则 2 执行。
4. 只在用户明确要求时调用写操作接口；一次只推进一个步骤，不并发提交
5. **不要**把任何访问令牌或验证信息明文写进对话回复、日志、prompt、交付文案
6. 不读取系统或浏览器中保存的登录状态（cookie / localStorage 一概不碰），不读取本机其它进程的数据；本地凭据文件**仅限** `aicp.json`、`aicp_password.bin`、`xiaomali_jwt.json` 三个，全部由 `scripts/aicp_credentials.py` 管理，不手写、不外传
7. 小程序 `type`：**新接口传 `wechat_mini`**（传 `wechat_program` 报 `unspported_type`），老接口传 `wechat_program`；用户要普通网页/网站时**本技能直接做**：同一个 create 接口传 `type: "web"`（老接口传 `type: "module"`），不要引导用户另装技能、也不要拒单
8. 实时播报必须每 10 秒一次，禁止全程不播报直到终态
9. 状态查询以 `status` 为准：`completed`/`success` 才算成功；失败如实报告 `error` 原文
10. 一次只创建一个小程序；一次失败不盲目连续重试，先分析错误（401/参数/网络/平台状态机错误）再决定
11. 老版 status.jss 必须 **POST body `{"run_id": ...}`**（GET query 方式返回 `runid_required`）；status 报 `trial_qrcode_url of null` 时：生成期内属 `project` 尚未创建 → 视为 in_progress 继续轮询；生成完成后仍报则代表**未绑定 appid**（见第 5 步路径 B），终态以消息流「Prototype complete」为准
12. 用户要求修改已生成的小程序时，优先走 chat.jss 增量修改，不要直接重建；**端点选 facade 新版**（`.../facade/api/agent/dev/chat.jss`，body 只需 `main_project_id`+`prompt`+`url`），异常时回退老版 `dev/skills/api/agent/chat.jss`（见第 7 步）
13. 主体绑定（mp_auth/create.jss）成败以 `data.errcode`（0=成功）为准，外层 `code=="success"` 不代表成功；个人注册把用户微信号填入 `wxuser`，企业注册 `code_type` 取 `1`=统一社会信用代码 / `2`=组织机构代码 / `3`=营业执照代码
14. **取码优先级**：先用项目接口返回的体验码，再查账号绑定列表。仅在网络或平台异常时尝试符合路径 B1 的同项目缓存。
15. **个人注册时序铁律**：`mp_auth/create.jss` 返回 `authorize_url`（二维码）≠ 注册完成——用户必须本人用手机微信扫码完成身份证+人脸核验、拿到 appid 后，才能调 proxy_ci_service 取码 / create_tester 加人。任何一步都不能跳过；appid 不可编造，用户未贴回前明确告知「还在等你的 appid」
16. 使用当前客户端展示授权或体验二维码 PNG，供用户在微信扫码。
17. 本地 JWT 缓存有效 90 小时，托管模式跳过缓存。交付文案只显示脱敏凭据。
18. 添加体验者（create_tester.jss）成败以 `data.errcode` 为准：`0`=成功；`85001`=微信号不存在或不可被搜索 → 提示核对微信号并确认微信「可通过微信号搜索」已开启；`appid` 不可编造，取不到（绑定响应无 / 用户未提供）就明说并询问
19. proxy_ci_service.jss（body `{appid, path, project_id}`）返回 `qrcode_url` + `trial_qrcode_url`：**交付优先 `trial_qrcode_url`**（`//` 补 `https:`，接口返回的图片 URL 可直连下载 → Pillow 加标题转 PNG）；`qrcode_url`（mmbiz.qpic.cn）**服务端下载命中防盗链会得到占位图**，只有拿不到 trial_qrcode_url 时才把 qrcode_url 编码成二维码 PNG 兜底交付
20. **`requires_action`（待确认卡片）一律由用户本人在页面确认**：技能不代为作答、不发送「跳过 / 直接结束」类替代 prompt 越过确认；确认后继续轮询 `status.jss` 取 `project.appid` + `trial_qrcode_url`
21. 长指令失败时按第 8 步拆小再发，需要接续会话时保留项目 ID 和当前待办。
22. **用户发报错截图时，必须先「图转文字」再提交**：从会话附件逐字提取**报错原文**（含大小写/括号/变量名，不许改写）、错误码或响应体、触发页面与操作、同屏其他提示，再按「现象 + 判断 + 只做一件事」三段式拼成 ≤300 字指令发 `chat.jss`。**禁止**把图片原样或本地路径塞进 `image` 字段（该字段只收公网可访问 URL），**禁止**只回「报错了帮你看看」。修完必须回报四件事：发给它的原文 / 真实根因 / 改了哪些文件 / 用户现在要做什么。完整流程与常见报错对照表见第 9 步
23. get_auth_list.jss 成功返回空列表且用户需要体验码或发布时，按第 6 步引导绑定。
24. 账号侧返回多个 AppID 时，请用户选择后再取码。交付时注明二维码归属的主体和当前项目。
25. **后端是异步子 run，跟踪对象必须换**：`chat.jss` 返回的 `run_id` 可能几十秒就 `completed`，而真正的开发 agent 跑在另一个 `run_id`（实测 `run_XXXXXX` 派发 → `run_XXXXXX` 实际开发 44 分钟）。做法：用 `messages/list.jss` 拉全量并**不按 run 过滤**，定位带 `developWechatMiniProgramBackend` 的 assistant 消息，取它所在 run_id 再跟踪 `status.jss`。只盯派发 run 会误判「后端已经做完了」（详见 7.5.1）
26. **后端完成后必须交付三样**：① 平台侧查看入口 `https://codetg.com/user-dev/dashboard?url=https://<domain>`；② **重新取一张体验码并交付（仅小程序）** —— 代码已从 mock 切真实接口，旧码图不能继续用，标题标「已接后端」；③ 一条真实落库凭证（订单号 / 条数 / 时间戳）。网页项目只交付站点 + 后台地址（详见 7.5.2）
27. **后台菜单必须落 `<模块>/admin/ui/admin_function.json`，这是平台唯一扫描路径**：写到 `setup/admin_function.json` 等于没注册（页面能开、侧边栏没有）。`url` 用 `.vuetify` 且带站点前缀，`component_name` 与模板 id 对齐。验证时注意**不存在的页面返回 `{"code":"failed","msg":null}` 而不是 404**；`var menu={}` 是 SPA 占位符，不能作为判断依据（详见第 7.6 步）
28. **jss 后端代码里禁止用 `i` 作循环变量**：`for (var i in rows)` 在 Nashorn 下会把平台函数库 `i`（`i.db` / `i.instance`）遮蔽成 `undefined`，报 `Cannot read property "instance" from undefined`，且外层 `safe()` 会静默吞掉。循环变量一律改 `row_index` / `s` / `k`。同一缺陷常同时存在于 `admin/domain/*`、`domain/mall/*`（订单列表、订单详情 `build_steps`）与播种逻辑，发现一处要全量搜一遍

---

## 待补齐

| 项                                    | 说明                                                       | 阻塞                     |
| ------------------------------------ | -------------------------------------------------------- | ---------------------- |
| 新版 create.jss 对 `wechat_program` 的支持 | ✅ 已闭环（2026-11-19）：必须传 `wechat_mini`，传 `wechat_program` 报 `unspported_type`；`build_mode: prototype` 出可跑原型，`plan` 只出方案 | 已固化 |
| status.jss 统一                        | 老版 GET query 返回 `runid_required`（2026-09-09 实测），须 POST body；新版前缀 `460046184` 是否随环境变     | 已给双路径，POST body 已固化        |
| messages/list.jss 对小程序 run           | ✅ 已实测可用（2026-09-09）：返回 data 数组，按 run_id 过滤 + id 字典序增量 | 已闭环                     |
| 后端异步子 run                          | ✅ 已闭环（2026-11-25）：派发 run 秒级 `completed`，真实开发 run 在消息流里另起；须不按 run 过滤捞取 | 已固化（7.5.1 / 规则 25）   |
| 后台菜单注册路径                        | ✅ 已闭环（2026-11-25）：唯一扫描路径 `<模块>/admin/ui/admin_function.json`，`setup/` 下无效 | 已固化（第 7.6 步 / 规则 27） |
| 演示数据播种                            | ✅ 已闭环（2026-11-25）：`setup/setup.jss` 只读且静默失败，改用 `api/setup/seed_demo.jss` 幂等接口 | 已固化（7.5.2）             |
| `var i` 遮蔽平台函数库                  | ✅ 已闭环（2026-11-25）：循环变量禁用 `i`，否则 `i.instance`/`i.db` 报 undefined 且被 safe() 吞掉 | 已固化（规则 28）           |
| 后台接口鉴权                            | ⚠️ 未解决：生成器产出的 `admin/api/*` 默认**不做登录校验**，公网可直接拉到收货人姓名/手机号/地址 | 交付时必须提示用户上线前补鉴权 |
| proxy_ci_service.jss                   | ✅ 已实测固化（2026-09-09 用户提供真实样例）：body `{appid, path, project_id}`，返回 `qrcode_url`(mmbiz 防盗链) + `trial_qrcode_url`(可直连)，鉴权 Bearer JWT | 已闭环；剩余：data 内 errcode 非 0 的错误分支枚举 |
| 交付字段                                 | 新版返回 `domain` vs 老版 `dev_link`+`miniprogram_preview_url` | 实测后固化单一交付路径            |
| `.vm` 系列请求编码                         | 当前假定 application/json                                    | 实测确认，必要时改表单编码          |
| mp_auth 成功后续                           | `data.errcode=0` 后是否还有审核/状态轮询接口                          | 用真实企业值试通后固化            |
| 授权已有小程序入口                           | ✅ 已闭环（2026-11-20）：无需「绑定」接口，`get_auth_list.jss` 直接列出账号下全部已授权小程序，取 `appid` 即可出码（多条让用户选） | 已固化；剩余：解绑/新增后的列表刷新时机 |
| create_tester 的 appid 来源                 | 个人注册：已确认须等用户扫码授权后从微信公众平台获取（2026-09-08 实测）；企业注册绑定响应是否直接返回 appid 待实测 | 实测后固化提取路径            |
| mp_auth 个人注册的微信侧授权回调               | 用户完成身份证+人脸核验后，appid 是否会自动回流到 codetg（刷新 status/publish 页可见），还是必须用户手动贴回 | 待用户完成一次完整授权后确认 |
| status.jss / publish 页「暂无预览码」          | 生成完成但 status 报 `trial_qrcode_url` null、publish 页显示「暂无预览码」——疑似需完成主体绑定+proxy_ci 取码后才触发，或平台预览服务故障 | 完成主体绑定后复查 |

---

## 触发示例

- 「帮我生成一个奶茶店点单小程序」 → 走完整工作流（取得用户 API Key → create → 实时播报 → 交付链接 → **若账号下无已绑定小程序，再发起主体注册链路：交付注册二维码 → 用户本人扫码完成注册 → proxy_ci 取体验码**）
- 「做一个会员打卡的微信小程序」 → 走完整工作流
- 「我没有 appid」「没注册过小程序」「这个 appid 去哪弄」 → 第 6 步「入口分流」：判定无 appid → 主动引导快速注册 → 要微信号 → 发授权二维码 PNG → 用户扫码完成身份证+人脸核验 → 拿 appid 回填缓存 → 4.2 取码
- 「我已经绑过小程序了 / 我有小程序，能直接用吗」 → **先调 `get_auth_list.jss`**（第 5 步路径 B0）→ 非空就用已有 appid 出码，**不要让人重新注册**；**多条一律让用户选，不许自动挑**
- 「为什么还要我注册？我明明绑过了」 → 说明本地只是没缓存、账号侧是有绑定的：先查 `get_auth_list` 证明给他看（「你账号下绑了 3 个，用哪个？」），查到就直接出码
- 「我就想先看看页面，不用体验码」 → 只交付 `dev_link` 直接打开，如实说明「以后要发布或给别人试用，再来注册小程序」，**不硬推注册**
- 「做个小程序」 → 需求过简，先走第 1 步追问再继续
- 「把刚才那个小程序的首页颜色改成蓝色」 → 走第 7 步增量修改（chat.jss）
- 「把这个小程序发布 / 正式上线 / 绑定主体」 → 走第 6 步：mp_auth/create.jss 发起注册 → 交付注册二维码（个人：用户微信扫码完成身份证+人脸核验；企业：提供名称/代码）→ 完成后 proxy_ci_service.jss 取体验码交付（JWT 由 `get-jwt` 自动登录换取，无需用户手动复制；失败才手动兜底）
- 「帮我加体验权限 / 加体验者 / 给 xxx 开体验」 → 第 6 步第 5 小节（create_tester.jss，用户只需给微信号）
- 「给我体验二维码」 → 第 6 步第 6 小节（先确认已绑定+取码，再交付二维码）
- 「改到一半报 Cannot read property "data" from undefined」→ 第 8 步，先用短指令验证，再分步提交。
- 「新开了会话，接着改刚才的小程序」→ 按第 8 步核对项目 ID、当前状态和待办后再继续。
- 「（发一张报错截图，不配文字）」 → 第 9 步：从会话附件逐字提取报错原文/错误码/页面/同屏提示 → 三段式短指令（≤300 字）→ 提交轮询 → 回报「原文 / 根因 / 改动文件 / 用户下一步」
- 「报错了，你修一下」+ 截图 → 同上，先转文字，不许回「收到，我看看」了事
- 「做个 todo 网页」 → 同一工作流，create 传 `type: "web"`（老接口 `module`），交付可直接访问的页面链接
