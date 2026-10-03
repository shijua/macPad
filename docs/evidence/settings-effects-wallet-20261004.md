# Settings effects and Wallet icon investigation

## Wallet: runtime-confirmed missing identifier record

The real Sonoma Wallet extension declares:

```text
CFBundleIdentifier=com.apple.WalletSettingsExtension
CFBundleIconFile=WalletSettingsExtension.icns
```

The original ICNS exists and is 151222 bytes. A bounded independent probe
using the actual IconServices implementation produced:

```text
REQUEST IDENTIFIER provider=nil record=nil
REQUEST URL provider=ISBundleResourceProvider record=nil
RESOLVED_RESOURCE URL resource=ISIcns symbol=nil
RESOURCE_RENDER class=ISIcns image=1 colored=1474
DIRECT_ICON IDENTIFIER image=1 visible=2280 colored=0
DIRECT_ICON URL image=1 visible=2280 colored=0
```

The real LSBundleRecord identifier lookup returned -10814 with:
`Unable to find this application extension record in the Launch Services database.`
Thus a non-nil original image was the monochrome placeholder, whereas the
actual URL resource rendered the declared colored artwork.

The existing complete registration command failed before reaching Wallet:
`stock LaunchServices registration failed status=-50 identifier=com.apple.SystemProfiler.AboutExtension`.
The registration failure remains separate work; the icon change does not
fabricate or register an extension record.

## Minimal icon change

Only the confirmed Wallet identifier is eligible. Validate the real bundle's
identifier and declared ICNS filename, obtain its normal ISBundleIcon URL
provider, resolve its unchanged resource, and require the real ISIcns class.
The existing imageForSize:scale: path renders that resource. Missing or
mismatched metadata/resources still use the original IconServices path.

Two compiled regression tests passed; both library architectures built.
Deployed library backups are under
`/var/jb/var/mobile/sonoma-workspace-originals/wallet-icon-20261004`.
Final Settings-window validation remains pending after its dependency repair.

## Dock: direct protocol works; pane interaction not yet verified

RE-confirmed via the actual DesktopSettings binary:
the controls call CoreDockSetTileSize, CoreDockSetAutoHideEnabled and
CoreDockSetOrientationAndPinning. Actual HIServices implementations communicate
with the original com.apple.dock.server service. CoreDockSetTileSize at
`0x18686dbb8` takes its float in s0 and forwards its additional x0 argument
through sendSetFloatValue; it is not simply a defaults write.

The correctly typed independent same-value, temporary setter experiment yielded:

```text
DOCK_SIZE 0.43
DOCK_AUTOHIDE 0
DOCK_SAME_SIZE_WRITE status=0 after=0.43
```

This validates an actual Dock read/write RPC, not the reported pane controls.
An initial incorrectly typed CoreDockCopyPreferences call exited 255; that
experiment was discarded. Actual disassembly shows it requires input keys
and an output pointer, rather than returning a dictionary directly.

The UI regression encountered a real Settings Error dialog stating
`Extension process Screen Saver(35031) exited.` The automation did not dismiss
that modal; no Dock or Control Center option was changed during the attempt.
The main-thread sample showed a mach-message/run-loop stack, which alone
does not establish a deadlock. Control Center preferences and Dock pane input
still require live validation.
