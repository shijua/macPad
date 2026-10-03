"""Compile the real fallback policy and check its failure/caller boundaries."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TLSPublicKeyCompatibility(unittest.TestCase):
    def test_fallback_is_limited_to_tls_and_preserves_failure(self):
        fixture = r'''
#include "MacWSTLSPublicKey.h"
#include <assert.h>
static unsigned calls;
static SecKeyRef result;
static SecKeyRef copyKey(SecTrustRef trust) {
    assert(trust == (SecTrustRef)0x11); calls++; return result;
}
int main(void) {
    SecTrustRef trust = (SecTrustRef)0x11;
    SecKeyRef original = (SecKeyRef)0x22;
    const char *tls = "/usr/lib/libcoretls_cfhelpers.dylib";
    result = (SecKeyRef)0x33;
    assert(macws_tls_public_key_fallback(trust, original, tls, copyKey) == original);
    assert(calls == 0);
    const char *others[] = {NULL, "/usr/lib/other.dylib",
        "/usr/lib/libcoretls_cfhelpers.dylib.extra",
        "/Applications/Other/libcoretls_cfhelpers.dylib"};
    for (unsigned i = 0; i < sizeof(others)/sizeof(*others); i++)
        assert(macws_tls_public_key_fallback(trust, NULL, others[i], copyKey) == NULL);
    assert(macws_tls_public_key_fallback(NULL, NULL, tls, copyKey) == NULL);
    assert(macws_tls_public_key_fallback(trust, NULL, tls, NULL) == NULL);
    assert(calls == 0);
    assert(macws_tls_public_key_fallback(trust, NULL, tls, copyKey) == result);
    assert(calls == 1);
    result = NULL;
    assert(macws_tls_public_key_fallback(trust, NULL, tls, copyKey) == NULL);
    assert(calls == 2);
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "test.c"
            binary = Path(directory) / "test"
            source.write_text(fixture)
            subprocess.run(["xcrun", "clang", "-Wall", "-Werror",
                            "-I", str(ROOT / "libmachook/Compatibility"),
                            str(source), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True, timeout=5)


if __name__ == "__main__":
    unittest.main()
