"""Validate real native slice extraction, including malformed containers."""
import importlib.util
import pathlib
import struct
import unittest
from unittest import mock
import plistlib
import tempfile
ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('profiler', ROOT / 'layout/usr/macOS/bin/macws_prepare_profiler_plugins.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def thin(subtype):
    return struct.pack('<8I', 0xfeedfacf, 0x0100000c, subtype, 8, 0, 0, 0, 0)

def fat(images):
    offset = 8 + len(images) * 20
    table = b''
    for image in images:
        cpu, subtype = struct.unpack_from('<II', image, 4)
        table += struct.pack('>5I', cpu, subtype, offset, len(image), 0)
        offset += len(image)
    return struct.pack('>II', 0xcafebabe, len(images)) + table + b''.join(images)

class ProfilerArchitectureTests(unittest.TestCase):
    def test_prefers_actual_arm64e_and_preserves_thin(self):
        image = thin(0x80000002)
        self.assertEqual(module.native_thin(fat([thin(0), image])), image)
        self.assertEqual(module.native_thin(image), image)
        self.assertEqual(module.native_thin(fat([thin(0)])), thin(0))

    def test_rejects_truncation_overlap_and_header_mismatch(self):
        good = fat([thin(0), thin(2)])
        malformed = [b'', good[:20], good[:-1], fat([thin(2), thin(2)])]
        overlap = bytearray(good)
        struct.pack_into('>I', overlap, 36, 48)
        malformed.append(bytes(overlap))
        mismatch = bytearray(good)
        struct.pack_into('>I', mismatch, 12, 2)
        malformed.append(bytes(mismatch))
        for data in malformed:
            with self.subTest(length=len(data)):
                with self.assertRaises(ValueError):
                    module.native_thin(data)


    def test_prepares_native_bundle_and_ignores_appledouble_sidecar(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td) / 'root'
            folder = root / 'System/Library/SystemProfiler'
            image = folder / 'SPFixture.spreporter/Contents/MacOS/SPFixture'
            image.parent.mkdir(parents=True)
            (image.parent.parent / 'Info.plist').write_bytes(
                plistlib.dumps({'CFBundleExecutable': 'SPFixture'}))
            original = fat([thin(0), thin(2)])
            image.write_bytes(original)
            (folder / '._SPFixture.spreporter').write_bytes(b'AppleDouble')
            resources = folder / 'SPResources.spreporter/Contents'
            resources.mkdir(parents=True)
            (resources / 'Info.plist').write_bytes(plistlib.dumps({}))
            with mock.patch.object(module.subprocess, 'run') as run:
                module.prepare(root, pathlib.Path(td) / 'backup', pathlib.Path('/tools'))
                self.assertEqual(run.call_count, 3)
                self.assertEqual(run.call_args.args[0][-1], str(image))
            self.assertEqual(image.read_bytes(), thin(2))
            self.assertEqual((pathlib.Path(td) / 'backup/SPFixture.spreporter/SPFixture').read_bytes(), original)
