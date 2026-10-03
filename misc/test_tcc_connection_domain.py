"""Exercise the actual private TCC lookup policy and preserve other flags."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TCCConnectionDomain(unittest.TestCase):
    def test_private_service_domain(self):
        source = r'''
#include "macws_tcc_connection.h"
#include <xpc/xpc.h>
#include <assert.h>
_Static_assert(XPC_CONNECTION_MACH_SERVICE_PRIVILEGED == 2, "XPC flag ABI");
int main(void) {
    for (uint64_t flags = 0; flags < 16; ++flags) {
        assert(macws_tcc_connection_flags("com.macwsguide.tccd.system", flags)
               == (flags & ~UINT64_C(2)));
        assert(macws_tcc_connection_flags("com.macwsguide.tccd", flags)
               == (flags & ~UINT64_C(2)));
        assert(macws_tcc_connection_flags("com.apple.tccd.system", flags) == flags);
        assert(macws_tcc_connection_flags("com.macwsguide.tccd.other", flags) == flags);
        assert(macws_tcc_connection_flags(NULL, flags) == flags);
    }
}
'''
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            (path / "probe.c").write_text(source)
            subprocess.run(["clang", "-Wall", "-Wextra", "-Werror", "-I",
                            str(ROOT / "include"), str(path / "probe.c"),
                            "-o", str(path / "probe")], check=True)
            subprocess.run([str(path / "probe")], check=True)


if __name__ == "__main__":
    unittest.main()
