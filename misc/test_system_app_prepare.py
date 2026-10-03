import importlib.util
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_boot_trust import ROOT, macho, trust
from test_macho_dependencies import deps

sys.modules['macws_boot_trust'] = trust
SPEC = importlib.util.spec_from_file_location('app_prepare',
    ROOT / 'layout/usr/macOS/bin/macws_system_app_prepare.py')
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)


class SystemAppPreparation(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.binary = self.root / 'Main'
        self.binary.write_bytes(macho())
        active = patch.object(app, 'bundle_identifier', return_value='com.apple.TestApp')
        active.start()
        self.addCleanup(active.stop)
        active = patch.object(app, 'has_identifier', return_value=True)
        active.start()
        self.addCleanup(active.stop)
        self.state = self.root / 'state'
        self.state.mkdir()
        self.profile = self.root / 'profile.plist'
        self.profile.write_bytes(plistlib.dumps(dict.fromkeys(app.REQUIRED, True)))
        active = patch.object(app, 'PROFILE', str(self.profile))
        active.start()
        self.addCleanup(active.stop)
        active = patch.object(app, 'ROOT', str(self.root))
        active.start()
        self.addCleanup(active.stop)

    def test_rejects_third_party_nested_executable_and_escape(self):
        for path in ('/Applications/Steam.app/Contents/MacOS/steam_osx',
                     '/System/Applications/A.app/Contents/MacOS/A/child',
                     '/System/Applications/A.app/Contents/MacOS/../Other',
                     '/System/Applications/../Other.app/Contents/MacOS/A'):
            with self.assertRaises(ValueError):
                app.resolve_target(path)

    def test_trusted_stock_is_not_proof_of_chroot_profile(self):
        record = [{'arch': 'arm64e'}]
        rights = {'com.apple.security.app-sandbox': True}
        with patch.object(app.subprocess, 'run', return_value=
                subprocess.CompletedProcess([], 0, plistlib.dumps(rights), b'')):
            self.assertFalse(app.has_profile(str(self.binary), record))
        rights.update(dict.fromkeys(app.REQUIRED, True))
        with patch.object(app.subprocess, 'run', return_value=
                subprocess.CompletedProcess([], 0, plistlib.dumps(rights), b'')):
            self.assertTrue(app.has_profile(str(self.binary), record))

    def test_existing_profile_is_never_resigned(self):
        with patch.object(app, 'has_profile', return_value=True), \
                patch.object(app.subprocess, 'run') as sign:
            self.assertFalse(app.ensure_main_profile(str(self.binary), str(self.state)))
            sign.assert_not_called()
        self.assertEqual(list(self.state.iterdir()), [])

    def test_conversion_is_backed_up_and_uses_a_new_inode(self):
        inode = self.binary.stat().st_ino
        with patch.object(app, 'has_profile', side_effect=[False, True]), \
                patch.object(app.os, 'chown'), \
                patch.object(app.subprocess, 'run') as sign, \
                patch.object(trust, 'restore', return_value=(1, 'test')) as restore:
            self.assertTrue(app.ensure_main_profile(str(self.binary), str(self.state)))
            self.assertEqual(sign.call_count, 2)
            for call in sign.call_args_list:
                self.assertNotEqual(call.args[0][-1], str(self.binary))
                self.assertIn('-M', call.args[0])
                self.assertIn('-Icom.apple.TestApp', call.args[0])
            restore.assert_called_once()
        self.assertNotEqual(inode, self.binary.stat().st_ino)
        self.assertEqual(next(self.state.glob('original-*')).read_bytes(), macho())
        self.assertEqual(list(self.root.glob('.macws-admission-*')), [])

    def test_failed_admission_leaves_original_inode_and_bytes(self):
        inode = self.binary.stat().st_ino
        with patch.object(app, 'has_profile', side_effect=[False, True]), \
                patch.object(app.os, 'chown'), patch.object(app.subprocess, 'run'), \
                patch.object(trust, 'restore', side_effect=ValueError('trust failure')):
            with self.assertRaisesRegex(ValueError, 'trust failure'):
                app.ensure_main_profile(str(self.binary), str(self.state))
        self.assertEqual(inode, self.binary.stat().st_ino)
        self.assertEqual(self.binary.read_bytes(), macho())
        self.assertEqual(list(self.root.glob('.macws-admission-*')), [])

    def test_existing_profile_with_temporary_identifier_is_repaired(self):
        with patch.object(app, 'has_profile', return_value=True), \
                patch.object(app, 'has_identifier', side_effect=[False, True]), \
                patch.object(app.os, 'chown'), \
                patch.object(app.subprocess, 'run') as sign, \
                patch.object(trust, 'restore', return_value=(1, 'test')):
            self.assertTrue(app.ensure_main_profile(str(self.binary), str(self.state)))
            self.assertEqual(sign.call_count, 2)
            for call in sign.call_args_list:
                self.assertIn('-Icom.apple.TestApp', call.args[0])

    def test_warm_preparation_still_checks_live_main_and_plugin_trust(self):
        plugins = self.root / 'PlugIns'
        plugins.mkdir()
        (plugins / 'Widget').write_bytes(macho())
        with patch.object(app, 'ensure_main_profile', return_value=False), \
                patch.object(trust, 'restore', return_value=(0, 'test')) as restore:
            for _ in range(2):
                result = app.prepare_locked(str(self.binary), str(plugins), str(self.state))
                self.assertEqual(result['images'], 2)
            self.assertEqual(restore.call_count, 2)

    def test_external_plugins_follow_actual_framework_imports(self):
        plugins = self.root / 'System/Library/Address Book Plug-Ins'
        plugins.mkdir(parents=True)
        address_book = '/System/Library/Frameworks/AddressBook.framework/Versions/A/AddressBook'
        self.assertEqual(app.dynamic_plugin_roots({
            'main': {'loads': [address_book]}}), [str(plugins.resolve())])
        self.assertEqual(app.dynamic_plugin_roots({
            'main': {'loads': ['/System/Library/Frameworks/AppKit.framework/AppKit']}}), [])
        self.assertEqual(app.dynamic_plugin_roots({
            'main': {'loads': ['/System/Library/Frameworks/AddressBook.framework-other/A']}}), [])

    def test_external_plugin_alias_cannot_escape_rootfs(self):
        plugins = self.root / 'System/Library/Address Book Plug-Ins'
        plugins.parent.mkdir(parents=True)
        plugins.symlink_to(self.root.parent)
        with self.assertRaisesRegex(ValueError, 'escapes rootfs'):
            app.dynamic_plugin_roots({'main': {'loads': [
                '/System/Library/Frameworks/AddressBook.framework/AddressBook']}})


class BundleIdentity(unittest.TestCase):
    def test_actual_metadata_and_mismatched_executable(self):
        with tempfile.TemporaryDirectory() as folder:
            contents = Path(folder) / 'App.app/Contents'
            binary = contents / 'MacOS/Main'
            binary.parent.mkdir(parents=True)
            info = contents / 'Info.plist'
            info.write_bytes(plistlib.dumps({'CFBundleIdentifier': 'com.apple.TestApp',
                                            'CFBundleExecutable': 'Main'}))
            self.assertEqual(app.bundle_identifier(str(binary)), 'com.apple.TestApp')
            with self.assertRaisesRegex(ValueError, 'does not match'):
                app.bundle_identifier(str(binary.parent / 'Helper'))
            info.write_bytes(plistlib.dumps({'CFBundleIdentifier': '-Ievil/escape',
                                            'CFBundleExecutable': 'Main'}))
            with self.assertRaisesRegex(ValueError, 'invalid'):
                app.bundle_identifier(str(binary))

    def test_every_native_slice_must_have_exact_identifier(self):
        records = [{'arch': 'arm64'}, {'arch': 'arm64e'}]
        results = [subprocess.CompletedProcess([], 0, b'Identifier=com.apple.TestApp\n', b''),
                   subprocess.CompletedProcess([], 0, b'Identifier=.macws-admission-random\n', b'')]
        with patch.object(app.subprocess, 'run', side_effect=results):
            self.assertFalse(app.has_identifier('Main', records, 'com.apple.TestApp'))


if __name__ == '__main__':
    unittest.main()
