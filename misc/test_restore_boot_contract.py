"""Guard the iOS-side repairs required by a filtered macOS rootfs restore."""
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BIND = (ROOT / "layout/usr/macOS/bin/ensure_jb_usr_bind.sh").read_text()
AUTOSIGND = (ROOT / "layout/usr/macOS/bin/restart_autosignd.sh").read_text()
CONTROL = (ROOT / "control").read_text()
MAKEFILE = (ROOT / "Makefile").read_text()
PACKAGE_POSTINST = (ROOT / "layout/DEBIAN/postinst").read_text()


class RestoreBootContract(unittest.TestCase):
    def test_pam_admission_replaces_cms_without_application_entitlements(self):
        postinst = (ROOT / "layout/usr/macOS/bin/postinst.sh").read_text()
        start = postinst.index("ensure_entitlement_free_signature_and_trustcache() {")
        end = postinst.index("\n}", start) + 2
        harness = '''
ldid() {
    case "$1" in
        -e) return 0 ;;
        -h) [ "$2" = "$STOCK" ] && echo 'Authority=Apple Root CA'; return 0 ;;
        -S) echo ENTITLEMENT_FREE_SIGN ;;
        *) return 1 ;;
    esac
}
add_all_trustcache() { echo TRUST; }
'''
        with tempfile.TemporaryDirectory() as directory:
            stock = Path(directory) / "stock"
            signed = Path(directory) / "signed"
            stock.touch()
            signed.touch()
            result = subprocess.run(
                ["bash", "-c", harness + postinst[start:end] +
                 '\nSTOCK="$1"\nensure_entitlement_free_signature_and_trustcache "$1" replace-apple-cms\n'
                 'ensure_entitlement_free_signature_and_trustcache "$2" replace-apple-cms\n',
                 "pam-signing", str(stock), str(signed)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["ENTITLEMENT_FREE_SIGN", "TRUST", "TRUST"])

    def test_hiservices_restore_requires_project_signature_before_trust(self):
        postinst = (ROOT / "layout/usr/macOS/bin/postinst.sh").read_text()
        marker = '    "/var/mnt/rootfs/System/Library/Frameworks/ApplicationServices.framework/'
        line = postinst.index(marker)
        start = postinst.rfind("\n", 0, line - 1) + 1
        end = postinst.index("\n", line)
        harness = 'ensure_project_signature_and_trustcache() { echo PROJECT_SIGNATURE; }\n'
        result = subprocess.run(["bash", "-c", harness + postinst[start:end]],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "PROJECT_SIGNATURE")

    def test_viewbridge_restore_requires_project_signature(self):
        postinst = (ROOT / "layout/usr/macOS/bin/postinst.sh").read_text()
        marker = '    "/var/mnt/rootfs/System/Library/PrivateFrameworks/ViewBridge.framework/'
        line = postinst.index(marker)
        start = postinst.rfind("\n", 0, line - 1) + 1
        end = postinst.index("\n", line)
        harness = 'ensure_project_signature_and_trustcache() { echo PROJECT_SIGNATURE; }\n'
        result = subprocess.run(["bash", "-c", harness + postinst[start:end]],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "PROJECT_SIGNATURE")

    def test_filecoordination_restore_applies_project_signing(self):
        postinst = (ROOT / "layout/usr/macOS/bin/postinst.sh").read_text()
        start = postinst.index('ensure_project_signature_and_trustcache \\\n    "$ROOTFS/usr/sbin/filecoordinationd"')
        end = postinst.index('\n# Terminal', start)
        harness = '''
ROOTFS=/test/rootfs
ensure_project_signature_and_trustcache() { echo "SIGN_AND_TRUST:$1"; }
'''
        result = subprocess.run(
            ["bash", "-c", harness + postinst[start:end]],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(),
                         "SIGN_AND_TRUST:/test/rootfs/usr/sbin/filecoordinationd")

    def test_terminal_restore_signs_regular_image_and_rejects_symlink(self):
        postinst = (ROOT / "layout/usr/macOS/bin/postinst.sh").read_text()
        start = postinst.index("TERMINAL_MAIN=")
        end = postinst.index("\nsign_and_trustcache ", start)
        block = postinst[start:end]
        block = 'TERMINAL_MAIN="$1"' + block[block.index("\n"):]
        harness = '''
chown() { echo OWNERSHIP; }
ensure_project_signature_and_trustcache() { echo SIGN_AND_TRUST; }
add_all_trustcache() { echo TRUST_ONLY; }
'''
        with tempfile.TemporaryDirectory() as directory:
            regular = Path(directory) / "Terminal"
            regular.touch()
            link = Path(directory) / "link"
            link.symlink_to(regular)
            for path, expected in ((regular, 0), (link, 1)):
                result = subprocess.run(
                    ["bash", "-c", harness + block, "terminal-restore", str(path)],
                    capture_output=True, text=True)
                self.assertEqual(result.returncode, expected)
                self.assertEqual(result.stdout.splitlines(),
                    ["OWNERSHIP", "SIGN_AND_TRUST"] if expected == 0 else [])

    def test_native_graphics_marker_does_not_skip_project_signing(self):
        postinst = (ROOT / "layout/usr/macOS/bin/postinst.sh").read_text()
        beginning = postinst.index("ensure_project_signature_and_trustcache() {")
        ending = postinst.index("\n}", beginning) + 2
        function = postinst[beginning:ending]
        # Exercise the actual signing policy against metadata from a stock
        # executable and an already-migrated executable with the same marker.
        script = r'''
ENT=/test/project-entitlements.plist
ldid() {
    case "$1" in
        -e) echo '<key>com.apple.private.graphics-restart-no-kill</key>' ;;
        -h) [ "$2" = "$STOCK" ] && echo 'Authority=Apple Root CA'; return 0 ;;
        -S*) echo SIGNED ;;
    esac
}
add_all_trustcache() { echo TRUSTED; }
'''
        with tempfile.TemporaryDirectory() as directory:
            stock = Path(directory) / "stock"
            migrated = Path(directory) / "migrated"
            stock.touch()
            migrated.touch()
            result = subprocess.run(
                ["bash", "-c", script + function +
                 '\nSTOCK="$1"\nensure_project_signature_and_trustcache "$1"\n'
                 'ensure_project_signature_and_trustcache "$2"\n',
                 "signing-policy", str(stock), str(migrated)],
                text=True, capture_output=True, check=True)
        self.assertEqual(result.stdout.splitlines(), ["SIGNED", "TRUSTED", "TRUSTED"])

    def test_dyld_boot_registration_removes_executable_entitlements(self):
        postinst = (ROOT / "layout/usr/macOS/bin/postinst.sh").read_text()
        self.assertIn(
            "ensure_entitlement_free_signature_and_trustcache /var/mnt/rootfs/usr/lib/dyld || exit 1",
            postinst)
        self.assertNotIn("add_all_trustcache /var/mnt/rootfs/usr/lib/dyld", postinst)

    def test_windowserver_starts_before_waiting_for_its_first_frame(self):
        gui = (ROOT / "layout/usr/macOS/bin/macos_gui.sh").read_text()
        start = gui[gui.index("start_macos() {"):]
        loaded = start.index('launchctl load "$WINDOWSERVER_PLIST" || return 1')
        launched = start.index('launchctl start "$WINDOWSERVER_LABEL" || return 1')
        ready = start.index('wait_for_initial_ws_ready "$ws_log_start_line"')
        self.assertLess(loaded, launched)
        self.assertLess(launched, ready)

    def test_diskarbitration_keeps_real_service_in_headless_mode(self):
        path = ROOT / "layout/usr/macOS/LaunchDaemons/com.macwsguide.macos-diskarbitrationd.plist"
        job = plistlib.loads(path.read_bytes())
        self.assertEqual(job["EnvironmentVariables"]["MACWS_UTILITY_PROCESS"], "1")
        self.assertEqual(job["ProgramArguments"][-1], "/usr/libexec/diskarbitrationd")
        self.assertTrue(job["MachServices"][
            "com.apple.macosbooter.DiskArbitration.diskarbitrationd"])

    def test_bind_probe_uses_the_ios_system_mount_binary(self):
        self.assertIn("system_mount=/sbin/mount", BIND)
        self.assertIn('[ -x "$system_mount" ]', BIND)
        self.assertEqual(BIND.count('if "$system_mount" | grep -Fq'), 2)
        self.assertIn('elif "$system_mount" | grep -Fq', BIND)

    def test_bind_mount_accepts_jbctl_bindfs_fallback(self):
        self.assertIn(
            'jbctl_bindfs=/var/jb/usr/libexec/mount_bindfs/jbctl-bindfs', BIND)
        self.assertIn('elif [ -x "$jbctl_bindfs" ]; then', BIND)
        self.assertIn('"$jbctl_bindfs" -m "$source_dir" "$target_dir"', BIND)

    def test_bind_mount_refreshes_only_its_stale_usr_view(self):
        self.assertIn('/sbin/umount "$canonical_target"', BIND)
        self.assertNotIn('/sbin/umount "$canonical_parent"', BIND)
        self.assertIn('if [ -x "$target_dir/$proxy_relative" ]; then', BIND)
        self.assertLess(
            BIND.index('/sbin/umount "$canonical_target"'),
            BIND.index('if [ -n "$(ls -A "$target_dir")" ]; then'))

    def test_filtered_restore_recreates_only_the_volatile_tmp_directory(self):
        self.assertIn("ROOTFS=/var/mnt/rootfs", AUTOSIGND)
        self.assertIn(
            '[ ! -f "$ROOTFS/System/Library/CoreServices/SystemVersion.plist" ]',
            AUTOSIGND)
        self.assertIn('mkdir -p "$ROOTFS/private/tmp" || exit 1', AUTOSIGND)
        self.assertIn('chmod 1777 "$ROOTFS/private/tmp" || exit 1', AUTOSIGND)
        self.assertIn('ln -s private/tmp "$ROOTFS/tmp" || exit 1', AUTOSIGND)
        self.assertLess(
            AUTOSIGND.index("SystemVersion.plist"),
            AUTOSIGND.index('mkdir -p "$ROOTFS/private/tmp"'))

    def test_package_declares_ios_tools_used_during_postinstall(self):
        depends = next(
            line.removeprefix("Depends:").strip()
            for line in CONTROL.splitlines() if line.startswith("Depends:"))
        self.assertEqual(
            {item.strip() for item in depends.split(",")},
            {"gawk", "ldid", "odcctools", "plutil", "python3"})

    def test_package_survives_dpkg_fat_macho_thinning(self):
        self.assertIn(
            'arm64="$(THEOS_STAGING_DIR)/usr/macOS/lib/libmachook_arm64.dylib"',
            MAKEFILE)
        self.assertIn('lipo "$$fat" -thin arm64 -output "$$arm64"', MAKEFILE)
        self.assertIn('lipo "$$fat" -thin arm64e -output "$$arm64e"', MAKEFILE)
        self.assertIn('elif [ -f "$LIBMACHOOK_ARM64" ]; then', PACKAGE_POSTINST)
        self.assertIn(
            '"$MACHO_PATCHER" "$LIBMACHOOK_ARM64" || exit 1',
            PACKAGE_POSTINST)

    def test_package_rejects_bootstraps_without_dynamic_trustcache_support(self):
        self.assertIn(
            'if [ ! -x /var/jb/usr/bin/jbctl ]; then',
            PACKAGE_POSTINST)
        self.assertIn(
            'NathanLR cannot admit the macOS shared-cache closure',
            PACKAGE_POSTINST)

    def test_package_signs_and_trusts_chroot_bash_once(self):
        self.assertIn('bash_target="$ROOTFS/bin/bash"', PACKAGE_POSTINST)
        self.assertIn(
            'ldid -e "$bash_target" 2>/dev/null |', PACKAGE_POSTINST)
        self.assertIn(
            'ldid -S"$ENTITLEMENTS" -M "$bash_target" || exit 1',
            PACKAGE_POSTINST)
        self.assertIn('trust_installed_macho "$bash_target"', PACKAGE_POSTINST)
        self.assertLess(
            PACKAGE_POSTINST.index('trust_installed_macho "$bash_target"'),
            PACKAGE_POSTINST.index('ensure_interop_signature \\'))

    def test_package_merges_and_trusts_defaults_before_gui_probe(self):
        self.assertIn('defaults_target="$ROOTFS/usr/bin/defaults"',
                      PACKAGE_POSTINST)
        self.assertIn(
            'ldid -S"$ENTITLEMENTS" -M "$defaults_target" || exit 1',
            PACKAGE_POSTINST)
        self.assertIn('trust_installed_macho "$defaults_target"',
                      PACKAGE_POSTINST)


if __name__ == "__main__":
    unittest.main()
