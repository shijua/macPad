#ifndef MACWS_APP_INPUT_SOCKET_H
#define MACWS_APP_INPUT_SOCKET_H

#include <stddef.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/syscall.h>

#define MACWS_APP_INPUT_FD_KEY "MACWS_APP_INPUT_FD"

// Freestanding: the launch proxy must preserve its one-shot XPC context.
static inline void MacWSInputAppend(char **out, const char *value) {
    while (*value) *(*out)++ = *value++;
}

static inline void MacWSInputAppendNumber(char **out, unsigned value) {
    char digits[10];
    unsigned count = 0;
    do { digits[count++] = '0' + value % 10; value /= 10; } while (value);
    while (count) *(*out)++ = digits[--count];
}

static inline int MacWSPreopenAppInputSocket(unsigned pid, char environment[64],
        long (*call)(long, long, long, long)) {
    if (pid <= 1) return 0;
    struct sockaddr_un address = {0};
    address.sun_family = AF_UNIX;
    address.sun_len = sizeof(address);
    char *out = address.sun_path;
    MacWSInputAppend(&out, "/private/tmp/macws_app_input.");
    MacWSInputAppendNumber(&out, pid);
    MacWSInputAppend(&out, ".sock");
    *out = 0;
    long fd = call(SYS_socket, AF_UNIX, SOCK_DGRAM, 0);
    if (fd < 0) return 0;
    (void)call(SYS_unlink, (long)address.sun_path, 0, 0);
    if (call(SYS_bind, fd, (long)&address, sizeof(address)) < 0) {
        (void)call(SYS_close, fd, 0, 0);
        return 0;
    }
    if (call(SYS_chmod, (long)address.sun_path, 0600, 0) < 0) {
        (void)call(SYS_close, fd, 0, 0);
        (void)call(SYS_unlink, (long)address.sun_path, 0, 0);
        return 0;
    }
    out = environment;
    MacWSInputAppend(&out, MACWS_APP_INPUT_FD_KEY "=");
    MacWSInputAppendNumber(&out, (unsigned)fd);
    *out = 0;
    return 1;
}

#endif
