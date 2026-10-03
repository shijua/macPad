"""Exercise the production import-directory repair without following links."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ImportDirectory(unittest.TestCase):
    def test_repair_and_reject_non_directories(self):
        source = r'''
#include "macws_import_directory.h"
#include <assert.h>
#include <stdio.h>
int main(int argc, char **argv) {
    assert(argc == 2);
    char directory[1024], link[1024], file[1024];
    snprintf(directory, sizeof(directory), "%s/imports", argv[1]);
    snprintf(link, sizeof(link), "%s/link", argv[1]);
    snprintf(file, sizeof(file), "%s/file", argv[1]);
    assert(macws_prepare_import_directory(directory, getuid(), getgid()) == 0);
    assert(chmod(directory, 0755) == 0);
    assert(macws_prepare_import_directory(directory, getuid(), getgid()) == 0);
    struct stat status;
    assert(stat(directory, &status) == 0 && (status.st_mode & 0777) == 0770);
    assert(symlink(directory, link) == 0);
    assert(chmod(directory, 0755) == 0);
    assert(macws_prepare_import_directory(link, getuid(), getgid()) == -1);
    assert(stat(directory, &status) == 0 && (status.st_mode & 0777) == 0755);
    int fd = open(file, O_CREAT | O_WRONLY, 0600);
    assert(fd >= 0); close(fd);
    assert(macws_prepare_import_directory(file, getuid(), getgid()) == -1);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            (path / "probe.c").write_text(source)
            subprocess.run(["clang", "-Wall", "-Wextra", "-Werror", "-I",
                            str(ROOT / "include"), str(path / "probe.c"),
                            "-o", str(path / "probe")], check=True)
            subprocess.run([str(path / "probe"), temporary], check=True)


if __name__ == "__main__":
    unittest.main()
