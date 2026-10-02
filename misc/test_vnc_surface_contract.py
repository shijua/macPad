"""Exercise the actual VNC texture/surface boundary without private ivars."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class VncSurfaceContract(unittest.TestCase):
    def test_real_getter_nil_and_unsupported_texture(self):
        source = (ROOT / "libmachook/Metal_hooks.x").read_text()
        start = source.index("static IOSurfaceRef macws_vnc_bound_surface(id<MTLTexture> texture) {")
        helper = source[start:source.index("\n}", start) + 2]
        harness = r'''#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <assert.h>
static int calls;
@interface SurfaceTexture : NSObject
@end
@implementation SurfaceTexture
- (IOSurfaceRef)iosurface { calls++; return (IOSurfaceRef)(uintptr_t)0xfeed; }
@end
''' + helper + r'''
int main(void) { @autoreleasepool {
 assert(macws_vnc_bound_surface(nil) == NULL);
 NSObject *unsupported = [NSObject new];
 assert(macws_vnc_bound_surface((id<MTLTexture>)unsupported) == NULL);
 SurfaceTexture *texture = [SurfaceTexture new];
 assert(macws_vnc_bound_surface((id<MTLTexture>)texture) == (IOSurfaceRef)(uintptr_t)0xfeed);
 assert(calls == 1);
 [texture release]; [unsupported release]; return 0;
} }
'''
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            (p / "probe.m").write_text(harness)
            subprocess.run(["xcrun", "clang", "-framework", "Foundation",
                            "-framework", "Metal", str(p / "probe.m"),
                            "-o", str(p / "probe")], check=True, capture_output=True)
            subprocess.run([str(p / "probe")], check=True, capture_output=True)
