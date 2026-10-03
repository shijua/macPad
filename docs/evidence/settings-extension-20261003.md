# Sonoma 设置面板：2026-10-03 实机证据

设备：iPad13,4，iPadOS 17.0 21A329，Sonoma 14.0 23A344。
外观、通用、辅助功能、桌面与 Dock 已有真实内容。托管控件的直接输入
仍需修复，不能把所有设置功能标为完成。

## chroot 内的可执行路径

`runtime-confirmed via appearance-launch-exit.log`：

```text
Sandbox: hook..execve() killing com.apple.Appearance-Settings.extension[pid=86780, uid=501]: (err=2) failed to set executable path
```

`RE-confirmed via actual iPadOS kernel com.apple.security.sandbox`：
调用点 `0xfffffe000a57f44c` 进入路径设置函数 `0xfffffe000a582d30`；
其路径查找失败返回非零，调用方在 `0xfffffe000a57f48c` 检查结果，
随后输出上面的拒绝消息。证据来自设备正在使用的 kernelcache。

`runtime-confirmed via appearance-path-alias.log`：增加
`/var/mnt/rootfs/private/var/mnt/rootfs -> /` 后，同一 Appearance 镜像
进入 macOS AppKit，随后出现下述独立崩溃。

`macws_chroot_exec_alias.py` 根据 rootfs 的真实路径建立别名。
它使用目录描述符和 `O_NOFOLLOW`，不沿中间符号链接创建目录，
不覆盖已有目录或不同目标的链接。设置运行时准备与验证先核验别名。
绝对目标 `/` 供 chroot 进程解析；原生侧清理不能沿它递归删除。

## XPC 用户身份检查

`runtime-confirmed via appearance-after-alias.ips`：实际 Appearance
进程 UID 为 501，崩溃栈包含 `_xpc_api_misuse+92`、
`xpc_connection_set_target_uid+216`、WindowManagement image offset 58980。

`RE-confirmed via Sonoma libxpc.dylib+0x18015e428`：
目标 UID 设置有连接类型、激活状态和调用方用户身份检查。
报告没有具体 API misuse 字符串，也没有调用前目标 UID；
不能据此断言是哪一个条件触发。

`runtime-confirmed via appearance-root-retry.log / settings-root-host.log`：
仅 Appearance 改为 root 后没有重现上述崩溃；主进程报告：

```text
Received remote view controller: <_EXRemoteViewController: 0x117e54170>
EXHostViewController: Will try to call delegate 0x13b6bd3e0 'hostViewController:didBeginHosting:' for session: <_EXHostViewControllerSession: 0x116cf5b90>
```

`appearance-root-final.png` 显示完整 Appearance 控件。
正式配置现在使设置扩展与 root 桌面身份一致，没有跳过 libxpc 检查。
运行时 schema 升为 v3，旧移动身份的标记不能满足准备检查。

批量准备日志 `settings-runtime-v3.log` 完成 50 个面板；运行时验证扫描
253 个镜像，通过签名、当前 trustcache 和注册检查。
`batch-general.png`、`batch-accessibility.png`、`batch-desktop-dock.png`
分别显示通用、辅助功能、桌面与 Dock 的真实内容。

## 托管控件输入

`runtime-confirmed via batch-purple.png / settings-global-purple.png`：
向设置主进程发送精确窗口点击未改变强调色；同一位置经过已授权
OSXvnc 的 WindowServer 输入通道后，强调色和高亮颜色均变为 Purple。
这确认输入路径差异，尚未确认是目标窗口路由还是调用进程的 TCC 权限。

Appearance 和设置主进程仍报告 `com.apple.windowmanager.server` 连接失败。
既然面板实际托管和显示成功，不能把此错误直接归因为空白界面的原因。

本地完整证据位于 `tmp/sonoma-14.0/priority-20261003/`。
单个 carrier 的回滚副本位于设备
`/var/jb/var/mobile/sonoma-workspace-originals/appearance-uid-20261003/`。
