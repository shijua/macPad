# Sonoma zsh module slices

Runtime-confirmed in the real Terminal desktop capture: zsh reported
`fat file, but missing compatible architecture (have 'x86_64,arm64e', need '')`
for terminfo, regex and zle. The native image list showed libmachook.dylib
(the arm64e slice) loaded by zsh PID 44085. The source module fat tables
contain the same arm64e subtype 0x80000002 as /bin/zsh.

A controlled first experiment selected the unchanged original arm64e
terminfo bundle slice, signed and trusted it, and supplied its module_path:

```
MODULE_STATUS=0
```

The production preparation helper validates the fat-table bounds and matching
MH_BUNDLE header, keeps every original module, signs thin copies in
/usr/local/lib/macws-zsh/5.9, and retains source/output hashes to avoid
re-signing unchanged files. It restores the copies' hashes on GUI cold start.
AppleDouble metadata is excluded. The matching module path and existing TLS
backend default are prepended to the real zprofile/zshrc, preserving original
content and permissions. Original startup checks remain intact.

Runtime-confirmed after preparing 36 real modules:

```
zsh-modules: prepared and trusted 36 original arm64e modules
Refusing to load unsafe zshenv.
MODULE_STATUS=0
TLS_BACKEND=openssl
HTTP/2 200
```

The zshenv warning is unresolved. RE-confirmed via actual /bin/zsh
0x100031f2c..0x100031ff0 and 0x10003217c..0x1000321b4: its startup code
reads csops status then can skip zshenv and emit that message. The precise
status seen at that startup branch remains to be traced. A later native
csops read of PID 44085 returned 0x36003005; that later value does not prove
the earlier branch input. No branch or status was forced.

Tests check mismatched/truncated slices, unmodified payload extraction,
startup ordering, repeated preparation and retained mode/content.
