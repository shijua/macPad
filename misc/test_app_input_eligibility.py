"""Compile the production eligibility predicate and check endpoint scope."""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class AppInputEligibilityTests(unittest.TestCase):
    def test_actual_predicate(self):
        with tempfile.TemporaryDirectory() as directory:
            source = pathlib.Path(directory) / 'eligibility.c'
            binary = pathlib.Path(directory) / 'eligibility'
            source.write_text(r'''
#include "macws_app_input_eligibility.h"
#include <assert.h>
int main(void) {
    assert(MacWSAppInputExecutableHasUILifecycle(
        "/System/Applications/System Settings.app/Contents/MacOS/System Settings"));
    assert(MacWSAppInputExecutableHasUILifecycle(
        "/System/Library/ExtensionKit/Extensions/DesktopSettings.appex/Contents/MacOS/DesktopSettings"));
    assert(MacWSAppInputExecutableHasUILifecycle(
        "/System/Library/ExtensionKit/Extensions/ControlCenterSettings.appex/Contents/MacOS/ControlCenterSettings"));
    assert(!MacWSAppInputExecutableHasUILifecycle(
        "/tmp/ControlCenterSettings.appex/Contents/MacOS/ControlCenterSettings"));
    assert(!MacWSAppInputExecutableHasUILifecycle(NULL));
    assert(!MacWSAppInputExecutableHasUILifecycle("/usr/bin/vim"));
    assert(!MacWSAppInputExecutableHasUILifecycle(
        "/System/Library/ExtensionKit/Extensions/Other.appex/Contents/MacOS/Other"));
    assert(!MacWSAppInputExecutableHasUILifecycle(
        "/tmp/DesktopSettings.appex/Contents/MacOS/DesktopSettings"));
    assert(!MacWSAppInputExecutableHasUILifecycle(
        "/System/Library/ExtensionKit/Extensions/DesktopSettings.appex/Contents/MacOS/Helper"));
    return 0;
}
''')
            subprocess.run(['xcrun', 'clang', '-Wall', '-Wextra', '-Werror',
                            '-I', str(ROOT / 'include'), str(source), '-o',
                            str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()
