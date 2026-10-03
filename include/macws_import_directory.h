#ifndef MACWS_IMPORT_DIRECTORY_H
#define MACWS_IMPORT_DIRECTORY_H

#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

// Repair the directory itself, never a symlink target or imported contents.
static inline int macws_prepare_import_directory(const char *path,
                                                 uid_t owner, gid_t group) {
    if (mkdir(path, 0770) != 0 && errno != EEXIST) return -1;
    int descriptor = open(path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (descriptor < 0) return -1;
    int result = fchown(descriptor, owner, group);
    if (result == 0) result = fchmod(descriptor, 0770);
    int saved = errno;
    close(descriptor);
    errno = saved;
    return result;
}

#endif
