# AICP 凭据与开户

脚本定位、配置优先级和托管环境的变量见 [技能入口](../SKILL.md)。以下子命令均通过同一凭据脚本执行。

本地凭据 JSON 必填 `ptKey` 和 `updatedAt`，可选 `mobile`、`accountId`、`hasPassword`。只有 `mobile` 加上登录密码才能自动换取发布所需的 JWT。`set-password` 可在本地终端隐藏输入，脚本把密码存入系统凭据存储。`clear-password` 清理密码，`delete` 删除 API Key 所在的凭据文件。

业务接口 401 时检查或刷新当前账号的 API Key，已有账号走 A3。新账号注册与发送验证码由用户确认后发起。验证码过期后根据平台提示重发。登录信息、验证码和 JWT 只用于对应的 AICP 调用，避免出现在回复和日志。

## 首次使用 / 凭据缺失时（核心"无感开户"）

### Step 0 — 探测

执行凭据脚本的 `read` 子命令：

- 返回带有效 `ptKey` 的 JSON → 继续当前任务。
- 本地模式返回空或缺少 `ptKey` → 进入 Step 1。
- 读取报错 → 先处理配置或文件错误。托管环境通过密钥配置修复失效的 `AICP_PT_KEY`。

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

→ 本地模式拿到 ptKey 后，将 JSON 写入凭据脚本 `write --stdin`（**不含 password**）。
→ JWT 不落盘（4 天有效，下次失效重走）。

### A3 — 老用户补 key

```
1) POST login.vm → 拿 JWT（正则提取 eyJ…）
2) POST view_private_token.jss（Authorization: Bearer <JWT>） → 拿 ptKey
```

- 问一次手机号 + 密码（用户决定是否存密码；本 skill **不存 password** 到凭据文件）
- 用户拒绝存密码：每次 401 时重问一次（罕见路径）
