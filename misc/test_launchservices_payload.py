import struct
import unittest

from misc.prepare_launchservices_payload import SONOMA_UUID, convert


def fixture():
    pagezero = struct.pack("<II16s4Q4I", 0x19, 72, b"__PAGEZERO",
                           0, 0x100000000, 0, 0, 0, 0, 0, 0)
    text = struct.pack("<II16s4Q4I", 0x19, 152, b"__TEXT",
                       0x100000000, 4096, 0, 4096, 5, 5, 1, 0)
    section = struct.pack("<16s16sQQ8I", b"__text", b"__TEXT",
                          0x100000400, 3072, 1024, 2, 0, 0, 0, 0, 0, 0)
    uuid = struct.pack("<II16s", 0x1b, 24, SONOMA_UUID)
    main = struct.pack("<IIQQ", 0x80000028, 24, 1024, 0)
    commands = pagezero + text + section + uuid + main
    data = bytearray(4096)
    data[:32] = struct.pack("<8I", 0xfeedfacf, 0x100000c, 2, 2,
                            4, len(commands), 0x200085, 0)
    data[32:32 + len(commands)] = commands
    data[1024:] = bytes([0xa5]) * 3072
    return data


class LaunchServicesPayload(unittest.TestCase):
    def test_conversion_preserves_code_and_entry(self):
        source = fixture()
        result = convert(source)
        self.assertEqual(len(result), len(source))
        self.assertEqual(result[1024:], source[1024:])
        self.assertEqual(struct.unpack_from("<I", result, 12)[0], 6)
        self.assertEqual(struct.unpack_from("<I", result, 16)[0], 5)
        self.assertEqual(struct.unpack_from("<I", result, 24)[0] & 0x200000, 0)
        identity_size = struct.unpack_from("<I", result, 36)[0]
        self.assertEqual(struct.unpack_from("<QQ", result, 32 + identity_size + 24),
                         (0xffffc000, 0x4000))
        self.assertEqual(result[32 + identity_size + 248:32 + identity_size + 272],
                         source[32 + 248:32 + 272])

    def test_rejects_unknown_image_and_architecture(self):
        for offset in (0, 4, 8, 12, 32 + 224 + 8):
            source = fixture()
            source[offset] ^= 1
            with self.assertRaises(ValueError):
                convert(source)

    def test_rejects_bad_bounds_and_nonzero_padding(self):
        for offset, value in ((20, 4096), (36, 0), (32 + 72 + 64, 2)):
            source = fixture()
            struct.pack_into("<I", source, offset, value)
            with self.assertRaises(ValueError):
                convert(source)
        source = fixture()
        source[32 + 272] = 1
        with self.assertRaises(ValueError):
            convert(source)

    def test_rejects_repeated_conversion(self):
        with self.assertRaises(ValueError):
            convert(convert(fixture()))


if __name__ == "__main__":
    unittest.main()
