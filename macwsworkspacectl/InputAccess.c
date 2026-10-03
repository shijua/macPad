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
    Boolean (*setForBundleID)(CFStringRef, CFStringRef, Boolean) = framework
        ? (Boolean (*)(CFStringRef, CFStringRef, Boolean))dlsym(
            framework, "TCCAccessSetForBundleId") : NULL;
    if (!service || !*service || !setForPath || !setForBundleID) {
        fprintf(stderr, "input-access: Sonoma TCC management API unavailable\n");
        return 69;
    }
    // Runtime-confirmed: __XPostEventRecord rejected OSXvnc with 1002;
    // tccd reported PostEvent Unknown. The stock TCC setter changed the
    // audit-token preflight to 0 and restored the real Dock context menu.
    // Grant the session's fixed input owners. Keep WindowServer's
    // authorization check intact.
    Boolean accepted = setForPath(
        *service, CFSTR("/usr/local/bin/OSXvnc-server"), true);
    if (!accepted) {
        fprintf(stderr, "input-access: TCC refused the input-owner grant\n");
        return 1;
    }
    // TCCD attributes desktop apps by bundle identity (type 0), not path.
    // Runtime A/B: path grants left Settings/Finder preflight at 2; bundle
    // grants changed both to 0 and restored Settings' hosted control clicks.
    static const char *const desktopOwners[] = {
        "com.apple.systempreferences", "com.apple.finder",
        "com.apple.Safari", "com.apple.Terminal",
    };
    for (unsigned index = 0;
         index < sizeof(desktopOwners) / sizeof(desktopOwners[0]); index++) {
        CFStringRef identifier = CFStringCreateWithCString(
            NULL, desktopOwners[index], kCFStringEncodingUTF8);
        if (!identifier) return 1;
        accepted = setForBundleID(*service, identifier, true);
        CFRelease(identifier);
        if (!accepted) {
            fprintf(stderr, "input-access: TCC refused desktop owner %s\n",
                    desktopOwners[index]);
            return 1;
        }
    }
    CFStringRef *captureService = (CFStringRef *)dlsym(
        framework, "kTCCServiceScreenCapture");
    if (!captureService || !*captureService) {
        fprintf(stderr, "input-access: ScreenCapture management API unavailable\n");
        return 69;
    }
    // The window-mode host receives only this daemon's capture surfaces.
    // Keep WindowServer's cross-process capture authorization intact.
    if (!setForPath(*captureService, CFSTR("/usr/local/bin/macwsdisplayd"), true)) {
        fprintf(stderr, "input-access: TCC refused the display-owner grant\n");
        return 1;
    }
    printf("input-access: PostEvent authorized for fixed session input owners; "
           "ScreenCapture authorized for macwsdisplayd\n");
    return 0;
}
