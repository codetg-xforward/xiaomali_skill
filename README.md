# 小码力安装说明

小码力通过 codetg.com 创建和修改微信小程序、网页、落地页和 H5，并交付预览链接或微信体验码。

## 安装

解压后将整个 `xiaomali` 目录放到客户端技能目录。确认目录中直接包含 `SKILL.md` 和 `scripts/`，然后重新打开会话。

| 客户端 | 用户级目录 | 项目级目录 |
| --- | --- | --- |
| Codex | `~/.agents/skills/xiaomali/` | `<项目根目录>/.agents/skills/xiaomali/` |
| WorkBuddy | `~/.workbuddy/skills/xiaomali/` | 通过客户端导入 |

Windows PowerShell 示例，在已经解压并包含 `xiaomali` 文件夹的目录运行：

```powershell
$skillRoot = Join-Path $env:USERPROFILE '.agents/skills'
New-Item -ItemType Directory -Force -Path $skillRoot | Out-Null
Copy-Item -LiteralPath .\xiaomali -Destination $skillRoot -Recurse
```

WorkBuddy 用户将第一行的 `.agents/skills` 换成 `.workbuddy/skills`。升级时用新版本完整替换旧技能目录。凭据与缓存位于技能目录之外。

运行环境需要 Python 3.10+ 并可访问 codetg.com。生成或处理二维码 PNG 需要 qrcode 和 Pillow，可运行 `python -m pip install "qrcode[pil]"`。Linux 使用本地密码存储还需 SecretStorage 和可访问的 Secret Service 会话。macOS 或 Linux 可按安装情况将 `python` 替换为 `python3`。

## 凭据与缓存

在技能目录中运行 `python scripts/aicp_credentials.py status` 查看脱敏状态，运行 `python scripts/aicp_credentials.py paths` 查看有效路径。

| 场景 | 配置 |
| --- | --- |
| 本地执行 | 默认使用 `~/.xiaomali/credentials/` 和 `~/.xiaomali/cache/`。默认凭据目录尚未创建时，自动复用已有 `~/.workbuddy/credentials/` 凭据和对应密钥链条目。 |
| 显式目录 | `XIAOMALI_CREDENTIALS_DIR` 和 `XIAOMALI_CACHE_DIR` 接受绝对路径。未指定缓存目录时，名为 `credentials` 的凭据目录使用同级 `cache`，其他目录使用自身下的 `cache`。可指定旧 WorkBuddy 凭据目录以持续共用。 |
| 托管执行 | 在运行环境的密钥配置中设置 `AICP_PT_KEY`。涉及主体绑定和取体验码时，再设置 `AICP_MOBILE` 和 `AICP_LOGIN_PASSWORD`。 |
| 旧环境变量 | `CODETG_PT_KEY` 仍可提供 API Key，优先级低于 `AICP_PT_KEY`。只配置 `CODETG_PT_KEY` 时，手机号和密码仍来自本地凭据。 |

本地已有账号可用 `set-account '<手机号>'` 配置手机号，再在终端运行 `set-password` 后隐藏输入密码，最后用 `get-pt-key` 获取 API Key。通过自动化安全输入通道传值时可使用 `set-password --stdin`。需要新建账号时，经本人明确同意后由技能发起短信注册，验证码由本人提供。微信主体绑定、实名核验和网页上的待确认卡片由用户本人完成。

可运行 `python scripts/codetg_token.py check` 校验环境中的 API Key，或运行 `python scripts/codetg_token.py mask` 查看脱敏值。通过标准输入提供 API Key 时，在子命令后加 `-`。

本地模式可保存 API Key，并缓存会话 JWT 最多 90 小时。托管模式直接从环境读取凭据，跳过本地凭据及缓存。详见 [安全说明](SECURITY.md)。

## 使用示例

- 「用小码力做一个奶茶店点单小程序」
- 「做一个活动落地页，把链接发给我」
- 「把刚才的小程序首页改成蓝色」
- 「给这个小程序生成微信体验码」
