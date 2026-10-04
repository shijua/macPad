#ifndef MACWS_MACHINE_ARCHITECTURE_H
#define MACWS_MACHINE_ARCHITECTURE_H
#include <sys/sysctl.h>
#include <stdbool.h>
#include <string.h>
#include <errno.h>

// Darwin HW_MACHINE names the CPU architecture. iPadOS returns the device
// model at this MIB; macOS clients need the architecture of this process.
static inline bool MacWSReadMachineArchitecture(const int *mib, unsigned count,
    void *output, size_t *size, const void *input, size_t inputSize, int *result) {
#if defined(__arm64__) || defined(__aarch64__)
    if (!mib || count != 2 || mib[0] != CTL_HW || mib[1] != HW_MACHINE ||
        input || inputSize || !size) return false;
    static const char architecture[] = "arm64";
    if (!output) {
        *size = sizeof(architecture);
    } else if (*size < sizeof(architecture)) {
        // Runtime-confirmed stock Darwin returns ENOMEM and zero copied bytes.
        *size = 0;
        errno = ENOMEM;
        *result = -1;
        return true;
    } else {
        memcpy(output, architecture, sizeof(architecture));
        *size = sizeof(architecture);
    }
    *result = 0;
    return true;
#else
    return false;
#endif
}
#endif
