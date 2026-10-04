# DesktopSettings menu input on iPadOS 17 / Sonoma 14.0

## Scope and result

Runtime-confirmed on the current M1 iPad, macOS 23A344: real Desktop & Dock
position menu selections moved the actual Dock Left → Bottom → Right → Bottom.
Each final selection used one mouse tap; defaults readback and authentic
DisplayStream pixels agreed. The final preference is Bottom.

This verifies the DesktopSettings position menu, not every settings pane or
Safari. The release runtime copies were updated after the menu regression:
base arm64/arm64e libmachook, base native carrier, local Desktop carrier,
and the 50 extension dependency copies. The actual verifier returned:

```
SETTINGS-VERIFY {"added": 0, "backend": "already-trusted", "cached": 200, "files": 253, "images": 253, "panes": 50, "resource_hits": 0, "total_seconds": 0.189}
```

A fresh chroot echo returned `menu-runtime-cli-ok`. A full device reboot was
not performed; these checks establish installation-source consistency.

## Runtime evidence

The extension input endpoint originally failed at bind(), with the diagnostic
stage/error `INPUTSTATE ... 01000200` (stage 2, errno 1 / EPERM). The native
carrier pre-opened the same PID's real AF_UNIX datagram endpoint before exec;
the extension validates its exact socket path and type and adopts that fd.
Socket install state became 2, and the broker reported:

```
MACWS-INPUT ROUTE seq=6 route=appkit-socket pid=35548 window=185
```

Runtime-confirmed with a hardware write watchpoint on PID 33338:

```
old value: 8386114176404172545
new value: 8386114176404172544
frame #0: 0x000000010290a294 libmachook.dylib
frame #15: 0x000000018be1d59c AppKit
frame #16: 0x00000001028ff618 libmachook.dylib
```

Actual mapped libmachook disassembly:

```
0x10290a27c: bl     0x10296dddc
0x10290a280: mov    x0, x23
0x10290a284: mov    x1, x25
0x10290a288: ldr    x2, [sp, #0xf0]
0x10290a28c: bl     0x1029131b0
0x10290a290: stlrb  wzr, [x22]
```

An inner input delivery cleared the outer active menu interval. The scoped
tracking helper now restores the previous value in @finally. The real menu
function still executes. Its actual runtime ABI is `v24@0:8@16` for
NSMenuTrackingSession startRunningMenuEventLoop:; the entry hook applies only
to DesktopSettings and checks that ABI.

A read-only snapshot additionally showed a cached mapping
`(window=172, origin=(925,-237), size=(1194,834))` for incoming full-desktop
2388×1668 pixels. The broker had encoded a resolved window without converting
the producer's coordinates. Ordinary fullscreen application records now retain
window zero; captured system surfaces retain their independent exact ID.
A newly opened menu invalidates the previous menu snapshot, so its first
main-run-loop delivery publishes the new real window and queues its down/up.

## Checks

- `python3 -m unittest discover -s misc -p 'test_app_input*.py'`: 3 passed.
- libmachook cross-build: arm64 and arm64e passed.
- SettingsExtensionProxy native carrier and macwsinputd builds passed.
- Actual menu selection readbacks: `left`, `bottom`, `right`, `bottom`.
- Authentic capture: `tmp/sonoma-14.0/priority-20261003/desktop-current.png`.
- Full diagnostics remain under the same local evidence directory.

Failed extra sandbox entitlements were restored to the original signed
DesktopSettings executable. No check-return bypass or synthetic image was
used to obtain the successful menu selections.

## ControlCenterSettings follow-up

The real pane menu opened, but its process had no input socket:

```
ls: cannot access '/var/mnt/rootfs/private/tmp/macws_app_input.46871.sock': No such file or directory
```

The same input eligibility, native pre-open, and menu loop mechanism was
scoped to the exact stock ControlCenterSettings executable. After native
carrier/local hook replacement and a normal pane relaunch:

```
srw------- 1 root wheel 0 Oct  4 20:48 /var/mnt/rootfs/private/tmp/macws_app_input.47136.sock
```

Selection and menu-bar icon changes are **not verified**. The attempted test
crossed the real standby transition:

```
2026-10-04 20:48:58.003 macwspowerd[62364:3650413] POWER suspended=65 total=65
CAPTURE_EXIT 124
```

After resume, authentic captures show both “Show in Menu Bar” and “Don't
Show in Menu Bar” selected by ordinary mouse packets. The Wi-Fi icon remains
visible. Menu selection works; preference persistence is still unresolved.

### Actual preference write and synchronization

Runtime-confirmed via LLDB on ControlCenterSettings PID 47136:

```
frame #0: 0x00000001880889fc CoreFoundation
frame #1: 0x00000001c2f26948 ControlCenter
x3 = 0x00000001e3356888  @"kCFPreferencesCurrentUser"
x4 = 0x00000001e33ffdc8  @"kCFPreferencesCurrentHost"
0x1c2f32110: com.apple.controlcenter
```

A hardware breakpoint at the actual return site after
CFPreferencesSynchronize confirms failure:

```
frame #0: 0x00000001c2f2695c ControlCenter
x0 = 0x0000000000000000
```

PID 48776 reproduces the same zero result. Its source object is a real
`CFPrefsPlistSource`: the runtime class RO name pointer is `0x1883f5c55`,
and reading the matching Sonoma shared-cache bytes with slide `0x7b10000`
returns that exact class name. Its `synchronize` dispatch reaches
CoreFoundation `0x187ffbd1c`; the first flag at source+0x82 sends execution
to `0x187ffbd60`, returns zero, and clears that flag. A hardware watchpoint
on source+0x82 catches `stlrb w25,[x8]` at `0x188043000` during the normal
set-value path (`x22=0x41eb21a00`, `w25=1`). This is a dirty/change flag,
**not evidence of an authorization rejection**. Do not bypass it or force
synchronization success.

A diagnostic entitlement trial granted only
`com.apple.security.temporary-exception.shared-preference.read-write` for
`com.apple.controlcenter`. Real menu selection changed, but the ByHost file
still contained only Sound, Display and its existing service token; no Wi-Fi
value persisted. The original executable was restored from
`sonoma-workspace-originals/control-input-20261004/ControlCenterSettings-before-pref-capability`.
This trial is not a fix and is not part of the installation contract.

The bounded native oslog capture decoded these macOS records as
`<compose failure [corrupt log]>`; it cannot establish a rejection reason.
All LLDB sessions were detached and their temporary SSH tunnels stopped.

### Persistence control and durable input release

Runtime-confirmed on the same rootfs and uid 0, with the stock defaults
executable and `MACWS_CFPREFERENCES_CLIENT=1`:

```
['-currentHost', 'write'] 0
['-currentHost', 'read'] 0 71
['-currentHost', 'delete'] 0
```

The isolated domain was `com.macwsguide.controlcenter-persistence-probe`;
the test domain was deleted. Therefore the current-host preference service
can persist a normal root client. The extension's failing client path is
still under investigation; authorization and early initialization remain
THEORY, not established causes.

Both architecture variants of the input release, the base native carrier,
and the global rootfs dylibs were updated. Dependency reconciliation repaired
50 panes, and ControlCenterSettings received a normal full preparation after
restoring the diagnostic signature trial. The final stock runtime verifier:

```
SETTINGS-VERIFY {"added": 0, "backend": "already-trusted", "cached": 200, "files": 253, "images": 253, "panes": 50, "resource_hits": 0, "total_seconds": 0.24}
```

This confirms installation consistency and menu input, not working Wi-Fi
icon visibility or completion of the remaining app backlog.
