# Sonoma 设置面板：2026-10-03 实机证据

设备：iPad13,4，iPadOS 17.0 21A329，Sonoma 14.0 23A344。
设置右侧空白仍未通过验收；下面只记录已经确认的启动障碍。

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

THEORY：root 桌面与 carrier 降为 UID 501 的身份差异可能参与失败。
仅 Appearance carrier 的 UID 对照诊断已保存原始二进制及权限。
锁屏阻止运行验证，现已恢复原始 carrier，诊断副本保存在同一备份目录；
解锁后再进行运行和可见面板验证。没有跳过 libxpc 检查。

本地完整证据位于 `tmp/sonoma-14.0/priority-20261003/`。
单个 carrier 的回滚副本位于设备
`/var/jb/var/mobile/sonoma-workspace-originals/appearance-uid-20261003/`。
