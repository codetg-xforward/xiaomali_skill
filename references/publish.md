# 主体绑定、体验码与体验者

## 第 6 步 — 小程序主体绑定、注册授权与取码交付

按[技能入口](../SKILL.md#选择流程)衔接主体绑定与取码。个人主体需要微信号 `wxuser`，企业主体需要企业名称、代码和代码类型。

**自动链路总览**：

```
mp_auth/create.jss（发起微信注册任务）
  → 个人注册: 返回 authorize_url（注册授权二维码）→ PNG 交付给用户扫码 → 用户完成微信「快速注册个人小程序」
  → 企业注册: 绑定响应含 appid（或无则从发布页取）
  → proxy_ci_service.jss（取体验码）→ 返回 qrcode_url → 以二维码形式交付
  →（可选）create_tester.jss 给更多微信号开体验权限
```

> **鉴权注意（与业务接口不同）**：本步接口均用**会话 JWT**（`Bearer eyJ…`，约 100 小时有效），**不是 pt-xxx**——用 pt-xxx 调会 401。
> JWT 由凭据脚本 `get-jwt` 自动登录获取（使用当前环境配置的手机号和密码）——**用户全程无需手动拷贝任何 token**；JWT 用完即弃，不落盘。

**流程**：

1. **分流并收集参数**：
   - **个人注册（默认）**：问「绑定个人主体需要你的微信号，是多少？」→ 填入 `wxuser`
   - **企业注册**：问「企业名称」「企业代码」「代码类型」；代码类型三选一：`1`=统一社会信用代码、`2`=组织机构代码、`3`=营业执照代码
2. **自动取 JWT（用户无感）**：
   - 用[凭据脚本](../SKILL.md#运行条件与凭据)执行 `get-jwt`。stdout 中的 JWT 用于本次 `Authorization: Bearer <JWT>` 请求。
   - `PASSWORD_NOT_SET` 时，本地请用户在终端运行 `set-password` 隐藏输入，托管环境请用户配置 `AICP_MOBILE` 和 `AICP_LOGIN_PASSWORD`。
   - `LOGIN_FAILED` 时核对网络和账号配置，再决定是否重试。
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

**授权二维码交付**

按[二维码交付规则](../SKILL.md#交付二维码)，把最新任务的 `authorize_url` 编码成 PNG，标明「个人小程序注册授权」并交付。引导用户在手机微信中扫描，或从微信扫一扫的相册入口选图。收到微信公众平台下发的 AppID 后进入取码。

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
- `trial_qrcode_url`：codetg 转存的体验码图片（pic.aier3.com，`//` 开头**须补 `https:`**），**可直连下载**——交付体验二维码**优先用这个**：下载 → Pillow 放大加标题（「小程序体验码」+ appid/projectid 副标题）→ 转 PNG → 通过当前客户端交付
- 如果无法取得有效的体验码图片，提供开发链接中的 `miniprogram_preview_url`，请用户在平台预览页查看实际体验码。
- 按[二维码交付规则](../SKILL.md#交付二维码)发送可扫描的 PNG。

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
   - 优先取 4.2 proxy_ci_service 返回的 **`trial_qrcode_url`**（`//` 开头补 `https:`，pic.aier3.com 可直连）下载 → Pillow 加标题转 PNG → 通过当前客户端交付
   - 图片被拦截或缺失时，提供第 5 步交付的 `miniprogram_preview_url`（`/publish?projectid=<id>`），引导用户在发布页查看体验码
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
