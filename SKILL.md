---
name: xiaomali
description: 用小码力（AICP）创建、查询或修改微信小程序，办理微信主体绑定并交付体验码。适用于用户要求生成微信小程序、修改已有小程序或获取微信体验二维码。
---

# 小码力微信小程序开发

通过 `codetg.com` 的 AICP 接口开发微信小程序，创建时使用 `type: "wechat_program"`。普通网站和 Web 应用属于 AICP 开发平台的 Web 流程。

## 运行条件与凭据

- 当前环境需要能通过 HTTPS 访问 `codetg.com`。图片依赖和各平台的本地凭据条件见 [README](README.md#运行条件)。
- 以已加载的 `SKILL.md` 所在目录定位 [凭据脚本](scripts/aicp_credentials.py)。从任何项目调用时使用脚本的完整路径并加引号。选择当前环境可用的 Python 3.10+ 启动命令，如 `python`、`python3` 或 Windows 的 `py -3`。
- 开始前执行凭据脚本的 `read`。业务调用用 `Authorization: <ptKey>`。本地缺少有效凭据时，按[凭据与开户流程](references/credentials.md)登录或注册。业务接口返回 401 时检查现有账号的 Key。
- 本地默认使用 `~/.xiaomali/credentials/`。可以用环境变量 `XIAOMALI_CREDENTIALS_DIR` 指定绝对目录。未显式配置且新目录尚未创建时，已有 WorkBuddy 凭据从 `~/.workbuddy/credentials/` 读取和更新，以便继续共用。
- 托管环境通过密钥配置设置 `AICP_PT_KEY`。主体绑定、取码和添加体验者还需要 `AICP_MOBILE` 和 `AICP_LOGIN_PASSWORD`。配置 `AICP_PT_KEY` 时，凭据脚本从环境读取，不读写本地凭据。
- 执行 `get-jwt` 可获取用于主体绑定、取码和添加体验者的 `Authorization: Bearer <JWT>`。本地缺少登录密码时可在终端运行 `set-password` 隐藏输入，密码由系统凭据存储保护。只在对应请求中使用密钥和 JWT，避免写入工作区、回复或日志。

## 选择流程

- **新建小程序**。按[创建与原型验收](references/create.md)先生成可扫码的原型并交付体验二维码，等待用户明确确认当前版本。收到原型修改意见时，在原项目修改后重新发码复验。用户确认最新原型后，才按[增量开发流程](references/update.md)在同一个 `main_project_id` 中开发所需的业务后端。
- **主体绑定、体验码或体验权限**。读取[主体绑定与取码](references/publish.md)。创建完成后衔接体验码交付，已有体验码时直接交付。需要新建主体时，先确认用户希望发起该操作并收集对应主体资料。个人主体由用户在手机微信里扫码并完成身份核验。拿到真实 AppID 后再取体验码或添加体验者。体验码的访问范围以体验者权限为准。
- **修改已有小程序**。读取[增量修改](references/update.md)。核对目标项目后优先用原项目的 `chat.jss` 提交，保留项目及运行标识。降级接口的唤醒与方案确认各有单独的 run。跟踪实际开发 run，验证完成后再交付。若项目正在等待原型验收，继续按[原型验收流程](references/create.md#第-5-步--交付原型并等待确认)推进。
- **核对端点或已知限制**。查看[AICP 接口索引与联调记录](references/api.md)。网络超时或结果不明时先查询任务状态，再决定是否重试创建、绑定或修改。

## 交付二维码

1. 个人注册时，将当前任务的微信 `authorize_url` 编码成 PNG，并标明「注册授权码」。体验码优先使用 `trial_qrcode_url` 返回的图片，协议相对 URL 补 `https:`，然后转为 PNG。只有微信原图 URL 时，按[取码规则](references/publish.md)处理。
2. 通过当前客户端可用的图片展示或文件附件功能交付 PNG。如果客户端和用户共享本地文件系统，也可以提供可打开的 PNG 完整路径。生成二维码可用 `qrcode`，转换或加标题可用 Pillow。确保保存后的二维码可以扫描。
3. 客户端无法交付文件时，提供能访问的原始体验二维码图片或平台预览入口。个人注册授权需要用户在手机微信中扫码，这一步应在能交付授权二维码的环境继续。
