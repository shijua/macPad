// Read-only witness for the actual native compiler target-constructor ABI.
#include <dlfcn.h>
#include <mach-o/loader.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static int observe(const char *path, const char *symbol) {
    void *image = dlopen(path, RTLD_NOW | RTLD_LOCAL);
    if (!image) { fprintf(stderr, "%s\n", dlerror()); return 1; }
    void *entry = dlsym(image, symbol);
    Dl_info info = {0};
    if (!entry || !dladdr(entry, &info)) return 2;
    const struct mach_header_64 *header = info.dli_fbase;
    if (header->magic != MH_MAGIC_64 || header->sizeofcmds > 1048576) return 3;
    const uint8_t *cursor = (const void *)(header + 1);
    const uint8_t *end = cursor + header->sizeofcmds;
    printf("COMPILER-TARGET symbol=%s image=%s offset=0x%llx\n", symbol, info.dli_fname,
        (unsigned long long)((uintptr_t)entry - (uintptr_t)header));
    for (uint32_t i = 0; i < header->ncmds && cursor + 8 <= end; i++) {
        const struct load_command *command = (const void *)cursor;
        if (command->cmdsize < 8 || command->cmdsize > (size_t)(end - cursor)) return 3;
        if (command->cmd == LC_UUID && command->cmdsize >= sizeof(struct uuid_command)) {
            const struct uuid_command *uuid = (const void *)cursor;
            printf("COMPILER-TARGET uuid=");
            for (unsigned j = 0; j < 16; j++) printf("%02x", uuid->uuid[j]);
            puts("");
        }
        cursor += command->cmdsize;
    }
    uint32_t words[16];
    memcpy(words, entry, sizeof(words));
    printf("COMPILER-TARGET instructions=");
    for (unsigned i = 0; i < 16; i++) printf("%s%08x", i ? " " : "", words[i]);
    puts("");
    return 0;
}

int main(void) {
    int result = observe("/System/Library/PrivateFrameworks/GPUCompiler.framework/Libraries/libGPUCompilerImpl.dylib",
        "_ZN7metalfe11GPUCompiler22getDefaultTargetTripleEN4llvm8OptionalINS1_5MachO12PlatformTypeEEE");
    if (result) return result;
    result = observe("/System/Library/PrivateFrameworks/GPUCompiler.framework/Libraries/libComposeFilters.dylib",
        "composeImageFilterFunctionsFromModulesSPI");
    if (result) return result;
    result = observe("/usr/lib/libLLVM.dylib", "LLVMGetTarget");
    if (result) return result;
    return observe("/usr/lib/libLLVM.dylib", "LLVMSetTarget");
}
