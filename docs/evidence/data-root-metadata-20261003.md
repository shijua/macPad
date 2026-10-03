# Sonoma Data 根目录属性：2026-10-03 实机证据

设备：iPad13,4，iPadOS 17.0，Sonoma 14.0 23A344。

## 启动崩溃

`runtime-confirmed via system-information-crash.ips`：System Information
在加载 NSPathComponentCell 的图标时退出，栈为：

```text
__assert_rtn+284
LinkBinding::resolveBinding() (.cold.2)+44
LinkBinding::resolveBinding()+372
LinkBinding::getURL()+68
+[ISIconFactory _iconWithBinding:]+44
-[NSWorkspace _iconForURL:]+96
```

独立 `NSWorkspace iconForFile:@"/"` 探针重现同一错误：

```text
Assertion failed: (_linkedBinding != this), function resolveBinding, file LinkBinding.mm, line 150.
ACTUAL_BLUEPRINT flags=4 url=file:///System/Volumes/Data/
```

用户目录和应用路径的图标探针正常完成。

`RE-confirmed via actual Sonoma LaunchServices`：
`BindingBlueprint::copySubstitutedURLAndProperties` 的
`0x180995ca8..0x180995ce8` 比较根路径并替换为 Data URL，再读取该 URL
的属性。`BindingManager::CreateWithBlueprint` 在
`0x1809970ac..0x1809970d4` 根据 flags & 0xc 选择 LinkBinding。
`resolveBinding` 在 `0x1809d9eac..0x1809d9eb8` 创建解析后的 Binding 并
检查是否返回自身；`0x180b5bc68..0x180b5bc90` 保留上述断言。

## 最小修复与 A/B

设备的 `/System/Volumes/Data` 是指回进程根目录的命名空间链接。
适配仅作用于已验证的 chroot：核验精确路径、lstat 符号链接类型、
stat 根目录类型，以及目标与根目录的 dev/inode 相等。
通过原始 CFURL/NSURL provider 查询实际根目录的完整属性；保留原始
查询错误、请求键及所有权规则。若调用请求 IsVolume，恢复逻辑卷根属性。
普通符号链接、不同 inode、非 chroot 和真实 Data 目录保留原始行为。

A/B 与正式库探针均得到：

```text
ACTUAL_BLUEPRINT flags=1012 url=file:///System/Volumes/Data/
ICON_PROBE completed icon=yes
```

正式库的 arm64、arm64e 已构建、部署并注册 trustcache。
原库备份在设备：
`/var/jb/var/mobile/sonoma-workspace-originals/data-root-20261003/`。

System Information 现在创建真实主窗口（PID 16214，window 262），
截图 `system-information-after.png` 仍显示空白列表。因此仅确认启动
断言修复，不能将报告生成标为完成。

`settings-about-global.png` 显示真实 About 页面、Sonoma 14.0、内存与
显示器；芯片字段为空、序列号不可用，仍需适配。全局输入能打开该页，
直接 AppInput 点击只高亮 General 的 About 行，仍需核验扩展输入路由。

完整本地证据：`tmp/sonoma-14.0/priority-20261003/`。
