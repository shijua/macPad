"""Validate the arm64e cache pair and repair ownership before first exec.

This does not patch dyld, alter signatures, or prove that mapping will succeed.
XNU xnu-10002.1.13 bsd/vm/vm_unix.c checks va_uid == 0 before mapping.
"""

import argparse
import importlib.util
import os
from pathlib import Path
import stat
import struct
import sys


CACHE_DIRS = (
    "System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld",
    "System/Library/dyld",
)


def inspect_caches(root):
    root = Path(root).resolve(strict=True)
    if root == Path("/"):
        raise ValueError("Refusing to operate on the host root")
    caches = {}
    for relative in CACHE_DIRS:
        directory = root / relative
        if not directory.exists() and not directory.is_symlink():
            continue
        for suffix in ("", ".01"):
            path = (directory / ("dyld_shared_cache_arm64e" + suffix)).resolve(strict=True)
            if root not in path.parents:
                raise ValueError(f"Cache escapes rootfs: {path}")
            metadata = path.stat()
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError(f"Cache is not a regular file: {path}")
            with path.open("rb") as stream:
                header = stream.read(56)
            if len(header) != 56 or header[:16] != b"dyld_v1  arm64e\0":
                raise ValueError(f"Invalid arm64e cache header: {path}")
            signature_offset, signature_size = struct.unpack_from("<QQ", header, 40)
            if (signature_offset < 56 or not signature_size
                    or signature_offset + signature_size > metadata.st_size):
                raise ValueError(f"Truncated or unsigned cache: {path}")
            caches[path] = metadata
    if not caches:
        raise ValueError("No arm64e cache pair found in rootfs")
    return caches


def cache_cdhashes(root):
    spec = importlib.util.spec_from_file_location(
        "macws_cache_signature_reader",
        Path(__file__).with_name("macws_boot_trust.py"))
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    hashes = set()
    for path, metadata in inspect_caches(root).items():
        with path.open("rb") as stream:
            header = reader.read_at(stream, 0, 56, 0, metadata.st_size)
            offset, available = struct.unpack_from("<QQ", header, 40)
            magic, length, count = struct.unpack(
                ">III", reader.read_at(stream, offset, 12, offset, offset + available))
            if (magic != 0xfade0cc0 or length > available or count > 64
                    or length < 12 + count * 8):
                raise ValueError(f"Invalid cache signature SuperBlob: {path}")
            found = False
            for index in range(count):
                slot, relative = struct.unpack(
                    ">II", reader.read_at(stream, offset + 12 + index * 8,
                                         8, offset, offset + length))
                if slot != 0 and not 0x1000 <= slot < 0x1005:
                    continue
                if not 12 + count * 8 <= relative < length:
                    raise ValueError(f"Cache CodeDirectory outside signature: {path}")
                _, _, digest = reader.directory_hash(
                    stream, offset + relative, length - relative)
                hashes.add(digest)
                found = True
            if not found:
                raise ValueError(f"Cache signature contains no CodeDirectory: {path}")
    return sorted(hashes)


def prepare(root, repair=False):
    # Validate the complete pair in each existing location before any mutation.
    caches = inspect_caches(root)
    invalid = [path for path, metadata in caches.items() if metadata.st_uid != 0]
    for path, metadata in caches.items():
        print(f"cache={path} uid={metadata.st_uid} size={metadata.st_size}")
    if invalid and not repair:
        raise ValueError("Shared caches must be root-owned; run with --repair as root")
    if invalid and os.geteuid() != 0:
        raise PermissionError("--repair requires root")
    for path in invalid:
        # Preserve group, modes, file contents and embedded CodeDirectories.
        os.chown(path, 0, -1)
        if path.stat().st_uid != 0:
            raise ValueError(f"Ownership repair failed: {path}")
        print(f"Repaired cache owner: {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="/var/mnt/rootfs")
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--cdhashes", action="store_true",
                        help="Print existing cache CDHashes without modifying files")
    args = parser.parse_args()
    try:
        if args.cdhashes:
            if args.repair:
                raise ValueError("--cdhashes cannot be combined with --repair")
            print("\n".join(cache_cdhashes(args.root)))
        else:
            prepare(args.root, args.repair)
    except (OSError, ValueError) as error:
        print(f"MacWS shared cache preflight: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
