# Read-only inventory for evaluating macPad on a RootHide Bootstrap device.
# Run with: bash misc/roothide_preflight.sh
# Keep this file without a shebang: some target devices reject script execve.

set -u

printf 'macPad RootHide preflight (read-only)\n'
printf 'uid: %s\n' "$(id -u)"
printf 'machine: %s\n' "$(uname -m)"
printf 'kernel release: %s\n' "$(uname -r)"
if command -v sudo >/dev/null 2>&1; then
    if [ "$(sudo -n id -u 2>/dev/null)" = 0 ]; then
        printf 'noninteractive root: available\n'
    else
        printf 'noninteractive root: unavailable\n'
    fi
fi
if command -v jbroot >/dev/null 2>&1; then
    printf 'mapped /usr/macOS: %s\n' "$(jbroot /usr/macOS)"
fi

printf '\nCommands in this shell:\n'
for name in jbroot rootfs dpkg ldid jbctl launchctl mount_bindfs; do
    if location=$(command -v "$name" 2>/dev/null); then
        printf '  %-14s %s\n' "$name" "$location"
    else
        printf '  %-14s absent\n' "$name"
    fi
done

printf '\nPaths visible in this shell:\n'
for path in \
    /var/jb \
    /var/jb/usr/macOS \
    /var/mnt/rootfs \
    /rootfs/var/mnt/rootfs \
    /rootfs/var/jb \
    /usr/macOS \
    /Library/LaunchDaemons; do
    if [ -L "$path" ]; then
        printf '  %-30s symlink -> %s\n' "$path" "$(readlink "$path")"
    elif [ -d "$path" ]; then
        printf '  %-30s directory\n' "$path"
    elif [ -e "$path" ]; then
        printf '  %-30s other file\n' "$path"
    else
        printf '  %-30s absent\n' "$path"
    fi
done

printf '\nDevice storage (df free space; may differ from Settings):\n'
df -h /var/mobile

printf '\nCurrent install prerequisites:\n'
if command -v jbctl >/dev/null 2>&1; then
    printf '  jbctl trustcache backend: command present; capability unverified\n'
else
    printf '  jbctl trustcache backend: absent; current postinst exits before install\n'
fi
if command -v mount_bindfs >/dev/null 2>&1; then
    printf '  mount_bindfs: command present; capability unverified\n'
else
    printf '  mount_bindfs: absent; current rootfs mount instructions cannot run\n'
fi

printf '\nThis inventory makes no changes. It does not establish GUI or GPU compatibility.\n'
