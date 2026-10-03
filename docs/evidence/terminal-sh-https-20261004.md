# Terminal sh HTTPS environment

Runtime-confirmed on the device: Terminal spawned `login -pf root` and `-sh`
(PIDs 44006 and 44009). A login sh does not read the managed `.bashrc`.
With CURL_SSL_BACKEND unset, curl reported active SecureTransport and:

```
curl: (77) SSL: invalid CA certificate subject
```

The configuration installer now also appends its existing TLS marker to
`/var/root/.profile` and `/Users/root/.profile`. It preserves an explicit
CURL_SSL_BACKEND override and leaves certificate verification enabled.

Actual keyboard records were sent to Terminal PID 44002, window 799. Its
interactive shell sourced the configured profile and ran the three HTTPS checks.
Runtime-confirmed via `/tmp/macws-terminal-https-result.log` inside chroot:

```
MACWS_TERMINAL_TLS
curl 8.1.2 (x86_64-apple-darwin23.0) libcurl/8.1.2 (SecureTransport) LibreSSL/3.3.6 zlib/1.2.12 nghttp2/1.55.1
HTTP/2 200
CURL_EXIT=0
curl: (60) SSL certificate problem: certificate has expired
CURL_EXIT=60
curl: (60) SSL certificate problem: self signed certificate
CURL_EXIT=60
```

The parentheses mark the inactive SecureTransport backend. No `-k` was used.
Existing shells need to source their profile; a future root sh login reads it
normally. A separate SSH-created shell preserved native HOME=/var/jb/var/root
and did not read either chroot home profile; that is not the Terminal login
environment. Automated tests exercise both profiles, repeated installation,
retained user content and an explicit backend override.
