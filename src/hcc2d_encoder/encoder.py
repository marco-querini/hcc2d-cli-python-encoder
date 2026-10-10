#!/usr/bin/env python3
# encoder.py
# HCC2D Encoder - Python reference implementation
# Copyright 2010-2026 Marco Querini
# SPDX-License-Identifier: Apache-2.0
# Version 0.9.0
# Date 2026-10-10
#
# Usage: hcc2d-encoder --help  (or: python3 -m hcc2d_encoder --help)
#
# This single-file Python HCC2D encoder is provided for educational purposes.
# It is a compact standalone reference implementation and is unrelated to the
# HCC2D Encoder and HCC2D Decoder desktop/mobile apps written in C/C++.
#
# Specification compliance:
# This encoder is intended to conform to the HCC2D Code Specification version
# 0.9.0, available at https://doi.org/10.5281/zenodo.22206528
#
# Terms of service / no-warranty notice:
# This file is provided "as is", without warranties or conditions of any kind,
# express or implied, including but not limited to merchantability, fitness for
# a particular purpose, and noninfringement. Use of this file is entirely at
# your own risk. The author assumes no responsibility or liability for any
# damages, losses, claims, unreadable or non-decodable codes, failed scans,
# data loss, or other consequences arising from the use of this file.
#
# Apache 2.0 summary:
# You may use, copy, modify, and redistribute this file, including for
# commercial purposes. You must keep the applicable copyright/license notices
# and state significant modifications when redistributing modified versions.
# This summary is informational only; the LICENSE file and Apache License 2.0
# text control the actual legal terms.
# Full license text: https://www.apache.org/licenses/LICENSE-2.0

from __future__ import annotations

_PROGRAM_INFO = """\
HCC2D Encoder - Python reference implementation
Copyright 2010-2026 Marco Querini  |  SPDX-License-Identifier: Apache-2.0  |  Version 0.9.0

Specification compliance:
  Intended to conform to the HCC2D Code Specification version 0.9.0.
  Reference specification: https://doi.org/10.5281/zenodo.22206528

Description:
  This encoder is provided for educational purposes. It is a compact standalone
  reference implementation and is unrelated to the HCC2D Encoder and HCC2D
  Decoder desktop/mobile apps written in C/C++.

Terms of service / no-warranty notice:
  This file is provided "as is", without warranties or conditions of any kind,
  express or implied, including but not limited to merchantability, fitness for
  a particular purpose, and noninfringement. Use of this file is entirely at
  your own risk. The author assumes no responsibility or liability for any
  damages, losses, claims, unreadable or non-decodable codes, failed scans,
  data loss, or other consequences arising from the use of this file.

Apache 2.0 summary:
  You may use, copy, modify, and redistribute this file, including for
  commercial purposes. You must keep the applicable copyright/license notices
  and state significant modifications when redistributing modified versions.
  This summary is informational only; the LICENSE file and Apache License 2.0
  text control the actual legal terms.
  Full license text: https://www.apache.org/licenses/LICENSE-2.0\
"""

import argparse
import struct
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence


PALETTE_QR = [
    (0, 0, 0),
    (255, 255, 255),
]


# ---------------------------------------------------------------------------
# Color Palette Model 1 — screen (default, spec §5.1 and §5.2)
# Active channels capped below 255 to reduce cross-display colour drift.
# ---------------------------------------------------------------------------
PALETTE_4_MODEL1 = [
    (0,   0,   0),    # 0 black
    (220, 0,   0),    # 1 red
    (0,   200, 220),  # 2 cyan
    (255, 255, 255),  # 3 white
]

PALETTE_8_MODEL1 = [
    (0,   0,   0),    # 0 black
    (200, 0,   0),    # 1 dark red
    (0,   130, 0),    # 2 dark green
    (0,   60,  180),  # 3 dark navy
    (0,   215, 235),  # 4 light cyan
    (255, 220, 50),   # 5 light yellow
    (255, 130, 230),  # 6 light magenta
    (255, 255, 255),  # 7 white
]

# ---------------------------------------------------------------------------
# Color Palette Model 2 — print (spec §5.4 and §5.5)
# Single-ink and two-ink CMYK combinations for printed codes.
# ---------------------------------------------------------------------------
PALETTE_4_MODEL2 = [
    (0,   0,   0),    # 0 black        (K)
    (255, 0,   255),  # 1 magenta      (M)
    (0,   255, 255),  # 2 cyan         (C)
    (255, 255, 255),  # 3 white        (no ink / paper)
]

PALETTE_8_MODEL2 = [
    (0,   0,   0),    # 0 black        (K)
    (0,   0,   255),  # 1 blue         (C+M)
    (255, 0,   0),    # 2 red          (M+Y)
    (255, 0,   255),  # 3 magenta      (M)
    (0,   255, 0),    # 4 green        (C+Y)
    (0,   255, 255),  # 5 cyan         (C)
    (255, 255, 0),    # 6 yellow       (Y)
    (255, 255, 255),  # 7 white        (no ink / paper)
]

# ---------------------------------------------------------------------------
# Custom palettes — add new entries here (spec §5.7–§5.9)
# ---------------------------------------------------------------------------
# Rules:
#   • index 0 must be (0, 0, 0)         — black anchor, non-negotiable
#   • last index must be (255, 255, 255) — white anchor, non-negotiable
#   • hcc2d4 needs exactly 4 entries; hcc2d8 needs exactly 8
#   • recommended: lower indices darker, higher indices lighter (spec §5.9)
#
# Example:
#   PALETTE_4_VIVID = [(0,0,0), (180,0,180), (0,200,0), (255,255,255)]
#
# Then register it below:
#   "vivid": (PALETTE_4_VIVID, PALETTE_8_VIVID),
# ---------------------------------------------------------------------------

# Registry used by the CLI --palette option.
PALETTE_REGISTRY: dict[str, tuple[list, list]] = {
    "model1": (PALETTE_4_MODEL1, PALETTE_8_MODEL1),
    "model2": (PALETTE_4_MODEL2, PALETTE_8_MODEL2),
}

# Validate that a palette entry in PALETTE_REGISTRY has the correct size and mandatory black/white anchors.
def _check_palette(name: str, palette: list, expected_size: int) -> None:
    if len(palette) != expected_size:
        raise ValueError(
            f"palette '{name}': expected {expected_size} entries, got {len(palette)}"
        )
    if palette[0] != (0, 0, 0):
        raise ValueError(
            f"palette '{name}': index 0 must be black (0, 0, 0). "
            f"The black anchor is normative and cannot be changed; "
            f"a palette that violates this rule is not compliant with the HCC2D specification (spec §5.8)."
        )
    if palette[-1] != (255, 255, 255):
        raise ValueError(
            f"palette '{name}': last index must be white (255, 255, 255). "
            f"The white anchor is normative and cannot be changed; "
            f"a palette that violates this rule is not compliant with the HCC2D specification (spec §5.8)."
        )

try:
    for _name, (_p4, _p8) in PALETTE_REGISTRY.items():
        _check_palette(_name, _p4, 4)
        _check_palette(_name, _p8, 8)
except ValueError as _e:
    import sys as _sys
    print(f"Configuration error in PALETTE_REGISTRY: {_e}", file=_sys.stderr)
    _sys.exit(1)

EC_LEVEL_BITS = {"L": 1, "M": 0, "Q": 3, "H": 2}
EC_LEVEL_INDEX = {"L": 0, "M": 1, "Q": 2, "H": 3}
MODE_BITS_BYTE = 0b0100
VERSION_INFO_POLY = 0x1F25
TYPE_INFO_POLY = 0x537
TYPE_INFO_MASK_PATTERN = 0x5412

# Each tuple is:
#   (version_number, alignment_centers, [(ecpb, count1, data1, count2, data2) for L/M/Q/H])
# This is copied into the single file so the script ships with all QR Model 2 geometry/block data.
QR_VERSIONS = [
    (1, [], [(7, 1, 19, 0, 0), (10, 1, 16, 0, 0), (13, 1, 13, 0, 0), (17, 1, 9, 0, 0)]),
    (2, [6, 18], [(10, 1, 34, 0, 0), (16, 1, 28, 0, 0), (22, 1, 22, 0, 0), (28, 1, 16, 0, 0)]),
    (3, [6, 22], [(15, 1, 55, 0, 0), (26, 1, 44, 0, 0), (18, 2, 17, 0, 0), (22, 2, 13, 0, 0)]),
    (4, [6, 26], [(20, 1, 80, 0, 0), (18, 2, 32, 0, 0), (26, 2, 24, 0, 0), (16, 4, 9, 0, 0)]),
    (5, [6, 30], [(26, 1, 108, 0, 0), (24, 2, 43, 0, 0), (18, 2, 15, 2, 16), (22, 2, 11, 2, 12)]),
    (6, [6, 34], [(18, 2, 68, 0, 0), (16, 4, 27, 0, 0), (24, 4, 19, 0, 0), (28, 4, 15, 0, 0)]),
    (7, [6, 22, 38], [(20, 2, 78, 0, 0), (18, 4, 31, 0, 0), (18, 2, 14, 4, 15), (26, 4, 13, 1, 14)]),
    (8, [6, 24, 42], [(24, 2, 97, 0, 0), (22, 2, 38, 2, 39), (22, 4, 18, 2, 19), (26, 4, 14, 2, 15)]),
    (9, [6, 26, 46], [(30, 2, 116, 0, 0), (22, 3, 36, 2, 37), (20, 4, 16, 4, 17), (24, 4, 12, 4, 13)]),
    (10, [6, 28, 50], [(18, 2, 68, 2, 69), (26, 4, 43, 1, 44), (24, 6, 19, 2, 20), (28, 6, 15, 2, 16)]),
    (11, [6, 30, 54], [(20, 4, 81, 0, 0), (30, 1, 50, 4, 51), (28, 4, 22, 4, 23), (24, 3, 12, 8, 13)]),
    (12, [6, 32, 58], [(24, 2, 92, 2, 93), (22, 6, 36, 2, 37), (26, 4, 20, 6, 21), (28, 7, 14, 4, 15)]),
    (13, [6, 34, 62], [(26, 4, 107, 0, 0), (22, 8, 37, 1, 38), (24, 8, 20, 4, 21), (22, 12, 11, 4, 12)]),
    (14, [6, 26, 46, 66], [(30, 3, 115, 1, 116), (24, 4, 40, 5, 41), (20, 11, 16, 5, 17), (24, 11, 12, 5, 13)]),
    (15, [6, 26, 48, 70], [(22, 5, 87, 1, 88), (24, 5, 41, 5, 42), (30, 5, 24, 7, 25), (24, 11, 12, 7, 13)]),
    (16, [6, 26, 50, 74], [(24, 5, 98, 1, 99), (28, 7, 45, 3, 46), (24, 15, 19, 2, 20), (30, 3, 15, 13, 16)]),
    (17, [6, 30, 54, 78], [(28, 1, 107, 5, 108), (28, 10, 46, 1, 47), (28, 1, 22, 15, 23), (28, 2, 14, 17, 15)]),
    (18, [6, 30, 56, 82], [(30, 5, 120, 1, 121), (26, 9, 43, 4, 44), (28, 17, 22, 1, 23), (28, 2, 14, 19, 15)]),
    (19, [6, 30, 58, 86], [(28, 3, 113, 4, 114), (26, 3, 44, 11, 45), (26, 17, 21, 4, 22), (26, 9, 13, 16, 14)]),
    (20, [6, 34, 62, 90], [(28, 3, 107, 5, 108), (26, 3, 41, 13, 42), (30, 15, 24, 5, 25), (28, 15, 15, 10, 16)]),
    (21, [6, 28, 50, 72, 94], [(28, 4, 116, 4, 117), (26, 17, 42, 0, 0), (28, 17, 22, 6, 23), (30, 19, 16, 6, 17)]),
    (22, [6, 26, 50, 74, 98], [(28, 2, 111, 7, 112), (28, 17, 46, 0, 0), (30, 7, 24, 16, 25), (24, 34, 13, 0, 0)]),
    (23, [6, 30, 54, 78, 102], [(30, 4, 121, 5, 122), (28, 4, 47, 14, 48), (30, 11, 24, 14, 25), (30, 16, 15, 14, 16)]),
    (24, [6, 28, 54, 80, 106], [(30, 6, 117, 4, 118), (28, 6, 45, 14, 46), (30, 11, 24, 16, 25), (30, 30, 16, 2, 17)]),
    (25, [6, 32, 58, 84, 110], [(26, 8, 106, 4, 107), (28, 8, 47, 13, 48), (30, 7, 24, 22, 25), (30, 22, 15, 13, 16)]),
    (26, [6, 30, 58, 86, 114], [(28, 10, 114, 2, 115), (28, 19, 46, 4, 47), (28, 28, 22, 6, 23), (30, 33, 16, 4, 17)]),
    (27, [6, 34, 62, 90, 118], [(30, 8, 122, 4, 123), (28, 22, 45, 3, 46), (30, 8, 23, 26, 24), (30, 12, 15, 28, 16)]),
    (28, [6, 26, 50, 74, 98, 122], [(30, 3, 117, 10, 118), (28, 3, 45, 23, 46), (30, 4, 24, 31, 25), (30, 11, 15, 31, 16)]),
    (29, [6, 30, 54, 78, 102, 126], [(30, 7, 116, 7, 117), (28, 21, 45, 7, 46), (30, 1, 23, 37, 24), (30, 19, 15, 26, 16)]),
    (30, [6, 26, 52, 78, 104, 130], [(30, 5, 115, 10, 116), (28, 19, 47, 10, 48), (30, 15, 24, 25, 25), (30, 23, 15, 25, 16)]),
    (31, [6, 30, 56, 82, 108, 134], [(30, 13, 115, 3, 116), (28, 2, 46, 29, 47), (30, 42, 24, 1, 25), (30, 23, 15, 28, 16)]),
    (32, [6, 34, 60, 86, 112, 138], [(30, 17, 115, 0, 0), (28, 10, 46, 23, 47), (30, 10, 24, 35, 25), (30, 19, 15, 35, 16)]),
    (33, [6, 30, 58, 86, 114, 142], [(30, 17, 115, 1, 116), (28, 14, 46, 21, 47), (30, 29, 24, 19, 25), (30, 11, 15, 46, 16)]),
    (34, [6, 34, 62, 90, 118, 146], [(30, 13, 115, 6, 116), (28, 14, 46, 23, 47), (30, 44, 24, 7, 25), (30, 59, 16, 1, 17)]),
    (35, [6, 30, 54, 78, 102, 126, 150], [(30, 12, 121, 7, 122), (28, 12, 47, 26, 48), (30, 39, 24, 14, 25), (30, 22, 15, 41, 16)]),
    (36, [6, 24, 50, 76, 102, 128, 154], [(30, 6, 121, 14, 122), (28, 6, 47, 34, 48), (30, 46, 24, 10, 25), (30, 2, 15, 64, 16)]),
    (37, [6, 28, 54, 80, 106, 132, 158], [(30, 17, 122, 4, 123), (28, 29, 46, 14, 47), (30, 49, 24, 10, 25), (30, 24, 15, 46, 16)]),
    (38, [6, 32, 58, 84, 110, 136, 162], [(30, 4, 122, 18, 123), (28, 13, 46, 32, 47), (30, 48, 24, 14, 25), (30, 42, 15, 32, 16)]),
    (39, [6, 26, 54, 82, 110, 138, 166], [(30, 20, 117, 4, 118), (28, 40, 47, 7, 48), (30, 43, 24, 22, 25), (30, 10, 15, 67, 16)]),
    (40, [6, 30, 58, 86, 114, 142, 170], [(30, 19, 118, 6, 119), (28, 18, 47, 31, 48), (30, 34, 24, 34, 25), (30, 20, 15, 61, 16)]),
]

MODE_SPECS = {
    "qr": {
        "plane_count": 1,
        "border_period": 0,
        "default_palette": PALETTE_QR,
        "version_multiplier": 1,
    },
    "hcc2d4": {
        "plane_count": 2,
        "border_period": 4,
        "default_palette": PALETTE_4_MODEL1,
        "version_multiplier": 2,
    },
    "hcc2d8": {
        "plane_count": 3,
        "border_period": 8,
        "default_palette": PALETTE_8_MODEL1,
        "version_multiplier": 3,
    },
}


@dataclass(frozen=True)
class ECBlocks:
    codewords_per_block: int
    count1: int
    data1: int
    count2: int
    data2: int

    # Total number of RS blocks (group 1 + group 2).
    @property
    def num_blocks(self) -> int:
        return self.count1 + self.count2

    # Total EC codewords across all blocks.
    @property
    def total_codewords(self) -> int:
        return self.codewords_per_block * self.num_blocks

    # Total codewords in the symbol (data + EC) across all blocks.
    @property
    def total_symbol_codewords(self) -> int:
        return self.count1 * (self.data1 + self.codewords_per_block) + self.count2 * (
            self.data2 + self.codewords_per_block
        )


@dataclass(frozen=True)
class VersionInfo:
    number: int
    alignments: List[int]
    ec_levels: List[ECBlocks]

    # Inner grid dimension in modules: N = 17 + 4 * version.
    @property
    def dimension(self) -> int:
        return 17 + 4 * self.number


# Parsed, typed view of the embedded table above.
MODEL2_VERSIONS = [
    VersionInfo(
        number=ver,
        alignments=alignments,
        ec_levels=[ECBlocks(*entry) for entry in ec_entries],
    )
    for ver, alignments, ec_entries in QR_VERSIONS
]


class BitBuffer:
    # Initialise an empty bit list.
    def __init__(self) -> None:
        self.bits: List[int] = []

    # Append a single bit (True→1, False→0).
    def append_bit(self, value: bool) -> None:
        self.bits.append(1 if value else 0)

    # Append the MSB-first binary representation of value using count bits.
    def append_bits(self, value: int, count: int) -> None:
        if count < 0:
            raise ValueError("count must be non-negative")
        for shift in range(count - 1, -1, -1):
            self.bits.append((value >> shift) & 1)

    # Pack bits into a list of bytes, padding the last byte with zeros if needed.
    def to_bytes(self, bit_offset: int = 0, num_bytes: int | None = None) -> List[int]:
        available_bits = len(self.bits) - bit_offset
        if available_bits < 0:
            raise ValueError("bit offset out of range")
        if num_bytes is None:
            num_bytes = (available_bits + 7) // 8
        out: List[int] = []
        for byte_index in range(num_bytes):
            value = 0
            for bit_index in range(8):
                src = bit_offset + byte_index * 8 + bit_index
                value = (value << 1) | (self.bits[src] if src < len(self.bits) else 0)
            out.append(value)
        return out


class GF256:
    # Precompute exponent/log tables for QR's GF(256) field so Reed-Solomon stays compact.
    def __init__(self, primitive: int = 0x011D) -> None:
        self.exp = [0] * 512
        self.log = [0] * 256
        x = 1
        for i in range(255):
            self.exp[i] = x
            self.log[x] = i
            x <<= 1
            if x & 0x100:
                x ^= primitive
        for i in range(255, 512):
            self.exp[i] = self.exp[i - 255]

    # Multiply two GF(256) elements using the precomputed log/exp tables.
    def multiply(self, a: int, b: int) -> int:
        if a == 0 or b == 0:
            return 0
        return self.exp[self.log[a] + self.log[b]]


GF = GF256()


# Multiply two polynomials in GF(256).
def poly_mul(a: Sequence[int], b: Sequence[int]) -> List[int]:
    out = [0] * (len(a) + len(b) - 1)
    for i, av in enumerate(a):
        for j, bv in enumerate(b):
            out[i + j] ^= GF.multiply(av, bv)
    return out


# Generator(x) = product of (x - a^i) over the QR field.
def rs_generator_poly(degree: int) -> List[int]:
    result = [1]
    for i in range(degree):
        result = poly_mul(result, [1, GF.exp[i]])
    return result


# Standard QR Reed-Solomon parity generation over the data codewords of one block.
# Conceptually, we append ec_words zero coefficients, divide by the generator
# polynomial, and keep the remainder as the parity bytes.
def rs_compute_remainder(data: Sequence[int], ec_words: int) -> List[int]:
    gen = rs_generator_poly(ec_words)
    rem = [0] * ec_words
    for byte in data:
        factor = byte ^ rem[0]
        rem = rem[1:] + [0]
        if factor:
            for i in range(ec_words):
                rem[i] ^= GF.multiply(gen[i + 1], factor)
    return rem


# Build the block layout for one version and mode. Standard QR keeps the base
# layout; HCC2D keeps the QR geometry while replicating the block structure 2x
# or 3x so the final stream can be split into colour planes.
def get_version(mode: str, number: int) -> VersionInfo:
    if mode not in MODE_SPECS:
        raise ValueError(f"unsupported mode: {mode}")
    if number < 1 or number > 40:
        raise ValueError("version must be 1-40")
    base = MODEL2_VERSIONS[number - 1]
    multiplier = MODE_SPECS[mode]["version_multiplier"]
    # Multiplier: 1x for QR, 2x for HCC2D4, 3x for HCC2D8.
    levels = [
        ECBlocks(
            entry.codewords_per_block,
            entry.count1 * multiplier,
            entry.data1,
            entry.count2 * multiplier,
            entry.data2,
        )
        for entry in base.ec_levels
    ]
    return VersionInfo(number=base.number, alignments=base.alignments, ec_levels=levels)


# Pick the smallest version that fits the payload.
def choose_version(mode: str, ec_level: str, payload: bytes) -> VersionInfo:
    for version in range(1, 41):
        info = get_version(mode, version)
        if will_fit(mode, ec_level, payload, info):
            return info
    raise ValueError("payload does not fit in any supported version")


# Check whether the payload fits after HCC2D framing but before EC/interleaving.
def will_fit(mode: str, ec_level: str, payload: bytes, version: VersionInfo) -> bool:
    count_bits = 8 if mode == "qr" and version.number <= 9 else 16
    if len(payload) >= (1 << count_bits):
        return False
    bits = build_header_and_data_bits(payload, count_bits)
    ec_blocks = version.ec_levels[EC_LEVEL_INDEX[ec_level]]
    num_data_bytes = ec_blocks.total_symbol_codewords - ec_blocks.total_codewords
    return num_data_bytes >= (len(bits.bits) + 7) // 8


# HCC2D uses a fixed 16-bit byte count. Standard QR uses 8 bits for versions
# 1-9 and 16 bits for versions 10-40.
def build_header_and_data_bits(payload: bytes, count_bits: int = 16) -> BitBuffer:
    if count_bits not in (8, 16):
        raise ValueError("byte-count field must contain 8 or 16 bits")
    if len(payload) >= (1 << count_bits):
        raise ValueError(f"payload length does not fit in a {count_bits}-bit byte-count field")
    bits = BitBuffer()
    bits.append_bits(MODE_BITS_BYTE, 4)
    bits.append_bits(len(payload), count_bits)
    for byte in payload:
        bits.append_bits(byte, 8)
    return bits


# Raw text or file bytes can be wrapped as HCC2DF:
#   magic(6) + wrapper_version(1) + compression_flag(1) + filename_len(1) + filename + content
# This is an application-level wrapper carried inside HCC2D payload bytes, not part
# of the barcode geometry itself.
def build_hcc2df_payload(filename: str, content: bytes) -> bytes:
    filename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    filename_bytes = filename.encode("utf-8")
    if not filename_bytes:
        raise ValueError("input filename must be non-empty")
    if len(filename_bytes) > 127:
        raise ValueError("input filename must be at most 127 UTF-8 bytes")
    # Match the native encoder's HCC2DF rule:
    # zlib default compression, and only keep the compressed bytes if they are strictly
    # smaller than 90% of the original payload size.
    compressed = zlib.compress(content, zlib.Z_DEFAULT_COMPRESSION)
    use_compressed = (
        len(content) >= 128
        and len(compressed) < len(content) * 0.9
    )
    stored_content = compressed if use_compressed else content
    compression_flag = 0x01 if use_compressed else 0x00

    payload = bytearray()
    payload.extend(b"HCC2DF")
    payload.append(0x01)
    payload.append(compression_flag)
    payload.append(len(filename_bytes))
    payload.extend(filename_bytes)
    payload.extend(stored_content)
    return bytes(payload)


# Same QR-compatible terminator/padding rule used before RS/interleaving.
def terminate_bits(num_data_bytes: int, bits: BitBuffer) -> None:
    capacity = num_data_bytes * 8
    if len(bits.bits) > capacity:
        raise ValueError("data bits exceed symbol capacity")
    for _ in range(min(4, capacity - len(bits.bits))):
        bits.append_bit(False)
    while len(bits.bits) % 8 != 0:
        bits.append_bit(False)
    pad_bytes = [0xEC, 0x11]
    i = 0
    while len(bits.bits) < capacity:
        bits.append_bits(pad_bytes[i % 2], 8)
        i += 1


# Compute the data/EC sizes for one interleaving block.
def get_block_layout(num_total_bytes: int, num_data_bytes: int, num_rs_blocks: int, block_id: int) -> tuple[int, int]:
    if block_id >= num_rs_blocks:
        raise ValueError("block id out of range")
    group2_blocks = num_total_bytes % num_rs_blocks
    group1_blocks = num_rs_blocks - group2_blocks
    total1 = num_total_bytes // num_rs_blocks
    total2 = total1 + 1
    data1 = num_data_bytes // num_rs_blocks
    data2 = data1 + 1
    ec1 = total1 - data1
    ec2 = total2 - data2
    if block_id < group1_blocks:
        return data1, ec1
    return data2, ec2


# Generate parity per block, then interleave data bytes followed by EC bytes across blocks.
# That interleaved byte stream is the final QR/HCC2D codeword stream. Only after this
# step does HCC2D split bits into planes.
def interleave_with_ec_bytes(bits: BitBuffer, num_total_bytes: int, num_data_bytes: int, num_rs_blocks: int) -> BitBuffer:
    if len(bits.bits) // 8 != num_data_bytes:
        raise ValueError("data byte count mismatch")
    blocks: List[tuple[List[int], List[int]]] = []
    offset = 0
    max_data_len = 0
    max_ec_len = 0
    source_bytes = bits.to_bytes()
    for block_id in range(num_rs_blocks):
        data_len, ec_len = get_block_layout(num_total_bytes, num_data_bytes, num_rs_blocks, block_id)
        data = source_bytes[offset : offset + data_len]
        ec = rs_compute_remainder(data, ec_len)
        blocks.append((data, ec))
        offset += data_len
        max_data_len = max(max_data_len, data_len)
        max_ec_len = max(max_ec_len, ec_len)
    out = BitBuffer()
    for i in range(max_data_len):
        for data, _ in blocks:
            if i < len(data):
                out.append_bits(data[i], 8)
    for i in range(max_ec_len):
        for _, ec in blocks:
            if i < len(ec):
                out.append_bits(ec[i], 8)
    return out


# Take every Nth bit to form one HCC2D plane.
# Example for 4-colour HCC2D:
#   plane 0 gets bits 0,2,4,...
#   plane 1 gets bits 1,3,5,...
def extract_plane_bits(bits: Sequence[int], plane_offset: int, plane_count: int) -> List[int]:
    return [bits[i] for i in range(plane_offset, len(bits), plane_count)]


# Invert a bit sequence.
def invert_bits(bits: Sequence[int]) -> List[int]:
    return [0 if bit else 1 for bit in bits]


# Evaluate one of the standard QR mask formulas at a module position.
def get_data_mask_bit(mask_index: int, x: int, y: int) -> bool:
    if mask_index == 0:
        return (y + x) % 2 == 0
    if mask_index == 1:
        return y % 2 == 0
    if mask_index == 2:
        return x % 3 == 0
    if mask_index == 3:
        return (y + x) % 3 == 0
    if mask_index == 4:
        return ((y // 2) + (x // 3)) % 2 == 0
    if mask_index == 5:
        return (y * x) % 6 == 0
    if mask_index == 6:
        return ((y * x) % 6) < 3
    if mask_index == 7:
        return (y + x + ((y * x) % 3)) % 2 == 0
    raise ValueError("invalid mask pattern")


# Create a square matrix whose cells start as "unassigned".
def empty_matrix(dim: int) -> List[List[int | None]]:
    return [[None for _ in range(dim)] for _ in range(dim)]


# Write a cell only if the coordinates are inside the matrix bounds.
def set_if_inside(matrix: List[List[int | None]], x: int, y: int, value: int) -> None:
    dim = len(matrix)
    if 0 <= x < dim and 0 <= y < dim:
        matrix[y][x] = value


# 7x7 finder plus its white separator ring.
def embed_position_detection_pattern(matrix: List[List[int | None]], x0: int, y0: int) -> None:
    for y in range(7):
        for x in range(7):
            matrix[y0 + y][x0 + x] = 1 if max(abs(x - 3), abs(y - 3)) != 2 else 0
    for i in range(-1, 8):
        set_if_inside(matrix, x0 + i, y0 - 1, 0)
        set_if_inside(matrix, x0 + i, y0 + 7, 0)
        set_if_inside(matrix, x0 - 1, y0 + i, 0)
        set_if_inside(matrix, x0 + 7, y0 + i, 0)


# Place the three QR finder patterns.
def embed_position_detection_patterns_and_separators(matrix: List[List[int | None]]) -> None:
    dim = len(matrix)
    embed_position_detection_pattern(matrix, 0, 0)
    embed_position_detection_pattern(matrix, dim - 7, 0)
    embed_position_detection_pattern(matrix, 0, dim - 7)


# Place QR's fixed dark module.
def embed_dark_module(matrix: List[List[int | None]]) -> None:
    matrix[len(matrix) - 8][8] = 1


# Draw one 5x5 alignment pattern.
def embed_position_adjustment_pattern(matrix: List[List[int | None]], x0: int, y0: int) -> None:
    for y in range(5):
        for x in range(5):
            matrix[y0 + y][x0 + x] = 1 if max(abs(x - 2), abs(y - 2)) != 1 else 0


# Place all alignment patterns for versions 2 and above, skipping positions that overlap finder patterns.
def embed_alignment_patterns(version: VersionInfo, matrix: List[List[int | None]]) -> None:
    if version.number < 2:
        return
    dim = len(matrix)
    # Alignment centers come directly from the embedded QR version table.
    for y in version.alignments:
        for x in version.alignments:
            if (x == 6 and y == 6) or (x == 6 and y == dim - 7) or (x == dim - 7 and y == 6):
                continue
            embed_position_adjustment_pattern(matrix, x - 2, y - 2)


# Place the horizontal and vertical timing patterns.
def embed_timing_patterns(matrix: List[List[int | None]]) -> None:
    dim = len(matrix)
    for i in range(8, dim - 8):
        bit = 1 if (i + 1) % 2 else 0
        matrix[6][i] = bit
        matrix[i][6] = bit


# Return the index of the most significant set bit, using Python's bit_length().
def find_msb_set(value: int) -> int:
    return value.bit_length()


# Compute the BCH remainder used by QR type/version metadata.
def calculate_bch_code(value: int, poly: int) -> int:
    msb = find_msb_set(poly)
    value <<= msb - 1
    while find_msb_set(value) >= msb:
        value ^= poly << (find_msb_set(value) - msb)
    return value


# Build the 15 QR type-information bits for EC level + mask.
def make_type_info_bits(ec_level: str, mask_pattern: int) -> List[int]:
    type_info = (EC_LEVEL_BITS[ec_level] << 3) | mask_pattern
    value = (type_info << 10) | calculate_bch_code(type_info, TYPE_INFO_POLY)
    value ^= TYPE_INFO_MASK_PATTERN
    return [(value >> shift) & 1 for shift in range(14, -1, -1)]


# Write QR type-information bits into their reserved cells.
def embed_type_info(ec_level: str, mask_pattern: int, matrix: List[List[int | None]]) -> None:
    coords = [
        (8, 0),
        (8, 1),
        (8, 2),
        (8, 3),
        (8, 4),
        (8, 5),
        (8, 7),
        (8, 8),
        (7, 8),
        (5, 8),
        (4, 8),
        (3, 8),
        (2, 8),
        (1, 8),
        (0, 8),
    ]
    bits = make_type_info_bits(ec_level, mask_pattern)
    dim = len(matrix)
    for i, bit in enumerate(reversed(bits)):
        x, y = coords[i]
        matrix[y][x] = bit
        if i < 8:
            matrix[8][dim - i - 1] = bit
        else:
            matrix[dim - 7 + (i - 8)][8] = bit


# Build the 18 QR version-information bits.
def make_version_info_bits(version_number: int) -> List[int]:
    value = (version_number << 12) | calculate_bch_code(version_number, VERSION_INFO_POLY)
    return [(value >> shift) & 1 for shift in range(17, -1, -1)]


# Write QR version-information bits for versions 7 and above.
def embed_version_info(version: VersionInfo, matrix: List[List[int | None]]) -> None:
    if version.number < 7:
        return
    bits = make_version_info_bits(version.number)
    dim = len(matrix)
    bit_index = len(bits) - 1
    for i in range(6):
        for j in range(3):
            bit = bits[bit_index]
            bit_index -= 1
            matrix[dim - 11 + j][i] = bit
            matrix[i][dim - 11 + j] = bit


# QR zig-zag scan from the bottom-right, skipping reserved function cells.
# This is the reused QR module-placement walk. HCC2D relies on the same walk for each
# plane, so only the plane bitstream changes between passes.
def embed_data_bits(data_bits: Sequence[int], mask_pattern: int, matrix: List[List[int | None]]) -> None:
    dim = len(matrix)
    bit_index = 0
    direction = -1
    x = dim - 1
    y = dim - 1
    while x > 0:
        if x == 6:
            x -= 1
        while 0 <= y < dim:
            for xx in range(x, x - 2, -1):
                if matrix[y][xx] is not None:
                    continue
                bit = data_bits[bit_index] if bit_index < len(data_bits) else 0
                bit_index += 1
                if get_data_mask_bit(mask_pattern, xx, y):
                    bit ^= 1
                matrix[y][xx] = bit
            y += direction
        direction = -direction
        y += direction
        x -= 2
    if bit_index < len(data_bits):
        raise ValueError(f"not all bits consumed: {bit_index}/{len(data_bits)}")


# HCC2D reuses standard QR inner-matrix construction. The HCC2D-specific part happens later:
# shared mask across all planes, color interpretation of data cells, and the outer palette border.
# By the time this function returns, we still only have a binary inner grid.
def build_matrix(data_bits: Sequence[int], ec_level: str, version: VersionInfo, mask_pattern: int) -> List[List[int]]:
    matrix = empty_matrix(version.dimension)
    embed_position_detection_patterns_and_separators(matrix)
    embed_dark_module(matrix)
    embed_alignment_patterns(version, matrix)
    embed_timing_patterns(matrix)
    embed_type_info(ec_level, mask_pattern, matrix)
    embed_version_info(version, matrix)
    embed_data_bits(data_bits, mask_pattern, matrix)
    return [[0 if cell is None else cell for cell in row] for row in matrix]


# Return a boolean map of all reserved function-module cells.
# We build a skeleton matrix only to learn which coordinates belong to finder,
# alignment, timing, type, or version structures. Those cells are rendered in
# black/white in HCC2D, even when data cells become coloured.
def build_function_pattern(version: VersionInfo) -> List[List[bool]]:
    matrix = empty_matrix(version.dimension)
    embed_position_detection_patterns_and_separators(matrix)
    embed_dark_module(matrix)
    embed_alignment_patterns(version, matrix)
    embed_timing_patterns(matrix)
    # We only need to know which cells are reserved, not their final values.
    embed_type_info("L", 0, matrix)
    if version.number >= 7:
        embed_version_info(version, matrix)
    return [[cell is not None for cell in row] for row in matrix]


# Score long runs of equal modules.
def apply_mask_penalty_rule_1(matrix: List[List[int]]) -> int:
    penalty = 0
    dim = len(matrix)
    for is_horizontal in (True, False):
        outer = dim
        inner = dim
        for i in range(outer):
            run_length = 0
            prev = -1
            for j in range(inner):
                bit = matrix[i][j] if is_horizontal else matrix[j][i]
                if bit == prev:
                    run_length += 1
                else:
                    if run_length >= 5:
                        penalty += 3 + (run_length - 5)
                    run_length = 1
                    prev = bit
            if run_length >= 5:
                penalty += 3 + (run_length - 5)
    return penalty


# Score 2x2 blocks of equal modules.
def apply_mask_penalty_rule_2(matrix: List[List[int]]) -> int:
    penalty = 0
    dim = len(matrix)
    for y in range(dim - 1):
        for x in range(dim - 1):
            v = matrix[y][x]
            if v == matrix[y][x + 1] == matrix[y + 1][x] == matrix[y + 1][x + 1]:
                penalty += 1
    return penalty * 3


# Check whether a binary pattern matches at a given offset.
def has_pattern_at(pattern: Sequence[int], line: Sequence[int], start: int) -> bool:
    end = start + len(pattern)
    if start < 0 or end > len(line):
        return False
    return list(line[start:end]) == list(pattern)


# Score finder-like run patterns that are visually undesirable.
def apply_mask_penalty_rule_3(matrix: List[List[int]]) -> int:
    white = [0, 0, 0, 0]
    finder = [1, 0, 1, 1, 1, 0, 1]
    penalties = 0
    dim = len(matrix)
    for y in range(dim):
        row = matrix[y]
        for x in range(dim):
            if has_pattern_at(finder, row, x):
                left_white = row[max(0, x - 4) : x]
                right_white = row[x + 7 : min(dim, x + 11)]
                if left_white == white[-len(left_white) :] or right_white == white[: len(right_white)]:
                    penalties += 1
    for x in range(dim):
        col = [matrix[y][x] for y in range(dim)]
        for y in range(dim):
            if has_pattern_at(finder, col, y):
                top_white = col[max(0, y - 4) : y]
                bottom_white = col[y + 7 : min(dim, y + 11)]
                if top_white == white[-len(top_white) :] or bottom_white == white[: len(bottom_white)]:
                    penalties += 1
    return penalties * 40


# Score deviation from a 50/50 dark-light balance.
def apply_mask_penalty_rule_4(matrix: List[List[int]]) -> int:
    dim = len(matrix)
    total = dim * dim
    dark = sum(sum(row) for row in matrix)
    return abs(dark * 2 - total) * 10 // total * 10


# Sum all four QR mask-penalty rules.
def calculate_mask_penalty(matrix: List[List[int]]) -> int:
    return (
        apply_mask_penalty_rule_1(matrix)
        + apply_mask_penalty_rule_2(matrix)
        + apply_mask_penalty_rule_3(matrix)
        + apply_mask_penalty_rule_4(matrix)
    )


# HCC2D chooses one common mask using plane 0 only (inverted in the encoder flow),
# then reuses that same mask for every plane.
# This mirrors the native encoder/spec behavior: mask scoring is still done with the
# QR penalty model, but over a binary proxy instead of the final coloured symbol.
def choose_mask_pattern(proxy_bits: Sequence[int], ec_level: str, version: VersionInfo) -> int:
    best_mask = 0
    best_penalty = None
    for mask in range(8):
        matrix = build_matrix(proxy_bits, ec_level, version, mask)
        penalty = calculate_mask_penalty(matrix)
        if best_penalty is None or penalty < best_penalty:
            best_penalty = penalty
            best_mask = mask
    return best_mask


# Exact HCC2D Color Palette Pattern formulas from the spec.
# The cycling spans help the decoder recover palette statistics; the remaining border
# cells fall back to the highest palette index (white in the default palettes).
def color_index_for_border(row: int, col: int, dim: int, period: int) -> int:
    if row == -1 and 8 <= col < dim - 8:
        return (col - 8) % period
    if row == dim and 8 <= col < dim:
        return (col - 8) % period
    if col == -1:
        start = dim - 9
        if 8 <= row <= start:
            return (start - row) % period
    if col == dim and 8 <= row < dim:
        return (row - 8) % period
    return period - 1


# Combine per-plane binary matrices into a full-colour module grid and add the Color Palette Pattern border.
def render_modules(planes: Sequence[List[List[int]]], version: VersionInfo, mode: str) -> List[List[int]]:
    spec = MODE_SPECS[mode]
    dim = version.dimension
    plane_count = spec["plane_count"]
    period = spec["border_period"]
    white_index = period - 1
    full_dim = dim + 2
    out = [[white_index for _ in range(full_dim)] for _ in range(full_dim)]
    function_pattern = build_function_pattern(version)
    for module_y in range(-1, dim + 1):
        for module_x in range(-1, dim + 1):
            if 0 <= module_x < dim and 0 <= module_y < dim:
                if function_pattern[module_y][module_x]:
                    # Function modules stay black/white even in color HCC2D.
                    color = 0 if planes[0][module_y][module_x] else white_index
                else:
                    # Data modules combine 2 or 3 plane bits into one palette index.
                    # For hcc2d4 this yields 0..3, for hcc2d8 it yields 0..7.
                    color = 0
                    for plane_index in range(plane_count):
                        color = (color << 1) | planes[plane_index][module_y][module_x]
            else:
                color = color_index_for_border(module_y, module_x, dim, period)
            out[module_y + 1][module_x + 1] = color
    return out


# Expand each logical module into a solid scale x scale pixel square.
# The quiet zone is added outside the full HCC2D symbol, including its palette border.
def rasterize(modules: List[List[int]], scale: int, quiet_zone: int, background: int) -> tuple[int, int, List[int]]:
    full_dim = len(modules)
    image_modules = full_dim + quiet_zone * 2
    image_size = image_modules * scale
    pixels = [background] * (image_size * image_size)
    for my, row in enumerate(modules):
        for mx, color in enumerate(row):
            base_x = (mx + quiet_zone) * scale
            base_y = (my + quiet_zone) * scale
            for dy in range(scale):
                start = (base_y + dy) * image_size + base_x
                pixels[start : start + scale] = [color] * scale
    return image_size, image_size, pixels


# Build one PNG chunk with length and CRC.
def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    )


# Write a minimal indexed PNG: IHDR + PLTE + zlib-compressed IDAT + IEND.
# Indexed PNG keeps the file small and maps naturally to HCC2D's palette-index model.
def build_indexed_png(width: int, height: int, indices: Sequence[int], palette: Sequence[tuple[int, int, int]]) -> bytes:
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        row_start = y * width
        raw.extend(indices[row_start : row_start + width])
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 3, 0, 0, 0)
    plte = bytes(component for rgb in palette for component in rgb)
    idat = zlib.compress(bytes(raw), 9)
    return signature + png_chunk(b"IHDR", ihdr) + png_chunk(b"PLTE", plte) + png_chunk(b"IDAT", idat) + png_chunk(b"IEND", b"")


# Holds the fully encoded HCC2D symbol ready for PNG output.
@dataclass
class EncodedSymbol:
    mode: str
    ec_level: str
    version: int
    inner_dimension: int
    full_dimension: int
    mask_pattern: int
    palette: Sequence[tuple[int, int, int]]
    pixels: List[int]
    width: int
    height: int


# End-to-end HCC2D encode flow:
# 1. frame payload
# 2. terminate/pad
# 3. generate and interleave Reed-Solomon blocks
# 4. split final bits into planes
# 5. choose one shared mask
# 6. build one QR-compatible matrix per plane
# 7. combine planes into colour modules and add the HCC2D border
# 8. rasterize to indexed pixels
def encode_hcc2d(
    payload: bytes,
    mode: str = "hcc2d4",
    ec_level: str = "Q",
    version: int = 0,
    scale: int = 12,
    quiet_zone: int = 4,
    palette: Sequence[tuple[int, int, int]] | None = None,
) -> EncodedSymbol:
    if not payload:
        raise ValueError("payload is empty")
    if mode not in ("hcc2d4", "hcc2d8"):
        raise ValueError("mode must be hcc2d4 or hcc2d8")
    if ec_level not in EC_LEVEL_INDEX:
        raise ValueError("ec level must be one of L/M/Q/H")
    if version < 0 or version > 40:
        raise ValueError("version must be 0-40")
    if scale < 6 or scale > 1000:
        raise ValueError("scale must be an integer from 6 to 1000")
    if quiet_zone < 0 or quiet_zone > 1000:
        raise ValueError("quiet zone must be an integer from 0 to 1000")

    spec = MODE_SPECS[mode]
    palette_size = 1 << spec["plane_count"]  # 4 for hcc2d4, 8 for hcc2d8
    if palette is None:
        palette = spec["default_palette"]
    else:
        if len(palette) != palette_size:
            raise ValueError(f"palette must have exactly {palette_size} entries for {mode}")
        if palette[0] != (0, 0, 0):
            raise ValueError("palette index 0 must be (0, 0, 0) — spec §5.8")
        if palette[-1] != (255, 255, 255):
            raise ValueError("palette last index must be (255, 255, 255) — spec §5.8")

    version_info = get_version(mode, version) if version else choose_version(mode, ec_level, payload)
    if not will_fit(mode, ec_level, payload, version_info):
        ec_capacity = version_info.ec_levels[EC_LEVEL_INDEX[ec_level]]
        data_bytes = ec_capacity.total_symbol_codewords - ec_capacity.total_codewords
        raise ValueError(
            f"{mode} payload is {len(payload)} bytes but version {version} at EC {ec_level} "
            f"fits at most {max(0, data_bytes - 3)} bytes"
        )
    ec_blocks = version_info.ec_levels[EC_LEVEL_INDEX[ec_level]]
    num_total_bytes = ec_blocks.total_symbol_codewords
    num_data_bytes = num_total_bytes - ec_blocks.total_codewords

    bits = build_header_and_data_bits(payload)
    terminate_bits(num_data_bytes, bits)
    final_bits = interleave_with_ec_bytes(bits, num_total_bytes, num_data_bytes, ec_blocks.num_blocks)

    plane_count = spec["plane_count"]
    # HCC2D chooses the shared mask using inverted plane 0 only.
    proxy_bits = invert_bits(extract_plane_bits(final_bits.bits, 0, plane_count))
    render_version = MODEL2_VERSIONS[version_info.number - 1]
    mask_pattern = choose_mask_pattern(proxy_bits, ec_level, render_version)
    # Once the winning mask is chosen, every plane is built with that same mask.
    planes = [
        build_matrix(extract_plane_bits(final_bits.bits, plane_index, plane_count), ec_level, render_version, mask_pattern)
        for plane_index in range(plane_count)
    ]

    modules = render_modules(planes, render_version, mode)
    white_index = len(palette) - 1
    width, height, pixels = rasterize(modules, scale, quiet_zone, white_index)
    return EncodedSymbol(
        mode=mode,
        ec_level=ec_level,
        version=version_info.number,
        inner_dimension=version_info.dimension,
        full_dimension=len(modules),
        mask_pattern=mask_pattern,
        palette=palette,
        pixels=pixels,
        width=width,
        height=height,
    )


# Encode a standards-compliant monochrome QR symbol using the same byte-mode,
# Reed-Solomon, placement, mask selection, and PNG primitives as the C 0.9.0
# reference encoder.
def encode_qr(
    payload: bytes,
    ec_level: str = "Q",
    version: int = 0,
    scale: int = 12,
    quiet_zone: int = 4,
) -> EncodedSymbol:
    if not payload:
        raise ValueError("payload is empty")
    if ec_level not in EC_LEVEL_INDEX:
        raise ValueError("ec level must be one of L/M/Q/H")
    if version < 0 or version > 40:
        raise ValueError("version must be 0-40")
    if scale < 6 or scale > 1000:
        raise ValueError("scale must be an integer from 6 to 1000")
    if quiet_zone < 0 or quiet_zone > 1000:
        raise ValueError("quiet zone must be an integer from 0 to 1000")

    version_info = get_version("qr", version) if version else choose_version("qr", ec_level, payload)
    if not will_fit("qr", ec_level, payload, version_info):
        ec_capacity = version_info.ec_levels[EC_LEVEL_INDEX[ec_level]]
        data_bits = (ec_capacity.total_symbol_codewords - ec_capacity.total_codewords) * 8
        count_bits = 8 if version_info.number <= 9 else 16
        max_payload = max(0, (data_bits - 4 - count_bits) // 8)
        raise ValueError(
            f"qr payload is {len(payload)} bytes but version {version} at EC {ec_level} "
            f"fits at most {max_payload} bytes"
        )

    ec_blocks = version_info.ec_levels[EC_LEVEL_INDEX[ec_level]]
    num_total_bytes = ec_blocks.total_symbol_codewords
    num_data_bytes = num_total_bytes - ec_blocks.total_codewords
    count_bits = 8 if version_info.number <= 9 else 16
    bits = build_header_and_data_bits(payload, count_bits)
    terminate_bits(num_data_bytes, bits)
    final_bits = interleave_with_ec_bytes(bits, num_total_bytes, num_data_bytes, ec_blocks.num_blocks)

    mask_pattern = choose_mask_pattern(final_bits.bits, ec_level, version_info)
    matrix = build_matrix(final_bits.bits, ec_level, version_info, mask_pattern)
    modules = [[0 if module else 1 for module in row] for row in matrix]
    width, height, pixels = rasterize(modules, scale, quiet_zone, 1)
    return EncodedSymbol(
        mode="qr",
        ec_level=ec_level,
        version=version_info.number,
        inner_dimension=version_info.dimension,
        full_dimension=version_info.dimension,
        mask_pattern=mask_pattern,
        palette=PALETTE_QR,
        pixels=pixels,
        width=width,
        height=height,
    )


# Translate internal exceptions into human-readable CLI error messages, adding payload/capacity details for overflow errors.
def friendly_error_message(
    error: Exception,
    args: argparse.Namespace | None = None,
    payload: bytes | None = None,
) -> str:
    message = str(error)
    if "payload does not fit in any supported version" in message and args is not None:
        mode = args.mode
        ec_level = args.ec_level
        max_v = get_version(mode, 40)
        ec_b = max_v.ec_levels[EC_LEVEL_INDEX[ec_level]]
        data_bits = (ec_b.total_symbol_codewords - ec_b.total_codewords) * 8
        # HCC2D always uses 16 bits; QR version 40 also uses 16 bits.
        count_bits = 16
        max_user_bytes = max(0, (data_bits - 4 - count_bits) // 8)
        payload_size = len(payload) if payload is not None else None
        size_str = f"{payload_size} bytes" if payload_size is not None else "unknown size"
        over_by = f", {payload_size - max_user_bytes} bytes over the limit" if payload_size is not None else ""
        file_note = (
            " Note: HCC2DF wrapping adds metadata bytes, "
            "which count toward the capacity."
            if getattr(args, "file_format", None) == "hcc2df"
            else ""
        )
        return (
            f"Error: with mode={mode} and ec_level={ec_level} the payload ({size_str}{over_by}) "
            f"does not fit in any supported symbol. "
            f"The maximum capacity for this combination (version 40) is {max_user_bytes} bytes.{file_note} "
            f"Try a lower EC level or a higher-capacity mode."
        )
    return f"Error: {message}"


# Serialize the encoded symbol as an indexed PNG file.
def write_png(path: Path, symbol: EncodedSymbol) -> None:
    path.write_bytes(build_indexed_png(symbol.width, symbol.height, symbol.pixels, symbol.palette))


class _HelpFormatter(argparse.RawDescriptionHelpFormatter, argparse.ArgumentDefaultsHelpFormatter):
    # Suppress the '(default: None)' suffix for arguments that have no default set.
    def _get_help_string(self, action: argparse.Action) -> str:
        if action.default is None:
            return action.help or ""
        return super()._get_help_string(action)


# Define and parse the CLI arguments; print help and exit cleanly when called with no arguments.
def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="hcc2d-encoder",
        description=_PROGRAM_INFO,
        epilog=(
            "Examples:\n"
            "  %(prog)s --text \"hello\" --mode qr --file-format raw qr.png\n"
            "  %(prog)s --text \"hello\" --mode hcc2d4 hcc2d4.png\n"
            "  %(prog)s --input-file photo.jpg --mode hcc2d8 --file-format hcc2df hcc2d8.png"
        ),
        formatter_class=_HelpFormatter,
    )
    parser.add_argument(
        "output",
        help="path of the PNG file to write",
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--text",
        metavar="STRING",
        help="UTF-8 string to encode as the payload",
    )
    src.add_argument(
        "--input-file",
        metavar="PATH",
        help="file bytes to encode",
    )
    parser.add_argument(
        "--file-format",
        choices=["hcc2df", "raw"],
        default="hcc2df",
        help=(
            "payload format: hcc2df wraps text or file bytes with name and "
            "compression metadata; raw encodes the bytes directly"
        ),
    )
    parser.add_argument(
        "--mode",
        choices=["qr", "hcc2d4", "hcc2d8"],
        default="hcc2d4",
        help=(
            "symbol mode: qr = standard black/white QR Code; hcc2d4 = 4 colours, "
            "2 bits per module; hcc2d8 = 8 colours, 3 bits per module. "
            "For qr, --file-format changes only the stored payload bytes"
        ),
    )
    parser.add_argument(
        "--ec-level",
        choices=["L", "M", "Q", "H"],
        default="Q",
        metavar="{L,M,Q,H}",
        help=(
            "error-correction level — how much of the symbol can be damaged "
            "and still decoded: L ≈ 7%%, M ≈ 15%%, Q ≈ 25%%, H ≈ 30%%. "
            "Higher levels reduce data capacity"
        ),
    )
    parser.add_argument(
        "--version",
        type=int,
        default=0,
        metavar="N",
        help=(
            "symbol version 1–40 (controls the grid size: version v → (17+4v)×(17+4v) "
            "inner modules); 0 = auto-select the smallest version that fits the payload"
        ),
    )
    parser.add_argument(
        "--scale",
        type=int,
        default=12,
        metavar="PX",
        help="pixels per module in the output PNG (minimum 6)",
    )
    parser.add_argument(
        "--quiet-zone",
        type=int,
        default=4,
        metavar="N",
        help="modules of white margin added outside the symbol border",
    )
    parser.add_argument(
        "--palette",
        choices=list(PALETTE_REGISTRY),
        default="model1",
        help=(
            "HCC2D colour palette: model1 = screen display; model2 = print/CMYK; "
            "ignored for qr"
        ),
    )
    if not argv:
        parser.print_help()
        sys.exit(0)
    return parser.parse_args(argv)


# CLI entry point: prepare payload, encode it, and write the PNG.
def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    payload: bytes | None = None
    try:
        if args.version < 0 or args.version > 40:
            raise ValueError("version must be an integer from 0 to 40")
        if args.scale < 6 or args.scale > 1000:
            raise ValueError("scale must be an integer from 6 to 1000")
        if args.quiet_zone < 0 or args.quiet_zone > 1000:
            raise ValueError("quiet zone must be an integer from 0 to 1000")

        if args.text is not None:
            source = args.text.encode("utf-8")
            source_name = "text.txt"
            source_kind = "text"
        else:
            input_path = Path(args.input_file)
            source = input_path.read_bytes()
            source_name = input_path.name
            source_kind = "file"
        if not source:
            raise ValueError("payload is empty")

        if args.file_format == "hcc2df":
            payload = build_hcc2df_payload(source_name, source)
            payload_kind = f"hcc2df-{source_kind}"
        else:
            payload = source
            payload_kind = f"raw-{source_kind}-bytes"

        if args.mode == "qr":
            symbol = encode_qr(
                payload=payload,
                ec_level=args.ec_level,
                version=args.version,
                scale=args.scale,
                quiet_zone=args.quiet_zone,
            )
        else:
            palette4, palette8 = PALETTE_REGISTRY[args.palette]
            palette = palette4 if args.mode == "hcc2d4" else palette8
            symbol = encode_hcc2d(
                payload=payload,
                mode=args.mode,
                ec_level=args.ec_level,
                version=args.version,
                scale=args.scale,
                quiet_zone=args.quiet_zone,
                palette=palette,
            )
        write_png(Path(args.output), symbol)
        print(
            f"wrote {args.output} mode={symbol.mode} ec={symbol.ec_level} version={symbol.version} "
            f"mask={symbol.mask_pattern} palette={args.palette} size={symbol.width}x{symbol.height} payload={payload_kind}"
        )
        return 0
    except Exception as error:
        print(friendly_error_message(error, args, payload), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
