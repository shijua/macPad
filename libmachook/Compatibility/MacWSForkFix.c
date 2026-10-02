/*
Adapted from Dopamine 3.0.10 forkfix and jbclient_mach (commit 1a54e76).
MIT License

Copyright (c) 2023-2024 Lars Fröder (opa334)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

*/
#include <errno.h>
#include <mach/mach.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

extern pid_t __fork(void);
extern pid_t macws_forkfix_raw_fork(void);
extern ssize_t macws_forkfix_raw_read(int, void *, size_t);
extern ssize_t macws_forkfix_raw_write(int, const void *, size_t);
extern int macws_forkfix_raw_close(int);
extern void macws_forkfix_raw_exit(int) __attribute__((noreturn));

#define MACWS_FORKFIX_MAGIC UINT64_C(0x444f50414d494e45)
#define MACWS_FORKFIX_ACTION UINT64_C(1)
struct MacWSForkMessage {
    mach_msg_header_t header;
    uint64_t magic;
    uint64_t action;
};
struct MacWSForkRequest {
    struct MacWSForkMessage message;
    pid_t child;
};
struct MacWSForkReply {
    struct MacWSForkMessage message;
    uint64_t status;
};

// The outer Dopamine launchd checks the audit-token parent against child.pptr
// and copies actual parent VM protections/user-debug flags. Run this before
// libSystem_atfork_child touches the parent's modified shared-cache pages.
static int MacWSRestoreForkPermissions(pid_t child) {
    mach_port_t server = MACH_PORT_NULL;
    kern_return_t result = task_get_bootstrap_port(mach_task_self(), &server);
    if (result != KERN_SUCCESS || !MACH_PORT_VALID(server)) return EIO;
    mach_port_t replyPort = mig_get_reply_port();
    if (!MACH_PORT_VALID(replyPort)) {
        mach_port_deallocate(mach_task_self(), server);
        return EIO;
    }
    struct MacWSForkRequest request = {0};
    request.message.header.msgh_bits = MACH_MSGH_BITS(
        MACH_MSG_TYPE_COPY_SEND, MACH_MSG_TYPE_MAKE_SEND_ONCE);
    request.message.header.msgh_size = sizeof(request);
    request.message.header.msgh_remote_port = server;
    request.message.header.msgh_local_port = replyPort;
    request.message.header.msgh_id = 0x400000ce;
    request.message.magic = MACWS_FORKFIX_MAGIC;
    request.message.action = MACWS_FORKFIX_ACTION;
    request.child = child;
    struct {
        struct MacWSForkReply reply;
        mach_msg_max_trailer_t trailer;
    } received = {0};
    result = mach_msg(&request.message.header,
                      MACH_SEND_MSG | MACH_SEND_TIMEOUT, sizeof(request),
                      0, MACH_PORT_NULL, 5000, MACH_PORT_NULL);
    if (result == KERN_SUCCESS) {
        result = mach_msg(&received.reply.message.header,
                          MACH_RCV_MSG | MACH_RCV_TIMEOUT, 0,
                          sizeof(received), replyPort, 5000, MACH_PORT_NULL);
    }
    int error = EIO;
    if (result == KERN_SUCCESS) {
        if (received.reply.message.header.msgh_size < sizeof(received.reply) ||
            received.reply.message.magic != MACWS_FORKFIX_MAGIC ||
            received.reply.message.action != MACWS_FORKFIX_ACTION) {
            error = EPROTO;
        } else {
            error = received.reply.status == 0 ? 0 : EPERM;
        }
        mach_msg_destroy(&received.reply.message.header);
    } else {
        // A timed-out MIG reply right must not leak a late reply into the next RPC.
        mig_dealloc_reply_port(replyPort);
    }
    mach_port_deallocate(mach_task_self(), server);
    if (error) dprintf(STDERR_FILENO,
        "MACWS FORK permission restore failed child=%d mach=%#x error=%d\n",
        child, result, error);
    return error;
}

static void MacWSCloseForkPipes(const int toParent[2], const int toChild[2]) {
    // Only direct syscalls are safe in the child before permission restoration.
    macws_forkfix_raw_close(toParent[0]);
    macws_forkfix_raw_close(toParent[1]);
    macws_forkfix_raw_close(toChild[0]);
    macws_forkfix_raw_close(toChild[1]);
}

pid_t MacWSForkWithPermissions(void) {
    // Per-call descriptors also keep simultaneous forks from sharing handshakes.
    int toParent[2], toChild[2];
    if (pipe(toParent) != 0) return -1;
    if (pipe(toChild) != 0) {
        int saved = errno;
        close(toParent[0]); close(toParent[1]);
        errno = saved;
        return -1;
    }
    pid_t child = macws_forkfix_raw_fork();
    if (child < 0) {
        int saved = errno;
        MacWSCloseForkPipes(toParent, toChild);
        errno = saved;
        return -1;
    }
    char token = ' ';
    if (child == 0) {
        if (macws_forkfix_raw_write(toParent[1], &token, 1) != 1 ||
            macws_forkfix_raw_read(toChild[0], &token, 1) != 1)
            macws_forkfix_raw_exit(127);
    } else {
        struct pollfd ready = {.fd = toParent[0], .events = POLLIN};
        int waited;
        do { waited = poll(&ready, 1, 5000); } while (waited < 0 && errno == EINTR);
        int error = waited > 0 && read(toParent[0], &token, 1) == 1
            ? MacWSRestoreForkPermissions(child) : EIO;
        if (!error && write(toChild[1], &token, 1) != 1) error = EIO;
        if (error) {
            // Never resume an uncorrected child or report a successful fork.
            kill(child, SIGKILL);
            while (waitpid(child, NULL, 0) < 0 && errno == EINTR) {}
            MacWSCloseForkPipes(toParent, toChild);
            errno = error;
            return -1;
        }
    }
    MacWSCloseForkPipes(toParent, toChild);
    return child;
}

// Interpose only the raw fork boundary. libc still runs its complete normal
// prepare/parent/child callback chain. Register at initial dyld load: a late
// dlopen interpose does not redirect already-bound shared-cache fork calls.
#include "interpose.h"
DYLD_INTERPOSE(MacWSForkWithPermissions, __fork)
