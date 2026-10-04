/* Diagnostic only: apply each profile in a fresh child, preserving real
 * kernel results. No profile replacement or sandbox hook is installed. */
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <mach/mach.h>
#include <poll.h>
#include <stdio.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <unistd.h>

extern int __sandbox_ms(const char *, int, void *);
extern kern_return_t bootstrap_look_up(mach_port_t, const char *, mach_port_t *);

static void permissions(const char *stage, const char *path) {
    errno = 0;
    int descriptor = open(path, O_WRONLY | O_CREAT | O_EXCL, 0600);
    int saved = errno;
    dprintf(STDOUT_FILENO, "%s file-create=%d errno=%d\n", stage,
            descriptor >= 0 ? 0 : -1, saved);
    if (descriptor >= 0) { close(descriptor); unlink(path); }

    errno = 0;
    int connection = socket(AF_INET, SOCK_STREAM, 0);
    int result = -1;
    saved = errno;
    if (connection >= 0) {
        int flags = fcntl(connection, F_GETFL);
        if (flags >= 0 && fcntl(connection, F_SETFL, flags | O_NONBLOCK) == 0) {
            struct sockaddr_in address = { .sin_len = sizeof(address),
                .sin_family = AF_INET, .sin_port = htons(22),
                .sin_addr.s_addr = htonl(INADDR_LOOPBACK) };
            errno = 0;
            result = connect(connection, (const void *)&address, sizeof(address));
            saved = errno;
            if (result < 0 && saved == EINPROGRESS) {
                struct pollfd event = { .fd = connection, .events = POLLOUT };
                int ready = poll(&event, 1, 500);
                socklen_t length = sizeof(saved);
                if (ready > 0 && getsockopt(connection, SOL_SOCKET, SO_ERROR,
                                           &saved, &length) == 0)
                    result = saved == 0 ? 0 : -1;
                else { result = -1; saved = ready == 0 ? ETIMEDOUT : errno; }
            }
        } else saved = errno;
        close(connection);
    }
    dprintf(STDOUT_FILENO, "%s loopback-connect=%d errno=%d\n", stage, result, saved);

    mach_port_t bootstrap = MACH_PORT_NULL;
    kern_return_t kr = task_get_bootstrap_port(mach_task_self(), &bootstrap);
    const char *services[] = { "com.apple.cfprefsd.daemon",
                              "com.apple.macosbooter.cfprefsd.daemon" };
    for (unsigned i = 0; i < sizeof(services) / sizeof(services[0]); ++i) {
        mach_port_t service = MACH_PORT_NULL;
        kern_return_t found = kr == KERN_SUCCESS
            ? bootstrap_look_up(bootstrap, services[i], &service) : kr;
        dprintf(STDOUT_FILENO, "%s lookup=%s result=%d\n", stage, services[i], found);
        if (MACH_PORT_VALID(service)) mach_port_deallocate(mach_task_self(), service);
    }
    if (MACH_PORT_VALID(bootstrap)) mach_port_deallocate(mach_task_self(), bootstrap);
}

static int test(int operation, const char *profile) {
    pid_t child = fork();
    if (child < 0) { perror("fork"); return 1; }
    if (child == 0) {
        alarm(5);
        char path[128];
        snprintf(path, sizeof(path), "/private/var/tmp/macws-sandbox-probe-%d", getpid());
        permissions("before", path);
        const void *arguments[3] = { profile, NULL, NULL };
        errno = 0;
        int result = __sandbox_ms("Sandbox", operation, operation ? arguments : NULL);
        int saved = errno;
        dprintf(STDOUT_FILENO, "operation=%d profile=%s result=%d errno=%d\n",
                operation, profile ? profile : "(none)", result, saved);
        permissions("after", path);
        _exit(0);
    }
    int status = 0;
    pid_t waited;
    do { waited = waitpid(child, &status, 0); } while (waited < 0 && errno == EINTR);
    if (waited != child || !WIFEXITED(status) || WEXITSTATUS(status)) {
        printf("child-status=%d wait-result=%d\n", status, waited);
        return 1;
    }
    return 0;
}

int main(void) {
    int failed = test(0, NULL);
    failed |= test(1, "com.apple.WebKit.Networking");
    failed |= test(1, "com.apple.WebKit.WebContent");
    failed |= test(1, "com.apple.no-such-macws-profile");
    return failed;
}
