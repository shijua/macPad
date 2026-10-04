# Target ExtensionKit feature configuration

The prior Ventura adapter returned false for every ExtensionKit feature. Runtime inspection on the iPad confirmed Sonoma has `/System/Library/FeatureFlags/Domain/ExtensionKit.plist`, with `prefer_inprocess_discovery` and `host_requires_entitlements` enabled. The outer iPadOS domain additionally enables `automatically_sandbox_extensions`, which the Sonoma domain does not contain.

The adapter now loads the target plist before hooking the provider, reads each real Boolean Enabled value, and retains absent-domain/default-false behavior for Ventura. Other domains still delegate to the original provider. A malformed target file is reported without installing a guessed replacement.

Runtime-confirmed through an actual chroot call to `_os_feature_enabled_impl` after deployment:

```text
prefer_inprocess_discovery=1
host_requires_entitlements=1
automatically_sandbox_extensions=0
unknown_macws_probe=0
```

Both library architectures built. A compiled test of the actual lookup covers true, false, missing and malformed entries and delegation to other domains. The 50 Settings runtimes were reprovisioned and the signature verifier exited 0. This corrects configuration semantics; whether it restores Settings pane rendering requires a separate UI witness.

Four library copies were preserved under `/var/jb/var/mobile/sonoma-workspace-originals/extension-features-20261004`. Only the unused `/etc/zshenv` scaffold created during this session was archived and removed after an exact content match; effective zsh startup configuration remains in zprofile/zshrc.
