"""Compile the ownership boundary guard; unrelated texture calls get no +1."""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class SurfaceOwnership(unittest.TestCase):
    def test_only_plain_surface_constructor_transfers_ownership(self):
        source = '''
#include "macws_skylight_surface_ownership.h"
#include <assert.h>
int main(void) {
    assert(macws_skylight_surface_owner_call(0x5baac));
    assert(!macws_skylight_surface_owner_call(0x5ba9c)); // explicit surface
    assert(!macws_skylight_surface_owner_call(0x5baac - 4));
    assert(!macws_skylight_surface_owner_call(0x5baac + 4));
    assert(!macws_skylight_surface_owner_call(0));
    assert(!macws_skylight_surface_owner_call(UINTPTR_MAX));
}
'''
        with tempfile.TemporaryDirectory() as directory:
            c = pathlib.Path(directory) / "guard.c"
            exe = pathlib.Path(directory) / "guard"
            c.write_text(source)
            subprocess.run(["cc", "-Wall", "-Werror", "-I", str(ROOT / "include"),
                            str(c), "-o", str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    unittest.main()
