#include <CoreFoundation/CoreFoundation.h>
#include <dlfcn.h>
#include <stdio.h>
#include <unistd.h>

int MacWSPrepareInputAccess(void) {
    if (geteuid() != 0) {
        fprintf(stderr, "input-access: root is required for TCC management\n");
        return 77;
    }
    void *framework = dlopen(
        "/System/Library/PrivateFrameworks/TCC.framework/TCC", RTLD_NOW);
    CFStringRef *service = framework
        ? (CFStringRef *)dlsym(framework, "kTCCServicePostEvent") : NULL;
    Boolean (*setForPath)(CFStringRef, CFStringRef, Boolean) = framework
        ? (Boolean (*)(CFStringRef, CFStringRef, Boolean))dlsym(
            framework, "TCCAccessSetForPath") : NULL;
    if (!service || !*service || !setForPath) {
        fprintf(stderr, "input-access: Sonoma TCC management API unavailable\n");
        return 69;
    }
    // Runtime-confirmed: __XPostEventRecord rejected OSXvnc with 1002;
    // tccd reported PostEvent Unknown. The stock TCC setter changed the
    // audit-token preflight to 0 and restored the real Dock context menu.
    // Grant only the session's fixed input owner, before its CGS connection
    // can cache a denial. Keep WindowServer's authorization check intact.
    Boolean accepted = setForPath(
        *service, CFSTR("/usr/local/bin/OSXvnc-server"), true);
    if (!accepted) {
        fprintf(stderr, "input-access: TCC refused the input-owner grant\n");
        return 1;
    }
    printf("input-access: PostEvent authorized for /usr/local/bin/OSXvnc-server\n");
    return 0;
}
