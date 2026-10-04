"""Execute the real exact-reservation helper and production allocator wrapper."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'libmachook/Compatibility/MacWSElectronPageAllocator.c'


def function(source, name):
    start = source.rindex('static void *' + name + '(')
    brace = source.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


@unittest.skipUnless(shutil.which('cc'), 'C compiler required')
class ExactReservationContract(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'darwin', 'Mach VM required')
    def test_private_data_page_preserves_bytes_and_read_only_permission(self):
        source = SOURCE.read_text()
        start = source.index('static kern_return_t replacePrivateDataPage(')
        brace = source.index('{', start)
        depth, end = 1, brace + 1
        while depth:
            depth += (source[end] == '{') - (source[end] == '}')
            end += 1
        helper = source[start:end]
        harness = r'''
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <assert.h>
typedef void *(*MacWSPageAllocate)(void *,void *,size_t,size_t,int);
static _Atomic(MacWSPageAllocate) originalAllocate;
static void *allocatePages(void *a,void *b,size_t c,size_t d,int e) {
  (void)a;(void)c;(void)d;(void)e;return b;
}
static void *original(void *a,void *b,size_t c,size_t d,int e) {
  (void)a;(void)c;(void)d;(void)e;return b;
}
HELPER
int main(void) {
  size_t size=(size_t)getpagesize();vm_address_t page=0;
  assert(vm_allocate(mach_task_self(),&page,size,VM_FLAGS_ANYWHERE)==0);
  memset((void *)page,0x5a,size);
  MacWSPageAllocate *slot=(void *)(page+128);*slot=original;
  unsigned char *snapshot=malloc(size);memcpy(snapshot,(void *)page,size);
  assert(vm_protect(mach_task_self(),page,size,false,VM_PROT_READ)==0);
  assert(replacePrivateDataPage(page,size,slot,allocatePages,VM_PROT_READ)!=0);
  assert(!atomic_load(&originalAllocate));
  assert(memcmp(snapshot,(void *)page,size)==0);
  assert(replacePrivateDataPage(page,size,slot,original,VM_PROT_READ)==0);
  *(MacWSPageAllocate *)(snapshot+128)=allocatePages;
  assert(memcmp(snapshot,(void *)page,size)==0);
  assert(atomic_load(&originalAllocate)==original);
  vm_address_t region=page;vm_size_t regionSize=0;
  vm_region_basic_info_data_64_t info={0};mach_port_t object=MACH_PORT_NULL;
  mach_msg_type_number_t count=VM_REGION_BASIC_INFO_COUNT_64;
  assert(vm_region_64(mach_task_self(),&region,&regionSize,
    VM_REGION_BASIC_INFO_64,(vm_region_info_t)&info,&count,&object)==0);
  if(object)mach_port_deallocate(mach_task_self(),object);
  assert(info.protection==VM_PROT_READ);
  vm_deallocate(mach_task_self(),page,size);free(snapshot);
  puts("PRIVATE DATA COPY PASS: exact bytes, mismatch unchanged, read-only");
}
'''.replace('HELPER', helper)
        with tempfile.TemporaryDirectory(prefix='macws-data-copy-') as directory:
            path = Path(directory) / 'copy.c'
            path.write_text(harness)
            binary = Path(directory) / 'copy'
            compiled = subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra',
                '-Werror', str(path), '-o', str(binary)], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn('PRIVATE DATA COPY PASS', run.stdout)

    def test_actual_helper_and_wrapper_success_fallback_guards_and_errno(self):
        wrapper = function(SOURCE.read_text(), 'allocatePages')
        harness = r'''
#include "macws_electron_page_allocator.h"
#include <assert.h>
#include <stdatomic.h>
#include <stdio.h>
typedef void *(*MacWSPageAllocate)(void *,void *,size_t,size_t,int);
static _Atomic(MacWSPageAllocate) originalAllocate;
static unsigned reservations, releases, fallbacks;
static void *mapResult, *lastHint, *lastUnmapped;
static size_t lastSize, lastUnmappedSize;
static int releaseError;
static void *reservePages(void *hint,size_t size) {
  ++reservations; lastHint=hint; lastSize=size; errno=ENOMEM; return mapResult;
}
static int releasePages(void *address,size_t size) {
  ++releases; lastUnmapped=address; lastUnmappedSize=size;
  if (releaseError) {errno=EIO;return -1;} return 0;
}
static void *fallback(void *self,void *hint,size_t size,size_t alignment,int permission) {
  ++fallbacks; assert(self==(void *)0x111); assert(hint==lastHint);
  assert(size==lastSize); assert(alignment==8192); assert(permission==0);
  assert(errno==EDOM); errno=EAGAIN; return (void *)0x777;
}
#define getpagesize() 4096
#define munmap releasePages
WRAPPER
#undef munmap
#undef getpagesize
static void reset(void *answer) {
  reservations=releases=fallbacks=0; releaseError=0; mapResult=answer;
  lastHint=lastUnmapped=NULL; lastSize=lastUnmappedSize=0; errno=EDOM;
}
static void rejected(void *hint,size_t size,size_t alignment,int permission,size_t page) {
  void *out=(void *)0x123;reset((void *)0x10000);
  assert(!MacWSElectronTryExactReservation(hint,size,alignment,permission,page,
    reservePages,releasePages,&out));
  assert(out==(void *)0x123 && !reservations && !releases && errno==EDOM);
}
int main(void) {
  atomic_store(&originalAllocate,fallback);
  reset((void *)0xe00000000ULL);
  void *out=NULL;
  assert(MacWSElectronTryExactReservation((void *)0xe00000000ULL,1ULL<<32,
    1ULL<<33,0,16384,reservePages,releasePages,&out));
  assert(out==(void *)0xe00000000ULL && lastSize==(1ULL<<32));
  assert(reservations==1 && !releases && errno==EDOM);
  reset((void *)0x20000);
  out=allocatePages((void *)0x111,(void *)0x10000,4096,8192,0);
  assert(out==(void *)0x20000 && reservations==1 && !releases && !fallbacks);
  assert(lastHint==(void *)0x10000 && lastSize==4096 && errno==EDOM);
  reset((void *)(intptr_t)-1);
  assert(allocatePages((void *)0x111,(void *)0x10000,4096,8192,0)==(void *)0x777);
  assert(reservations==1 && !releases && fallbacks==1 && errno==EAGAIN);
  reset((void *)0x11000);
  assert(allocatePages((void *)0x111,(void *)0x10000,4096,8192,0)==(void *)0x777);
  assert(reservations==1 && releases==1 && fallbacks==1);
  assert(lastUnmapped==(void *)0x11000 && lastUnmappedSize==4096);
  reset(NULL);
  assert(allocatePages((void *)0x111,(void *)0x10000,4096,8192,0)==(void *)0x777);
  assert(releases==1 && lastUnmapped==NULL && fallbacks==1);
  reset((void *)0x11000); releaseError=1;
  assert(allocatePages((void *)0x111,(void *)0x10000,4096,8192,0)==NULL);
  assert(releases==1 && !fallbacks && errno==EIO);
  rejected(NULL,4096,8192,0,4096);
  rejected((void *)0x11000,4096,8192,0,4096);
  rejected((void *)0x10000,0,8192,0,4096);
  rejected((void *)0x10000,4097,8192,0,4096);
  rejected((void *)0x10000,4096,0,0,4096);
  rejected((void *)0x10000,4096,4095,0,4096);
  rejected((void *)0x10000,4096,2048,0,4096);
  rejected((void *)0x10000,4096,8192,0,0);
  rejected((void *)0x10000,4096,8192,0,4095);
  rejected((void *)0x10000,4096,8192,1,4096);
  rejected((void *)0x10000,4096,8192,3,4096);
  rejected((void *)(UINTPTR_MAX-8191),8192,8192,0,4096);
  assert(!MacWSElectronTryExactReservation((void *)0x10000,4096,8192,0,4096,
    reservePages,releasePages,NULL));
  puts("ELECTRON PAGE ALLOCATOR CONTRACT PASS: real-size, exact-or-aligned, original fallback, guards, errno, no leak");
}
'''.replace('WRAPPER', wrapper)
        with tempfile.TemporaryDirectory(prefix='macws-electron-allocator-') as directory:
            source = Path(directory) / 'contract.c'
            source.write_text(harness)
            binary = Path(directory) / 'contract'
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-I' + str(ROOT/'include'), str(source), '-o', str(binary)],
                           check=True, capture_output=True, text=True)
            result = subprocess.run([str(binary)], check=True, capture_output=True,
                                    text=True, timeout=5)
            self.assertIn('ELECTRON PAGE ALLOCATOR CONTRACT PASS', result.stdout)

    def test_scoped_data_only_install_and_default_packaging(self):
        source = SOURCE.read_text()
        self.assertIn('Compatibility/MacWSElectronPageAllocator.c', (ROOT/'libmachook/Makefile').read_text())
        self.assertIn('!version140 && (!nodeMode || strcmp(nodeMode, "1"))', source)
        self.assertIn('strcmp(name, "Code Helper (Plugin)")', source)
        self.assertIn('0x4c,0x4c,0x44,0x42,0x55,0x55,0x31,0x44', source)
        self.assertIn('memcmp(base + thunkOffset, version140 ? thunk140 : thunk', source)
        self.assertIn('version140 ? 0xb18ff28 : 0xac8b748', source)
        self.assertIn('if (*slot != expected) return;', source)
        self.assertIn('info.protection & VM_PROT_EXECUTE', source)
        self.assertIn('_dyld_register_func_for_add_image(imageAdded)', source)
        self.assertNotIn('MSHookFunction', source)
        self.assertNotIn('MAP_FIXED', source)
        self.assertNotIn('getenv("MACWS_', source)


if __name__ == '__main__':
    unittest.main()
