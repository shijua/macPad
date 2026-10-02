"""Provision verified 23A344 shader companions on kernel build 21A329."""
import argparse
import hashlib
from pathlib import Path
import plistlib
import subprocess
import sys

from metal2metal_manifest import verify_runtime_manifest

PROFILE = "sonoma14-ios17-macabi"
LIBRARIES = (
    ("quartzcore", "System/Library/Frameworks/QuartzCore.framework/Versions/A/Resources/default.metallib",
     "e9284537b6703522149dee9df5609fc2c9d77e365853fb5e1c0563e66e89a33a",
     "default-desktop-effects-macabi.metallib", "quartzcore-default"),
    ("skylight", "System/Library/PrivateFrameworks/SkyLight.framework/Versions/A/Resources/SkyLightShaders.air64.metallib",
     "bd9ca43875b5e8a8d7ecd08066216a687a4e738c0ab5495659436fc1ee1b501a",
     "SkyLightShaders-desktop-effects-macabi.metallib", "skylight-shaders"),
    ("mpsimage", "System/Library/Frameworks/MetalPerformanceShaders.framework/Versions/A/Frameworks/MPSImage.framework/Versions/A/Resources/default.metallib",
     "af4557ccaea92c3a0b05b73a170b75e4e264b00860a3d7cef0a75695241f78d1",
     "default-desktop-effects-macabi.metallib", "mpsimage-default"),
)


def validate_sources(root, kernel_build):
    with (root / "System/Library/CoreServices/SystemVersion.plist").open("rb") as stream:
        version = plistlib.load(stream)
    if (version.get("ProductVersion"), version.get("ProductBuildVersion"),
            kernel_build) != ("14.0", "23A344", "21A329"):
        raise ValueError("unsupported macOS/kernel build pair")
    # Validate the whole source closure before creating any outputs.
    for _, relative, expected, _, _ in LIBRARIES:
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != expected:
            raise ValueError("unsupported shader source: " + relative)


def provision(root, kernel_build, tools):
    validate_sources(root, kernel_build)
    for family, relative, _, filename, route in LIBRARIES:
        source = root / relative
        output_relative = "usr/local/share/macws/" + family + "/" + filename
        output = root / output_relative
        manifest = root / ("usr/local/share/macws/metal2metal/routes/" + route + ".route.plist")
        try:
            current = verify_runtime_manifest(manifest, source, output)
            if (current["profile"] == PROFILE and
                    current["source"]["runtime_path"] == "/" + relative and
                    current["output"]["runtime_path"] == "/" + output_relative):
                continue
        except (OSError, ValueError, KeyError, plistlib.InvalidFileException):
            pass
        output.parent.mkdir(parents=True, exist_ok=True)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(output.name + ".new")
        temporary_manifest = manifest.with_name(manifest.name + ".new")
        try:
            subprocess.run([
                sys.executable, str(tools / "metal2metal.py"), "translate",
                str(source), str(temporary), "--profile", PROFILE,
                "--llvm-dis", "/var/jb/usr/lib/llvm-16/bin/llvm-dis",
                "--llvm-as", "/var/jb/usr/lib/llvm-16/bin/llvm-as",
                "--auto-lower-known-air", "--runtime-manifest", str(temporary_manifest),
                "--runtime-source-path", "/" + relative,
                "--runtime-output-path", "/" + output_relative,
            ], check=True)
            verify_runtime_manifest(temporary_manifest, source, temporary)
            temporary.chmod(0o644)
            temporary_manifest.chmod(0o644)
            temporary.replace(output)
            temporary_manifest.replace(manifest)
        finally:
            temporary.unlink(missing_ok=True)
            temporary_manifest.unlink(missing_ok=True)
        print("[INFO] installed Sonoma shader companion: " + family, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    kernel_build = subprocess.check_output(
        ["/var/jb/usr/sbin/sysctl", "-n", "kern.osversion"], text=True).strip()
    provision(args.root, kernel_build, Path(__file__).resolve().parent)


if __name__ == "__main__":
    main()
