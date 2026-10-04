"""Run the actual feature lookup against target-domain fixtures on macOS."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ExtensionFeatureConfiguration(unittest.TestCase):
    def test_target_values_and_provider_delegation(self):
        source = (ROOT / 'libmachook/mac_hooks.m').read_text()
        start = source.index('typedef bool (*macws_os_feature_enabled_impl_fn)')
        end = source.index('static void macws_install_target_feature_flag_compatibility', start)
        harness = '''#import <Foundation/Foundation.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
''' + source[start:end] + '''
static bool outer(const char *domain, const char *feature) { return true; }
int main(void) { @autoreleasepool {
 macws_os_feature_enabled_impl_orig = outer;
 if (macws_os_feature_enabled_impl_compat("ExtensionKit", "absent")) return 1;
 macws_target_extension_features = @{
   @"enabled": @{ @"Enabled": @YES },
   @"disabled": @{ @"Enabled": @NO },
   @"malformed": @"not-a-dictionary" };
 if (!macws_os_feature_enabled_impl_compat("ExtensionKit", "enabled")) return 2;
 if (macws_os_feature_enabled_impl_compat("ExtensionKit", "disabled")) return 3;
 if (macws_os_feature_enabled_impl_compat("ExtensionKit", "unknown")) return 4;
 if (macws_os_feature_enabled_impl_compat("ExtensionKit", "malformed")) return 5;
 if (!macws_os_feature_enabled_impl_compat("OtherDomain", "enabled")) return 6;
 } return 0; }
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'probe.m').write_text(harness)
            subprocess.run(['clang', '-fobjc-arc', '-framework', 'Foundation',
                            str(path / 'probe.m'), '-o', str(path / 'probe')],
                           check=True, capture_output=True, timeout=30)
            subprocess.run([str(path / 'probe')], check=True, timeout=5)


if __name__ == '__main__':
    unittest.main()
