# 独立知识图谱与诊断网站

部署于 https://math.ghtxx.cn，和错题本独立，没有改写错题或用户数据。
上游：https://github.com/xiaoyang111222/cn-math-taxonomy
固定提交：`276b88c4ff57d6bb9da986c68d7058a0cbc5225f`。
这是纯静态页面，不运行 npm 或上游的 Cloudflare 发布脚本，不需要数据库或 AI 服务。

## 本机部署记录

- 服务：`cn-math-taxonomy.service`，无登录权限专用用户，开机自启，失败自动重启。
- 发布目录：`/opt/cn-math-taxonomy/releases/276b88c4ff57`，`current` 为活动版本软链接。
- 源站仅监听 `127.0.0.1:3002`，Cloudflare Tunnel 的 `math.ghtxx.cn` 规则指向该端口。
- 复用 iPad 的 `ipad-ctb` 通道；保留 `ctb.ghtxx.cn` 的原规则及最终 404 规则。
- 新增代理 CNAME 指向该 iPad 通道，没有覆盖已有 DNS 记录。
- 服务限制为 64MB 内存、32 个任务。实测加载页面后约 17MB，未启动数据库或 Node 服务。

按上游 `scripts/deploy-cf.sh` 的静态文件清单打包：`index.html`、`sw.js`、
`manifest.webmanifest`、`assets/`、`explore/`、`diagnose/`、`children/`，以及
`data/` 中 `topics.json`、`dependencies.json`、`cn-curriculum-standards.json`、
`questions.json`、`id-aliases.json`。另保留根 `LICENSE` 与部署来源说明。
不打包 Git、脚本、生成批次和截图。

部署副本只做了三处调整：

1. `assets/stats-config.js` 的统计 token 和 endpoint 设为空，停用上游统计上报。
2. `diagnose/share.js` 的分享二维码目标改为 `https://math.ghtxx.cn/?from=share`。
3. `sw.js` 缓存版本设为 `ghtxx-276b88c4-v1`。

保留作者来源、CC BY-NC 4.0 许可证和 vendor 各自许可证；未复制到本仓库更换许可。
本次发布包 2240065 字节，SHA-256：
`6615cbe17baa2eb0b7c1401e14c467476b3ad88f329993fc661b280faf65c765`。
经已授权、严格校验主机身份的 SSH 上传，在 iPad 上校验 SHA-256 后解压到版本目录，
静态目录由 root 持有、只读给服务用户。

同目录的 service 文件保存服务配置。`enable-taxonomy.sh` 验证本机数据、保留旧通道
配置备份并增加新主机名规则，校验 ingress 后重启连接器；不包含任何通道凭据。
DNS 绑定另在机主 Cloudflare 账号中完成。

## 验证与使用限制

上游 `node tests/test_engine.js`：94 通过、0 失败；
`node tests/test_blindspots.js`：7 通过。
离线缓存清单引用的资源全部存在。公网首页、统计关闭配置和诊断数据加载通过；
浏览器实际进入七年级整体筛查并显示第 1 题。重启静态服务后首页仍返回 200，
错题本健康检查保持正常。

学习记录和孩子档案只存在访问者浏览器 localStorage，不在服务器，也不跨设备同步。
不能把这里的离线/PWA 支持理解为已为用户的每台设备安装或缓存成功。
在需要的设备上用浏览器访问，再使用浏览器“添加到主屏幕”。

回退时停用 `cn-math-taxonomy.service`，只移除 `math.ghtxx.cn` 的 ingress 和专用 DNS
记录，保留错题本及其他通道。服务源站文件无用户学习记录，浏览器中的记录需用户自行导出。
本项是可选部署，不进入镜像默认安装。CHANGELOG 未修改；拟议说明：可选部署轻量知识图谱
与自适应诊断网站，并支持独立 HTTPS 访问。
