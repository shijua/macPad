# Private Sonoma TCC routing and real window capture

## Rejection source

RE-confirmed via actual Sonoma TCC `0x185b14914..0x185b14930`:
its system service uses XPC_CONNECTION_MACH_SERVICE_PRIVILEGED (2).
The renamed Sonoma endpoints are registered in user/501, not system.
Runtime-confirmed by the same diagnostic operation on the same private
endpoint, varying only the lookup bit:

```
flags=2 type=error error=Connection invalid
flags=0 type=dictionary error=(null)
```

The interposer now clears only bit 2 for the two exact private TCC names.
All other endpoints and all other flags retain their original behavior.
No reply result or WindowServer permission check is changed.

## Real permissions and identity

The stock Sonoma daemons are registered under private bootstrap names.
Their missing Quarantine identity operation is adapted using the actual
live task's audit token (including pidversion), csops entitlement/signing
blobs and main-image build fields. Original successful policy reads remain
unchanged; a missing, mismatched or inaccessible live identity fails.
The old `_audit_token_check_tcc_access` always-return hook is removed.

Runtime-confirmed via tccd-system-macos.log:

```
TCC live-identity pid=43515 version=892527 platform=1 entitlement-bytes=9265
```

Before the lookup correction both management operations failed. After it:

```
ScreenCapture displayd manager result=1
input-access: PostEvent authorized for fixed session input owners; ScreenCapture authorized for macwsdisplayd
```

The startup helper grants only its existing fixed input owners and the
project-owned `/usr/local/bin/macwsdisplayd` capture path. It exits on refusal.
The external diagnostic process remains ungranted: its cross-process capture
still returned NULL. Own-window captures previously succeeded.

## Visible output

After replacing both hook slices and reloading only the display job,
Host recorded actual Finder window 257 frames in window mode:

```
1791070583.146 display-stream first-frame revalidate-input mode=2 target=70909 status=DisplayStream IOSurface 首帧已就绪
1791070583.146 display-stream first-frame revalidate-input mode=2 target=70909 status=2388×1462  ·  DisplayStream  ·  IOSurface 直传
1791070583.148 runtime-confirmed native Metal present scene=733f60b77e811531 frame=2388x1462 backing=2.000 drawable=2436x1748 content=(12.00,71.50 1194.00x731.00) density=1.00 source=IOSurface status=4 error=nil
```

Geometry fallback still reported a size mismatch in this run; frame restoration
does not certify every window geometry, gesture or Settings control.
Hook and workspace-helper builds passed. Tests on the staged version cover
lookup flags, manager errors, exact grant scope, live-token mismatch and
startup ordering. Existing unrelated working-tree changes remain unstaged.
Backups are in `sonoma-workspace-originals/tcc-domain-20261004` on the device.
