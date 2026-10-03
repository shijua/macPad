# Sonoma's curl includes a second TLS backend. SecureTransport cannot parse
# the peer certificate in this chroot; LibreSSL verifies it with the CA bundle.
export CURL_SSL_BACKEND="${CURL_SSL_BACKEND:-openssl}"
/var/jb/usr/macOS/bin/launchdchrootexec 0 0 /var/mnt/rootfs /bin/bash "$@"
