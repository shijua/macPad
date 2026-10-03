"""Verify the optional sandbox witness preserves the kernel's errno."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SandboxTraceTests(unittest.TestCase):
    def test_scope_and_errno_preservation(self):
        source = (ROOT / 'libmachook/mac_hooks.m').read_text()
        start = source.index('static void macws_trace_sandbox_result(')
        end = source.index('\nint __mac_syscall_new(', start)
        harness = '''
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
'''
        main = '''
int main(int argc, char **argv) {
    assert(argc == 3);
    int expected = EINVAL;
    errno = EIO;
    macws_trace_sandbox_result("test", argv[1], atoi(argv[2]), -1, expected);
    assert(errno == expected);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            c = path / 'test.c'
            c.write_text(harness + source[start:end] + main)
            exe = path / 'test'
            subprocess.run(['clang', '-Wall', '-Wextra', '-Werror',
                            str(c), '-o', str(exe)], check=True)
            cases = [('Sandbox', '0', True), ('Sandbox', '1', True),
                     ('Sandbox', '2', False), ('AMFI', '0', False)]
            for policy, operation, enabled in cases:
                with self.subTest(policy=policy, operation=operation):
                    result = subprocess.run(
                        [str(exe), policy, operation],
                        env={'MACWS_SANDBOX_TRACE': '1'},
                        capture_output=True, text=True, check=True)
                    self.assertEqual('SANDBOX-APPLY-DIAG' in result.stderr,
                                     enabled)
            result = subprocess.run([str(exe), 'Sandbox', '0'], env={},
                                    capture_output=True, text=True, check=True)
            self.assertEqual(result.stderr, '')


if __name__ == '__main__':
    unittest.main()
