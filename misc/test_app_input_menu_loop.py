"""Verify the production menu wrapper preserves execution and exception state."""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class AppInputMenuLoopTests(unittest.TestCase):
    def test_real_wrapper_lifecycle(self):
        text = (ROOT / 'libmachook/AppInputBridge.m').read_text()
        start = text.index('static void MacWSWithSynchronousInputTracking(')
        end = text.index('static void MacWSInstallMenuEventLoopWitness(void) {', start)
        wrapper = text[start:end]
        harness = r'''
#import <Foundation/Foundation.h>
#import <CoreGraphics/CoreGraphics.h>
#include <stdatomic.h>
#include <assert.h>
#include <pthread.h>
static pthread_mutex_t MacWSAppInputRouteLock = PTHREAD_MUTEX_INITIALIZER;
static void MacWSClearMenuContextLocked(void) {}
static _Atomic BOOL MacWSAppInputSynchronousTrackingActive;
static void (*MacWSOriginalMenuTrackingRunLoop)(id, SEL, id);
static void MacWSWithSynchronousInputTracking(void (^delivery)(void));
static int calls;
static BOOL raiseException;
static void original(id self, SEL command, id mode) {
    assert([self isEqual:@"owner"] && [mode isEqual:@"mode"]);
    assert(command == @selector(description));
    assert(atomic_load(&MacWSAppInputSynchronousTrackingActive));
    calls++;
    MacWSWithSynchronousInputTracking(^{
        assert(atomic_load(&MacWSAppInputSynchronousTrackingActive));
    });
    assert(atomic_load(&MacWSAppInputSynchronousTrackingActive));
    @try {
        MacWSWithSynchronousInputTracking(^{
            @throw [NSException exceptionWithName:@"nested" reason:nil userInfo:nil];
        });
    } @catch (NSException *exception) {
        assert([exception.name isEqual:@"nested"]);
    }
    assert(atomic_load(&MacWSAppInputSynchronousTrackingActive));
    if (raiseException) @throw [NSException exceptionWithName:@"test" reason:nil userInfo:nil];
}
''' + wrapper + r'''
int main(void) { @autoreleasepool {
    MacWSOriginalMenuTrackingRunLoop = original;
    for (int previous = 0; previous < 2; previous++) {
        for (int throwing = 0; throwing < 2; throwing++) {
            atomic_store(&MacWSAppInputSynchronousTrackingActive, previous);
            raiseException = throwing; int caught = 0;
            @try { MacWSMenuTrackingRunLoop(@"owner", @selector(description), @"mode"); }
            @catch (NSException *exception) { caught++; }
            assert(caught == throwing);
            assert(atomic_load(&MacWSAppInputSynchronousTrackingActive) == previous);
        }
    }
    assert(calls == 4); return 0;
}}
'''
        with tempfile.TemporaryDirectory() as directory:
            source = pathlib.Path(directory) / 'menu.m'
            binary = pathlib.Path(directory) / 'menu'
            source.write_text(harness)
            subprocess.run(['xcrun', 'clang', '-Wall', '-Wextra', '-Werror',
                            '-framework', 'Foundation', str(source), '-o',
                            str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
