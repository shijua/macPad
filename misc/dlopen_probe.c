// Minimal one-shot loader diagnostic for an exact dylib path.

#include <dlfcn.h>
#include <stdio.h>
#include <stdbool.h>
#include <string.h>

extern bool dlopen_preflight(const char *path);

int main(int argc, char **argv) {
    bool preflight = argc == 3 && strcmp(argv[1], "--preflight") == 0;
    if (argc != 2 && !preflight) {
        fprintf(stderr, "usage: %s [--preflight] /path/to/image.dylib\n", argv[0]);
        return 64;
    }
    const char *path = argv[preflight ? 2 : 1];
    if (preflight) {
        dlerror();
        bool accepted = dlopen_preflight(path);
        const char *error = dlerror();
        printf("dlopen_preflight path=%s accepted=%d error=%s\n", path,
               accepted, error ? error : "none");
        return accepted ? 0 : 1;
    }
    dlerror();
    void *image = dlopen(path, RTLD_NOW | RTLD_LOCAL);
    const char *error = dlerror();
    printf("dlopen path=%s image=%p error=%s\n", path, image,
           error ? error : "none");
    return image ? 0 : 1;
}
