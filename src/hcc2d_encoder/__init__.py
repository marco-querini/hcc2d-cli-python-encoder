"""Public API for the HCC2D Python reference encoder."""

from .encoder import (
    EncodedSymbol,
    PALETTE_4_MODEL1,
    PALETTE_4_MODEL2,
    PALETTE_8_MODEL1,
    PALETTE_8_MODEL2,
    PALETTE_QR,
    build_hcc2df_payload,
    build_indexed_png,
    encode_hcc2d,
    encode_qr,
    write_png,
)

__version__ = "0.9.0"

__all__ = [
    "EncodedSymbol",
    "PALETTE_4_MODEL1",
    "PALETTE_4_MODEL2",
    "PALETTE_8_MODEL1",
    "PALETTE_8_MODEL2",
    "PALETTE_QR",
    "__version__",
    "build_hcc2df_payload",
    "build_indexed_png",
    "encode_hcc2d",
    "encode_qr",
    "write_png",
]

