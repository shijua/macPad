"""Exercise the actual xpc_main transport adapter and its identity guards."""
from pathlib import Path
import subprocess
import plistlib
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AccountPolicyLaunch(unittest.TestCase):
    def test_service_jobs_have_private_ports_and_start_before_terminal(self):
        services = []
        for name in ('accountpolicy', 'opendirectory'):
            p = ROOT / f'layout/usr/macOS/LaunchDaemons/com.macwsguide.{name}.plist'
            job = plistlib.loads(p.read_bytes())
            self.assertEqual(job['EnvironmentVariables']['XPC_SERVICE_NAME'], job['Label'])
            self.assertEqual(job['ProgramArguments'][1:4], ['0', '0', '/var/mnt/rootfs'])
            self.assertFalse(job['KeepAlive'])
            services += list(job['MachServices'])
        self.assertEqual(len(services), 8)
        self.assertTrue(all(name.startswith('com.macwsguide.od.') for name in services))
        gui = (ROOT / 'layout/usr/macOS/bin/macos_gui.sh').read_text()
        start = gui.index('if [ "$WANT_TERMINAL" = 1 ]; then', gui.index('start_macos() {'))
        self.assertLess(gui.index('start_macos_directory_services || return 1', start),
                        gui.index('launchctl load "$TERM_PLIST"', start))

    def test_directory_start_stops_when_policy_load_fails(self):
        gui = (ROOT / 'layout/usr/macOS/bin/macos_gui.sh').read_text()
        start = gui.index('start_macos_directory_services() {')
        end = gui.index('\n}\n', start) + 2
        function = gui[start:end]
        harness = r'''
ACCOUNT_POLICY_PLIST="$1"
OPENDIRECTORY_PLIST="$2"
launchctl() {
 if [ "$1" = list ]; then return 1; fi
 echo "LOAD:$2"
 [ "${DENY:-0}" = 0 ]
}
launchd_job_pid() { echo 123; }
kill() { return 0; }
log() { :; }
'''
        with tempfile.TemporaryDirectory() as directory:
            policy, od = [Path(directory) / n for n in ('policy', 'od')]
            policy.touch()
            od.touch()
            for deny in (0, 1):
                result = subprocess.run(['bash', '-c', harness + function +
                    f'\nDENY={deny}\nstart_macos_directory_services\n',
                    'directory-start', str(policy), str(od)], capture_output=True, text=True)
                self.assertEqual(result.returncode, deny)
                expected = [f'LOAD:{policy}'] + ([f'LOAD:{od}'] if not deny else [])
                self.assertEqual(result.stdout.splitlines(), expected)

    def test_stock_handler_is_retained_only_for_the_managed_root_helper(self):
        source = (ROOT / 'libmachook/mac_hooks.m').read_text()
        start = source.index('void macws_xpc_main(xpc_connection_handler_t handler) {')
        end = source.index('\n}\n', start) + 2
        function = source[start:end]
        harness = r'''
#include <string.h>
#include <setjmp.h>
#include <assert.h>
typedef void *xpc_connection_t;
typedef void *xpc_object_t;
typedef void (^xpc_connection_handler_t)(xpc_connection_t);
#define XPC_CONNECTION_MACH_SERVICE_LISTENER 1
#define XPC_TYPE_CONNECTION ((void *)1)
#define VIEWBRIDGE_AUXILIARY_NEW "viewbridge"
#define EXTENSIONKIT_SERVICE_NEW "extensionkit"
#define HISERVICES_SERVICE_NEW "hiservices"
#define AUTHD_SERVICE_NEW "authd"
#define QUICKLOOK_SATELLITE_NEW "quicklook"
static const char *program, *service, *endpoint;
static int privileged=1, called;
static jmp_buf finish;
static const char *getprogname(void) { return program; }
static char *getenv(const char *key) { (void)key; return (char *)service; }
static int getuid(void) { return privileged ? 0 : 501; }
static int geteuid(void) { return getuid(); }
static int macws_install_qlsatellite_connection_owner(void) { return 1; }
static void *dispatch_get_main_queue(void) { return 0; }
static xpc_connection_t macws_xpc_connection_create_mach_service_raw(
 const char *name, void *queue, unsigned flags) {
 (void)queue; assert(flags==1); endpoint=name; return (void *)1;
}
static void *xpc_get_type(xpc_object_t object) { (void)object; return XPC_TYPE_CONNECTION; }
static void xpc_connection_set_event_handler(xpc_connection_t c, void (^handler)(xpc_object_t)) { handler(c); }
static void xpc_connection_resume(xpc_connection_t c) { assert(c); }
static void dispatch_main(void) { longjmp(finish,2); }
static void macws_xpc_main_raw(xpc_connection_handler_t handler) { (void)handler; longjmp(finish,1); }
'''
        main = r'''
int main(void) {
 const char *programs[]={"com.apple.AccountPolicyHelper","other","com.apple.AccountPolicyHelper","com.apple.AccountPolicyHelper"};
 const char *services[]={"com.macwsguide.accountpolicy","com.macwsguide.accountpolicy","other","com.macwsguide.accountpolicy"};
 for(int i=0;i<4;i++) {
  program=programs[i];service=services[i];privileged=i!=3;endpoint=0;called=0;
  int result=setjmp(finish);
  if(!result)macws_xpc_main(^(xpc_connection_t c){assert(c);called++;});
  if(i==0){assert(result==2&&called==1);assert(!strcmp(endpoint,"com.macwsguide.od.accountpolicy"));}
  else assert(result==1&&called==0&&!endpoint);
 }
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'adapter.c'
            binary = Path(directory) / 'adapter'
            path.write_text(harness + function + main)
            subprocess.run(['xcrun', 'clang', '-fblocks', str(path), '-o', str(binary)], check=True, capture_output=True)
            subprocess.run([str(binary)], check=True, capture_output=True)


if __name__ == '__main__':
    unittest.main()
