"""Exercise TCC manager failures and the fixed session input-owner grants."""
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
static CFStringRef captureService;
static int captureCalls;
static int mode;
static int bundleCalls;
uid_t test_geteuid(void) { return mode == 1 ? 501 : 0; }
void *test_dlopen(const char *path, int flags) {
    (void)path; (void)flags; return mode == 2 ? NULL : (void *)1;
}
static Boolean setter(CFStringRef s, CFStringRef path, Boolean allow) {
    if (s == captureService) {
        if (!allow || !CFEqual(path, CFSTR("/usr/local/bin/macwsdisplayd"))) abort();
        ++captureCalls;
        return mode != 6;
    }
    if (s != service || !allow || !CFEqual(path,
        CFSTR("/usr/local/bin/OSXvnc-server"))) abort();
    return mode != 4;
}
static Boolean bundleSetter(CFStringRef s, CFStringRef identifier, Boolean allow) {
    const char *owners[] = {"com.apple.systempreferences", "com.apple.finder",
                           "com.apple.Safari", "com.apple.Terminal"};
    if (s != service || !allow || bundleCalls >= 4) abort();
    CFStringRef expected = CFStringCreateWithCString(NULL, owners[bundleCalls++],
                                                    kCFStringEncodingUTF8);
    Boolean matches = CFEqual(identifier, expected); CFRelease(expected);
    if (!matches) abort();
    return mode != 5;
}
void *test_dlsym(void *h, const char *name) {
    (void)h;
    if (!strcmp(name, "kTCCServicePostEvent")) return &service;
    if (!strcmp(name, "kTCCServiceScreenCapture")) return mode == 7 ? NULL : &captureService;
    if (mode == 3) return NULL;
    if (!strcmp(name, "TCCAccessSetForPath")) return (void *)setter;
    if (!strcmp(name, "TCCAccessSetForBundleId")) return (void *)bundleSetter;
    abort();
}
extern int MacWSPrepareInputAccess(void);
int main(int argc, char **argv) {
    if (argc != 2) return 99;
    mode = atoi(argv[1]); service = CFSTR("kTCCServicePostEvent");
    captureService = CFSTR("kTCCServiceScreenCapture");
    int result = MacWSPrepareInputAccess();
    if (mode == 0 && bundleCalls != 4) abort();
    if ((mode == 0 || mode == 6) && captureCalls != 1) abort();
    if (mode > 0 && mode != 6 && captureCalls != 0) abort();
    if (mode == 4 && bundleCalls != 0) abort();
    if (mode == 5 && bundleCalls != 1) abort();
    return result;
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
        for mode, status in [(0, 0), (1, 77), (2, 69), (3, 69), (4, 1),
                             (5, 1), (6, 1), (7, 69)]:
            with self.subTest(mode=mode):
                result = subprocess.run([str(self.binary), str(mode)],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, status, result.stderr)
                if status == 0:
                    self.assertIn('PostEvent authorized', result.stdout)
                    self.assertIn('ScreenCapture authorized', result.stdout)
                else:
                    self.assertNotIn('authorized', result.stdout)


class InputAccessStartupTests(unittest.TestCase):
    def test_authorization_precedes_input_process_on_start_and_recovery(self):
        script = (ROOT / 'layout/usr/macOS/bin/macos_gui.sh').read_text()
        for name in ('start_macos', 'start_ws_dependents_after_replacement'):
            start = script.index(name + '() {')
            body = script[start:script.index('\n}', start)]
            grant = body.index('prepare_pointer_input_access || return 1')
            launch = body.index('launchctl load "$VNC_PLIST"')
            self.assertLess(grant, launch, name)

    def test_failed_service_registration_stops_before_grant(self):
        script = (ROOT / 'layout/usr/macOS/bin/macos_gui.sh').read_text()
        start = script.index('prepare_pointer_input_access() {')
        function = script[start:script.index('\n}', start) + 2]
        # Execute the shipped function. A failing registration must return
        # before attempting the device-only timeout/chroot command.
        result = subprocess.run([
            '/bin/bash', '-c',
            'publish_macos_tcc_service() { return 23; }\n'
            'log() { echo "unexpected-log: $*"; }\n' + function +
            '\nprepare_pointer_input_access'
        ], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.stderr, '')


if __name__ == '__main__':
    unittest.main()
