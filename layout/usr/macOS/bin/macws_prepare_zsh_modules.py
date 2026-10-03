"""Prepare the original Sonoma zsh bundle slices without changing originals."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile


def arm64e_bundle(data):
    if len(data) < 8 or data[:4] != b'\xca\xfe\xba\xbe':
        raise ValueError('expected a universal Mach-O module')
    count = struct.unpack_from('>I', data, 4)[0]
    if not 1 <= count <= 32 or len(data) < 8 + count * 20:
        raise ValueError('invalid architecture table')
    for index in range(count):
        cpu, subtype, offset, size, _ = struct.unpack_from('>IIIII', data, 8 + index * 20)
        if cpu != 0x100000c or subtype & 0xffffff != 2:
            continue
        if offset < 8 + count * 20 or size < 32 or offset + size > len(data):
            raise ValueError('invalid arm64e range')
        image = data[offset:offset + size]
        magic, actual_cpu, actual_subtype, filetype = struct.unpack_from('<IIII', image)
        if (magic, actual_cpu, actual_subtype, filetype) != (0xfeedfacf, cpu, subtype, 8):
            raise ValueError('expected the matching arm64e MH_BUNDLE')
        return image
    raise ValueError('module has no arm64e slice')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def configure_startup(rootfs):
    marker = '# MacWS: verified zsh modules and TLS v1'
    block = (marker + '\nexport CURL_SSL_BACKEND="${CURL_SSL_BACKEND:-openssl}"\n'
             'typeset -U module_path\n'
             'module_path=(/usr/local/lib/macws-zsh/5.9 $module_path)\n')
    # The stock shell can decline zshenv after its code-status check. Its
    # normal login/interactive files still run; configure before their first
    # zmodload, keeping the shell's own startup checks unchanged.
    for name in ('zprofile', 'zshrc'):
        path = rootfs / 'etc' / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('expected the real Sonoma ' + name)
        existing = path.read_text()
        if marker in existing:
            continue
        mode = path.stat().st_mode & 0o777
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as output:
            output.write(block + '\n' + existing)
            temporary = Path(output.name)
        temporary.chmod(mode)
        temporary.replace(path)


def prepare(rootfs):
    source = rootfs / 'usr/lib/zsh/5.9'
    destination = rootfs / 'usr/local/lib/macws-zsh/5.9'
    # AppleDouble metadata from the rootfs archive is not executable code.
    modules = sorted(path for path in source.rglob('*.so')
                     if not path.name.startswith('._'))
    if not modules:
        raise ValueError('Sonoma zsh modules are absent')
    if source.is_symlink() or destination.is_symlink():
        raise ValueError('module roots must be real directories')
    destination.mkdir(parents=True, exist_ok=True)
    manifest = destination / 'manifest.json'
    previous = json.loads(manifest.read_text()) if manifest.is_file() else {}
    records = {}
    for original in modules:
        if original.is_symlink():
            raise ValueError('source module must not be a symlink')
        relative = original.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink() or target.parent.is_symlink():
            raise ValueError('prepared module must not follow a symlink')
        raw = original.read_bytes()
        source_hash = digest(raw)
        cached = previous.get(str(relative), {})
        if (not target.is_file() or cached.get('source') != source_hash or
                cached.get('prepared') != digest(target.read_bytes())):
            image = arm64e_bundle(raw)
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as output:
                temporary = Path(output.name)
                output.write(image)
            try:
                temporary.chmod(0o755)
                for _ in range(2):
                    subprocess.run(['/var/jb/usr/bin/ldid', '-S', str(temporary)], check=True)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
        result = subprocess.run(['/var/jb/usr/bin/ldid', '-h', str(target)],
                                check=True, capture_output=True, text=True)
        hashes = re.findall(r'^CDHash=([0-9a-fA-F]{40})$', result.stdout + result.stderr, re.M)
        if len(hashes) != 1:
            raise ValueError('expected one prepared module CDHash')
        subprocess.run(['/var/jb/usr/bin/jbctl', 'trustcache', 'add', hashes[0]], check=True)
        records[str(relative)] = {'source': source_hash, 'prepared': digest(target.read_bytes())}
    with tempfile.NamedTemporaryFile(mode='w', dir=destination, delete=False) as output:
        json.dump(records, output, sort_keys=True)
        temporary = Path(output.name)
    temporary.replace(manifest)
    configure_startup(rootfs)
    print('zsh-modules: prepared and trusted', len(records), 'original arm64e modules')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('rootfs', type=Path)
    args = parser.parse_args()
    if not args.rootfs.is_absolute() or args.rootfs.is_symlink():
        parser.error('rootfs must be an absolute real directory')
    prepare(args.rootfs)
