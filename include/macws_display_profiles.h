#ifndef MACWS_DISPLAY_PROFILES_H
#define MACWS_DISPLAY_PROFILES_H
#include <stdint.h>

/* RE-confirmed image-specific layouts. All offsets are relative to the
 * loaded image header or the original object; no field is synthesized. */
struct macws_quartzcore_display_profile {
    uint8_t uuid[16];
    uint32_t enable_tags, callback, framebuffer, flags;
    uint64_t enabled_mask;
    uint32_t pending_begin, pending_end, begin_update, finish_update;
};
static const struct macws_quartzcore_display_profile macws_qc_ventura = {
    {0xcf,0x85,0x3b,0xbd,0x01,0xb6,0x3f,0x46,
     0xad,0xa1,0xec,0x70,0xfd,0x2d,0xc9,0xdc},
    0x29285c, 0x29209c, 0x300, 0x9a4, UINT64_C(0x800000000),
    0x510, 0x518, 0x291288, 0x291220,
};
/* 23A344 QuartzCore DCE2EDB3-C713-39F9-8AF6-3102F2B9B695:
 * enable_tags +0x84 loads framebuffer+0x6328; set_frame_info_enabled
 * +0x31b400 writes flags+0x6a34 bit34; collect_frame_info +0x2ff180
 * reads pending +0x6558/+0x6560. begin/finish lock server+0x18/+0x1d8. */
static const struct macws_quartzcore_display_profile macws_qc_sonoma = {
    {0xdc,0xe2,0xed,0xb3,0xc7,0x13,0x39,0xf9,
     0x8a,0xf6,0x31,0x02,0xf2,0xb9,0xb6,0x95},
    0x2c0c90, 0x2c00d8, 0x6328, 0x6a34, UINT64_C(0x400000000),
    0x6558, 0x6560, 0x2bf18c, 0x2bf124,
};
struct macws_iomfb_display_profile {
    uint32_t swap_end_wrapper, dispatch_load, submit, submit_instruction;
    uint32_t swap_struct_size, swap_id;
};
static const struct macws_iomfb_display_profile macws_iomfb_ventura = {
    0x11cc, 0xf9439401, 0x4430, 0x94001f64, 0x46c, 0x68,
};
/* 23A344 UUID38690B38-1FAA-3211-89D2-1A8A2D0424EB. Runtime iOS17
 * userspace independently confirms 0x4fc/+0xb0/dispatch+0x868 and
 * scalar SwapCancel selector0x34 with exactly one input. */
static const uint8_t macws_iomfb_sonoma_uuid[16] = {
    0x38,0x69,0x0b,0x38,0x1f,0xaa,0x32,0x11,
    0x89,0xd2,0x1a,0x8a,0x2d,0x04,0x24,0xeb,
};
static const struct macws_iomfb_display_profile macws_iomfb_sonoma = {
    0x1f84, 0xf9443401, 0x5838, 0x940021c6, 0x4fc, 0xb0,
};
#endif
