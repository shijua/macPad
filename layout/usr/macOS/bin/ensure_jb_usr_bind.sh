# The XPC activation bundles are installed under /var/jb/usr. A chrooted
# client must be able to read their Info.plist at the same absolute path that
# iOS launchd will later use to start the proxy. Keep the existing
# /var/mnt/rootfs/var/jb/var tree visible: it contains user data and makes the
# old "mount /var/jb only if the directory is empty" guard silently skip this
# prerequisite.
set -eu

source_dir=/var/jb/usr
target_dir=/var/mnt/rootfs/var/jb/usr
parent_dir=/var/mnt/rootfs/var/jb
mount_tool=/var/jb/usr/local/bin/mount_bindfs
jbctl_bindfs=/var/jb/usr/libexec/mount_bindfs/jbctl-bindfs
system_mount=/sbin/mount
proxy_relative=macOS/Frameworks/Dock.framework/Versions/A/XPCServices/DockHelperProxy.xpc/DockHelperProxy

[ -d "$source_dir" ] && [ -x "$source_dir/$proxy_relative" ] || {
    echo "MacWS: required Dock XPC proxy is absent from $source_dir" >&2
    exit 1
}
[ -d "$parent_dir" ] || mkdir -p "$parent_dir"
[ -d "$target_dir" ] || mkdir -p "$target_dir"
canonical_target=$(realpath "$target_dir")
canonical_parent=$(realpath "$parent_dir")
[ -x "$system_mount" ] || {
    echo "MacWS: system mount utility is unavailable: $system_mount" >&2
    exit 1
}

if "$system_mount" | grep -Fq "/var/jb/usr on $canonical_target ("; then
    if [ -x "$target_dir/$proxy_relative" ]; then
        exit 0
    fi
    # bindfs can retain the previous inode after dpkg replaces a proxy.
    # Refresh only this exact mount; the source file remains untouched.
    /sbin/umount "$canonical_target" || {
        echo "MacWS: could not refresh stale /var/jb/usr bind" >&2
        exit 1
    }
elif "$system_mount" | grep -Fq "/var/jb on $canonical_parent ("; then
    [ -x "$target_dir/$proxy_relative" ] || {
        echo "MacWS: existing /var/jb bind does not expose the XPC proxy" >&2
        exit 1
    }
    exit 0
fi

if [ -n "$(ls -A "$target_dir")" ]; then
    echo "MacWS: refusing to cover nonempty $target_dir with a bind mount" >&2
    exit 1
fi
if [ -x "$mount_tool" ]; then
    "$mount_tool" "$source_dir" "$target_dir" || exit 1
elif [ -x "$jbctl_bindfs" ]; then
    "$jbctl_bindfs" -m "$source_dir" "$target_dir" || exit 1
else
    echo "MacWS: no compatible bindfs mount tool is available" >&2
    exit 1
fi
[ -x "$target_dir/$proxy_relative" ] || {
    echo "MacWS: XPC proxy is not visible after mounting $target_dir" >&2
    exit 1
}
