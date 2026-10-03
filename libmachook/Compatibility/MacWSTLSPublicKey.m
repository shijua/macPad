#import <Foundation/Foundation.h>
#include <dlfcn.h>
#include <ptrauth.h>
#include "MacWSTLSPublicKey.h"

extern void MSHookFunction(void *, void *, void **);
static SecKeyRef (*macws_original_copy_public_key)(SecTrustRef);

static SecKeyRef macws_copy_public_key_for_tls(SecTrustRef trust) {
    void *caller = ptrauth_strip(__builtin_return_address(0),
                                 ptrauth_key_return_address);
    Dl_info image = {0};
    dladdr(caller, &image);
    SecKeyRef original = macws_original_copy_public_key(trust);
    // This changes key extraction only. coreTLS still installs the real RSA
    // or EC key, verifies signatures, and evaluates certificate/hostname trust.
    return macws_tls_public_key_fallback(
        trust, original, image.dli_fname, SecTrustCopyKey);
}

__attribute__((constructor))
static void macws_install_tls_public_key_compatibility(void) {
    void *target = dlsym(RTLD_DEFAULT, "SecTrustCopyPublicKey");
    Dl_info image = {0};
    if (!target || !dladdr(target, &image) || !image.dli_fname ||
        !strstr(image.dli_fname, "/Security.framework/")) return;
    MSHookFunction(target, (void *)macws_copy_public_key_for_tls,
                   (void **)&macws_original_copy_public_key);
}
