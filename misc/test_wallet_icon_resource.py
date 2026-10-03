"""Compile the actual Wallet file-resource route and exercise its boundaries."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WalletIconResource(unittest.TestCase):
    def test_uses_declared_resource_and_preserves_failures(self):
        source = (ROOT / "libmachook/mac_hooks.m").read_text()
        helper = "static id macws_settings_wallet_icon_resource" + source.split(
            "static id macws_settings_wallet_icon_resource", 1)[1].split(
            "\nstatic id macws_settings_concrete_icon_image", 1)[0]
        fixture = r'''
#import <Foundation/Foundation.h>
#include <objc/runtime.h>
#include <objc/message.h>
#include <assert.h>
static NSString *identifier;
static NSString *declaredIdentifier;
static NSString *declaredIcon;
static id resource;
static unsigned resolved;
@interface ISIcns : NSObject @end
@implementation ISIcns @end
@interface Icon : NSObject
- (id)bundleIdentifier;
@end
@implementation Icon
- (id)bundleIdentifier { return identifier; }
@end
@interface Provider : NSObject
- (void)resolveResources;
- (id)iconResource;
@end
@implementation Provider
- (void)resolveResources { resolved++; }
- (id)iconResource { assert(resolved); return resource; }
@end
@interface ISBundleIcon : NSObject
- (id)initWithBundleURL:(NSURL *)url;
- (id)makeSymbolResourceProvider;
@end
@implementation ISBundleIcon
- (id)initWithBundleURL:(NSURL *)url {
    assert([url.path isEqual:@"/System/Library/ExtensionKit/Extensions/WalletSettingsExtension.appex"]);
    return [super init];
}
- (id)makeSymbolResourceProvider { return [[[Provider alloc] init] autorelease]; }
@end
@interface TestBundle : NSObject
+ (id)bundleWithURL:(NSURL *)url;
- (NSString *)bundleIdentifier;
- (NSDictionary *)infoDictionary;
@end
@implementation TestBundle
+ (id)bundleWithURL:(NSURL *)url { return [[[self alloc] init] autorelease]; }
- (NSString *)bundleIdentifier { return declaredIdentifier; }
- (NSDictionary *)infoDictionary {
    return declaredIcon ? @{@"CFBundleIconFile": declaredIcon} : @{};
}
@end
#define NSBundle TestBundle
/* ACTUAL_HELPER */
int main(void) { @autoreleasepool {
    Icon *icon = [[[Icon alloc] init] autorelease];
    assert(macws_settings_wallet_icon_resource(nil) == nil);
    assert(macws_settings_wallet_icon_resource([NSObject new]) == nil);
    declaredIdentifier = @"com.apple.WalletSettingsExtension";
    declaredIcon = @"WalletSettingsExtension.icns";
    resource = [[[ISIcns alloc] init] autorelease];
    identifier = @"com.apple.Other";
    assert(macws_settings_wallet_icon_resource(icon) == nil && !resolved);
    identifier = declaredIdentifier;
    assert(macws_settings_wallet_icon_resource(icon) == resource && resolved == 1);
    declaredIdentifier = @"com.apple.Other";
    assert(macws_settings_wallet_icon_resource(icon) == nil && resolved == 1);
    declaredIdentifier = identifier;
    declaredIcon = @"../Other.icns";
    assert(macws_settings_wallet_icon_resource(icon) == nil && resolved == 1);
    declaredIcon = nil;
    assert(macws_settings_wallet_icon_resource(icon) == nil && resolved == 1);
    declaredIcon = @"WalletSettingsExtension.icns";
    resource = [NSObject new];
    assert(macws_settings_wallet_icon_resource(icon) == nil);
    resource = nil;
    assert(macws_settings_wallet_icon_resource(icon) == nil);
} }
'''
        with tempfile.TemporaryDirectory() as directory:
            code, binary = Path(directory) / "test.m", Path(directory) / "test"
            code.write_text(fixture.replace("/* ACTUAL_HELPER */", helper))
            subprocess.run(["xcrun", "clang", "-Wall", "-Werror", str(code),
                            "-framework", "Foundation", "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True, timeout=5)


if __name__ == "__main__":
    unittest.main()
