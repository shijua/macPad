"""Exercise namespace conflicts using real directory descriptors."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'exec_alias', ROOT / 'layout/usr/macOS/bin/macws_chroot_exec_alias.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExecAliasTests(unittest.TestCase):
    def test_create_and_reconcile_exact_alias(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            alias = MODULE.ensure_alias(root)
            self.assertEqual(alias, root.joinpath(*root.parts[1:]))
            self.assertEqual(os.readlink(alias), '/')
            inode = alias.lstat().st_ino
            self.assertEqual(MODULE.ensure_alias(root).lstat().st_ino, inode)

    def test_existing_directory_and_different_link_are_preserved(self):
        for kind in ('directory', 'link'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                alias = root.joinpath(*root.parts[1:])
                alias.parent.mkdir(parents=True)
                if kind == 'directory':
                    alias.mkdir()
                    (alias / 'user-data').write_text('preserve')
                else:
                    alias.symlink_to('/tmp')
                with self.assertRaises(ValueError):
                    MODULE.ensure_alias(root)
                if kind == 'directory':
                    self.assertEqual((alias / 'user-data').read_text(), 'preserve')
                else:
                    self.assertEqual(os.readlink(alias), '/tmp')

    def test_parent_symlink_cannot_redirect_creation_outside_rootfs(self):
        with tempfile.TemporaryDirectory() as temporary, \
                tempfile.TemporaryDirectory() as outside:
            root = Path(temporary).resolve()
            (root / root.parts[1]).symlink_to(outside, target_is_directory=True)
            with self.assertRaises(OSError):
                MODULE.ensure_alias(root)
            self.assertEqual(list(Path(outside).iterdir()), [])

    def test_host_root_is_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.ensure_alias('/')


if __name__ == '__main__':
    unittest.main()
