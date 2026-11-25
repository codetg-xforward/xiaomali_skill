# SECURITY.md — 小码力技能安全声明

版本：1.1.0
适用技能：`xiaomali`（codetg.com 生成技能）

## 1. 能力范围

本技能通过 codetg.com 的 HTTP 接口编排两类任务：

- 微信小程序：创建项目、轮询进度、交付预览链接与体验二维码、增量修改
- 网页 / 落地页 / H5：同一 create 接口传 `type: "web"`

技能不包含本地可执行的服务端、不安装系统级组件、不启动后台进程。

## 2. 凭据处理

登录密码用于向 codetg.com 登录或注册。本地密码使用系统密钥链，托管密码由运行环境的密钥配置提供。

| 项目 | 处理方式 |
| --- | --- |
| API Key（`pt-` 开头） | 本地可保存至 `aicp.json` 供复用。托管从 `AICP_PT_KEY` 读取。旧变量 `CODETG_PT_KEY` 也可提供 API Key。 |
| 账号手机号 | 本地保存在 `aicp.json`。托管从 `AICP_MOBILE` 读取。 |
| 登录密码 | 本地使用 Windows DPAPI、macOS Keychain 或 Linux Secret Service。托管从 `AICP_LOGIN_PASSWORD` 读取。 |
| 会话 JWT | `get-jwt` 通过登录换取。本地 `xiaomali_jwt.json` 缓存最长 90 小时。托管或指定 `--no-cache` 时跳过缓存。 |
| 短信验证码 | 由用户提供，在本次注册请求中使用。 |
| 系统或浏览器中保存的登录状态 | 技能不读取浏览器 Cookie 或 localStorage。 |

完整 API Key 和 JWT 仅供请求使用。需要向用户展示时使用脱敏值。密码可在终端隐藏输入或经安全输入通道传入标准输入。

## 3. 本地文件与清理

默认位置为 `~/.xiaomali/credentials/` 与 `~/.xiaomali/cache/`。显式路径和旧 WorkBuddy 目录的优先级见 [安装说明](README.md)。运行 `python scripts/aicp_credentials.py paths` 查看当前路径。

| 文件 | 内容 | 清理方法 |
| --- | --- | --- |
| `aicp.json` | 手机号、账号 ID、API Key 及状态字段。API Key 和手机号为明文。 | `delete` |
| `aicp_password.bin`（Windows）或系统密钥链条目 | 加密或受系统保护的登录密码。 | `clear-password`，建议在执行 `delete` 前清除。 |
| `xiaomali_jwt.json` | 会话 JWT、获取时间和手机号散列。JWT 为明文。 | `clear-password` 会同时清除，或按输出路径单独移除。 |
| `xiaomali_appid.json` | 小程序和对应项目标识。 | 按输出路径移除。 |

托管模式只使用环境凭据，跳过以上本地文件。Windows DPAPI 将密文绑定当前登录用户，同一用户身份运行的其他进程仍可能解密。脚本尝试收紧本地凭据和 JWT 文件的权限。

## 4. 网络访问

- 主动请求仅限 `https://codetg.com`（用户账号所在平台）
- 交付体验码时会按接口返回的图片 URL 做只读下载，该 URL 由平台下发，不在包内硬编码任何第三方域名
- 不上传用户本地文件到其它服务；用户提供的截图仅作当次任务的文本化识别

## 5. 需要用户本人完成的操作

以下操作涉及用户身份，技能只提供入口与接口编排：

1. 账号注册：技能可代调 `send-code` / `register`，但**手机号与短信验证码必须由用户本人提供**，技能不编造号码、不绕过验证码校验
2. 微信小程序主体绑定与实名核验（身份证 + 人脸）
3. 页面上的待确认卡片（`requires_action`）选择与确认
4. 授权二维码、体验码的扫码动作

技能不会发送「跳过确认 / 直接结束」类替代指令来越过上述确认。

## 6. 敏感数据

- 包内示例中的 appid、project id、siteid、账号 ID 均已替换为占位值
- 不包含真实账号的个人信息、令牌、公司名称
- 不包含任何硬编码的密钥或令牌

## 7. 依赖

- Python 3.10+ 标准库（`codetg_token.py` 只用 `os`、`sys`）
- 生成或处理二维码 PNG 需要 `qrcode` 和 `Pillow`
- Linux 本地密码存储需要 SecretStorage 和可访问的 Secret Service 会话

## 8. 联系方式

如需核实行为或报告问题，请联系技能发布者（codetg.com）。
