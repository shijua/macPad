"""Run the production ABI guard; actual GPU witnesses remain device tests."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SonomaResourceABI(unittest.TestCase):
    def test_exact_image_kernel_selector_and_size(self):
        source = r'''
#include "macws_sonoma_resource_abi.h"
#include <assert.h>
int main(void) {
    uint8_t uuid[16]; memcpy(uuid, MacWSSonomaIOGPUUUID, sizeof(uuid));
    assert(MacWSSonomaResourceABIReady(uuid, "21A329", 9, 104));
    for (unsigned i = 0; i < sizeof(uuid); i++) {
        uuid[i] ^= 1;
        assert(!MacWSSonomaResourceABIReady(uuid, "21A329", 9, 104));
        uuid[i] ^= 1;
    }
    assert(!MacWSSonomaResourceABIReady(uuid, "20D67", 9, 104));
    assert(!MacWSSonomaResourceABIReady(uuid, "21A329x", 9, 104));
    assert(!MacWSSonomaResourceABIReady(NULL, "21A329", 9, 104));
    assert(!MacWSSonomaResourceABIReady(uuid, NULL, 9, 104));
    assert(!MacWSSonomaResourceABIReady(uuid, "21A329", 10, 104));
    assert(!MacWSSonomaResourceABIReady(uuid, "21A329", 9, 96));
    assert(!MacWSSonomaResourceABIReady(uuid, "21A329", 9, 103));
    assert(!MacWSSonomaResourceABIReady(uuid, "21A329", 9, 105));
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix="macws-sonoma-abi-") as tmp:
            binary = str(Path(tmp) / "guard")
            subprocess.run(["cc", "-x", "c", "-std=c11", "-Wall", "-Wextra",
                            "-Werror", "-I", str(ROOT / "include"), "-",
                            "-o", binary], input=source, text=True,
                           check=True, timeout=30)
            subprocess.run([binary], check=True, timeout=10)


if __name__ == "__main__":
    unittest.main()
