"""Exercise the real fork handshake against accepted and rejected server replies."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include <errno.h>
#include <mach/mach.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>
static int mode, pipes[2][2], pipe_count, killed, reaped, closed, rpc;
static int ProbePipe(int p[2]) {
    if (mode == 3) { errno = EMFILE; return -1; }
    int result = pipe(p);
    if (!result) memcpy(pipes[pipe_count++], p, sizeof(pipes[0]));
    return result;
}
static int ProbeKill(pid_t p, int sig) {
    if (p != 321 || sig != SIGKILL) abort();
    killed++; return 0;
}
static pid_t ProbeWait(pid_t p, int *status, int flags) { reaped++; return p; }
static kern_return_t ProbeBootstrap(task_t t, mach_port_t *p) { *p=999; return 0; }
static mach_port_t ProbeReply(void) { return 888; }
static void ProbeReplyFree(mach_port_t p) {}
static kern_return_t ProbeDealloc(task_t t, mach_port_t p) { return 0; }
static void ProbeDestroy(mach_msg_header_t *p) {}
static mach_msg_return_t ProbeMach(mach_msg_header_t *,mach_msg_option_t,
    mach_msg_size_t,mach_msg_size_t,mach_port_name_t,mach_msg_timeout_t,mach_port_name_t);
#define pipe ProbePipe
#define kill ProbeKill
#define waitpid ProbeWait
#define task_get_bootstrap_port ProbeBootstrap
#define mig_get_reply_port ProbeReply
#define mig_dealloc_reply_port ProbeReplyFree
#define mach_port_deallocate ProbeDealloc
#define mach_msg_destroy ProbeDestroy
#define mach_msg ProbeMach
#include "libmachook/Compatibility/MacWSForkFix.c"
#undef pipe
#undef kill
#undef waitpid
#undef mach_msg
pid_t macws_forkfix_raw_fork(void) {
    if (mode == 4) return 0;
    char token=' ';
    if (write(pipes[0][1],&token,1)!=1) abort();
    return 321;
}
ssize_t macws_forkfix_raw_read(int f,void *b,size_t n) { *(char *)b=' '; return 1; }
ssize_t macws_forkfix_raw_write(int f,const void *b,size_t n) { return write(f,b,n); }
int macws_forkfix_raw_close(int f) { closed++; return close(f); }
void macws_forkfix_raw_exit(int status) { exit(status); }
static mach_msg_return_t ProbeMach(mach_msg_header_t *h,mach_msg_option_t option,
    mach_msg_size_t send,mach_msg_size_t receive,mach_port_name_t port,
    mach_msg_timeout_t timeout,mach_port_name_t notify) {
    rpc++;
    if (timeout!=5000) abort();
    if (option & MACH_SEND_MSG) {
        struct MacWSForkRequest *r=(void *)h;
        if (r->child!=321 || r->message.magic!=UINT64_C(0x444f50414d494e45) ||
            r->message.action!=1 || h->msgh_id!=0x400000ce ||
            send!=sizeof(*r) || h->msgh_remote_port!=999) abort();
    } else {
        struct MacWSForkReply *r=(void *)h;
        memset(r,0,sizeof(*r));
        r->message.header.msgh_size=sizeof(*r);
        r->message.magic=mode==2 ? 0 : UINT64_C(0x444f50414d494e45);
        r->message.action=1;
        r->status=mode==1 ? 2 : 0;
    }
    return 0;
}
int main(int argc,char **argv) {
    mode=atoi(argv[1]); errno=0;
    pid_t result=MacWSForkWithPermissions();
    int e=errno;
    if (mode==0) return !(result==321 && rpc==2 && closed==4 && !killed && !reaped);
    if (mode==1 || mode==2) return !(result==-1 && e==(mode==1?EPERM:EPROTO) &&
        killed==1 && reaped==1 && closed==4 && rpc==2);
    if (mode==3) return !(result==-1 && e==EMFILE && !rpc && !killed);
    if (mode==4) return !(result==0 && !rpc && closed==4);
    return 9;
}
'''


class ForkPermissions(unittest.TestCase):
    def test_handshake_and_failure_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "probe.c"
            binary = Path(directory) / "probe"
            source.write_text(HARNESS)
            subprocess.run(["xcrun", "clang", "-I", str(ROOT), str(source),
                            "-o", str(binary)], check=True, capture_output=True)
            for mode in range(5):
                with self.subTest(mode=mode):
                    result = subprocess.run([str(binary), str(mode)],
                                            timeout=5, capture_output=True)
                    self.assertEqual(result.returncode, 0,
                                     result.stderr.decode(errors="replace"))


if __name__ == "__main__":
    unittest.main()
