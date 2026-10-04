# Configure only MacWS's managed tail block in the chroot user's interactive
# shell file. Keep this in one helper because both the Debian maintainer script
# and the manually-invoked deep postinst path must establish the same CLI
# environment.
set -e

ROOTFS=${1:-/var/mnt/rootfs}
case "$ROOTFS" in
	/*) ;;
	*) echo "ERROR: macOS rootfs must be an absolute path: $ROOTFS" >&2; exit 1 ;;
esac

TERMINAL_USER_BASHRC="$ROOTFS/Users/root/.bashrc"
TERMINAL_CLI_ENV_MARKER='# MacWS: managed CLI environment v2'
mkdir -p "${TERMINAL_USER_BASHRC%/*}"
if ! grep -Fq "$TERMINAL_CLI_ENV_MARKER" "$TERMINAL_USER_BASHRC" 2>/dev/null; then
	{
		printf '\n%s\n' "$TERMINAL_CLI_ENV_MARKER"
		printf 'export PATH=/opt/local/bin:/opt/local/sbin:/usr/local/bin:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/bin:/bin:/usr/sbin:/sbin\n'
		# The upstream 341 KiB Bash implementation starts many short-lived
		# processes. Native macws-neofetch gathers the same default core fields
		# in one process; the original remains available by absolute path.
		printf "alias neofetch='command /usr/local/bin/macws-neofetch'\n"
	} >> "$TERMINAL_USER_BASHRC"
fi
TERMINAL_TLS_MARKER='# MacWS: verified curl TLS backend v1'
if ! grep -Fq "$TERMINAL_TLS_MARKER" "$TERMINAL_USER_BASHRC" 2>/dev/null; then
	{
		printf '\n%s\n' "$TERMINAL_TLS_MARKER"
		printf 'export CURL_SSL_BACKEND="${CURL_SSL_BACKEND:-openssl}"\n'
	} >> "$TERMINAL_USER_BASHRC"
fi
# Sonoma's root account launches /bin/sh and login sets its home to /var/root.
# A sh login reads .profile, not .bashrc. Cover the launcher home as well so
# direct chroot login shells inherit the same verified backend.
for TERMINAL_LOGIN_PROFILE in "$ROOTFS/var/root/.profile" "$ROOTFS/Users/root/.profile"; do
	mkdir -p "${TERMINAL_LOGIN_PROFILE%/*}"
	if ! grep -Fq "$TERMINAL_TLS_MARKER" "$TERMINAL_LOGIN_PROFILE" 2>/dev/null; then
		{
			printf '\n%s\n' "$TERMINAL_TLS_MARKER"
			printf 'export CURL_SSL_BACKEND="${CURL_SSL_BACKEND:-openssl}"\n'
		} >> "$TERMINAL_LOGIN_PROFILE"
	fi
done
if [ -d "$ROOTFS/usr/lib/zsh/5.9" ]; then
	/var/jb/usr/bin/python3 /var/jb/usr/macOS/bin/macws_prepare_zsh_modules.py "$ROOTFS"
fi
bash "$(dirname -- "$0")/configure_code_cli.sh" "$ROOTFS"
echo '[INFO] Terminal CLI and verified curl TLS profiles are installed'
