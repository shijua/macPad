#pragma once
#include <Security/SecTrust.h>
#include <string.h>

// Sonoma's coreTLS helper accepts modern SecKey objects, but obtains them
// through the legacy CDSA-backed API that cannot create a key in the chroot.
static inline SecKeyRef macws_tls_public_key_fallback(
    SecTrustRef trust, SecKeyRef legacyKey, const char *callerImage,
    SecKeyRef (*copyModernKey)(SecTrustRef)) {
    if (legacyKey || !trust || !copyModernKey || !callerImage ||
        strcmp(callerImage, "/usr/lib/libcoretls_cfhelpers.dylib") != 0)
        return legacyKey;
    return copyModernKey(trust);
}
