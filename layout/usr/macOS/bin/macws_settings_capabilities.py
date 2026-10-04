"""Maintain the observed Dock RPC capability for its exact Settings pane."""
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

DESKTOP = 'com.apple.Desktop-Settings.extension'
LOOKUP = 'com.apple.security.exception.mach-lookup.global-name'
DOCK = 'com.apple.dock.server'
LDID = '/var/jb/usr/bin/ldid'
JBCTL = '/var/jb/usr/bin/jbctl'


def entitlements(executable):
    raw = subprocess.run([LDID, '-arch', 'arm64e', '-e', executable],
                         capture_output=True, check=True, timeout=15).stdout
    # ldid can print more than one slice; select one complete XML document.
    start, end = raw.find(b'<?xml'), raw.find(b'</plist>')
    if start < 0 or end < start:
        raise ValueError('missing Settings entitlement document: ' + executable)
    value = plistlib.loads(raw[start:end + len(b'</plist>')])
    if not isinstance(value, dict):
        raise ValueError('invalid Settings entitlement dictionary: ' + executable)
    return value


def required(identifier, value):
    if identifier != DESKTOP:
        return True
    names = value.get(LOOKUP, [])
    if isinstance(names, str):
        names = [names]
    if not isinstance(names, list) or any(not isinstance(name, str) for name in names):
        raise ValueError('invalid Settings Mach lookup capability list')
    return DOCK in names


def verify(identifier, executable):
    if identifier == DESKTOP and not required(identifier, entitlements(executable)):
        raise ValueError('Dock Settings cannot query ' + DOCK)


def repair(identifier, executable):
    if identifier != DESKTOP:
        return False
    value = entitlements(executable)
    if required(identifier, value):
        return False
    names = value.get(LOOKUP, [])
    value[LOOKUP] = ([names] if isinstance(names, str) else list(names)) + [DOCK]
    source = Path(executable)
    temporary = source.with_name(source.name + '.new-capability-' + str(os.getpid()))
    document = temporary.with_suffix(temporary.suffix + '.plist')
    try:
        # Sign a fresh inode; mapped executable pages remain on the old inode.
        shutil.copy2(source, temporary)
        document.write_bytes(plistlib.dumps(value))
        for _ in range(2):
            subprocess.run([LDID, '-I' + identifier, '-S' + str(document),
                            str(temporary)], check=True, timeout=15)
        verify(identifier, str(temporary))
        trusted = False
        for arch in ('arm64e', 'arm64'):
            output = subprocess.run([LDID, '-arch', arch, '-h', str(temporary)],
                                    capture_output=True, text=True, timeout=15)
            hashes = [line[7:] for line in output.stdout.splitlines()
                      if line.startswith('CDHash=')]
            for digest in hashes:
                if len(digest) != 40 or any(c not in '0123456789abcdefABCDEF' for c in digest):
                    raise ValueError('invalid Settings CodeDirectory hash')
                subprocess.run([JBCTL, 'trustcache', 'add', digest],
                               check=True, timeout=15)
                trusted = True
        if not trusted:
            raise ValueError('no signed Settings arm64 slice')
        os.replace(temporary, source)
    finally:
        temporary.unlink(missing_ok=True)
        document.unlink(missing_ok=True)
    return True


if __name__ == '__main__':
    try:
        if len(sys.argv) != 4 or sys.argv[1] not in ('--verify', '--repair'):
            raise ValueError('usage: --verify|--repair identifier executable')
        action, identifier, executable = sys.argv[1:]
        if action == '--repair':
            if repair(identifier, executable):
                print('Settings Dock RPC capability repaired')
        else:
            verify(identifier, executable)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print('Settings capability error: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
