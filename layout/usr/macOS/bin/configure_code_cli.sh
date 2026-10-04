# Install a scoped CLI entry without changing the user's shell environment.
set -e
ROOTFS=${1:-/var/mnt/rootfs}
case "$ROOTFS" in
    /*) ;;
    *) echo 'ERROR: macOS rootfs must be an absolute path' >&2; exit 1 ;;
esac
VENDOR_CODE='/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code'
[ -f "$ROOTFS$VENDOR_CODE" ] || exit 0
CODE_ENTRY="$ROOTFS/usr/local/bin/code"
MANAGED_CODE='/usr/local/libexec/macws-code'
if [ -e "$CODE_ENTRY" ] || [ -L "$CODE_ENTRY" ]; then
    CURRENT_CODE=$(readlink "$CODE_ENTRY" 2>/dev/null || true)
    case "$CURRENT_CODE" in
        "$VENDOR_CODE"|"$MANAGED_CODE") ;;
        *) echo '[INFO] Preserving custom code CLI entry'; exit 0 ;;
    esac
fi
SCRIPT_DIRECTORY=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
mkdir -p "$ROOTFS/usr/local/libexec" "$ROOTFS/usr/local/bin"
cp "$SCRIPT_DIRECTORY/macws_code_cli.sh" "$ROOTFS$MANAGED_CODE"
chmod 755 "$ROOTFS$MANAGED_CODE"
ln -s "$MANAGED_CODE" "$CODE_ENTRY.macws-new"
mv -f "$CODE_ENTRY.macws-new" "$CODE_ENTRY"
echo '[INFO] VS Code CLI JIT configuration installed'
