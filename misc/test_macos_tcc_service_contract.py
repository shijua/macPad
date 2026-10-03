"""Verify that Sonoma privacy requests reach its own TCC daemon."""
from pathlib import Path
import plistlib
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLIST = ROOT / "layout/usr/macOS/LaunchDaemons/com.macwsguide.tccd-system.plist"
GUI = (ROOT / "layout/usr/macOS/bin/macos_gui.sh").read_text()
HOOKS = (ROOT / "libmachook/mac_hooks.m").read_text()
POSTINST = (ROOT / "layout/usr/macOS/bin/postinst.sh").read_text()


class MacOSTCCServiceContract(unittest.TestCase):
    def test_user_privacy_requests_use_user_daemon(self):
        job = plistlib.loads(PLIST.with_name(
            'com.macwsguide.tccd-user.plist').read_bytes())
        self.assertEqual(job['ProgramArguments'][-1],
                         '/System/Library/PrivateFrameworks/TCC.framework/Support/tccd')
        self.assertEqual(job['MachServices'], {'com.macwsguide.tccd': True})
        self.assertEqual(job['EnvironmentVariables']['HOME'], '/var/root')
        self.assertIn('if (!strcmp(name, "com.apple.tccd"))\n'
                      '        return "com.macwsguide.tccd";', HOOKS)
        self.assertIn('launchctl load "$TCC_USER_PLIST" || return 1', GUI)

    def test_daemon_is_prepared_and_restored_before_clients_start(self):
        path = '$ROOTFS/System/Library/PrivateFrameworks/TCC.framework/Support/tccd'
        self.assertIn('ensure_project_signature_and_trustcache \\\n    "' + path + '" || exit 1', POSTINST)
        start = GUI.index('restore_cold_boot_trust()')
        self.assertIn('"' + path + '"', GUI[start:GUI.index('\n}', start)])

    def test_job_uses_stock_sonoma_tccd_with_private_listener(self):
        job = plistlib.loads(PLIST.read_bytes())
        self.assertEqual(job["Label"], "com.macwsguide.tccd-system")
        self.assertEqual(
            job["ProgramArguments"],
            [
                "/var/jb/usr/macOS/bin/launchdchrootexec",
                "0",
                "0",
                "/var/mnt/rootfs",
                "/System/Library/PrivateFrameworks/TCC.framework/Support/tccd",
                "system",
            ],
        )
        self.assertEqual(
            job["MachServices"], {"com.macwsguide.tccd.system": True}
        )
        self.assertEqual(job["POSIXSpawnType"], "Adaptive")
        self.assertTrue(job["EnablePressuredExit"])
        self.assertEqual(
            job["PublishesEvents"],
            {"com.macwsguide.tccd.events": {"DomainInternal": True}},
        )
        self.assertNotIn("RunAtLoad", job)
        self.assertNotIn("KeepAlive", job)

    def test_gui_stack_manages_and_routes_the_stock_service(self):
        self.assertIn("publish_macos_tcc_service || return 1", GUI)
        self.assertIn('launchctl print "user/501/$TCC_SYSTEM_LABEL"', GUI)
        self.assertIn("demand-started TCC service", GUI)
        self.assertIn('launchctl remove "$TCC_SYSTEM_LABEL"', GUI)
        self.assertIn(
            'if (!strcmp(name, "com.apple.tccd.system"))\n'
            '        return "com.macwsguide.tccd.system";',
            HOOKS,
        )
        self.assertNotIn("_audit_token_check_tcc_access", HOOKS)


if __name__ == "__main__":
    unittest.main()
