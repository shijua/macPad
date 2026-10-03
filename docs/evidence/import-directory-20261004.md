# Import-directory permissions, iPadOS 17 / Sonoma 14

Runtime-confirmed via USB SSH on the running device:

```
drwxr-xr-x 2 root wheel 64 Oct 1 23:27 /var/mnt/rootfs/Users/Shared/MacWS Imports
34247 501 .../Applications/MacWSHost.app/MacWSHost
```

The Host's `MacWSStageProviderURL` creates a UUID subdirectory here before
copying provider data. The reported screenshot shows that directory creation
denied. The observed owner/mode does not permit UID 501 to create entries.
The install script already specifies mobile ownership and mode 0770; this
observed directory does not satisfy that contract. Its creation history has
not been established, so this is not attributed to the Settings icon change.

Repair applied only to this directory using `open(O_DIRECTORY|O_NOFOLLOW)`,
`fchown(501,501)` and `fchmod(0770)`. An actual UID/GID 501 process then
created and removed its own temporary subdirectory:

```
mobile create/remove directory: PASS; root mode=0770 owner=501:501
```

`macwshostd` now checks this fixed directory on startup. Failures are logged;
the other desktop services remain available. Imported contents are not
recursively modified. The helper rejects symlinks and ordinary files.

Validation: `python3 misc/test_import_directory.py` passed; Theos arm64
macwshostd build passed. The new daemon was signed with its existing profile,
trustcached, and atomically installed. The running daemon was not restarted;
the startup repair takes effect at its next normal lifecycle. Permissions
were separately repaired in the current session. The native Host's existing
`test-drop-file` action subsequently reported:

```
1791069045.696 interop-provider-load item=0 kind=file-url type=public.file-url accepted=YES error=nil
1791069045.698 interop-drop-probe file=macws-drop-probe-14DF7633-0411-443C-93C8-50F10A59AEDB.txt window=257 pid=70909 applied=YES error=nil
```

The staged file and source fixture both matched the expected 35 bytes. Only
these two exact matching test files were removed. This proves provider-file
staging and publication, not the receiving application's final paste action.
Other provider-source access failures remain separate.
