# Home＋音量加：触摸应急恢复

适用设备：iPad 6 Wi-Fi（`iPad7,5` / `apple,j71b`）。其他设备不会启动此服务。

点击失灵、窗口无法拖动，且系统仍在运行时，同时按住 **Home＋音量加至少 3 秒**，然后松开。恢复会关闭当前应用，未保存的内容可能丢失。等待正常登录界面出现后，用原来的 PIN 登录，再试点击和拖动。无需电脑；不会重启 Linux，也不会跳过登录验证。

每次完整按下、松开只触发一次，两次恢复至少间隔 30 秒。单独使用 Home 和音量键仍沿用原有功能。组合键按住期间会抑制桌面的 Home 动作及音量连发；刚开始按键时可能先产生一次正常音量调整。

## 恢复内容

后台服务直接监听物理 `gpio-keys` 的 Home 和音量加事件，不独占按键，不依赖触屏或桌面快捷键。它不记录触摸坐标、输入内容或 PIN。

触发后，恢复工具先核对 J71b 型号、控制器驱动、固件、显示输出和当前本机会话，然后：

1. 备份登录界面和当前用户的 Labwc 配置，恢复命名触摸设备的原生触摸、实际输出映射及单位校准矩阵；保留显示方向及其他快捷键。
2. 结束当前桌面会话，由原有 `greetd` 显示正常 PIN 登录界面。用户配置以用户权限写入。
3. 重新绑定 `apple-z2` 控制器，等待输入设备注册，并点亮屏幕。

这是把本机已奏效的恢复步骤做成应急入口，不能证明长期故障根因已修复。它与 Orchard 驱动候选 [PR #52](https://github.com/OrchardLinux/orchard/pull/52) 独立；不会安装或卸载内核模块。没有定时重置，只有明确按下组合键才执行恢复。

## 安装与检查

新镜像通过 `desktop/stage.py` 安装并启用 `omarchy-touch-recovery.service`，重启后仍生效。已有系统需同时安装 `desktop/recovery/` 的工具和服务，以及本次更新的 `omarchy-tablet-power`、`omarchy-volume`；仅复制服务不能抑制桌面的组合键副作用。

```sh
timeout -k 5 10 systemctl status omarchy-touch-recovery.service --no-pager
timeout -k 5 10 journalctl -u omarchy-touch-recovery.service -n 25 --no-pager
```

日志应先显示 `Home + Volume Up recovery ready`。触发后可见 `Physical recovery chord activated`、恢复完成及 `Recovery exit: 0`。若失败，保留日志并通过 SSH 排查；不要持续重复按键。关机、低电量断电或系统完全卡死时，此软件入口无法运行。

停用入口（不卸载触摸驱动）：

```sh
sudo timeout -k 5 15 systemctl disable --now omarchy-touch-recovery.service
```

登录配置备份在 `/var/lib/omarchy-touch-recovery/greeter-rc.before-recovery.xml`，用户备份在 `~/.config/labwc/rc.xml.before-hardware-recovery`；每次恢复前更新。服务需要特权访问输入设备、控制器及登录界面，因此由 root 管理；不为普通账户新增免密码 sudo。
