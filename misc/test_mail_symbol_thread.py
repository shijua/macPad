"""Exercise real main-queue dispatch, result lifetime, and exception propagation."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MailSymbolThread(unittest.TestCase):
    def test_routes_original_and_preserves_results(self):
        fixture = r'''
#include "MacWSMailSymbolThread.h"
#include <assert.h>
static unsigned calls;
static BOOL done;
static id render(id receiver, SEL selector, id name, NSInteger scale,
                 id font, id description) {
    assert(pthread_main_np()); calls++;
    assert(receiver == [NSObject class]);
    assert(selector == @selector(description));
    assert(scale == 2 && font == nil && description == nil);
    if ([name isEqual:@"throw"])
        @throw [NSException exceptionWithName:@"OriginalFailure" reason:nil userInfo:nil];
    if (!name) return nil;
    return [[[NSObject alloc] init] autorelease];
}
int main(void) { @autoreleasepool {
    assert(macws_mail_symbol_on_main_thread(render, [NSObject class],
        @selector(description), @"main", 2, nil, nil) != nil);
    assert(calls == 1);
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_DEFAULT, 0), ^{ @autoreleasepool {
        id image = macws_mail_symbol_on_main_thread(render, [NSObject class],
            @selector(description), @"background", 2, nil, nil);
        assert([image isKindOfClass:[NSObject class]]);
        assert(macws_mail_symbol_on_main_thread(render, [NSObject class],
            @selector(description), nil, 2, nil, nil) == nil);
        BOOL caught = NO;
        @try {
            macws_mail_symbol_on_main_thread(render, [NSObject class],
                @selector(description), @"throw", 2, nil, nil);
        } @catch (NSException *e) { caught = [e.name isEqual:@"OriginalFailure"]; }
        assert(caught);
        dispatch_async(dispatch_get_main_queue(), ^{ assert(calls == 4); done = YES; });
    } });
    while (!done)
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.01]];
} }
'''
        with tempfile.TemporaryDirectory() as directory:
            source, binary = Path(directory) / "test.m", Path(directory) / "test"
            source.write_text(fixture)
            subprocess.run(["xcrun", "clang", "-Wall", "-Werror", "-fblocks",
                            "-I", str(ROOT / "libmachook/Compatibility"),
                            str(source), "-framework", "Foundation", "-o", str(binary)],
                           check=True)
            subprocess.run([str(binary)], check=True, timeout=5)


if __name__ == "__main__":
    unittest.main()
