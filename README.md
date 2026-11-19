# 小码力（微信小程序开发）安装说明

在 codetg.com（AICP 开发平台）上生成微信小程序的技能。

## 安装步骤

1. 将整个 `xiaomali` 文件夹复制到技能目录：
   - Windows: `C:\Users\<你的用户名>\.workbuddy\skills\xiaomali\`
   - macOS / Linux: `~/.workbuddy/skills/xiaomali/`
   - 最终结构应为 `.../.workbuddy/skills/xiaomali/SKILL.md` 与 `.../xiaomali/scripts/aicp_credentials.py`
2. 重启 WorkBuddy 会话（或新开会话），技能即自动加载
3. 首次使用时无需手动配置令牌：技能会自动检测本地凭据 `~/.workbuddy/credentials/aicp.json`
   - 已安装并配置过「AICP 开发平台」（aicp-dev-platform）技能的用户：凭据共用，**无需任何操作**
   - 无凭据时，技能会在对话里引导完成注册 / 登录并自动换取 API Key（`pt-` 开头），全程无需手动填文件

> Web 网站/落地页开发请安装配套技能「AICP 开发平台」（aicp-dev-platform）。两技能共用同一账号与凭据文件。

## 使用方式

安装后直接对话即可触发，例如：
- 「帮我生成一个奶茶店点单小程序」
- 「做一个会员打卡的微信小程序」
- 创建完成后**自动衔接**：技能会调用 mp_auth/create.jss 发起微信主体注册，把注册授权二维码交付给你扫码（个人注册需身份证+人脸核验），注册完成后自动调 proxy_ci_service.jss 取体验码并以二维码交付
- 「把这个小程序发布 / 绑定主体」→ 技能自动完成微信主体绑定 → 注册二维码 → 取码交付，只需提供微信号（个人）或企业名称/企业代码/代码类型（企业）；首次会引导设置一次登录密码

## 安全说明

- API Key 保存在本地凭据文件 `~/.workbuddy/credentials/aicp.json`（自动收紧文件权限），**不再写入 SKILL.md**
- 登录密码保存在**系统密钥链**（Windows DPAPI / macOS Keychain / Linux secretstorage），明文永不落盘
- 发布绑定用的会话 JWT 由脚本自动登录获取，仅当次使用后丢弃，不落盘
- **不要**把已含凭据的文件分发或提交到 git 仓库
- 令牌失效（接口返回 401）时，对话里说一声即可，技能会引导重新获取
