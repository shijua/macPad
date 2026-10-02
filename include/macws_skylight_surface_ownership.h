#ifndef MACWS_SKYLIGHT_SURFACE_OWNERSHIP_H
#define MACWS_SKYLIGHT_SURFACE_OWNERSHIP_H
#include <stdbool.h>
#include <stdint.h>

static const uint8_t macws_sonoma_skylight_surface_uuid[16] = {
    0x42, 0xfd, 0x2e, 0x33, 0x2b, 0xb2, 0x37, 0x2f,
    0xa0, 0x1f, 0xb2, 0xb3, 0x6c, 0x82, 0x77, 0xb9
};

// WS::SurfacePool::Acquire's plain-texture call, macOS 14.0 (23A344).
static inline bool macws_skylight_surface_owner_call(uintptr_t offset) {
    return offset == 0x5baac;
}
#endif
