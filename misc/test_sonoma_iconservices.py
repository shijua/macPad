"""Run the actual quarantine adapter against controlled API return values."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class QuarantineContract(unittest.TestCase):
    def test_native_results_and_foreign_policy_state(self):
        source = (ROOT / 'libmachook/Metal_hooks.x').read_text()
        start = source.index('typedef int (*macws_qtn_proc_init_with_self_fn)')
        end = source.index('static void macws_install_iconservices_quarantine_fallback', start)
        adapter = source[start:end]
        harness = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <errno.h>
typedef bool BOOL;
static bool macws_runtime_diagnostics_enabled(void) { return false; }
'''+adapter+r'''
static int native_result, native_error;
static uint32_t actual_flags;
static int native_call(void *p) { (void)p; errno=native_error; return native_result; }
static int init(void *p) { (void)p; return 0; }
static int set_flags(void *p, uint32_t f) { (void)p; actual_flags=f; return 0; }
static uint32_t get_flags(void *p) { (void)p; return actual_flags; }
int main(void) {
 g_macws_orig_qtn_proc_init_with_self=native_call;
 g_macws_orig_qtn_proc_apply_to_self=native_call;
 g_macws_orig_qtn_proc_init=init;
 g_macws_orig_qtn_proc_set_flags=set_flags;
 g_macws_qtn_proc_get_flags=get_flags;
 native_result=0; native_error=0;
 assert(macws_qtn_proc_init_with_self(NULL)==0 && errno==0);
 native_result=-2; native_error=22;
 assert(macws_qtn_proc_init_with_self(NULL)==-2 && errno==22);
 native_error=103;
 assert(macws_qtn_proc_init_with_self(NULL)==-2 && errno==93);
 actual_flags=4;
 assert(macws_qtn_proc_apply_to_self(NULL)==-2 && errno==103);
 assert(g_macws_iconservices_emulated_qtn_flags==0);
 actual_flags=6;
 assert(macws_qtn_proc_apply_to_self(NULL)==0 && errno==0);
 actual_flags=0;
 assert(macws_qtn_proc_init_with_self(NULL)==0 && errno==0);
 assert(actual_flags==6);
 native_error=22;
 assert(macws_qtn_proc_init_with_self(NULL)==-2 && errno==22);
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as folder:
            code, executable = Path(folder) / 'contract.c', Path(folder) / 'contract'
            code.write_text(harness)
            subprocess.run(['cc', '-Wall', '-Werror', str(code), '-o', str(executable)], check=True,
                           capture_output=True, text=True)
            subprocess.run([str(executable)], check=True, capture_output=True, text=True)


if __name__ == '__main__':
    unittest.main()
