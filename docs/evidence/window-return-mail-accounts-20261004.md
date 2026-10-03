# Window return and Mail accounts: runtime checks

## Window mode

Runtime-confirmed in `/var/mobile/Library/Logs/MacWSHost.log`:

```
1791068644.436 scene-initial-size postcondition id=9135B41A-0002-417D-8AD3-AD54A6BA1BA6 landed=NO expected=1194.0x779.0 actual=1389.0x970.0 action=fallback-resize
```

The Host's initial-layout fallback previously sent `windowed_role=NO`.
`MacWSWindowing/Tweak.x` intentionally preserves the current layout role for
ordinary resize requests; explicit windowed requests use the role conversion
derived from the actual SpringBoard functions documented beside that code.
The fallback now requests windowed role only for
`initial-layout-postcondition-failed`. Ordinary app-driven resizes retain
their existing role. This is a recovery-path correction, not evidence that
this missing flag caused every reported window-mode failure.

The Host arm64 build passed and the executable was backed up, signed with
its existing profile, trustcached and atomically installed. Only the native
Host was terminated for reload; chroot application processes were preserved.
After enter-workspace / exit-workspace using the existing URL actions:

```
1791068915.392 scene-initial-size postcondition id=3356DC63-FDB6-43FB-9DDD-CDD30E31F1A9 landed=YES expected=1194.0x779.0 actual=1194.0x779.0 action=keep-initial-layout
```

This verifies a fresh return's actual geometry. This run did not exercise the
modified fallback, so its role conversion remains pending a failing-layout
case. It does not certify every application or resize gesture.

## Mail: accounts exist, receiving is unresolved

A read-only Accounts-framework probe in the real chroot, signed with the two
account-access entitlements already present on Mail, returned:

```
type=com.apple.account.IMAP supported=1 count=1
type=com.apple.account.Google supported=1 count=2
type=com.apple.account.Exchange supported=1 count=1
```

Both root and UID 501 returned these counts. All four accounts include
`com.apple.Dataclass.Mail` in enabledDataclasses. The first diagnostic probe
omitted those account entitlements and returned zero; that experiment does
not establish a user-identity failure. No credential values were read.

Google account property keys lack `Hostname` and declare `Class=GmailAccount`.
Exchange has `DAAccountHost` and ActiveSync/OAuth property keys. The running
Mail log separately says `Hostname is required to start watching reachability`
and `This account doesn't have a hostname: <MFEWSAccount: ...>` (personal
account address and identifier omitted here).

Actual Sonoma Mail disassembly is in the local diagnostic artifact
`/tmp/macws-mail-framework-disasm.txt`: `+[MFMailAccount newAccountWithSystemAccount:]`
starts at `0x1bc097330`; `-[MFEWSAccount initWithSystemAccount:]` starts at
`0x1bc156cb8`; `-[MFAccount accountPropertyForKey:]` at `0x1bc125810` delegates
to its base system account. Account conversion, provider defaults and
protocol-specific endpoints still need investigation. These observations do
not justify replacing EWS with an ActiveSync URL or copying passwords/tokens.
