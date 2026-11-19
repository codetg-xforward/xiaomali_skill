# AICP 接口索引与联调记录

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
