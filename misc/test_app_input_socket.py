"""Exercise the freestanding pre-exec socket capability and failure cleanup."""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class AppInputSocketTests(unittest.TestCase):
    def test_preopen_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            source = pathlib.Path(directory) / 'socket.c'
            binary = pathlib.Path(directory) / 'socket'
            source.write_text(r'''
#include "macws_app_input_socket.h"
#include <assert.h>
#include <string.h>
static int mode, calls, closed, unlinked;
static long fake(long number, long a, long b, long c) {
    calls++;
    if (number == SYS_socket) {
        assert(a == AF_UNIX && b == SOCK_DGRAM && c == 0);
        return mode == 1 ? -1 : 42;
    }
    if (number == SYS_unlink) { unlinked++; return 0; }
    if (number == SYS_bind) {
        struct sockaddr_un *address = (void *)b;
        assert(a == 42 && c == sizeof(*address));
        assert(address->sun_family == AF_UNIX);
        assert(!strcmp(address->sun_path,
                       "/private/tmp/macws_app_input.12345.sock"));
        return mode == 2 ? -1 : 0;
    }
    if (number == SYS_chmod) { assert(b == 0600); return mode == 3 ? -1 : 0; }
    assert(number == SYS_close && a == 42); closed++; return 0;
}
int main(void) {
    for (mode = 0; mode < 4; mode++) {
        char environment[64] = {0}; calls = closed = unlinked = 0;
        assert(MacWSPreopenAppInputSocket(12345, environment, fake) == (mode == 0));
        if (!mode) assert(!strcmp(environment, "MACWS_APP_INPUT_FD=42"));
        else assert(!*environment);
        assert(closed == (mode == 2 || mode == 3));
        assert(unlinked == (mode == 1 ? 0 : mode == 3 ? 2 : 1));
    }
    char environment[64] = {0}; calls = 0;
    assert(!MacWSPreopenAppInputSocket(1, environment, fake));
    assert(!calls);
    return 0;
}
''')
            subprocess.run(['xcrun', 'clang', '-Wall', '-Wextra', '-Werror',
                            '-I', str(ROOT / 'include'), str(source), '-o',
                            str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()
