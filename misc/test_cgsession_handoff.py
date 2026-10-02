"""Exercise the actual session handoff against CoreFoundation dictionaries."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == "darwin", "requires CoreFoundation")
class SessionHandoff(unittest.TestCase):
    def test_real_provider_and_only_placeholder_login_field_change(self):
        source = (ROOT / "libmachook/Metal_hooks.x").read_text()
        start = source.index("extern CFDictionaryRef CGSSessionCopyCurrentSessionProperties")
        end = source.index("// A Sonoma AppKit/USR00 control", start)
        functions = source[start:end]
        self.assertNotIn("MSHookFunction", functions)
        harness = r'''
#include <CoreFoundation/CoreFoundation.h>
#include <stdint.h>
#include <assert.h>
typedef signed char BOOL;
#define YES 1
#define NO 0
static CFDictionaryRef provider;
static int calls;
CFDictionaryRef CGSSessionCopyCurrentSessionProperties(void) {
    calls++; return provider ? CFRetain(provider) : NULL;
}
CFDictionaryRef CGSessionCopyCurrentDictionary(void) {
    calls++; return provider ? CFRetain(provider) : NULL;
}
'''
        harness += functions
        harness += r'''
static CFMutableDictionaryRef session(int64_t uid, CFBooleanRef done) {
    CFMutableDictionaryRef d = CFDictionaryCreateMutable(NULL, 0,
        &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
    int64_t audit = 0x004d5753;
    CFNumberRef a = CFNumberCreate(NULL, kCFNumberSInt64Type, &audit);
    CFNumberRef u = CFNumberCreate(NULL, kCFNumberSInt64Type, &uid);
    CFDictionarySetValue(d, CFSTR("kCGSSessionAuditIDKey"), a);
    CFDictionarySetValue(d, CFSTR("kCGSSessionUserIDKey"), u);
    CFDictionarySetValue(d, CFSTR("kCGSSessionUserNameKey"), CFSTR("unknown"));
    CFDictionarySetValue(d, CFSTR("kCGSSessionOnConsoleKey"), kCFBooleanTrue);
    CFDictionarySetValue(d, CFSTR("kCGSessionLoginDoneKey"), done);
    CFDictionarySetValue(d, CFSTR("provider-owned"), CFSTR("retained"));
    CFRelease(a); CFRelease(u); return d;
}
int main(void) {
    assert(macws_cgsession_private_compat() == NULL && calls == 1);
    provider = session(88, kCFBooleanFalse);
    CFDictionaryRef result = macws_cgsession_private_compat();
    assert(calls == 2 && result != provider);
    assert(CFDictionaryGetCount(result) == CFDictionaryGetCount(provider));
    assert(CFDictionaryGetValue(result, CFSTR("kCGSessionLoginDoneKey")) == kCFBooleanTrue);
    assert(CFDictionaryGetValue(provider, CFSTR("kCGSessionLoginDoneKey")) == kCFBooleanFalse);
    assert(CFEqual(CFDictionaryGetValue(result, CFSTR("provider-owned")), CFSTR("retained")));
    CFRelease(result); CFRelease(provider);
    provider = session(501, kCFBooleanFalse);
    result = macws_cgsession_public_compat();
    assert(calls == 3 && result == provider);
    CFRelease(result); CFRelease(provider);
    provider = session(88, kCFBooleanTrue);
    result = macws_cgsession_private_compat();
    assert(calls == 4 && result == provider);
    CFRelease(result); CFRelease(provider);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            code = Path(directory) / "session.c"
            executable = Path(directory) / "session"
            code.write_text(harness)
            subprocess.run(["xcrun", "clang", str(code), "-framework",
                            "CoreFoundation", "-o", str(executable)],
                           check=True, capture_output=True, text=True)
            subprocess.run([str(executable)], check=True)


if __name__ == "__main__":
    unittest.main()
