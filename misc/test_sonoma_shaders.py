import importlib.util
from pathlib import Path
import plistlib
import sys
import tempfile
import unittest
from unittest.mock import patch
import hashlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
MODULE = Path(__file__).resolve().parents[1] / "layout/usr/macOS/bin/ensure_sonoma_shaders.py"
SPEC = importlib.util.spec_from_file_location("sonoma_shaders", MODULE)
SHADERS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SHADERS)


class SonomaShaders(unittest.TestCase):
    def test_provisioner_uses_specialization_validated_profile(self):
        from metal2metal_profiles import SONOMA_IOS17_PROFILE, get_profile
        self.assertEqual(SHADERS.PROFILE, SONOMA_IOS17_PROFILE)
        self.assertEqual(get_profile(SHADERS.PROFILE).target_triple,
                         "air64-apple-ios17.0.0-macabi")

    def test_gui_uses_version_checked_sonoma_provisioner(self):
        script = (MODULE.parent / 'macos_gui.sh').read_text()
        selector = script.split('ensure_rootfs_shaders() {', 1)[1].split('\n}', 1)[0]
        self.assertIn('SystemVersion.plist', selector)
        self.assertIn('[ "$version" = 14.0 ]', selector)
        self.assertIn('/ensure_sonoma_shaders.py', selector)
        self.assertIn('--root "$ROOTFS"', selector)
        self.assertIn('bash "$METAL2METAL_COMPAT_PROVISIONER"', selector)
        preflight = script.split('ensure_chroot_works() {', 1)[1].split('\n}', 1)[0]
        self.assertIn('if ! ensure_rootfs_shaders', preflight)

    def test_version_gate_precedes_shader_work(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            version = root / "System/Library/CoreServices/SystemVersion.plist"
            version.parent.mkdir(parents=True)
            for macos, build, kernel in (("13.4", "22F66", "21A329"),
                                         ("14.0", "23A344", "21A330"),
                                         ("14.0", "23A345", "21A329")):
                version.write_bytes(plistlib.dumps({"ProductVersion": macos,
                                                   "ProductBuildVersion": build}))
                with patch.object(SHADERS.subprocess, "run") as run:
                    with self.assertRaises(ValueError):
                        SHADERS.provision(root, kernel, root)
                    run.assert_not_called()

    def test_entire_source_closure_checked_before_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            version = root / "System/Library/CoreServices/SystemVersion.plist"
            version.parent.mkdir(parents=True)
            version.write_bytes(plistlib.dumps({"ProductVersion": "14.0",
                                               "ProductBuildVersion": "23A344"}))
            (root / "a").write_bytes(b"accepted")
            (root / "b").write_bytes(b"modified")
            expected = hashlib.sha256(b"accepted").hexdigest()
            libraries = (("a", "a", expected, "a", "a"),
                         ("b", "b", expected, "b", "b"))
            with patch.object(SHADERS, "LIBRARIES", libraries), \
                    patch.object(SHADERS.subprocess, "run") as run:
                with self.assertRaisesRegex(ValueError, "unsupported shader source: b"):
                    SHADERS.provision(root, "21A329", root)
                run.assert_not_called()
                self.assertFalse((root / "usr").exists())


if __name__ == "__main__":
    unittest.main()
