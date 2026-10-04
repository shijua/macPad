# Text clipboard and CLI architecture

## Clipboard

Runtime-confirmed: the user-supplied MacWS Imports path points to a 46-byte ASCII file containing the copied installer command. The snapshot loader used `loadItemForTypeIdentifier` for text, which can return a promised file URL. The archive converter treated any file URL as an import and transferred its path under the text type.

Text-conforming representations now use NSItemProvider's data loader. File-URL and other representations retain their existing route. A compiled regression test covers asynchronous ordering, failure, timeout, single completion, genuine file URLs and a real file-backed text promise. An iOS-native probe on the device reports:

```text
IOS-PROMISED-TEXT inline-data=1 exact-text=1 error=0
```

The Host application rebuilt and was deployed with its original entitlements. No user clipboard content was replaced for the probe. Copy fresh text to replace an already imported path.

## Architecture

Runtime-confirmed: the stock chroot `/usr/bin/uname -m` returned `iPad13,4`. RE-confirmed in that actual Sonoma binary at `0x100003ca0..0x100003cd4`: it builds MIB `{6,1}` (`CTL_HW/HW_MACHINE`) and calls `_sysctl`. The official Codex installer rejects architecture names other than its supported CPU families.

The sysctl adapter now reports this arm64 process's architecture for read-only HW_MACHINE queries. Other MIBs and writes delegate to the original API. Size queries and insufficient-buffer errors are covered by a compiled C test; native Darwin confirmed ENOMEM reports zero copied bytes for the undersized string buffer.

After deployment the same uname command exits 0 with `arm64`. Codex's official installer detects macOS Apple Silicon. The stock shasum Perl shebang is rejected with Operation not permitted on this device; the install session supplies an OpenSSL-backed SHA-256 function, retaining the original installer's expected-digest comparison. Authentication and model calls are outside the installation verification.

Backups: `/var/jb/var/mobile/sonoma-workspace-originals/text-architecture-20261004`.

## Codex package preparation

The official 0.160.0 Apple Silicon archive was completed on the Mac while the iPad's lock-screen policy suspended the installer. Its SHA-256 matched `007df41b607dbbc8d204b9746ce7fed2d4ce6c813f44c32ceee54175ca796525`; the checksum manifest matched `82da8661fd9603329785350cce676e066d4b3419484c75d59314209e8edf8fcd`. The archive was reverified on the iPad before extraction, its entries checked for path traversal, and 30 Mach-O images signed and trusted using the project's existing admission tools.

Prepared release: `/var/root/.codex/packages/standalone/releases/0.160.0-aarch64-apple-darwin`; CLI link: `/var/root/.local/bin/codex`. Root's profile and zshrc received the local-bin PATH entry with backups preserved. The two exact paused installer/download processes were retired to prevent conflicting installation after unlock. Native-side package preparation was followed by actual chroot execution. Both the utility environment and the ordinary environment returned exit 0 and `codex-cli 0.160.0`. Interactive startup and authentication still require user verification. No user authentication was read or created.
