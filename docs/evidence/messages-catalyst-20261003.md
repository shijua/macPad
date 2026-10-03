# Messages Catalyst startup on iPadOS 17 / Sonoma 14

## Runtime-confirmed failure

The ordinary custom-path launcher reproduced this exception in
`/var/mobile/Library/Logs/CustomApp.host.log`:

```text
NSInternalInconsistencyException
returning nil screen from mainScreen is not allowed!
```

The crash backtrace includes `+[UIScreen mainScreen]`,
`-[UIApplication _compellApplicationLaunchToCompleteUnconditionally]`,
`UIApplicationMain`, and `Messages + 16424`.

The original Sonoma Messages executable has `LC_BUILD_VERSION platform 6`
(Mac Catalyst), `minos 17.0`, UUID
`1A6149DC-746E-3373-9CF0-C7666A954A0C`. Its original Info.plist has
`CFBundleIdentifier=com.apple.MobileSMS`, `UIDeviceFamily=[2]`, and
`NSPrincipalClass=SMSApplication`; these values match the installed app.

## Change and actual witness

Route the exact Messages executable through the existing foreground Host
Catalyst launcher, with its real bundle identity and mobile container.
Keep the existing carrier's failure handling and PID-scoped identity check.
No UIScreen is fabricated and no UIKit assertion is bypassed.

```text
ok=yes launched-pid=26318 message=信息 正在当前工作区打开，未创建新的 iPadOS 窗口
26318   501 S    /System/Applications/Messages.app/Contents/MacOS/Messages
ok=yes launched-pid=26318 message=信息 已在当前 macPad 工作区运行
```

The native DisplayStream capture produced a real 2388×1668 frame showing
Messages' search sidebar, composition button and “No Conversation Selected”
content, with Messages' actual menu bar. The second request reused the same
PID. Account authentication and sending/receiving messages remain unverified;
no messages were sent during these checks.

Before this witness, Host PID 18118 stopped processing launch notifications.
A native thread sample showed its main thread waiting through a dispatch
synchronous path. Restarting only Host restored notification delivery.
The saved sample is `host-launch-wait-20261003.log` on the device. The exact
waiting caller still needs symbolication; a restart is recovery, not a fix
for that separate issue.

## Checks

- Theos arm64 daemon build succeeded.
- 13 launch admission, Launchpad routing and Weather signing tests passed.
- The added compiled test verifies the real Messages wrapper's bundle and
  container identity, and that carrier failures remain failures.
- Installed daemon backed up under
  `/var/jb/var/mobile/sonoma-workspace-originals/messages-route-20261003`.
