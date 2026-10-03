from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PasteboardSnapshot(unittest.TestCase):
    def test_async_order_failure_timeout_and_single_completion(self):
        program = r'''
#import "MacWSHost/Transport/MacWSPasteboardSnapshot.h"
#include <assert.h>
#include <stdlib.h>
@interface Provider : NSItemProvider
@property NSTimeInterval delay;
@property BOOL fails;
@property NSString *value;
@end
@implementation Provider
- (NSArray *)registeredTypeIdentifiers { return @[@"public.utf8-plain-text"]; }
- (void)loadItemForTypeIdentifier:(NSString *)type options:(NSDictionary *)options
               completionHandler:(NSItemProviderCompletionHandler)completion {
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, self.delay * NSEC_PER_SEC),
        dispatch_get_global_queue(QOS_CLASS_DEFAULT, 0), ^{
            completion(self.fails ? nil : self.value,
                self.fails ? [NSError errorWithDomain:@"test" code:77
                                            userInfo:nil] : nil);
        });
}
@end
int main(void) { @autoreleasepool {
    Provider *slow = [Provider new]; slow.delay = .12; slow.value = @"first";
    Provider *fast = [Provider new]; fast.delay = .02; fast.value = @"second";
    Provider *late = [Provider new]; late.delay = .14; late.value = @"late";
    Provider *bad = [Provider new]; bad.delay = .01; bad.fails = YES;
    __block int calls = 0;
    __block BOOL uiAdvanced = NO;
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, .01 * NSEC_PER_SEC),
                   dispatch_get_main_queue(), ^{ uiAdvanced = YES; });
    MacWSLoadPasteboardSnapshot(@[slow, fast], .5, ^(NSArray *items, NSError *e) {
        assert(uiAdvanced && !e && items.count == 2);
        assert([items[0][@"public.utf8-plain-text"] isEqual:@"first"]);
        assert([items[1][@"public.utf8-plain-text"] isEqual:@"second"]);
        calls++;
    });
    MacWSLoadPasteboardSnapshot(@[late], .03, ^(NSArray *items, NSError *e) {
        assert(!items && e.code == 2); calls++;
    });
    MacWSLoadPasteboardSnapshot(@[fast, bad], .5, ^(NSArray *items, NSError *e) {
        assert(!items && e.code == 77); calls++;
    });
    MacWSLoadPasteboardSnapshot(@[], .5, ^(NSArray *items, NSError *e) {
        assert(!e && items.count == 0); calls++;
    });
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, .7 * NSEC_PER_SEC),
        dispatch_get_main_queue(), ^{ assert(calls == 4); exit(0); });
    dispatch_main();
} }
'''
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "snapshot"
            subprocess.run(["clang", "-x", "objective-c", "-", "-fobjc-arc",
                            "-framework", "Foundation", "-I", str(ROOT),
                            "-o", str(binary)], input=program, text=True,
                           capture_output=True, check=True)
            subprocess.run([str(binary)], check=True, timeout=5)
