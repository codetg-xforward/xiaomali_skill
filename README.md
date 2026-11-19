# 小码力微信小程序开发

通过 AICP 平台创建、查询和修改微信小程序，支持微信主体绑定和体验码交付。

## 安装

将本仓库克隆、解压或复制为名为 `xiaomali` 的目录，放到客户端支持的技能目录。目录内应直接包含 `SKILL.md`、`scripts/` 和 `references/`。

| 客户端 | 用户级位置 | 项目级位置 |
| --- | --- | --- |
| Codex、Gemini CLI | `~/.agents/skills/xiaomali/` | `<项目根目录>/.agents/skills/xiaomali/` |
| Claude Code | `~/.claude/skills/xiaomali/` | `<项目根目录>/.claude/skills/xiaomali/` |
| WorkBuddy | `~/.workbuddy/skills/xiaomali/` | 依客户端的导入方式 |

`~` 表示当前用户的主目录，Windows PowerShell 中可用 `$HOME`。其他客户端可通过自身的 Agent Skills 导入功能加载同一目录。安装后新开会话，确认技能列表中出现 `xiaomali`。

例如，用 Windows PowerShell 为 Codex 或 Gemini CLI 安装到用户目录：

```powershell
git clone https://github.com/codetg-xforward/xiaomali_skill.git "$HOME/.agents/skills/xiaomali"
```

## 运行条件

- Python 3.10 或更新版本。当前执行环境需允许访问 `https://codetg.com`。下载平台托管的体验码图片时还需访问响应中给出的图片域名。
- 生成授权二维码或转换体验码图片需要 `qrcode` 和 `Pillow`，可用 `python -m pip install "qrcode[pil]"` 安装。
- 本地密码使用 Windows DPAPI、macOS Keychain 或 Linux Secret Service。Linux 保存登录密码还需安装 `SecretStorage` 并有可访问的 Secret Service 会话。
- 托管客户端需要在实际执行技能的环境中安装脚本依赖、配置网络和密钥，并支持交付生成的图片文件。

## 配置凭据

| 使用场景 | 配置 |
| --- | --- |
| 新安装 | 本地默认使用 `~/.xiaomali/credentials/`。没有 API Key 时，技能会引导登录或注册。 |
| 已有 WorkBuddy 或配套 AICP 开发平台凭据 | 如果新目录尚未创建，自动沿用 `~/.workbuddy/credentials/`。要持续使用共享目录，可将 `XIAOMALI_CREDENTIALS_DIR` 设为该目录的绝对路径。 |
| 托管执行 | 在环境的密钥配置中设置 `AICP_PT_KEY`。主体绑定、取体验码或添加体验者时，也设置 `AICP_MOBILE` 和 `AICP_LOGIN_PASSWORD`。 |

`AICP_PT_KEY` 优先于本地文件。未配置它时，本地路径按显式配置、新目录、已有 WorkBuddy 凭据的顺序选取。登录密码可由凭据脚本的 `set-password` 子命令在终端隐藏输入。API Key、密码和 JWT 都应留在各自的凭据存储或运行环境中。

## 使用

- 「生成一个奶茶店点单微信小程序」
- 「把刚才那个小程序的首页改成蓝色」
- 「绑定这个小程序的个人主体，发我授权二维码」
- 「给这个已绑定的小程序生成体验码」

个人主体授权需要本人在手机微信中完成扫码和身份核验。技能会在取得 AppID 后继续取码。完整流程见 [SKILL.md](SKILL.md)。
