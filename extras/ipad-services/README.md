# iPad 可选常驻服务

J71b 原生 ARM64 Linux 上的个人部署示例，**不是镜像默认安装内容**。
2026-11-04 已实机启动错题本与电池监测，并验证局域网访问和服务重启。

## 智能错题本

项目：[margrop/wrong-notebook](https://github.com/margrop/wrong-notebook)。
部署方式：[官方 npm 安装说明](https://github.com/margrop/wrong-notebook/blob/main/doc/INSTALL_PACKAGES.md)。

本次固定版本：

- Node.js `v24.22.2`，官方 Linux ARM64 二进制，安装前匹配官方 `SHASUMS256.txt`。
- npm 包 `wrong-notebook@2026.11.3`，安装时由 npm 验证 registry 的 integrity。
- 系统 OpenSSL 3，页大小 16384 字节；Prisma ARM64/OpenSSL 3 查询引擎已成功加载。

没有运行桌面 Electron 壳、没有在 iPad 上编译 Next.js、没有安装 Docker，
也没有替换系统 Node 或执行系统整机升级。

本机目录约定：

| 路径 | 用途 |
| --- | --- |
| `/opt/wrong-notebook/runtime/node-v24.22.2-linux-arm64` | 独立 Node 运行环境 |
| `/opt/wrong-notebook/runtime/current` | 指向 Node 运行环境 |
| `/opt/wrong-notebook/releases/2026.11.3` | npm 安装前缀 |
| `/opt/wrong-notebook/current` | 指向当前安装前缀 |
| `/var/lib/wrong-notebook` | 数据库、配置、会话密钥；仅服务账户可读写 |
| `/var/cache/wrong-notebook` | npm 和 Next.js 可重建缓存 |

用独立的 `wrong-notebook` 系统账户安装及运行，不允许交互登录。
npm 安装使用固定版本、独立前缀和缓存；执行 Node 命令前切换到服务账户可访问的目录，
避免继承 root 的 `/root` 工作目录。安装完成后应用文件改为 root 管理、不可由服务账户修改。
`.next/cache` 链接到该账户可写的缓存目录。

`wrong-notebook.service` 监听端口 3000，使用生产模式，配置自动重启和开机启动。
Node 堆上限 384MB，服务内存硬上限 800MB；这是本机运行约束，不代表应用永远只需这些内存。
数据库和缓存位于 systemd 的可写目录，应用和系统目录保持只读。

首次启动会生成私有的一次性初始化链接，令牌在数据目录的 `config/setup-token`。
机主通过初始化页面设置管理员邮箱和密码；密码、令牌、密钥、数据库和 AI 配置不进入 Git。
配置 AI 渠道后才能识题或生成讲解。其他设备通过浏览器访问本机局域网地址的 3000 端口。

## 只读电池监测

`battery-monitor.py` 仅依赖 Python 标准库，读取 `/sys/class/power_supply`：

- 当前电量、仪表状态、净电流、温度、电压、健康和输入限流。
- 每分钟记录一次到 SQLite，滚动保留七天；网页每 20 秒刷新，支持最近 1、6、24 小时曲线。
- 电池净电流保留正负号；正为充入、负为净放电。缺失传感器显示未知。
- 输入限流与实际电池电流分别展示；两类读数的更新时间可能不同。
- 没有驱动重绑、充电控制、限流写入、USB 操作或自动桌面恢复功能。

将 `battery-monitor.py`、`index.html` 安装到 `/opt/ipad-battery-monitor/`，
创建无交互登录的 `ipad-battery-monitor` 系统账户，再安装同名 service 到 `/etc/systemd/system/`。
服务监听 3001，使用 `/var/lib/ipad-battery-monitor/history.sqlite3`，内存上限 64MB，
CPU 配额 10%，数据目录仅服务账户可读写。unit 的 IP 规则允许本机与 RFC1918 局域网地址。
它没有账号体系，适用于可信局域网，不应直接映射到公网。

```sh
systemd-analyze verify /etc/systemd/system/wrong-notebook.service /etc/systemd/system/ipad-battery-monitor.service
systemctl daemon-reload
systemctl enable --now wrong-notebook.service ipad-battery-monitor.service
curl http://127.0.0.1:3000/api/health
curl http://127.0.0.1:3001/health
```

卸载入口是停止、禁用对应 unit；删除应用程序不会代替备份或自动删除数据目录。
升级错题本时保留数据、会话密钥和配置，并使用官方数据库迁移流程。

## 验证与限制

- `check-monitor.py` 验证负电流、缺失传感器和七天历史清理。
- 实机两个健康接口和 Mac 经局域网访问均返回 200。
- 两个 unit 重启后，错题本会话密钥及初始化令牌不变，监测历史保留。
- 手机宽度页面无横向溢出；曲线刻度按实际容器宽度排版。
- 启动初期错题本约 150–180MB、电池监测约 16–21MB；不是压力测试结果。
- 管理员已由机主创建并登录，一次性初始化令牌已删除；未声称已完成 AI 识题、打印或多人并发测试。
- 已启用 Linux 内的开机启动，不代表 checkm8 设备能脱离电脑自动重新引导 Linux。
- 本机充电仍有波动，第二版充电候选待重新引导验证；部署不改变充电驱动。

CHANGELOG 未改动。可提议的条目：新增可选的个人错题本部署示例与只读电池监测服务。
