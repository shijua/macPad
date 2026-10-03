"""Reject malformed or mismatched zsh bundles before signing any bytes."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('zsh_modules', ROOT / 'layout/usr/macOS/bin/macws_prepare_zsh_modules.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture(subtype=0x80000002, filetype=8):
    image = struct.pack('<IIIIIIII', 0xfeedfacf, 0x100000c, subtype, filetype, 0, 0, 0, 0)
    return struct.pack('>IIIIIII', 0xcafebabe, 1, 0x100000c, subtype, 32, len(image), 4) + b'\0'*4 + image


class ZshModuleSlices(unittest.TestCase):
    def test_startup_precedes_original_module_load_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'etc').mkdir()
            for name in ('zshrc', 'zprofile'):
                (root / 'etc' / name).write_text('zmodload zsh/terminfo\n')
                (root / 'etc' / name).chmod(0o444)
            module.configure_startup(root)
            module.configure_startup(root)
            for name in ('zshrc', 'zprofile'):
                path = root / 'etc' / name
                data = path.read_text()
                self.assertEqual(data.count('# MacWS:'), 1)
                self.assertTrue(data.endswith('zmodload zsh/terminfo\n'))
                self.assertLess(data.index('module_path='), data.index('zmodload'))
                self.assertEqual(path.stat().st_mode & 0o777, 0o444)

    def test_keeps_original_header_and_payload(self):
        data = fixture()
        self.assertEqual(module.arm64e_bundle(data), data[32:])

    def test_rejects_other_architecture_wrong_image_and_bad_bounds(self):
        corrupt_header = bytearray(fixture())
        struct.pack_into('<I', corrupt_header, 32 + 8, 0)
        bad_range = bytearray(fixture())
        struct.pack_into('>I', bad_range, 16, 128)
        for data in [b'', fixture(subtype=0), fixture(filetype=2),
                     fixture()[:-1], bytes(corrupt_header), bytes(bad_range)]:
            with self.subTest(size=len(data)):
                with self.assertRaises(ValueError):
                    module.arm64e_bundle(data)


if __name__ == '__main__':
    unittest.main()
