# 错题本公网入口与 Cindy 推理

2026-11-04，本机 J71b 的错题本入口配置为 https://ctb.ghtxx.cn，源站是 iPad 上的
`http://127.0.0.1:3000`。使用原有错题本账号登录，未开放注册或更换账号密码。
电池监测与 SSH 不在这个域名的通道规则中。

cloudflared 2026.10.7 使用官方 Linux ARM64 发布文件，校验值：
`3df43aedc9ff291d1735b5cb576cb97e0b157488796db2e32b28aecabb445775`。
服务名为 `cloudflared-ctb.service`，已启用开机启动及失败重启。
配置在 `/etc/cloudflared-ctb/config.yml`，使用独立无登录权限用户。
指标和就绪接口只监听 `127.0.0.1:37310`。实机网络使用 IPv4、HTTP/2 建立连接。
初次网络预检可能超时，判断可用性以 `/ready` 的 HTTP 200、有效连接和公网请求为准。

仓库中的通道 UUID、域名及文件是这一实例的操作记录；复制到其他设备时必须替换成自己的通道。
运行凭据只存于设备 `/etc/cloudflared-ctb/credentials.json`（root 所有、服务组只读），
不提交到 Git。Cloudflare 账号证书保留在 Mac，不复制到 iPad。
仅部署程序不会创建 DNS 或凭据，需先在机主授权账号中创建专用通道，确认子域名无冲突后绑定代理 CNAME。

同目录的 `cloudflared-ctb.yml` 和 `.service` 保存非秘密配置。
恢复或维护可用 `systemctl restart cloudflared-ctb.service`，再检查本地 `/ready` 与公网
`https://ctb.ghtxx.cn/api/health`。回退公网入口时停用此服务并移除该专用 DNS 记录；
不删除错题本数据，也不影响其他通道。

AI 提供商已选择 MacMini Cindy / GPT-6.1 Sol。可选插件源码见
`../wrong-notebook-cindy-bridge/`，通过 Cindy Forge 安装，不直接改 Host 安装目录。
文字、真实图片与 iPad 发起的完整请求均已验证。图片整数答案在 Cindy 消息中可能是数字类型，
桥接保留并转成文本，避免把正确答案误判为空。
旧错题本 AI 配置备份保留在设备私有维护目录，不在仓库中。

公网通道直接运行于 iPad，Mac 关机不影响网页入口，但 AI 推理需要 MacMini、Cindy 和
专用 AI HTTPS 通道持续可用。iPad 关机或断网时网页不可用。
这些服务与个人模型选择都是可选部署，不会在系统镜像中默认安装或开启。

拟议更新说明（未修改 CHANGELOG）：支持为 iPad 错题本配置独立 HTTPS 通道，并通过
Mac 上的 Cindy 进行文字和图片推理。

## 换网后的 AI 调用

旧配置使用 iPad 的 `127.0.0.1:37309`，依赖 Mac 到 iPad 内网地址的 SSH 反向转发。
因此网页虽能从公网打开，iPad 换到另一个网络后仍可能无法调用 AI。
现已迁移到 `https://cindy-ctb.ghtxx.cn/v1`，由 Mac 上独立通道
`cindy-ctb-api`（UUID `c473f2f5-06d2-445e-86a1-632f0bacf158`）转到 Mac 回环端口 37309。
插件的旧 SSH 转发已停止，重启插件也不会自动恢复旧路径。
新增入口仍使用原有随机桥接 Bearer 密钥，未认证的模型请求实测返回 401。
这是桥接自身的认证，不是 Cloudflare Access 服务令牌。

Mac 的 `app.cindy.ctb-api-tunnel` LaunchAgent 在用户登录时启动并自动重启连接器；
配置为 `~/.cloudflared/cindy-ctb-api.yml`，指标只监听 `127.0.0.1:37311`。
重建说明见同目录 `install-mac-cindy-tunnel.py`；该脚本不会覆盖已有配置。
它是特定实例的操作记录，不会创建 DNS 或生成、分发凭据，其他部署须使用自己的通道。

验证：8 项桥接测试通过；停止旧转发后，iPad 读取当前提供商配置并通过公网 HTTPS
完成文字和图片推理；Mac 通道重启后 iPad 的认证模型请求仍成功。
没有自动修改 iPad Wi-Fi，未声称已经在其他运营商网络实测。
回退可显式重新配置旧内网模式并重新配对，或恢复设备私有目录中的原应用配置。
不要直接删除通道或 DNS，除非确定已不再被当前 AI 提供商使用。
