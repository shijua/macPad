"""Exercise TCC manager failures and the single permitted input-owner grant."""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class InputAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        directory = pathlib.Path(cls.temp.name)
        harness = directory / 'harness.c'
        harness.write_text(r'''
#include <CoreFoundation/CoreFoundation.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static CFStringRef service;
static int mode;
uid_t test_geteuid(void) { return mode == 1 ? 501 : 0; }
void *test_dlopen(const char *path, int flags) {
    (void)path; (void)flags; return mode == 2 ? NULL : (void *)1;
}
static Boolean setter(CFStringRef s, CFStringRef path, Boolean allow) {
    if (s != service || !allow || !CFEqual(path,
        CFSTR("/usr/local/bin/OSXvnc-server"))) abort();
    return mode != 4;
}
void *test_dlsym(void *h, const char *name) {
    (void)h;
    if (!strcmp(name, "kTCCServicePostEvent")) return &service;
    return mode == 3 ? NULL : (void *)setter;
}
extern int MacWSPrepareInputAccess(void);
int main(int argc, char **argv) {
    if (argc != 2) return 99;
    mode = atoi(argv[1]); service = CFSTR("kTCCServicePostEvent");
    return MacWSPrepareInputAccess();
}
''')
        obj = directory / 'InputAccess.o'
        cls.binary = directory / 'test'
        subprocess.run([
            'xcrun', 'clang', '-Wall', '-Wextra', '-Werror',
            '-Dgeteuid=test_geteuid', '-Ddlopen=test_dlopen',
            '-Ddlsym=test_dlsym', '-c',
            str(ROOT / 'macwsworkspacectl/InputAccess.c'), '-o', str(obj)
        ], check=True)
        subprocess.run([
            'xcrun', 'clang', str(harness), str(obj),
            '-framework', 'CoreFoundation', '-o', str(cls.binary)
        ], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_manager_results_and_fixed_scope(self):
        for mode, status in [(0, 0), (1, 77), (2, 69), (3, 69), (4, 1)]:
            with self.subTest(mode=mode):
                result = subprocess.run([str(self.binary), str(mode)],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, status, result.stderr)
                if status == 0:
                    self.assertIn('PostEvent authorized', result.stdout)
                else:
                    self.assertNotIn('authorized', result.stdout)


if __name__ == '__main__':
    unittest.main()
