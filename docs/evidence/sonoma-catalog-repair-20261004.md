# Sonoma application catalog recovery

Runtime-confirmed on the iPad: the stock `lsregister -kill -seed` reported Spotlight scan errors `-50` and exited 2. The subsequent Terminal lookup returned `resolvedURL=<nil>`. Explicit `lsregister -f` for Terminal, System Settings, Finder, Dock and the Cryptex Safari bundle each exited 0. The optional VS Code bundle was absent.

Sonoma recovery now preserves the live database, registers missing fixed core application URLs with LaunchServices, and registers Settings extensions through the existing registrar. Ventura retains its previously verified clean-seed route. The startup path calls the same version-aware controller.

After deploying the controller, both `repair-launchservices-catalog` and `verify-launchservices-catalog` exited 0, with `settings-extensions-verified candidates=49 records=49`. The Settings shell still did not start a pane process. Catalog integrity is repaired; pane rendering is not yet verified and this change does not explain why records were originally lost.

Validation: controller cross-build, four live-catalog regression checks and shell syntax check. Device backups: `/var/jb/var/mobile/sonoma-workspace-originals/catalog-repair-20261004`.
