"""UUID-locked VA geometry port for VS Code 1.140.0 arm64.

RE evidence: docs/evidence/vscode140-20261004.md. Keep the stock checks,
compressed-pointer ABI, and allocator setup; change their geometry together.
Invoke with python3, preserving the original Microsoft framework as input.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

import patch_electron_pa_ios_va as engine

EXPECTED_UUID = "4c4c44e7-5555-3144-a1d4-12c2efa5967e"
EXPECTED_LOGICAL_COUNTS = {
    0xFFFFFFFC00000000: 37037,
    0x00000003FFFFFFFF: 451,
    0xFFFFFFF800000000: 34,
    0x00000007FFFFFFFF: 10,
}
EXPECTED_RETAINED_LOGICAL_COUNTS = {
    0xFFFFFFFC00000000: 104,
    0x00000003FFFFFFFF: 12,
    0xFFFFFFF800000000: 21,
    0x00000007FFFFFFFF: 39,
}
CORE_POOL_BASE_MASK_MATERIALIZATIONS = {
    0x10B7694: (0xFFFFFFFC00000000, 0xFFFFFFFE00000000),
    0x10B7860: (0xFFFFFFFC00000000, 0xFFFFFFFE00000000),
}
# Both paths feed the register-form AND at +0x39fa8 before the table index.
CORE_POOL_OFFSET_MASK_MATERIALIZATIONS = {
    0x39FA4: (0x3FFFFFFFF, 0x1FFFFFFFF),
    0x39FDC: (0x3FFFFFFFF, 0x1FFFFFFFF),
}
# This is subtraction in metadata setup, not an address-mask operation.
INIT_LOGICAL_IMMEDIATE_PATCHES = {
    0x10B80E0: (0xFFFFFFFC00000000, 0xFFFFFFFE00000000),
}
INIT_MOVE_WIDE_PATCHES = {
    0x10B8014: (32 << 30, 16 << 30),
    0x10B8018: (32 << 30, 16 << 30),
    0x10B803C: (16 << 30, 8 << 30),
    0x10B805C: (16 << 30, 8 << 30),
    0x10B8070: (16 << 30, 8 << 30),
    0x10B80A4: (16 << 30, 8 << 30),
}
CORE_POOL_SUPERPAGE_INDEX_PATCHES = {
    0x10DEC, 0x10F80, 0x3C964, 0x6DD54, 0x34DC44, 0x550E114,
}
CPPGC_CAGE_MOVE_WIDE_PATCHES = {
    0x20274C4: (16 << 30, 4 << 30),
    0x20274D0: (32 << 30, 8 << 30),
    0x20274D4: (16 << 30, 8 << 30),
    0x2027500: (16 << 30, 8 << 30),
    0x2027588: (16 << 30, 4 << 30),
    0x2027678: (16 << 30, 4 << 30),
    0x20276D8: (16 << 30, 4 << 30),
    0x20276DC: (16 << 30, 8 << 30),
    0x2027714: (16 << 30, 4 << 30),
    0x2027718: (16 << 30, 8 << 30),
    0x2027750: (16 << 30, 4 << 30),
    0x2027754: (16 << 30, 8 << 30),
    0x202778C: (16 << 30, 4 << 30),
    0x2027790: (16 << 30, 8 << 30),
}
CPPGC_CAGE_WORD_PATCHES = {
    0x20274C8: (0x925F7801, 0xD2C001C1),
    # After freeing all eight GiB, enter the existing checked fallback.
    0x2027508: (0xD2800008, 0x1400006C),
    0x2027538: (0xD362FD29, 0xD361FD29),
    0x2027540: (0xB24086C9, 0xB24082C9),
    0x2027584: (0xD362FD0A, 0xD360FD0A),
    0x20276D0: (0x925F7904, 0xD2C001C4),
    0x202770C: (0x925F7904, 0xD2C001C4),
    0x2027748: (0x925F7904, 0xD2C001C4),
    0x2027784: (0x925F7904, 0xD2C001C4),
}
CPPGC_CAGE_DATA_PATCHES = {
    0xB68E9C0: (16 * 1024**3 - 1, 8 * 1024**3 - 1),
}


def configure_engine() -> None:
    for name in (
        "EXPECTED_UUID", "EXPECTED_LOGICAL_COUNTS",
        "EXPECTED_RETAINED_LOGICAL_COUNTS",
        "CORE_POOL_BASE_MASK_MATERIALIZATIONS",
        "CORE_POOL_OFFSET_MASK_MATERIALIZATIONS",
        "INIT_LOGICAL_IMMEDIATE_PATCHES", "INIT_MOVE_WIDE_PATCHES",
        "CORE_POOL_SUPERPAGE_INDEX_PATCHES", "CPPGC_CAGE_MOVE_WIDE_PATCHES",
        "CPPGC_CAGE_WORD_PATCHES", "CPPGC_CAGE_DATA_PATCHES",
    ):
        setattr(engine, name, globals()[name])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    configure_engine()
    try:
        manifest = engine.patch(args.input, args.output)
    except (OSError, ValueError, struct.error) as error:
        print(f"patch_vscode140_pa_ios_va: {error}", file=sys.stderr)
        return 1
    manifest["profile"] = "VS Code 1.140.0 arm64 / iPadOS VA"
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
