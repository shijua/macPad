"""Exercise the locked port on an optional original Microsoft framework.

MACWS_VSCODE140_FRAMEWORK=/path/to/original python3 misc/test_vscode140_va.py
"""
import hashlib
import os
from pathlib import Path
import struct
import tempfile
import unittest

import patch_vscode140_pa_ios_va as profile


class VSCode140Geometry(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('MACWS_VSCODE140_FRAMEWORK'),
                         'supply original framework for binary validation')
    def test_complete_port_and_reject_other_uuid_without_output(self):
        original = Path(os.environ['MACWS_VSCODE140_FRAMEWORK'])
        before = hashlib.sha256(original.read_bytes()).digest()
        profile.configure_engine()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'ported'
            result = profile.engine.patch(original, output)
            self.assertEqual(result['uuid'], profile.EXPECTED_UUID)
            self.assertEqual(result['total_instructions_changed'], 37572)
            data = output.read_bytes()
            self.assertEqual(struct.unpack_from('<I', data, 0x10B8014)[0],
                             0xD2C00081)  # MOV X1,#16 GiB
            self.assertEqual(struct.unpack_from('<Q', data, 0xB68E9C0)[0],
                             8 * 1024**3 - 1)
            # Unrelated packed constants must remain verbatim.
            old = original.read_bytes()
            self.assertEqual(data[0x3F627BC:0x3F627D4],
                             old[0x3F627BC:0x3F627D4])
            with self.assertRaisesRegex(ValueError, 'unsupported Electron Framework UUID'):
                changed = bytearray(old)
                cursor = 32
                for _ in range(struct.unpack_from('<I', changed, 16)[0]):
                    command, size = struct.unpack_from('<II', changed, cursor)
                    if command == 0x1B:
                        changed[cursor + 8] ^= 1
                        break
                    cursor += size
                wrong = Path(temporary) / 'wrong-version'
                wrong.write_bytes(changed)
                profile.engine.patch(wrong, Path(temporary) / 'must-not-exist')
            self.assertFalse((Path(temporary) / 'must-not-exist').exists())
        self.assertEqual(hashlib.sha256(original.read_bytes()).digest(), before)


if __name__ == '__main__':
    unittest.main()
