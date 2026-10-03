"""Compile the actual Settings resource resolver against real ObjC dispatch."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SettingsIconResource(unittest.TestCase):
    def test_resolves_real_resource_without_capability_bypass(self):
        source = (ROOT / "libmachook/mac_hooks.m").read_text()
        helper = source.split("static id macws_settings_resolved_icon_resource", 1)[1]
        helper = "static id macws_settings_resolved_icon_resource" + helper.split(
            "\nstatic id macws_settings_concrete_icon_image", 1)[0]
        fixture = r'''
#import <Foundation/Foundation.h>
#include <objc/runtime.h>
#include <objc/message.h>
#include <assert.h>
@interface ISGraphicSymbolResource : NSObject @end
@implementation ISGraphicSymbolResource @end
@interface ISAssetCatalogResource : NSObject @end
@implementation ISAssetCatalogResource @end
@interface MacWSTestExtensionRecord : NSObject
@property NSURL *URL;
@end
@implementation MacWSTestExtensionRecord @end
@interface Provider : NSObject
@property id resource;
@property id record;
@property unsigned resolved;
- (BOOL)supportsGraphicIcons;
- (void)resolveResources;
- (id)iconResource;
@end
@implementation Provider
- (BOOL)supportsGraphicIcons { return NO; }
- (void)resolveResources { self.resolved++; }
- (id)iconResource { assert(self.resolved); return self.resource; }
@end
static Class TestClassLookup(const char *name) {
    if (!strcmp(name, "LSApplicationExtensionRecord"))
        return [MacWSTestExtensionRecord class];
    return objc_getClass(name);
}
#define objc_getClass(name) TestClassLookup(name)
/* ACTUAL_HELPER */
int main(void) { @autoreleasepool {
    assert(macws_settings_resolved_icon_resource(nil) == nil);
    assert(macws_settings_resolved_icon_resource([NSObject new]) == nil);
    Provider *p = [Provider new];
    assert(!p.supportsGraphicIcons);
    p.resource = [ISGraphicSymbolResource new];
    assert(macws_settings_resolved_icon_resource(p) == p.resource);
    assert(p.resolved == 1 && !p.supportsGraphicIcons);
    p.resource = [NSObject new];
    assert(macws_settings_resolved_icon_resource(p) == nil);
    assert(p.resolved == 2);
    p.resource = nil;
    assert(macws_settings_resolved_icon_resource(p) == nil);
    assert(p.resolved == 3);
    p.resource = [ISAssetCatalogResource new];
    assert(macws_settings_resolved_icon_resource(p) == nil);
    MacWSTestExtensionRecord *record = [MacWSTestExtensionRecord new];
    p.record = record;
    for (NSString *path in @[@"/System/Library/ExtensionKit/Extensions/Siri.appex",
        @"/System/Applications/System Settings.app/Contents/PlugIns/General.appex"]) {
        record.URL = [NSURL fileURLWithPath:path];
        assert(macws_settings_resolved_icon_resource(p) == p.resource);
    }
    for (NSString *path in @[@"/Applications/Other.appex",
        @"/System/Library/ExtensionKit/Extensions/../../Other.appex",
        @"/System/Library/ExtensionKit/Extensions/Siri.app"]) {
        record.URL = [NSURL fileURLWithPath:path];
        assert(macws_settings_resolved_icon_resource(p) == nil);
    }
    record.URL = [NSURL URLWithString:@"https://example.com/Siri.appex"];
    assert(macws_settings_resolved_icon_resource(p) == nil);
    p.record = [NSObject new];
    assert(macws_settings_resolved_icon_resource(p) == nil);
} }
'''
        with tempfile.TemporaryDirectory() as td:
            code, executable = Path(td) / "test.m", Path(td) / "test"
            code.write_text(fixture.replace("/* ACTUAL_HELPER */", helper))
            subprocess.run(["xcrun", "clang", "-fobjc-arc", "-Wall", "-Werror",
                            str(code), "-framework", "Foundation", "-o", str(executable)],
                           check=True, capture_output=True, text=True)
            subprocess.run([str(executable)], check=True, timeout=5)


if __name__ == "__main__":
    unittest.main()
