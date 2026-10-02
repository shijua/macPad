"""Convert a verified Sonoma arm64e launchservicesd for the existing loader.

The output must be re-signed after conversion. No executable instructions,
section offsets or LC_MAIN entry point are changed.
"""
import argparse
from pathlib import Path
import struct

SONOMA_UUID = bytes.fromhex("57514207f477361ca969d82efd96ab5b")


def convert(data):
    if len(data) < 32:
        raise ValueError("truncated Mach-O header")
    magic, cpu, subtype, kind, count, size, flags, _ = struct.unpack_from("<8I", data)
    if (magic, cpu, subtype & 0xffffff, kind) != (0xfeedfacf, 0x100000c, 2, 2):
        raise ValueError("expected thin arm64e MH_EXECUTE; extract the slice first")
    end = 32 + size
    if end > len(data):
        raise ValueError("truncated load commands")
    offset = 32
    commands = []
    uuid = None
    entry = None
    pagezero = None
    text = None
    first_section = len(data)
    for _ in range(count):
        if offset + 8 > end:
            raise ValueError("truncated load command")
        cmd, length = struct.unpack_from("<II", data, offset)
        if length < 8 or length % 8 or offset + length > end:
            raise ValueError("invalid load command size")
        block = bytearray(data[offset:offset + length])
        if cmd == 0x1b:
            if length != 24:
                raise ValueError("invalid UUID command")
            uuid = bytes(block[8:24])
        elif cmd == 0x80000028:
            if length != 24:
                raise ValueError("invalid main command")
            entry = struct.unpack_from("<Q", block, 8)[0]
        elif cmd == 0xd:
            raise ValueError("input already has LC_ID_DYLIB")
        elif cmd == 0x19:
            if length < 72:
                raise ValueError("truncated segment")
            name = bytes(block[8:24]).rstrip(b"\0")
            vm, span, fileoff, filesize = struct.unpack_from("<4Q", block, 24)
            sections = struct.unpack_from("<I", block, 64)[0]
            if length != 72 + 80 * sections:
                raise ValueError("invalid segment sections")
            if name == b"__PAGEZERO":
                if (vm, span, fileoff, filesize, sections) != (0, 0x100000000, 0, 0, 0):
                    raise ValueError("unexpected PAGEZERO layout")
                pagezero = block
            if name == b"__TEXT":
                text = (vm, fileoff, filesize)
            for index in range(sections):
                section_offset = struct.unpack_from("<I", block, 72 + index * 80 + 48)[0]
                if section_offset:
                    first_section = min(first_section, section_offset)
        commands.append(block)
        offset += length
    if offset != end or uuid != SONOMA_UUID:
        raise ValueError("unsupported image UUID or command bounds")
    if pagezero is None or text is None or text[0:2] != (0x100000000, 0):
        raise ValueError("missing expected TEXT/PAGEZERO layout")
    if entry is None or not first_section <= entry < text[2]:
        raise ValueError("entry point is outside executable file range")
    name = b"launchservicesd_arm64e.dylib\0"
    id_size = (24 + len(name) + 7) & ~7
    if end + id_size > first_section or any(data[end:end + id_size]):
        raise ValueError("insufficient zero header padding")
    identity = struct.pack("<6I", 0xd, id_size, 24, 2, 0x10000, 0x10000)
    identity += name + bytes(id_size - 24 - len(name))
    struct.pack_into("<QQ", pagezero, 24, text[0] - 0x4000, 0x4000)
    result = bytearray(data)
    struct.pack_into("<IIII", result, 12, 6, count + 1, size + id_size,
                     (flags & ~0x200000) | 0x100000)
    result[32:end + id_size] = identity + b"".join(commands)
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = convert(args.source.read_bytes())
    with args.output.open("xb") as output:
        output.write(result)
    args.output.chmod(0o755)


if __name__ == "__main__":
    main()
