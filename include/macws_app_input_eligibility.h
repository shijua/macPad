#ifndef MACWS_APP_INPUT_ELIGIBILITY_H
#define MACWS_APP_INPUT_ELIGIBILITY_H

#include <stdbool.h>
#include <string.h>

static inline bool MacWSAppInputExecutableHasUILifecycle(const char *path) {
    if (!path) return false;
    if (strstr(path, ".app/Contents/MacOS/")) return true;
    // These verified Settings processes own their popup menu event loops.
    // Other extensions may merely load AppKit without owning an event loop.
    return strcmp(path,
        "/System/Library/ExtensionKit/Extensions/DesktopSettings.appex/"
        "Contents/MacOS/DesktopSettings") == 0 || strcmp(path,
        "/System/Library/ExtensionKit/Extensions/ControlCenterSettings.appex/"
        "Contents/MacOS/ControlCenterSettings") == 0;
}

#endif
