"""Exercise installation and the actual CLI wrapper without starting Electron."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'layout/usr/macOS/bin'
VENDOR = '/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code'


class CodeLauncher(unittest.TestCase):
    def test_install_upgrade_idempotence_and_custom_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vendor = root / VENDOR.lstrip('/')
            vendor.parent.mkdir(parents=True)
            vendor.write_text('vendor script\n')
            entry = root / 'usr/local/bin/code'
            entry.parent.mkdir(parents=True)
            entry.symlink_to(VENDOR)
            command = ['bash', str(SCRIPTS / 'configure_code_cli.sh'), directory]
            for _ in range(2):
                subprocess.run(command, check=True, capture_output=True)
                self.assertEqual(os.readlink(entry), '/usr/local/libexec/macws-code')
                installed = root / 'usr/local/libexec/macws-code'
                self.assertEqual(installed.read_bytes(), (SCRIPTS / 'macws_code_cli.sh').read_bytes())
                self.assertTrue(os.access(installed, os.X_OK))
                self.assertEqual(vendor.read_text(), 'vendor script\n')
            entry.unlink()
            entry.write_text('user custom entry\n')
            subprocess.run(command, check=True, capture_output=True)
            self.assertEqual(entry.read_text(), 'user custom entry\n')

    def test_arguments_and_child_only_jit_environment(self):
        # Substitute only the unavailable local app path in the actual wrapper.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vendor = root / 'vendor'
            vendor.write_text('printf "%s\\n" "$MACWS_JIT_MPROTECT_COMPAT" "$MACWS_JIT_FAULT_WRITE_COMPAT" "$@"\n')
            wrapper = root / 'wrapper'
            wrapper.write_text((SCRIPTS / 'macws_code_cli.sh').read_text().replace(VENDOR, str(vendor)))
            environment = dict(os.environ, MACWS_JIT_MPROTECT_COMPAT='parent', MACWS_JIT_FAULT_WRITE_COMPAT='parent')
            result = subprocess.run(['bash', str(wrapper), '--help', 'a b', '$(literal)'],
                                    env=environment, text=True, capture_output=True, check=True)
            self.assertEqual(result.stdout.splitlines(), ['1', '1', '--help', 'a b', '$(literal)'])
            self.assertEqual(environment['MACWS_JIT_MPROTECT_COMPAT'], 'parent')


if __name__ == '__main__':
    unittest.main()
