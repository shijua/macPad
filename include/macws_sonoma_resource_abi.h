#ifndef MACWS_SONOMA_RESOURCE_ABI_H
#define MACWS_SONOMA_RESOURCE_ABI_H

#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>

static const uint8_t MacWSSonomaIOGPUUUID[16] = {
    0xf7, 0x15, 0xe9, 0xb3, 0x5d, 0xfb, 0x39, 0x95,
    0xba, 0x08, 0x54, 0x83, 0x36, 0xe8, 0xf1, 0x40
};

/* Native iPadOS17 and this Sonoma producer send the same resource wire ABI.
 * Runtime witnesses: lldb-buffer-native-signed / lldb-raw-resource-trial-fixed.
 * Other versions still need their existing translation. */
static inline bool MacWSSonomaResourceABIReady(const uint8_t *uuid,
        const char *kernel_build, uint32_t selector, size_t request_size) {
    return uuid && kernel_build && selector == 9 && request_size == 104 &&
        strcmp(kernel_build, "21A329") == 0 &&
        memcmp(uuid, MacWSSonomaIOGPUUUID, 16) == 0;
}

#endif
