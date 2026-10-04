# Dock Settings RPC permission

## Confirmed failure

The real DesktopSettings controls updated their displayed values while Dock
retained size `0.4286` and automatic hiding disabled. A separately launched
CLI probe could call the same Dock interfaces successfully. The probe did
not prove that the sandboxed extension could query the server.

Runtime-confirmed via hardware breakpoints on the production DesktopSettings
PID 23842, without an injected diagnostic hook:

```text
stop reason = breakpoint 1.1
frame #0: 0x000000018e37dbb8 HIServices
x0 = 0x0000000000000000
s0 = 0.266666681
lr = 0x00000001046a7614
```

At the setter's return address, before its caller overwrote x0:

```text
w0 = 0xffffeca1
```

Automatic hiding returned the same `-4959`. A further hardware breakpoint
at the real server lookup return (`0x18e367d44`) recorded:

```text
w0 = 0x0000044c
```

The SDK's `bootstrap_defs.h` defines 1100 as `BOOTSTRAP_NOT_PRIVILEGED`.
RE-confirmed via actual HIServices UUID
`3F6ED85B-CC96-39CF-8FFF-0C9A35DF55C7`: `+0x18d40` calls the lookup of
`com.apple.dock.server`; `+0x18d44` tests its result; failure at `+0x18d4c`
sets `-4959`. This is upstream of the Dock settings message.

## Minimal repair and validation

Add `com.apple.dock.server` to the existing
`com.apple.security.exception.mach-lookup.global-name` list of only
`com.apple.Desktop-Settings.extension`. Preserve all other entitlements.
Sign a fresh inode, verify its capability and register the actual arm64
CodeDirectory hashes before replacing the executable.

After this exact permission change, actual clicks in the Settings page
changed getters to `size=0.2589 autohide=1`. Authentic native DisplayStream
capture `dock-permission-ui-pass.png` shows the Dock hidden. Toggling hiding
off showed a visibly smaller Dock in `dock-left-real-pass.png`; despite
that historical filename, the Dock remained at the bottom. Position menu
selection therefore remains unverified. The original size/hiding state was
restored to `0.4286/0` using the actual RPC, with both setters returning 0.

Initial provisioning, incremental repair and both runtime verifiers now
check the narrow capability. All 50 panes/253 images pass device signature
and trust verification. 23 Settings regression tests and shell syntax checks
pass. The executable and previous scripts are preserved at
`/var/jb/var/mobile/sonoma-workspace-originals/dock-permission-20261004/`.

## Discarded instrumentation

A temporary inline-hook diagnostic crashed the extension. Repeating the
controls with the production library kept the extension running. A later
GOT diagnostic was refused with `KERN_PROTECTION_FAILURE (2)` even with
`import-debugged=1`. Neither attempt established a production crash cause.
Both diagnostic implementations were removed from the working tree; the
device marker was removed and all local production libraries reconciled.
Hardware breakpoints supplied the final witnesses above and were detached.

Local captures and experiments are under
`tmp/sonoma-14.0/priority-20261003/`. No setter result, conversion check,
server lookup or sandbox decision is replaced with fabricated success.
