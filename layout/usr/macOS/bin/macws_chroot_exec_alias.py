"""Make the kernel's outer executable path resolvable inside the chroot."""
import os
from pathlib import Path
import stat
import sys


def ensure_alias(rootfs):
    canonical = Path(rootfs).resolve(strict=True)
    if canonical == Path('/') or not canonical.is_dir():
        raise ValueError('rootfs must be a directory distinct from the host root')
    # Runtime-confirmed: Sandbox looked up the outer executable path again
    # after chroot. Without this alias, Appearance was killed with ENOENT;
    # adding it admitted the real extension image without changing policy.
    parts = canonical.parts[1:]
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory = os.open(canonical, flags)
    try:
        for part in parts[:-1]:
            try:
                os.mkdir(part, 0o755, dir_fd=directory)
            except FileExistsError:
                pass
            child = os.open(part, flags, dir_fd=directory)
            os.close(directory)
            directory = child
        leaf = parts[-1]
        try:
            os.symlink('/', leaf, dir_fd=directory)
        except FileExistsError:
            existing = os.stat(leaf, dir_fd=directory, follow_symlinks=False)
            if not stat.S_ISLNK(existing.st_mode) or \
                    os.readlink(leaf, dir_fd=directory) != '/':
                raise ValueError('executable namespace alias conflicts with an existing path')
    finally:
        os.close(directory)
    return canonical.joinpath(*parts)


if __name__ == '__main__':
    try:
        if len(sys.argv) != 1 or os.geteuid() != 0:
            raise ValueError('invoke as root without arguments')
        alias = ensure_alias('/var/mnt/rootfs')
        print(f'chroot-exec-alias ready: {alias} -> /')
    except (OSError, ValueError) as error:
        print(f'chroot-exec-alias: {error}', file=sys.stderr)
        sys.exit(1)
