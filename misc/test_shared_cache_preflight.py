import importlib.util
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "layout/usr/macOS/bin/macws_prepare_shared_cache.py"
SPEC = importlib.util.spec_from_file_location("cache_preflight", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SharedCachePreflight(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.directory = self.root / MODULE.CACHE_DIRS[0]
        self.directory.mkdir(parents=True)
        header = bytearray(64)
        header[:16] = b"dyld_v1  arm64e\0"
        struct.pack_into("<QQ", header, 40, 56, 8)
        self.paths = [self.directory / ("dyld_shared_cache_arm64e" + suffix)
                      for suffix in ("", ".01")]
        for path in self.paths:
            path.write_bytes(header)

    def test_valid_pair_and_alias_are_deduplicated(self):
        alias = self.root / MODULE.CACHE_DIRS[1]
        alias.parent.mkdir(parents=True)
        alias.symlink_to(self.directory)
        self.assertEqual(set(MODULE.inspect_caches(self.root)), set(self.paths))

    def test_missing_subcache_prevents_any_repair(self):
        self.paths[1].unlink()
        with patch.object(MODULE.os, "chown") as chown:
            with self.assertRaises(FileNotFoundError):
                MODULE.prepare(self.root, repair=True)
            chown.assert_not_called()

    def test_truncated_signature_is_rejected(self):
        self.paths[0].write_bytes(self.paths[0].read_bytes()[:-1])
        with self.assertRaisesRegex(ValueError, "Truncated"):
            MODULE.inspect_caches(self.root)

    def test_escape_is_rejected(self):
        self.paths[0].unlink()
        self.paths[0].symlink_to("/etc/passwd")
        with self.assertRaisesRegex(ValueError, "escapes"):
            MODULE.inspect_caches(self.root)

    def test_host_root_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "host root"):
            MODULE.inspect_caches("/")

    def test_repair_changes_only_owner(self):
        before = {path: path.read_bytes() for path in self.paths}
        metadata = type("Metadata", (), {"st_uid": 501, "st_size": 64})()
        repaired = type("Metadata", (), {"st_uid": 0})()
        with patch.object(MODULE, "inspect_caches", return_value={p: metadata for p in self.paths}), \
                patch.object(MODULE.os, "geteuid", return_value=0), \
                patch.object(MODULE.os, "chown") as chown, \
                patch.object(Path, "stat", return_value=repaired):
            MODULE.prepare(self.root, repair=True)
            self.assertEqual(chown.call_count, 2)
            for path in self.paths:
                chown.assert_any_call(path, 0, -1)
        self.assertEqual(before, {path: path.read_bytes() for path in self.paths})

    def signed_pair(self, codes):
        offset = 12 + len(codes) * 8
        indexes = bytearray()
        content = bytearray()
        for index, code in enumerate(codes):
            indexes.extend(struct.pack('>II', 0 if index == 0 else 0x1000,
                                       offset + len(content)))
            content.extend(code)
        signature = (struct.pack('>III', 0xfade0cc0,
                                 offset + len(content), len(codes))
                     + indexes + content)
        header = bytearray(56)
        header[:16] = b"dyld_v1  arm64e\0"
        struct.pack_into('<QQ', header, 40, 56, len(signature))
        for path in self.paths:
            path.write_bytes(header + signature)

    @staticmethod
    def code_directory(hash_type=2):
        size = {1: 20, 2: 32}[hash_type]
        return (struct.pack('>9I4BI', 0xfade0c02, 48 + size, 0x20001,
                            0, 48, 44, 0, 1, 4096,
                            size, hash_type, 0, 12, 0)
                + b'app\0' + bytes(size))

    def test_cdhashes_include_alternates_and_deduplicate_aliases(self):
        codes = [self.code_directory(1), self.code_directory(2)]
        self.signed_pair(codes)
        alias = self.root / MODULE.CACHE_DIRS[1]
        alias.parent.mkdir(parents=True)
        alias.symlink_to(self.directory)
        self.assertEqual(MODULE.cache_cdhashes(self.root), sorted([
            hashlib.sha1(codes[0]).hexdigest(),
            hashlib.sha256(codes[1]).hexdigest()[:40]]))

    def test_cdhashes_reject_missing_code_directory(self):
        self.signed_pair([])
        with self.assertRaisesRegex(ValueError, 'no CodeDirectory'):
            MODULE.cache_cdhashes(self.root)

    def test_cdhashes_reject_directory_overlapping_index(self):
        self.signed_pair([self.code_directory()])
        damaged = bytearray(self.paths[1].read_bytes())
        struct.pack_into('>I', damaged, 56 + 16, 12)
        self.paths[1].write_bytes(damaged)
        with self.assertRaisesRegex(ValueError, 'outside signature'):
            MODULE.cache_cdhashes(self.root)


if __name__ == "__main__":
    unittest.main()
