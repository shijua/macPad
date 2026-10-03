"""Prepare real SystemProfiler plugin images for the chroot dyld loader."""
from pathlib import Path
import argparse
import os
import plistlib
import shutil
import struct
import subprocess
import tempfile


class UnsupportedNativeImage(ValueError):
    pass


def native_thin(data):
    if len(data) < 32:
        raise ValueError('truncated Mach-O')
    if data[:4] == b'\xcf\xfa\xed\xfe':
        cpu, subtype = struct.unpack_from('<II', data, 4)
        if cpu != 0x0100000c or subtype & 0xffffff not in (0, 2):
            raise UnsupportedNativeImage('not a native ARM64 image')
        return data
    formats = {b'\xca\xfe\xba\xbe': ('>', 20), b'\xbe\xba\xfe\xca': ('<', 20),
               b'\xca\xfe\xba\xbf': ('>', 32), b'\xbf\xba\xfe\xca': ('<', 32)}
    if data[:4] not in formats:
        raise ValueError('unknown Mach-O container')
    endian, width = formats[data[:4]]
    count, = struct.unpack_from(endian + 'I', data, 4)
    end = 8 + count * width
    if not 0 < count <= 32 or end > len(data):
        raise ValueError('invalid architecture table')
    choices = {}
    ranges = []
    for index in range(count):
        fmt = 'IIIII' if width == 20 else 'IIQQII'
        fields = struct.unpack_from(endian + fmt, data, 8 + index * width)
        cpu, subtype, offset, size = fields[:4]
        if offset < end or size < 32 or offset + size > len(data):
            raise ValueError('slice outside file')
        if any(offset < stop and offset + size > start for start, stop in ranges):
            raise ValueError('overlapping architecture slices')
        ranges.append((offset, offset + size))
        arch = subtype & 0xffffff
        if cpu == 0x0100000c and arch in (0, 2):
            if arch in choices:
                raise ValueError('duplicate native architecture')
            image = data[offset:offset + size]
            if image[:4] != b'\xcf\xfa\xed\xfe' or struct.unpack_from('<II', image, 4) != (cpu, subtype):
                raise ValueError('architecture table/header mismatch')
            choices[arch] = image
    if not choices:
        raise UnsupportedNativeImage('no compatible native slice')
    return choices[2] if 2 in choices else choices[0]


def prepare(root, backup, tools):
    directory = root / 'System/Library/SystemProfiler'
    if not directory.is_dir():
        raise RuntimeError('SystemProfiler directory is missing')
    paths = []
    changed = 0
    for bundle in sorted(directory.glob('*.spreporter')):
        if bundle.name.startswith('._'):
            continue
        if bundle.is_symlink() or not bundle.is_dir():
            raise ValueError(f'unsafe report bundle: {bundle}')
        info = plistlib.loads((bundle / 'Contents/Info.plist').read_bytes())
        executable = info.get('CFBundleExecutable')
        if executable is None:
            continue
        if not isinstance(executable, str) or executable in ('', '.', '..') or '/' in executable:
            raise ValueError(f'invalid executable in {bundle.name}')
        path = bundle / 'Contents/MacOS' / executable
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'unsafe/missing plugin image: {path}')
        data = path.read_bytes()
        try:
            thin = native_thin(data)
        except UnsupportedNativeImage:
            continue
        if thin != data:
            saved = backup / bundle.name / executable
            saved.parent.mkdir(parents=True, exist_ok=True)
            if saved.exists():
                if saved.read_bytes() != data:
                    raise ValueError(f'backup conflict: {saved}')
            else:
                shutil.copy2(path, saved)
            fd, staged = tempfile.mkstemp(prefix=path.name + '.macws-', dir=path.parent)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(thin)
                for _ in range(2):
                    subprocess.run([str(tools / 'ldid'), '-S', staged], check=True)
                metadata = path.stat()
                os.chmod(staged, metadata.st_mode & 0o7777)
                os.chown(staged, metadata.st_uid, metadata.st_gid)
                os.replace(staged, path)
                changed += 1
            finally:
                if os.path.exists(staged):
                    os.unlink(staged)
        paths.append(str(path))
    if not paths:
        raise RuntimeError('no report plugins found')
    subprocess.run([str(tools / 'python3'), '/var/jb/usr/macOS/bin/macws_boot_trust.py',
                    *paths], check=True)
    print(f'SystemProfiler plugins ready: {len(paths)}, converted: {changed}, backup: {backup}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('/var/mnt/rootfs'))
    parser.add_argument('--backup', type=Path, default=Path('/var/jb/var/lib/macws/profiler-plugin-originals'))
    args = parser.parse_args()
    prepare(args.root, args.backup, Path('/var/jb/usr/bin'))
