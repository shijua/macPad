#include "MacWSMailSymbolThread.h"
#include <objc/runtime.h>
#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <ptrauth.h>
#include <string.h>

static MacWSMailSymbolFunction macws_mail_symbol_original;
static BOOL macws_mail_symbol_installed;

static id macws_mail_symbol_main_thread(
    id receiver, SEL selector, id name, NSInteger scale, id font, id description) {
    return macws_mail_symbol_on_main_thread(
        macws_mail_symbol_original, receiver, selector, name, scale, font, description);
}

static void macws_install_mail_symbol_thread(void) {
    Class cls = objc_getClass("NSImage");
    SEL selector = sel_registerName(
        "mf_imageWithSystemSymbolName:hintScale:hintFont:accessibilityDescription:");
    Method method = cls ? class_getClassMethod(cls, selector) : NULL;
    if (!method || strcmp(method_getTypeEncoding(method),
                          "@48@0:8@16q24@32@40")) return;
    @synchronized (cls) {
        if (macws_mail_symbol_installed) return;
        Dl_info image = {0};
        void *implementation = ptrauth_strip(
            (void *)method_getImplementation(method), ptrauth_key_function_pointer);
        if (!dladdr(implementation, &image) ||
            !image.dli_fname ||
            !strstr(image.dli_fname, "/MailUI.framework/")) return;
        macws_mail_symbol_original = (MacWSMailSymbolFunction)
            method_setImplementation(method, (IMP)macws_mail_symbol_main_thread);
        macws_mail_symbol_installed = YES;
    }
}

static void macws_mail_symbol_image_added(
    const struct mach_header *header, intptr_t slide) {
    (void)header;
    (void)slide;
    macws_install_mail_symbol_thread();
}

__attribute__((constructor))
static void macws_mail_symbol_thread_constructor(void) {
    const char *program = getprogname();
    if (!program || strcmp(program, "Mail")) return;
    _dyld_register_func_for_add_image(macws_mail_symbol_image_added);
    // Some image callbacks precede ObjC category registration. Retry after
    // startup has completed, before the next main-run-loop interaction.
    dispatch_async(dispatch_get_main_queue(), ^{ macws_install_mail_symbol_thread(); });
}
