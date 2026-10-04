import importlib.util
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('capabilities',
    ROOT / 'layout/usr/macOS/bin/macws_settings_capabilities.py')
cap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cap)


class SettingsCapabilities(unittest.TestCase):
    def test_other_panes_require_no_new_capability(self):
        with patch.object(cap, 'entitlements', side_effect=AssertionError('unexpected read')):
            cap.verify('com.apple.TestSettings', '/unused')
            self.assertFalse(cap.repair('com.apple.TestSettings', '/unused'))

    def test_missing_dock_permission_is_rejected(self):
        with patch.object(cap, 'entitlements', return_value={cap.LOOKUP: ['other']}):
            with self.assertRaisesRegex(ValueError, 'cannot query'):
                cap.verify(cap.DESKTOP, '/test')

    def test_wrong_type_is_rejected(self):
        for value in (False, {'service': cap.DOCK}, [12]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cap.required(cap.DESKTOP, {cap.LOOKUP: value})

    def test_existing_permission_needs_no_signature_change(self):
        with patch.object(cap, 'entitlements', return_value={cap.LOOKUP: [cap.DOCK]}), \
                patch.object(cap.subprocess, 'run') as run:
            self.assertFalse(cap.repair(cap.DESKTOP, '/test'))
            run.assert_not_called()

    def test_multiple_slice_documents_parse_first_selected_slice(self):
        value = {cap.LOOKUP: [cap.DOCK], 'private.original': True}
        raw = plistlib.dumps(value)
        with patch.object(cap.subprocess, 'run', return_value=
                          subprocess.CompletedProcess([], 0, raw + raw)):
            self.assertEqual(cap.entitlements('/test'), value)

    def test_repair_preserves_permissions_and_trusts_before_replace(self):
        old = {cap.LOOKUP: ['other'], 'private.original': True}
        calls = []
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'DesktopSettings'
            source.write_bytes(b'original image')
            source.chmod(0o755)

            def run(command, **kwargs):
                calls.append(command)
                self.assertEqual(source.read_bytes(), b'original image')
                if any(argument.startswith('-S') for argument in command):
                    document = plistlib.loads(Path(next(a[2:] for a in command
                                              if a.startswith('-S'))).read_bytes())
                    self.assertEqual(document, {cap.LOOKUP: ['other', cap.DOCK],
                                                'private.original': True})
                output = 'CDHash=' + 'a' * 40 + '\n' if '-h' in command else ''
                return subprocess.CompletedProcess(command, 0, output)

            with patch.object(cap, 'entitlements', side_effect=[old,
                     {cap.LOOKUP: ['other', cap.DOCK]}]), \
                    patch.object(cap.subprocess, 'run', side_effect=run):
                self.assertTrue(cap.repair(cap.DESKTOP, str(source)))
            self.assertEqual(source.stat().st_mode & 0o777, 0o755)
            self.assertEqual(list(Path(folder).iterdir()), [source])
            self.assertEqual(sum('trustcache' in command for command in calls), 2)

    def test_failed_signing_keeps_original_and_cleans_temporary_files(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'DesktopSettings'
            source.write_bytes(b'original image')
            with patch.object(cap, 'entitlements', return_value={}), \
                    patch.object(cap.subprocess, 'run', side_effect=
                        subprocess.CalledProcessError(1, ['ldid'])):
                with self.assertRaises(subprocess.CalledProcessError):
                    cap.repair(cap.DESKTOP, str(source))
            self.assertEqual(source.read_bytes(), b'original image')
            self.assertEqual(list(Path(folder).iterdir()), [source])


if __name__ == '__main__':
    unittest.main()
