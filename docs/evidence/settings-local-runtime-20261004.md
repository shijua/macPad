# Sonoma Settings runtime dependency and feature lifetime

## Confirmed failures

Runtime-confirmed via `settings-general-current.ips` (GeneralSettings PID 77458):

```text
namespace: DYLD; indicator: Library missing
Library not loaded: /Library/Frameworks/CydiaSubstrate.framework/CydiaSubstrate
Referenced from: <14FB8844-B5A8-3523-BD86-CD4415AA1D5C>
/System/Applications/System Settings.app/Contents/PlugIns/GeneralSettings.appex/Contents/Frameworks/libmachook.dylib
/System/Library/Frameworks/CydiaSubstrate.framework/CydiaSubstrate
(file system sandbox blocked mmap())
```

The provisioning script already copied ElleKit into each extension's
`Contents/Frameworks/.jbroot/Library/Frameworks/CydiaSubstrate.framework/`.
The hook still imported the global framework, so this local copy was unused.
Provisioning now changes only that known import to the bundle-local
`@loader_path` path on a fresh inode, re-signs it and trusts the actual new
CodeDirectories. Unknown imports fail reconciliation. Runtime schema v4 and
verification reject global or missing substrate imports. Incremental repair
records the modified local hook hash separately from the source hook hash.

Runtime-confirmed via `extensionkit-current.ips` (extensionkitservice PID 85503):

```text
EXC_BAD_ACCESS / SIGSEGV
objc_msgSend + 32
macws_os_feature_enabled_impl_compat + 96
-[_EXService launchWithConfiguration:clientConnection:error:] + 496
```

RE-confirmed via the deployed arm64e libmachook before replacement:
`+0xbd10` calls `dictionaryWithContentsOfFile:`, `+0xbd18` stores the result
globally without retaining it. Feature lookup at `+0x27b9c` messages that
stored pointer (`objectForKeyedSubscript:`); the crash's caller is `+0x27ba0`.
The initializer now owns the immutable dictionary for the hook's process
lifetime. It preserves the actual Sonoma values and all feature checks.
The regression runs without ARC and queries after the creating autorelease
pool drains.

## Validation

- 16 Settings tests and the compiled non-ARC feature regression pass.
- Both libmachook architectures build.
- All 50 Settings panes and 253 images pass actual signature/trust verification.
- Authentic native DisplayStream capture `settings-local-dependency-result.png`
  shows the complete General pane after the dependency repair.
- Authentic capture `settings-restart-current.png` shows Appearance controls.
- After the lifetime repair, continuous native input navigation produced real
  General, About, Appearance, Desktop & Dock and Control Center captures
  (`settings-lifetime-*.png`). About shows Sonoma 14.0, memory and the real
  display dimensions; chip identity is still blank.
- Individual settings effects still require separate witnesses; page rendering
  does not prove that each control changes the relevant system state.

Local logs/captures are under `tmp/sonoma-14.0/priority-20261003/`.
Original scripts and four source/runtime libraries are preserved on-device in
`/var/jb/var/mobile/sonoma-workspace-originals/settings-local-dependency-20261004/`.
No authorization checks or failed setup calls are replaced with success.

## Remaining Dock control effect

The actual UI slider and automatic-hide toggle change their displayed state,
but `CoreDockGetTileSize`/`CoreDockGetAutoHideEnabled` still returned
`0.4286`/`0` after those clicks. This remains unresolved.

RE-confirmed via arm64e DesktopSettings: `+0x60564..+0x60580` loads its
requested Double and calls wrapper `+0x5b5bc`. That wrapper boxes and
conditionally unboxes NSNumber via the Foundation Swift bridges, and only
calls the real setter at `+0x5b610` if conversion supplied a value. Bool
uses corresponding wrapper `+0x5ba0c`. No branch was bypassed.

An independent actual chroot probe rules out a general Swift NSNumber bridge
failure: Double 0.27 round-tripped with `accepted=1, absent=0`, and Bool true
with `accepted=1, output=1`. That does not prove the wrapper ran inside the
Settings extension.

A separate real CoreDock RPC probe, signed with the exact DesktopSettings
entitlement dictionary, returned:

```text
before size=0.4286 autohide=0
set size result=0
set autohide result=0
after size=0.2679 autohide=1
```

The previous size was restored using the full float value (a truncated
six-decimal value rounds down one Dock step); final getters returned
`size=0.4286 autohide=0`. Thus adding the general hook entitlement set is
not supported as the fix. The control's callback/notification path needs
an in-process witness. A bounded native oslog subscription produced zero
bytes; that is not evidence that the client made or completed its calls.
