"""Verify Sonoma's extra Flush argument and outermost submission boundary."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SonomaSubmission(unittest.TestCase):
    def test_profile_against_actual_sonoma_images(self):
        import struct
        artifacts = ROOT / 'tmp/sonoma-14.0/re-frameworks'
        if not all((artifacts / n).is_file() for n in
                   ('QuartzCore', 'IOMobileFramebuffer', 'SkyLight')):
            self.skipTest('requires extracted 23A344 images')
        code = r'''#include <stdio.h>
#include "macws_display_profiles.h"
int main(void) {
 const struct macws_quartzcore_display_profile *q=&macws_qc_sonoma;
 const struct macws_iomfb_display_profile *f=&macws_iomfb_sonoma;
 printf("%x %x %x %x %llx %x %x %x %x %x %x %x %x %x %x",
 q->enable_tags,q->callback,q->framebuffer,q->flags,
 (unsigned long long)q->enabled_mask,q->pending_begin,q->pending_end,
 q->begin_update,q->finish_update,f->swap_end_wrapper,f->dispatch_load,
 f->submit,f->submit_instruction,f->swap_struct_size,f->swap_id);
 return 0;
}'''
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder); (p/'profile.c').write_text(code)
            subprocess.run(['cc','-I',str(ROOT/'include'),str(p/'profile.c'),
                            '-o',str(p/'profile')],check=True,capture_output=True)
            values=[int(x,16) for x in subprocess.check_output(
                [str(p/'profile')],text=True).split()]
        enable,callback,fb,flags,mask,pb,pe,begin,finish,wrapper,dispatch,submit,bl,size,swapid=values
        def reader(name):
            b=(artifacts/name).read_bytes(); o=32; segments=[]; uid=None
            for _ in range(struct.unpack_from('<I',b,16)[0]):
                cmd,n=struct.unpack_from('<II',b,o)
                if cmd==25: segments.append(struct.unpack_from('<QQQQ',b,o+24))
                if cmd==27: uid=b[o+8:o+24]
                o+=n
            def words(offset,count=1):
                va=segments[0][0]+offset
                v,_,f,n=next(x for x in segments if x[0]<=va and va+4*count<=x[0]+x[3])
                return struct.unpack_from('<'+'I'*count,b,f+va-v)
            return uid,words
        uid,words=reader('QuartzCore')
        self.assertEqual(uid.hex(),'dce2edb3c71339f98af63102f2b9b695')
        self.assertEqual(words(enable,4),(0xd503237f,0xd10243ff,0xa9036ffc,0xa90467fa))
        self.assertEqual(words(callback,4),(0xd503237f,0xd106c3ff,0x6d1423e9,0xa9156ffc))
        for offset in (begin,finish):
            self.assertEqual(words(offset,4),(0xd503237f,0xa9be4ff4,0xa9017bfd,0x910043fd))
        self.assertEqual(words(enable+0x84)[0],0xf9400100|((fb//8)<<10))
        self.assertEqual((words(0x31b428)[0]>>5)&0xffff,flags)
        self.assertEqual(words(0x31b434)[0],0xd2c0000b|((mask>>32)<<5))
        self.assertEqual(words(0x2ff1bc)[0],0xf9400278|((pb//8)<<10))
        self.assertEqual(words(0x2ff1c0)[0],0xf9400268|((pe//8)<<10))
        uid,words=reader('IOMobileFramebuffer')
        self.assertEqual(uid.hex(),'38690b381faa321189d21a8a2d0424eb')
        self.assertEqual(words(wrapper,4),(0xb4000080,dispatch,0xb4000041,0xd61f083f))
        self.assertEqual(words(submit)[0],bl)
        self.assertEqual(words(submit-12)[0],0x52800003|(size<<5))
        self.assertEqual(words(0x57c8)[0],0xb9000268|((swapid//4)<<10))

    def test_arguments_and_completed_outermost_update(self):
        source = (ROOT / 'libmachook/mac_hooks.m').read_text()
        start = source.index('typedef void (*EndUpdateSonoma_t)')
        end = source.index('// SkyLight `WSCompositeDestinationCreate', start)
        hook = source[start:end]
        harness = r'''
#include <stdbool.h>
#include <stdint.h>
#include <assert.h>
#include <string.h>
static _Thread_local void *g_macws_last_end_update_metal_context;
static int calls, finishes;
static bool wanted_wait, wanted_option;
static void *wanted_self;
static void original(void *self, bool wait, bool option) {
    assert(self == wanted_self);
    assert(wait == wanted_wait && option == wanted_option);
    calls++;
    if (self) {
        int32_t *depth = (int32_t *)((char *)self + 0x178);
        if (*depth == 1) {
            *(uintptr_t *)((char *)self + 0x68) = 0xfeed;
        }
        if (*depth > 0) --*depth;
    }
}
void macws_vnc_finish_update(void *self) {
    assert(self == wanted_self);
    assert(calls > 0);
    assert(*(int32_t *)((char *)self + 0x178) == 0);
    assert(*(uintptr_t *)((char *)self + 0x68) == 0xfeed);
    assert(g_macws_last_end_update_metal_context == self);
    finishes++;
}
''' + hook + r'''
int main(void) {
    _Alignas(8) unsigned char context[0x200] = {0};
    orig_skylight_end_update_sonoma = original;
    for (int wait = 0; wait < 2; ++wait) {
        for (int option = 0; option < 2; ++option) {
            wanted_self = context;
            wanted_wait = wait; wanted_option = option;
            *(int32_t *)(context + 0x178) = 2;
            g_macws_last_end_update_metal_context = 0;
            int previous = finishes;
            hooked_skylight_end_update_sonoma(context, wait, option);
            assert(finishes == previous);
            assert(g_macws_last_end_update_metal_context == 0);
            hooked_skylight_end_update_sonoma(context, wait, option);
            assert(finishes == previous + 1);
        }
    }
    wanted_self = 0; wanted_wait = true; wanted_option = false;
    int previous = finishes;
    hooked_skylight_end_update_sonoma(0, true, false);
    assert(finishes == previous && calls == 9);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as folder:
            code = Path(folder) / 'submission.c'
            binary = Path(folder) / 'submission'
            code.write_text(harness)
            subprocess.run(['cc', '-std=c11', '-Wall', '-Werror', str(code),
                            '-o', str(binary)], check=True, capture_output=True)
            subprocess.run([str(binary)], check=True, capture_output=True)


if __name__ == '__main__':
    unittest.main()
