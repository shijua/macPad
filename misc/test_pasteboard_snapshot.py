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
@property BOOL file;
@end
@implementation Provider
- (NSArray *)registeredTypeIdentifiers {
 return @[self.file ? @"public.file-url" : @"public.utf8-plain-text"];
}
- (void)loadItemForTypeIdentifier:(NSString *)type options:(NSDictionary *)options
               completionHandler:(NSItemProviderCompletionHandler)completion {
 // A text producer could return a promised temporary file here. The text
 // route must not request this representation; real file URLs still do.
 assert(self.file);
 completion([NSURL fileURLWithPath:@"/tmp/genuine-file"], nil);
}
- (void)loadDataRepresentationForTypeIdentifier:(NSString *)type
               completionHandler:(void (^)(NSData *, NSError *))completion {
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, self.delay * NSEC_PER_SEC),
        dispatch_get_global_queue(QOS_CLASS_DEFAULT, 0), ^{
            completion(self.fails ? nil : [self.value dataUsingEncoding:NSUTF8StringEncoding],
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
    Provider *file = [Provider new]; file.file = YES;
    NSString *command = @"curl -fsSL https://example.com/install.sh | sh";
    NSURL *promisedURL = [NSURL fileURLWithPath:[NSTemporaryDirectory()
        stringByAppendingPathComponent:NSUUID.UUID.UUIDString]];
    assert([command writeToURL:promisedURL atomically:YES
        encoding:NSUTF8StringEncoding error:nil]);
    NSItemProvider *promised = [NSItemProvider new];
    [promised registerFileRepresentationForTypeIdentifier:@"public.utf8-plain-text"
        fileOptions:0 visibility:NSItemProviderRepresentationVisibilityAll
        loadHandler:^NSProgress *(void (^done)(NSURL *, BOOL, NSError *)) {
            done(promisedURL, NO, nil); return nil;
        }];
    __block int calls = 0;
    __block BOOL uiAdvanced = NO;
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, .01 * NSEC_PER_SEC),
                   dispatch_get_main_queue(), ^{ uiAdvanced = YES; });
    MacWSLoadPasteboardSnapshot(@[slow, fast], .5, ^(NSArray *items, NSError *e) {
        assert(uiAdvanced && !e && items.count == 2);
        assert([[[NSString alloc] initWithData:items[0][@"public.utf8-plain-text"] encoding:NSUTF8StringEncoding] isEqual:@"first"]);
        assert([[[NSString alloc] initWithData:items[1][@"public.utf8-plain-text"] encoding:NSUTF8StringEncoding] isEqual:@"second"]);
        calls++;
    });
    MacWSLoadPasteboardSnapshot(@[late], .03, ^(NSArray *items, NSError *e) {
        assert(!items && e.code == 2); calls++;
    });
    MacWSLoadPasteboardSnapshot(@[fast, bad], .5, ^(NSArray *items, NSError *e) {
        assert(!items && e.code == 77); calls++;
    });
    MacWSLoadPasteboardSnapshot(@[promised], .5, ^(NSArray *items, NSError *e) {
        id value = items[0][@"public.utf8-plain-text"];
        assert(!e && [value isKindOfClass:NSData.class]);
        assert([[[NSString alloc] initWithData:value encoding:NSUTF8StringEncoding]
            isEqual:command]);
        assert([NSFileManager.defaultManager removeItemAtURL:promisedURL error:nil]);
        calls++;
    });
    MacWSLoadPasteboardSnapshot(@[file], .5, ^(NSArray *items, NSError *e) {
        assert(!e && [items[0][@"public.file-url"] isKindOfClass:NSURL.class]);
        calls++;
    });
    MacWSLoadPasteboardSnapshot(@[], .5, ^(NSArray *items, NSError *e) {
        assert(!e && items.count == 0); calls++;
    });
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, .7 * NSEC_PER_SEC),
        dispatch_get_main_queue(), ^{ assert(calls == 6); exit(0); });
    dispatch_main();
} }
'''
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "snapshot"
            subprocess.run(["clang", "-x", "objective-c", "-", "-fobjc-arc",
                            "-framework", "Foundation", "-framework", "UniformTypeIdentifiers", "-I", str(ROOT),
                            "-o", str(binary)], input=program, text=True,
                           capture_output=True, check=True)
            subprocess.run([str(binary)], check=True, timeout=5)
