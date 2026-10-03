"""Exercise the real Data-root metadata adapter and its vnode guard."""
import pathlib
import subprocess
import tempfile
import unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]

class DataRootMetadataTests(unittest.TestCase):
    def test_exact_alias_identity_and_requested_properties(self):
        source = (ROOT / 'libmachook/Metal_hooks.x').read_text()
        start = source.index('static CFURLRef macws_copy_data_root_provider_url(')
        end = source.index('static id macws_nsurl_get_resources(', start)
        functions = source[start:end]
        fixture = r'''
#import <Foundation/Foundation.h>
#include <sys/stat.h>
#include <sys/param.h>
#include <assert.h>
static BOOL macws_chroot_root_mount_needs_rebase;
static int mode;
static int mock_stat(const char *path, struct stat *s) {
 memset(s,0,sizeof(*s));s->st_mode=S_IFDIR;s->st_dev=2;s->st_ino=3;
 if(mode==2)return -1;
 if(mode==3 && strcmp(path,"/"))s->st_ino=4;
 if(mode==4 && strcmp(path,"/"))s->st_dev=4;
 return 0;
}
static int mock_lstat(const char *p, struct stat *s) {
 (void)p;memset(s,0,sizeof(*s));s->st_mode=mode==1?S_IFDIR:S_IFLNK;return 0;
}
#define stat(p,s) mock_stat(p,s)
#define lstat(p,s) mock_lstat(p,s)
/* FUNCTIONS */
int main(void) { @autoreleasepool {
 CFURLRef url=CFURLCreateFromFileSystemRepresentation(NULL,(const UInt8 *)"/System/Volumes/Data",20,true);
 assert(!macws_copy_data_root_provider_url(url));
 macws_chroot_root_mount_needs_rebase=YES;
 CFURLRef root=macws_copy_data_root_provider_url(url);
 assert(root && CFEqual(CFURLGetString(root),CFSTR("file:///")));CFRelease(root);
 for(mode=1;mode<=4;mode++)assert(!macws_copy_data_root_provider_url(url));
 mode=0;
 CFURLRef other=CFURLCreateFromFileSystemRepresentation(NULL,(const UInt8 *)"/other",6,true);
 assert(!macws_copy_data_root_provider_url(other));CFRelease(other);CFRelease(url);
 assert(!macws_copy_data_root_volume_flag(NULL));
 NSDictionary *without=@{ @"other": @42 };
 assert(!macws_copy_data_root_volume_flag((__bridge CFDictionaryRef)without));
 NSDictionary *input=@{ (__bridge NSString *)kCFURLIsVolumeKey:@NO, @"other":@42 };
 CFDictionaryRef changed=macws_copy_data_root_volume_flag((__bridge CFDictionaryRef)input);
 assert(changed && CFDictionaryGetValue(changed,kCFURLIsVolumeKey)==kCFBooleanTrue);
 assert([input[(__bridge NSString *)kCFURLIsVolumeKey] isEqual:@NO]);
 assert([(__bridge NSDictionary *)changed count]==2);CFRelease(changed);
 }}
'''
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / 'test.m'
            path.write_text(fixture.replace('/* FUNCTIONS */', functions))
            binary = pathlib.Path(td) / 'test'
            subprocess.run(['clang', '-Wall', '-Wextra', '-Werror', str(path),
                            '-framework', 'Foundation', '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True, timeout=5)
