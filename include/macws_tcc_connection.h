#ifndef MACWS_TCC_CONNECTION_H
#define MACWS_TCC_CONNECTION_H

#include <stdint.h>
#include <string.h>

static inline uint64_t macws_tcc_connection_flags(const char *name,
                                                  uint64_t flags) {
    // These private listeners live in user/501. XPC's privileged lookup bit
    // selects the system bootstrap domain, where neither listener exists.
    if (name && (!strcmp(name, "com.macwsguide.tccd.system") ||
                 !strcmp(name, "com.macwsguide.tccd")))
        return flags & ~UINT64_C(2);
    return flags;
}

#endif
