# Sonoma SecureTransport public-key extraction on iPadOS 17

## Evidence

Runtime-confirmed with a bounded SecureTransport client connecting to
`www.apple.com:443`, without sending application or account data:

```text
TLS server_auth_stage=-9808
TLS peer_trust_status=0 certificates=3
TLS trust key legacy=0 modern=1
TLS certificate index=0 bytes=1917 parse=1 key=1 key_bytes=270 key_error=0
```

The same program on the Mac reaches `errSSLServerAuthCompleted` (`-9841`)
and both public-key APIs succeed. Partial socket reads/writes must return
`errSSLWouldBlock`; an earlier probe violated that contract and returned
`-50`. That probe result was discarded.

RE-confirmed via Sonoma 14.0's actual `libcoretls_cfhelpers.dylib`, extracted
from the 23A344 shared cache:

- `tls_helper_set_peer_pubkey+0x48` (`0x18e0c0e38`) calls
  `SecTrustCopyPublicKey`.
- `+0x4c` branches on a null key to `+0x184` (`0x18e0c0f74`), which sets
  `w23=-0x2650`, i.e. `errSSLBadCert=-9808`.
- A real key proceeds through `SecKeyGetAlgorithmId`, RSA modulus/exponent
  or EC curve/public bits, and the actual coreTLS key setter.
- Security's `SecTrustCopyPublicKey` (`0x18340e68c`) calls
  `SecCertificateCopyPublicKey$LEGACYMAC` at `+0x20`. The newer
  `SecTrustCopyKey` successfully extracts the same leaf's real key.

Apple documents [errSSLBadCert](https://developer.apple.com/documentation/security/errsslbadcert)
as a certificate-format error. Its
[SecureTransport certificate callback source](https://github.com/apple-oss-distributions/Security/blob/main/OSX/libsecurity_ssl/lib/tlsCallbacks.c)
calls the public-key helper before server-certificate verification. These
sources provide context; the offsets above come from the actual device image.

## Change

`MacWSTLSPublicKey.m` calls the original API first. Only a null result whose
actual return address belongs to `/usr/lib/libcoretls_cfhelpers.dylib` uses
`SecTrustCopyKey`. Every other caller retains the original result. A failure
to obtain a modern key remains a failure.

This supplies a real RSA or EC public key. Certificate trust, hostname checks,
and handshake signatures still run in the original TLS implementation.

## Verification

After deployment, a fresh client without the temporary test hook produced:

```text
[launchdchrootexec] target=/usr/local/bin/macws-securetransport-live-probe arch=arm64 insert=/usr/local/lib/libmachook_arm64.dylib
TLS server_auth_stage=0
TLS trust key legacy=0 modern=1
[launchdchrootexec] target=/usr/local/bin/macws-securetransport-live-probe-arm64e arch=arm64e insert=/usr/local/lib/libmachook.dylib
TLS server_auth_stage=0
```

With automatic certificate verification enabled, connecting to Apple with an
incorrect peer hostname returned `-9807`. `expired.badssl.com` also returned
`-9807`. No certificate-verification bypass was used. The isolated preliminary
test additionally returned `TLS trust verified=1 error=0` and `TLS completed=0`.

The compiled fallback-policy test covers exact caller scope, existing key
preservation, missing inputs, and propagation of modern key extraction failure.
Both library architectures build successfully.

Previous libraries are retained on the device at
`/var/jb/var/mobile/sonoma-workspace-originals/tls-key-20261004`.

Mail was relaunched as PID 30866 to load the new library. This fixes the
reproduced public-key extraction failure; account synchronization, server
authentication, and all Mail UI behavior require separate runtime verification.
curl forced to SecureTransport still reports a distinct CA-import error (`77`);
the verified OpenSSL-backed curl configuration remains in place.
