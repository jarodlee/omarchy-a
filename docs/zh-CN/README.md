# Omarchy A 中文安装与使用指南

本 fork 面向简体中文用户。新构建镜像在首次进入桌面前就准备好语言、字体和输入法，不需要先用英文桌面在线补装。

## 默认配置

| 项目 | 默认值 |
| --- | --- |
| 系统 locale | `zh_CN.UTF-8`，构建时生成 |
| 桌面语言 | `zh-CN`，包含 Shell 和菜单词典 |
| 中文字体 | Noto Sans CJK，简体中文优先使用 SC 字形 |
| 输入法 | Fcitx5，英文键盘和拼音；GTK、Qt 集成 |
| 中英文切换 | `Ctrl + 空格`；应用列表也有“切换中英文输入” |
| 桌面方向 | 支持的单块原生 iPad 面板默认横屏 `90`，锁定方向 |
| 触摸 | 原生触摸 `mouseEmulation="no"`，映射到实际连接的显示输出 |
| 启动登录 | 沿用上游 PIN greeter；桌面内锁屏仍正常验证 PIN |

硬件实测范围是 iPad 6 Wi-Fi（`iPad7,5` / J71b）、Omarchy A v0.2.0、Labwc / wlroots 0.20.2。当前 fork 在该经验基础上集成了默认值；本次没有重新构建和安装完整的新镜像。其他机型不能据此视为已验证。触摸在短时验证通过后又发生过失效，目前重新初始化控制器可恢复，但长期稳定性问题尚未解决，详见[复发记录](operations.md#7-触摸复发补记2026-11-02)。启动 greeter 保留原有方向；登录后的桌面应用已保存的横屏偏好。

## 安装到 iPad

完整机制见[上游安装说明](../../README.md#install)。Omarchy A 是原生启动的 Arch Linux ARM 桌面，与 iPadOS 里的 LinuxRunner 应用属于不同方案。

1. 备份设备。分区工具和安装器可能改动磁盘，备份不是中文配置脚本的一部分。
2. 使用能传输数据的 USB 线。此次 USB-C 转 Lightning 线进入 DFU 不可靠，换成 USB-A 转 Lightning 后继续；电脑没有 USB-A 时可用转接器或扩展坞。
3. 下载 [Resize APFS](https://github.com/OrchardLinux/resize-apfs/releases)，在 macOS 推荐用 `ditto -x -k` 解压，保留 app 内文件的执行权限。运行其 `boot`，按提示进入 DFU。
4. 若屏幕是“连接电脑”的图案，当前是恢复模式，不是 DFU；正确 DFU 屏幕应保持黑色。带 Home 键设备按安装器的倒计时操作，勿只依据固定秒数判断成功。
5. 启动回 iPadOS 后解锁，打开 Resize APFS，清理存储后再选 **Adjust size → Review changes**。此次 128 GB 设备保留约 72 GB 给 APFS，留约 56 GB 未分配空间给 Linux。该数字是一次实测选择，并非所有设备的强制默认值。
6. 等工具显示 **Completed and verified**。耗时取决于数据搬移量；不能从聊天时间推算磁盘操作耗时。
7. 构建本 fork 的镜像并通过 Orchard 安装，见下一节。不要以为上游 `releases/latest/download/install.sh` 已包含本 fork 的中文配置。
8. 在安装器的本地安全提示中设置 Linux 账户密码及 6 位锁屏 PIN。SSH 公钥由安装器导入；不要将密码、PIN 或私钥写入 Git。

若利用过程中重连超时，可按安装器提示将 iPad 端 Lightning 插头拔下，等约 2 秒后插回。保持供电；不要在分区写入阶段这样操作。

## 从本 fork 构建

按 [BUILD.md](../../BUILD.md) 准备 Orchard 开发环境和原生 ARM64 构建环境。本仓库负责发行版，Orchard 负责硬件和启动；不要绕过它直接运行内核或引导组件的生产脚本。

```sh
git clone https://github.com/jarodlee/omarchy-a.git
cd omarchy-a
orchard build --version dev-zh-CN
orchard install
```

`orchard` 必须是支持开发命令的 Orchard launcher（参见上游 README 的 Development checkout），不是只带 `install/launch` 的发布版 CLI。完整构建会安装 `system/packages.txt` 的签名软件包并生成中文 locale；请勿只把新配置叠到不含 Fcitx5 和 CJK 字体的旧 base root 上。

当前仓库提交不等于已经发布可下载镜像。新镜像须按上游发布流程构建、审计，并另行实测新安装及冷启动。

## 日常使用

- **打开应用：** 点左上角菜单里的“应用”。桌面默认不铺应用图标。
- **中文输入：** 先聚焦文本输入框，按 `Ctrl + 空格` 切换拼音。输入 `nihao`，空格选择“你好”；外接键盘和屏幕键盘都通过正常输入法通路输入。
- **只有触屏时切换：** 在应用列表打开“切换中英文输入”，再回到文本框。Fcitx5 配置工具也已安装。
- **SSH：** 默认只接受公钥，不是 Linux 密码。USB 地址在此次安装中是 `172.16.42.1`，用户名是 `tablet`；无线地址由路由器分配，用 `ip -br addr` 查看。

```sh
ssh -i /path/to/installer-key tablet@172.16.42.1
```

请使用自己安装器导入的私钥路径，不要照搬其他电脑的路径或泄露私钥。

方向可以随时更改：

```sh
omarchy-display-orientation landscape
omarchy-display-orientation portrait
omarchy-display-orientation auto
```

`auto` 恢复仓库已有的 iio-sensor-proxy 旋转监听，随后转动设备即可生效。固定方向保存于 `~/.config/omarchy/output-transform`，`rotation-lock` 存在时监听器不改变方向。保持原生触摸及输出映射；本次实测不需要另加旋转校准矩阵。

## 重启后进入 Linux

这仍是 **tethered boot**。冷启动后需要连接电脑，进入 DFU，再运行：

```sh
orchard launch
```

本 fork 不会把它变成脱离电脑的自动原生启动，也不改变 iPadOS 的启动路径。

## 已安装用户补装中文

新默认值用于新镜像；现有系统不会因 Git 仓库更新而自动修改。先在本机备份将要替换的配置，再按以下顺序操作：

1. 在 iPad 的 Linux 终端完成系统升级并安装软件包：

   ```sh
   sudo pacman -Syu --needed fcitx5 fcitx5-chinese-addons fcitx5-gtk fcitx5-qt fcitx5-configtool noto-fonts-cjk
   ```

2. 在 `/etc/locale.gen` 启用 `zh_CN.UTF-8 UTF-8`，运行 `sudo locale-gen`，再运行 `sudo localectl set-locale LANG=zh_CN.UTF-8`。
3. 将 `desktop/configuration/chinese-defaults/home/tablet/` 下需要的文件复制到当前用户的家目录，对已有文件先做备份。`labwc/environment` 的变量应合并，不能覆盖已有个性化配置。
4. 将 `desktop/shell/default/i18n/zh-CN/` 复制到 `~/.local/share/omarchy-ipad/default/i18n/zh-CN/`。Shell、菜单词典缺一不可。
5. 按本仓库 `labwc-autostart` 的方式在 Wayland 会话内启动 `fcitx5 -d`。`--daemon` 不是这里验证过的正确选项。
6. 新版发行版还包含输出、输入法自启和方向命令；旧 v0.2.0 若未升级这些脚本，需要按[操作记录](operations.md)设置横屏和原生触摸，不能只复制一个方向偏好文件。
7. 退出并重新登录，让桌面和应用重新加载字体及环境。修改已有系统前保存正在编辑的内容；不要终止处于锁定状态的锁屏进程。

## 验证清单

- 顶部菜单显示“应用、外观、设置”。
- 终端或编辑器输入 `nihao` 后能选中并写入“你好”，不仅仅是能显示中文文字。
- 竖屏、横屏时点按与目标位置一致，窗口能拖动。
- 锁屏数字能在 iPad 玻璃屏幕上点击，输入 PIN 后正常解锁。
- `locale` 显示中文 locale，`fc-match ':lang=zh-cn'` 命中 SC 字体。
- 新镜像发布前，另做新安装和冷重启引导验证；单元测试不能替代这些硬件步骤。
