"""Exercise the actual bridge admission function with kernel query results."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MapBridgeAdmission(unittest.TestCase):
    def test_kernel_ports_and_failed_queries_remain_native(self):
        source = (ROOT / 'libmachook/mac_hooks.m').read_text()
        start = source.index('typedef kern_return_t (*MacWSKernelObjectQuery)')
        end = source.index('static bool macws_core_services_bridge_map(', start)
        admission = source[start:end]
        harness = r'''
#include <stdbool.h>
#include <stdio.h>
#include <assert.h>
typedef int kern_return_t, ipc_space_read_t, dispatch_once_t;
typedef unsigned mach_port_name_t, mach_port_t;
#define KERN_SUCCESS 0
#define KERN_NOT_SUPPORTED 46
#define STDERR_FILENO 2
#define RTLD_DEFAULT 0
static int query_result;
static unsigned query_kind;
static bool query_available = true;
static int query(int task, unsigned port, unsigned *kind, unsigned *address) {
 assert(task == 7 && port == 42);
 *kind=query_kind; *address=0;
 return query_result;
}
static void *dlsym(void *scope, const char *name) {
 (void)scope; (void)name;
 return query_available ? (void *)query : 0;
}
// Re-run lookup so the same compiled function also covers an absent API.
#define dispatch_once(token, block) ((void)(token), (block)())
static int mach_task_self(void) { return 7; }
static int getpid(void) { return 100; }
static bool macws_runtime_diagnostics_enabled(void) { return false; }
'''+admission+r'''
int main(void) {
 query_result=0; query_kind=0;
 assert(macws_core_services_is_map_bridge_port(42));
 query_kind=2;
 assert(!macws_core_services_is_map_bridge_port(42));
 query_kind=28;
 assert(!macws_core_services_is_map_bridge_port(42));
 query_kind=0; query_result=5;
 assert(!macws_core_services_is_map_bridge_port(42));
 query_available=false;
 assert(!macws_core_services_is_map_bridge_port(42));
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as folder:
            code = Path(folder) / 'admission.c'
            executable = Path(folder) / 'admission'
            code.write_text(harness)
            subprocess.run(['cc', '-fblocks', '-Wall', '-Werror', str(code),
                            '-o', str(executable)], check=True,
                           capture_output=True, text=True)
            subprocess.run([str(executable)], check=True,
                           capture_output=True, text=True)


if __name__ == '__main__':
    unittest.main()
