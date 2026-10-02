# macPad

Your touch Mac in iPad.

## iPadOS 17 / macOS 14 adaptation

This fork's `codex/ipados17-sonoma14` branch adds compatibility work for an
M1 iPad Pro running iPadOS 17.0 (21A329), Dopamine 3.0.10 and macOS 14.0
(23A344). Basic desktop presentation and Launchpad folder rendering are
verified on the configured device. Full upstream feature parity and a fresh
device installation are still pending.

See the dedicated [iPadOS 17 + macOS 14 update notes (中文)](docs/ipados17-macos14-update.md)
for verified features, known issues, changes and test results.

Run macOS GUI applications in your jailbroken iPad/iPhone. Demo video:

[![macPad Demo](https://img.youtube.com/vi/SGaiSSRIy8g/0.jpg)](https://www.youtube.com/watch?v=SGaiSSRIy8g)

Features:

The following is the original feature list. It is not a validation checklist
for the iPadOS 17/macOS 14 branch; use the coverage table linked above.

* Touch Gestures:
    - Scroll
    - hold to right click
    - Drag to resize/move window and move files
    - Drag to select text
    - Double tap to maximize window
    - Two fingers zoom and rotate
    - Two fingers tap to right click
    - Two fingers double tap zoom view
    - Two fingers hold and drag to share files to iOS
    - Three fingers mission control, swipe desktops and App Expose 
* Share files and clipboard between iOS and macPad
* Touch screen as trackpad
* Native CPU and GPU driver without any performance lost
    - Geekbench 6 CPU 2293 single-core score, 8156 multi-score score in my iPad Pro m1
    - Geekbench 6 GPU 32359 score in my iPad Pro m1
* Hardware video encode/decode
* Virtual keyboard
* Display density (125% and 150%)
* Native WiFi/Bluetooth/Apple pencil/Screen mirror, etc. supports
* Window Mode:
    - Run macOS applications like iOS native windows
    - Auto resized window
    - Auto popup new window
    - Fixed size window
* Fullscreen Mode:
    - Run macOS desktop in fullscreen
 
## Starting up

Prepare macOS rootfs installation as per [this link](https://github.com/DCMMC/MacWSBootingGuide#setting-up-macos-full-installation)

build macPad in macOS:

```
# edit DEVICE_IP/DEVICE_PORT at the top of misc/build.sh to match your iPad/iPhone
bash misc/build.sh
# you can also build it on iOS
# bash misc/build_on_ios.sh
```

run macPad in your iPad/iPhone device:

```
sudo bash /var/jb/usr/macOS/bin/postinst.sh
# enter macOS bash environment
sudo bash /var/jb/usr/macOS/bin/run_bash.sh
```

## Note

* Original validation: iPad Pro m1 11-inch, iPadOS 16.3, dopamine jailbroken, macOS 13.4. This branch's iPadOS 17/macOS 14 validation is documented separately above.
* In theory, support all m-series and A18 jailbroken iPad/iPhone. But there are many hardcoded logics for my device's OS version currently
* Compared with [VirtualMacOniPad](https://github.com/nfzerox/VirtualMacOniPad), macPad uses native CPU and GPU drivers through chroot while VirtualBuddy uses hardware hypervirsor for CPU and mental2vulkan GPU  translation ([reims-vgpu](https://github.com/steelbrain/reims-vgpu)) which loss some performances
* Compared with [MacWSBootingGuide](https://github.com/khanhduytran0/MacWSBootingGuide), it uses MTLSimDriver for GPU which has many graphic issues and performance problems while macPad uses native GPU drivers

## Credits
- Codex
- [MacWSBootingGuide](https://github.com/khanhduytran0/MacWSBootingGuide)
- [AsahiLinux](https://github.com/AsahiLinux/linux)
- [iOS-run-macOS-executables-tools](https://github.com/zhuowei/iOS-run-macOS-executables-tools)
