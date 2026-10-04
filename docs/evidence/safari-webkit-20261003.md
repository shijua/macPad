# Sonoma Safari / WebKit：2026-10-03 实机证据

设备：iPad13,4，iPadOS 17.0 21A329，Sonoma 14.0 23A344。
这些结果用于定位剩余问题，不能作为网页加载成功的证据。

## 启动通道

`runtime-confirmed via webkit-private-priority.log`：默认服务启动出现：

```text
System Policy: Safari(71888) deny(1) mach-lookup com.apple.WebKit.Networking (xpc)
System Policy: Safari(71888) deny(1) mach-lookup com.apple.WebKit.WebContent (xpc)
```

`MACWS_WEBKIT_PROXY_EXPERIMENT=1` 仅在单独 Safari 实验 job 中启用。
四个精确服务名映射到私有的原生启动 stub；保留 launchd 给出的每实例
XPC 启动上下文，经 chroot/exec 启动原始 Sonoma 可执行文件。
初次实验被原始 CT 签名拒绝：

```text
unsuitable CT policy 0x8 for this platform/device, rejecting signature.
```

保存四个原始可执行文件及 entitlements 后，重新进行原生 slice 签名和
trustcache 准入；随后得到下面两个独立失败点。实验 job 已卸载，常规
Safari 未设置该开关。没有禁用 Gigacage 或强制沙箱调用成功。

## WebContent：Gigacage 虚拟地址预留

`RE-confirmed via JavaScriptCore+0x19c169b50`：实际 Sonoma 镜像执行
`mmap(NULL, totalSize + maxAlignment, 3, 0x1002, 0x3f000000, 0)`。
随机排列的两个 cage 在这份构建中合计 96 GiB，最大对齐要求为 32 GiB，
因此这次预留请求为 128 GiB。分配失败分支终止，而非继续使用空指针。

`runtime-confirmed via webcontent-crash.ips`：PC `0x1a3611ecc`；减去
shared-cache slide `0x74a8000` 后为 `JavaScriptCore+0x19c169ecc`。
该处为显式 `brk #0xc471`。寄存器 x19 为 `0x1800000000`，x22 为
`0x800000000`。其对应消息为：

```text
FATAL: Could not allocate gigacage memory with maxAlignment = %lu, totalSize = %lu.
```

不能仅凭报告的 PAC exception 分类把它归因于指针认证。

`runtime-confirmed via vm-reservation.log`：带项目执行权限的原生 iOS
探针和 macOS chroot 探针均能成功预留 16、32、48 GiB；64、96、128 GiB
均返回 `MAP_FAILED` / `ENOMEM`。这些是虚拟地址预留，不是实际分配相同
数量的物理内存。

源码交叉核对：[XNU 10002.1.13 的 pmap.c](https://github.com/apple-oss-distributions/xnu/blob/xnu-10002.1.13/osfmk/arm/pmap/pmap.c)
中 `pmap_max_64bit_offset(ARM_PMAP_MAX_OFFSET_JUMBO)` 标注最大偏移为
64 GB。[kern_exec.c](https://github.com/apple-oss-distributions/xnu/blob/xnu-10002.1.13/bsd/kern/kern_exec.c)
把 extended-virtual-addressing/JIT 等权限路由到该 jumbo map。
项目执行配置已有扩展虚拟地址权限；添加相同权限不能作为已解决的证据。
源码用于交叉核对，尚未反编译设备内核的该函数。

补充 `runtime-confirmed via vm-boundary.log`：原生探针只申请 16 KiB，
`vm_allocate` 在固定地址 `0x800000000` 成功；在 `0xff0000000`、
`0x1000000000`、`0x1800000000`、`0x2000000000` 返回
`KERN_INVALID_ADDRESS`（1）。这排除了这些请求仅因预留块太大而失败，
尚未测出精确 map 上界。

## Networking：编译后沙箱应用

`runtime-confirmed via networking-crash.ips`：PC `0x1aa4401a8`；减去
同一 slide 后为 `WebKit+0x1a2f981a8`。
`RE-confirmed via WebKit+0x1a2f98168`：失败路径读取 errno，形成错误消息，
调用终止例程后执行 `brk #0xc471`。对应字符串位于 `0x1a37ecf16`：

```text
%s: Could not apply compiled sandbox: %s
```

`RE-confirmed via WebKit+0x1a2f97ec0`：调用的 stub 位于
`0x1a37a3ba0`；实际 Mach-O 的 indirect symbol table 将它解析为
`_sandbox_apply`。返回值非零即跳到上述终止路径。
`libsandbox.1.dylib+0x183c7bb84` 根据传入 profile 的字段选择 kernel
policy operation 0 或 1，再提交 profile。具体传入配置和内核
拒绝原因仍需核对。这与 WebContent 的
地址预留失败是两个待解决问题，不能用关闭其中一个检查代替修复。

`runtime-confirmed via safari-sandbox-diagnostic2.log`：后续实机日志为：

```text
com.apple.WebKit.Networking: Could not apply cached sandbox: Operation not supported
com.apple.WebKit.Networking: Could not apply compiled sandbox: Operation not supported
```

这次实验确认了应用失败的错误文本，当时尚未确认内核拒绝位置和 profile 格式。
此次实验 job 已卸载，避免重复失败造成持续进程重启。

## 2026-10-04：实际内核接口与内置配置

`RE-confirmed via com.apple.security.sandbox UUID
483EE0EF-E657-3EA7-91BA-324D3550643F`：策略配置引用字符串
`0xfffffe00078ef8fd`（`Sandbox`）和 `0xfffffe00078edeeb`
（`Seatbelt sandbox policy`），其 operations 表位于 `0xfffffe0007f24220`。
`mpo_policy_syscall` 槽位 `0xfffffe0007f245c8` 的 chained pointer
`0x8010fee303566294` 解析到 `0xfffffe000a56a294`。
槽位偏移 `0x3a8` 与 [Apple XNU 10002.1.13 的 mac_policy.h](https://github.com/apple-oss-distributions/xnu/blob/xnu-10002.1.13/security/mac_policy.h)
结构布局交叉核对一致。

实际分发函数：

```text
0xfffffe000a56a2d4 mov w21, #0x2d
0xfffffe000a56a2d8 cmp w1, #0x33
0xfffffe000a56a2e0 sub w16, w1, #1
0xfffffe000a56a2e4 cmp w16, #0x1c
0xfffffe000a56a2e8 b.hi #0xfffffe000a56a4b0
0xfffffe000a56a4b0 cmp w1, #0x2e
0xfffffe000a56a4b4 b.ne #0xfffffe000a56aeb8
0xfffffe000a56aed4 mov x0, x21
```

operation 0 因无符号减一进入上述默认返回路径，在解析用户配置之前
返回 45。operation 1 的跳转表项进入 `0xfffffe000a56c180`，该函数
复制 24 字节参数并按名称查找内置配置。不能将编译后配置的 operation 0
直接修改成 1：参数格式不同，配置内容和权限也不同。

`runtime-confirmed via sandbox-interface-probe.log`：独立原生 iOS
探针（没有 libmachook）获得：

```text
operation=0 profile=(none) result=-1 errno=45
operation=1 profile=com.apple.WebKit.Networking result=0 errno=0
operation=1 profile=com.apple.WebKit.WebContent result=0 errno=0
operation=1 profile=com.apple.no-such-macws-profile result=-1 errno=22
```

`runtime-confirmed via sandbox-permissions-probe.log`：每项测试都在新子进程
中应用配置。之前临时文件创建、回环 SSH 端口连接和两个偏好服务查询均
成功；应用 Networking/WebContent 配置后：

```text
after file-create=-1 errno=1
after loopback-connect=-1 errno=1
after lookup=com.apple.cfprefsd.daemon result=1100
after lookup=com.apple.macosbooter.cfprefsd.daemon result=1100
```

应用不存在配置失败后，上述操作仍成功。这证实内置配置真正施加了限制，
也说明无参数调用不能作为可用的 Networking 服务适配。
读取实际 iPadOS Networking 可执行文件的签名，确认其内置配置名就是
`com.apple.WebKit.Networking`，且有
`com.apple.private.network.socket-delegate=true`。给探针仅补上该相同
布尔权限后，结果没有改变；不能把增加该权限当成修复。

`misc/macws_sandbox_interface_probe.c` 保留这个可复现测试，子进程有五秒
截止时间。该诊断不修改任何运行中的服务，也没有发布返回成功的沙盒替代。

## 证据和回滚副本

本地完整日志、原始 crash report、反汇编和 IOSurface 截图保存在
`tmp/sonoma-14.0/priority-20261003/`，未随仓库发布。
设备原始库备份：
`/var/jb/var/mobile/sonoma-workspace-originals/webkit-experiment-20261003/`。
四个服务原始文件及权限备份：
`/var/jb/var/mobile/sonoma-workspace-originals/webkit-services-20261003/`。

后续验收必须包括真实网页内容、导航及 Safari 设置的操作结果；服务存活、
成功启动或显示起始页都不足以通过验收。
