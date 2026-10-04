# iPadOS 17.0 + macOS 14.0 适配说明

更新日期：2026-10-04。分支：`codex/ipados17-sonoma14`。

**基础桌面已经跑通，上游提到的功能尚未全部验证。** 本分支记录现有设备上的适配和回归结果，不代表任意 iOS 17 设备都能直接安装成功。

后续实机反馈：窗口拖动正常；设置空白、浏览器无法正常使用、菜单栏无响应、macOS Wi-Fi/蓝牙控制不可用。桌面画面验证不代表这些功能已完成。以下表格已据此更新。

## 2026-10-04：VS Code 1.140

- **已安装并适配官方 arm64 1.140.0。** 原包通过微软 SHA-256 校验；为该版本单独核对并修改地址池与压缩指针堆布局，没有套用 1.130 偏移。
- **已验证 CLI、Node 脚本和真实欢迎页。** macPad 正式启动入口已改为 `Code`，`code --version` 返回 `1.140.0`；集成终端所用的 shell 环境解析协议测试通过。
- 扩展、账户登录、HTTPS 网页和长期使用仍需分别验证。Safari、系统设置空白等既有问题仍未完成。
- 二进制位置、实际错误及测试见 [VS Code 1.140 实机记录](evidence/vscode140-20261004.md)。

## 验证环境

| 项目 | 实际环境 |
| --- | --- |
| 设备 | M1 iPad Pro，iPad13,4 |
| iPadOS | 17.0，21A329 |
| macOS rootfs | Sonoma 14.0，23A344，设备路径 `/var/mnt/rootfs` |
| 越狱环境 | Dopamine 3.0.10；已从早期 RootHide Bootstrap 环境迁移 |
| 渲染 | iOS 原生 AGX GPU 路径，Host 最终画面呈现 |
| 基础代码 | DCMMC/macPad，本地适配起点 `0106674` |

版本来自实际设备的 SystemVersion.plist；设备、渲染及服务结果见[调查记录](ipados17-startup-investigation.md)。RootHide Bootstrap 单独使用的启动能力没有通过验证。其他系统小版本、其他越狱构建及其他设备仍需重新核对二进制。

## GitHub 功能覆盖情况

“已验证”仅指下列具体操作；“待验证”表示本次没有足够证据，不等于该功能一定不工作。上游 README 的演示、性能分数和其他设备结果不能直接算作本环境的结果。

| 功能 | 本环境状态 | 验证范围或剩余问题 |
| --- | --- | --- |
| macOS chroot 命令行 | 已验证 | 实际 echo 输出、退出码 0 |
| 全屏桌面、菜单栏、Dock、Finder 桌面 | 已验证 | Host 实际画面；Finder 文件操作未全面验证 |
| 原生 AGX GPU 和最终画面呈现 | 已验证 | 实际 GPU 工作完成和可见像素；尚无“不损失性能”的基准证据 |
| Launchpad 文件夹和背景模糊 | 已验证 | 修复打开文件夹的崩溃；连续关闭/打开 12 次，真实图标和模糊可见 |
| Terminal、键盘和指针 | 部分验证 | `whoami` 实际返回 root；原生菜单新建第二个窗口；指针切换焦点。已修复 `--no-terminal` 桌面启动漏加载登录服务的问题，修复后新窗口实际进入 root shell；完整冷启动仍待回归 |
| 系统设置及系统应用 | 已知故障 | 用户确认设置空白；日志记录 ViewBridge endpoint 无效及 shader 格式错误；原因尚未完全定位 |
| 菜单栏交互 | 部分验证 | 2026-10-02：Finder 菜单快照返回 212 项；通过原生菜单动作新建 Finder 窗口成功。Finder 获得焦点后真实画面显示 Finder 菜单栏。其他应用及用户手指直接点菜单栏仍需回归 |
| 每个应用独立 iOS 窗口、Stage Manager、自动调整尺寸 | 待验证 | 最终合成画面成功不等于独立窗口协议全部成立 |
| 应用直接 drawable 加速 | 未确认 | Host 的 authority capability/controller identity 仍为 NO；不能以最终画面替代此项验证 |
| 滚动、选择、拖动/调整窗口、右键、缩放/旋转 | 部分验证 | 用户确认窗口拖动正常；2026-10-02 对 Finder 空白区域发送原生右键后，实际画面出现 Finder 的“新建文件夹/显示简介/排序”上下文菜单。其余手势及完整组合尚未逐项回归 |
| Mission Control、桌面切换、App Exposé、触屏触控板 | 待验证 | 未完成本环境功能回归 |
| Magic Keyboard、虚拟键盘、快捷键工具栏、中文输入法 | 待完整验证 | 已验证基础硬件键盘输入；其他输入方式和中文组合输入尚未验证 |
| 剪贴板、文件共享、拖放、导入导出、打开/保存面板 | 待验证 | 服务端点就绪不能证明用户操作全部成功 |
| 显示密度、Retina、80–120 Hz、自适应帧率 | 待验证 | 没有本环境完整显示档位和帧率测量 |
| 硬件视频编解码、音频、定位 | 待验证 | 未完成本环境端到端验证 |
| macOS Wi-Fi/蓝牙控制 | 已报告故障 | 用户确认不可用；iPadOS 的联网、配对与 macOS 面板控制是不同验证项目 |
| Apple Pencil、屏幕镜像 | 待验证 | 未完成本环境端到端操作 |
| Safari/浏览器 | 已报告故障 | Safari 形成窗口的日志不能证明网页可用；HTTPS 命令行探针也失败，具体见下文 |
| VS Code 1.140 | CLI 与真实欢迎页已验证 | 1.140 独立地址布局适配；扩展与登录等待验证 |
| Steam、Office、游戏 | 待验证 | 不沿用上游其他设备的运行结果 |
| Apple ID / iCloud 登录、同步 | 当前未接通 | Finder 显示 iCloud Drive 入口，但该 iPad 配置没有 macOS ubiquity 容器；本次只让 Finder 在容器确实缺失时按系统 API 返回 nil，容器存在则调用系统实现。未实现 Apple ID 登录或同步；上游 README 也没有明确的 iCloud 支持声明 |
| VNC、锁屏/睡眠及恢复 | 待验证 | 当前桌面验证使用 Host 实际画面；VNC 不作为启动成功的必要条件 |
| 长时间稳定运行、冷启动、全新安装 | 尚未完成 | 当前为已经配置的单台设备上的验证 |

上游功能列表：[macPad](https://github.com/DCMMC/macPad)。文件系统准备背景：[MacWSBootingGuide](https://github.com/DCMMC/MacWSBootingGuide)。

## 本分支的适配内容

1. **安装和 shared cache 准备**：检查缓存属主、路径与签名边界，补全安装目录、签名和启动 trustcache；检查旧 `/var/jb/usr` bind mount 视图。
2. **Sonoma 显示和 GPU ABI**：增加精确版本的 display/resource profiles，适配 IOMobileFramebuffer、SkyLight 提交和 AGX 资源调用。依据实际二进制和日志，不把旧版本偏移直接套用到新版本。
3. **Metal shader 闭包**：为 23A344 + 21A329 准备对应 shader companions 和清单；校验原始源码 SHA256 及完整转换结果。版本不匹配时拒绝自动套用。
4. **应用和服务启动**：补充 LaunchServices payload、IconServices/CoreServices 桥接、OpenDirectory/accountpolicy 启动，以及 Dopamine fork 后的页面权限修复。
5. **Launchpad 文件夹崩溃**：修复兼容纹理引入 IOSurface 后的所有权缺口。仅在精确 SkyLight UUID 和调用地址匹配时，向 `WS::Surface` 转移独立 retain；原有析构释放和缓存淘汰继续执行。
6. **Finder 启动和菜单**：`sonoma-finder-admission.err` 记录 Finder 经 `NSFileManager ubiquityIdentityToken` 进入 CloudDocs/FileProvider 后崩溃；当 iCloud 容器确实缺失时向 Finder 返回 nil，容器存在时调用系统实现。2026-10-02 实测 Finder 窗口、212 项原生菜单、新窗口菜单动作和右键上下文菜单。激活 Finder 后真实画面显示 Finder 菜单栏；其他应用菜单及手指直接点击系统菜单栏仍需回归。

第 5 项 RE-confirmed：实际 23A344 SkyLight UUID 为 `42FD2E33-2BB2-372F-A01F-B2B36C8277B9`，plain-texture 调用返回地址为 image + `0x5baac`；析构中的 CFRelease 位于 + `0x5b254`。runtime-confirmed：所有权跟踪显示旧路径的释放顺序耗尽了 pool 所持引用。具体证据及修复边界见调查记录的 “Sonoma Launchpad folder” 一节。

## 验证结果

- `test_sonoma*.py`：8 项通过。
- SkyLight 所有权边界测试：1 项通过。
- 启动 trust、恢复、shader 转换、账户服务、会话、CoreServices、fork、LaunchServices、shared cache 和 VNC surface 合约相关测试：72 项通过。
- Launchpad 修复的 libmachook 两个架构均编译并部署；运行时连续 12 次文件夹开关后 WindowServer 和 Dock 未退出，实际画面显示内容和背景模糊。

这些测试覆盖指定适配边界，不能替代全部应用功能或长期稳定性测试。运行证据保存在本地 `tmp/sonoma-14.0/`，该目录不随 Git 发布；调查记录保留了证据文件名、二进制 UUID 和地址。

## 使用边界与已有设备操作

需要自行准备合法获取的完整 macOS 14.0 rootfs 和所需 Apple 框架资源。Git 仓库只包含适配源码、准备脚本及测试，不包含 IPSW、系统镜像、设备数据或私钥。当前设备上验证成功的准备流程包含文件系统侧操作，尚未完成一台全新设备的一键安装回归。

下面命令在**已安装本分支、完成 rootfs 准备的设备**上执行；以 root shell 为例：

```sh
# 查看 GUI 服务状态
bash /var/jb/usr/macOS/bin/macos_gui.sh status

# 启动共存模式，再通过 macPad Host 查看桌面
bash /var/jb/usr/macOS/bin/macos_gui.sh start coexist

# 验证 chroot CLI
bash /var/jb/usr/macOS/bin/run_bash.sh -c \
  'export PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin; echo macws-cli-ok'

# 停止 GUI
bash /var/jb/usr/macOS/bin/macos_gui.sh stop
```

完整构建背景见主 README 和项目说明。不要直接使用旧脚本中的示例 IP；先配置自己的 SSH 连接。不要在运行中的 rootfs 内直接递归删除文件；必须先检查并卸载嵌套挂载。

## 下一步

优先定位 ViewBridge/设置服务、浏览器网络和菜单响应，再解决 Terminal 冷启动、图标生成及硬件控制问题。文件共享、输入法等仍需逐项回归。每项功能需有真实操作结果；进程存活、跳过断言或服务返回成功都不能单独作为完成证据。

### Terminal 自动登录修复

`login -pf root` 的当前失败原因已通过对照验证：桌面以 `--no-terminal` 启动时，代码也跳过了 OpenDirectory/AccountPolicy 两个登录服务。稍后从 Host 打开 Terminal，PAM 返回 `PAM_ACCOUNT=3 error in service module`。加载两个服务后，同一探针返回 `PAM_ACCOUNT=0 success`，真实 PTY 登录进入 shell。

现在登录服务在桌面启动时必需加载，`--no-terminal` 只控制是否自动打开 Terminal 窗口。新窗口的真实键盘输入 `whoami` 返回 root，最终合成截图显示实际提示符及结果；没有设置密码或绕过 PAM。新增回归覆盖有/无 Terminal 和依赖启动失败，账户服务测试共 4 项通过。已退回 `login:` 提示的旧窗口需要关闭并新开窗口。

## 2026-10-02 补充功能检查

### 本轮实际修复

- Dock 配置中指向不存在的 `/Applications/Keynote.app`、`Numbers.app`、`Pages.app` 三项已移除；原始 plist 保存在设备的 `sonoma-workspace-originals/dock-before-missing-iwork-cleanup.plist`。
- `postinst.sh` 的签名判断已修正：受信任但仍带 Apple CMS 的二进制不会被误判为已完成 MacWS 签名；19 项启动合约测试通过。
- 设置扩展服务本身已能启动，49 个设置扩展记录可验证。真实启动仍在创建容器时失败：运行日志记录 `com.apple.Appearance-Settings.extension ... (err=2) failed to set container`，UID 501 对照后仍无法发布扩展窗口。这个问题仍未完成，不能把空白右侧面板当作可用设置。
- 为验证容器边界，已备份并修正 rootfs 内 `/var/mobile`、`Containers`、`Shared`、`AppGroup` 四级目录的属主；修正后错误由 `err=13` 变为 `err=2`，仍无法创建扩展容器。原属主记录与运行日志保存在迁移备份的 `settings-container/` 目录。

- **设置**：`SystemSettings.host.log` 实际记录 `com.apple.view-bridge: Connection invalid`；ThemeWidgetControlViewService 的 listener 请求也无效。`settings-bridge ready=yes` 仅证明桥接能力发布，不能证明设置页面可用。
- **图标**：`iconservicesagent.log` 记录 `This library format is not supported on this platform (or was built with an old version of the tools)`。THEORY：图标生成失败可能关联问号图标；需捕获具体应用的图标请求和失败回复才能确认。
- **菜单**：当前 Terminal PID 的生产菜单快照协议请求得到 `socket.timeout: timed out`。该结果不证明所有应用的菜单都失败，也未定位到输入路由或主线程中的具体阻塞点。
- **网络**：chroot 的真实 echo 仍成功。系统 `/usr/bin/curl` 请求 `https://www.apple.com`，设置 `SSL_CERT_FILE=/etc/ssl/cert.pem` 后仍返回 `curl: (60) SSL certificate problem: Couldn't understand the server certificate format`；显式指定两个 PEM bundle 后又得到证书链验证失败。没有通过关闭证书验证来宣称网络修复。此结果不能单独解释 Safari 的全部故障。
- 项目示例中的 `socks5h://127.0.0.1:1082` 当前没有监听端口；实测代理连接直接返回 curl 7。因此不能把代理环境变量写进 Safari 启动项后就声称网络恢复。
- **其他应用**：Host 日志记录 Maps 未完成 Catalyst 场景启动；Messages 抛出 `returning nil screen from mainScreen is not allowed!`；Notes 也有 ViewBridge listener 无效记录；Activity Monitor 报 AssetCacheManagerService lookup 失败。尚未完成这些应用的所有用户操作。
- **iCloud**：查阅当前 macPad 和 MacWSBootingGuide README，未找到明确支持声明。没有读取设备账号、登录信息或尝试同步；现有 iPadOS cloud daemon 的存在不能作为 macOS iCloud 验证。

上述记录来自实际运行系统，调查记录列出了本地证据位置。当前状态仍是适配中的基础桌面，不是完整可用的 macOS 系统。

## 2026-10-03 菜单和原生滤镜修复

- Finder 分组菜单：修正原生事件投递时遗留的鼠标位置缓存，以及菜单跟踪中全屏坐标与窗口映射坐标的混用。实际选择“Kind”后，文件列表出现“Folders”分组，再次打开菜单时“Kind”带勾。其他二级菜单仍需逐项验证。
- 弹出窗口：固定尺寸窗口不再读取仅用于诊断的 `resizeIncrements`，避免 `NSPopoverFrame` 不支持该方法时被诊断代码弄崩溃。
- Sonoma CoreImage/CoreUI：识别真实请求中的 `air64-apple-macosx14.0.0`。仅在 iPadOS 17 编译器 UUID、入口指令和所有模块目标一致时，使用原生 Catalyst 编译目标。未修改输出库头或跳过 Metal 验证。
- 派生缓存：补充 Sonoma 的 `32023` 缓存槽；只归档 `libraries.list` 和 `libraries.data`。本机共归档 24 个文件到 rootfs 内 `/Library/Caches/MacWS/metal-library-target/retired/macws-macabi-sonoma-ios17-v4/`，未删除用户数据。
- 实际 GPU 验证：普通 CoreImage 滤镜与 CoreUI 的 `CUIHueSaturationFilterLocal` 均生成 256/256 个可见像素，输出具有变化。桌面恢复后日历的欢迎界面和月视图均实际可见；事件保存、账户同步尚未验证。
- AddressBook 动态插件：依真实框架依赖补充插件 trustcache，保留原签名；Contacts 原来的 LocalSource 架构拒绝和随后的 NSNull 崩溃已消失，但尚未验证完整联系人窗口。

相关测试 76 项通过；libmachook 和编译器 tweak 的 arm64/arm64e 构建通过并已部署。**粉色方块仍在 Finder 工具栏复现，设置右侧仍空白，浏览器及 App Store、Photos、FaceTime、TV 的完整使用仍未通过。** 滤镜探针成功不能作为这些功能全部完成的证据。
