"""Run the exact responsibility adapter with controlled kernel responses."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class ResponsibilityCompatibility(unittest.TestCase):
    def test_kernel_blob_lengths_and_optional_absence(self):
        source = (ROOT / 'libmachook/Compatibility/MacWSResponsibilityIdentity.c').read_text()
        functions = source[source.index('static uint32_t blob_length('):source.index('static void *macws_attribution(')]
        harness = r"""
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stddef.h>
#include <sys/types.h>
#include <string.h>
typedef struct { unsigned val[8]; } audit_token_t;
static int result, code;
static int csops_audittoken(pid_t pid,unsigned op,void *buf,size_t size,audit_token_t *token) {
 errno=code; return result;
}
"""
        main = r"""
int main(void) {
 audit_token_t token={{0}}; unsigned char buffer[32]={0};
 buffer[7]=16;
 assert(read_blob(&token,7,buffer,sizeof(buffer),0)==8);
 buffer[7]=7;
 assert(read_blob(&token,7,buffer,sizeof(buffer),0)==SIZE_MAX);
 buffer[7]=33;
 assert(read_blob(&token,7,buffer,sizeof(buffer),0)==SIZE_MAX);
 result=-1; code=ENOENT;
 assert(read_blob(&token,14,buffer,sizeof(buffer),1)==0);
 assert(read_blob(&token,11,buffer,sizeof(buffer),0)==SIZE_MAX);
 code=EPERM;
 assert(read_blob(&token,7,buffer,sizeof(buffer),1)==SIZE_MAX);
 return 0;
}
"""
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            (path/'test.c').write_text(harness+functions+main)
            subprocess.run(['clang',str(path/'test.c'),'-o',str(path/'test')],check=True)
            subprocess.run([str(path/'test')],check=True)

    def test_only_verified_live_identity_can_replace_missing_policy(self):
        source = (ROOT / 'libmachook/mac_hooks.m').read_text()
        adapter = source[source.index('static int macws_responsible_token('):
                         source.index('static void macws_install_responsibility_compatibility')]
        harness = r'''
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#define ENOPOLICY 103
#define MACH_PORT_NULL 0
#define KERN_SUCCESS 0
#define TASK_AUDIT_TOKEN 15
#define TASK_AUDIT_TOKEN_COUNT 8
struct token { uint32_t val[8]; };
typedef struct token audit_token_t;
typedef int mach_port_t;
typedef int kern_return_t;
typedef unsigned mach_msg_type_number_t;
typedef int *task_info_t;
static audit_token_t kernel_token;
static int kernel_status, original_result=-1, original_errno=103;
static int mach_task_self(void) { return 1; }
static int task_name_for_pid(int self,int pid,int *task) { *task=4; return kernel_status; }
static int task_info(int task,int flavor,int *info,unsigned *count) {
 memcpy(info,&kernel_token,sizeof(kernel_token)); return kernel_status;
}
static void mach_port_deallocate(int self,int task) {}
static int original(const audit_token_t *a,audit_token_t *b,void *c,void *d) {
 errno=original_errno; return original_result;
}
static int (*macws_original_responsible_token)(const audit_token_t *,audit_token_t *,void *,void *)=original;
'''
        main = r'''
int main(void) {
 audit_token_t input={{0,0,0,0,0,123,0,7}}, output={{0}};
 kernel_token=input;
 assert(macws_responsible_token(&input,&output,0,0)==0);
 assert(memcmp(&input,&output,sizeof(input))==0);
 kernel_token.val[7]++;
 assert(macws_responsible_token(&input,&output,0,0)==-1 && errno==103);
 kernel_token=input; kernel_status=5;
 assert(macws_responsible_token(&input,&output,0,0)==-1 && errno==103);
 kernel_status=0;
 assert(macws_responsible_token(&input,&output,&input,0)==-1);
 assert(macws_responsible_token(&input,&output,0,&input)==-1);
 original_errno=EPERM;
 assert(macws_responsible_token(&input,&output,0,0)==-1 && errno==EPERM);
 original_result=0;
 assert(macws_responsible_token(&input,&output,0,0)==0);
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            (path/'test.c').write_text(harness+adapter+main)
            subprocess.run(['clang',str(path/'test.c'),'-o',str(path/'test')],check=True)
            subprocess.run([str(path/'test')],check=True,capture_output=True)

if __name__ == '__main__': unittest.main()
