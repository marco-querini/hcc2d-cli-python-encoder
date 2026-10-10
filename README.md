# HCC2D Python Encoder 0.9.0

Written by Marco Querini.

Pure Python distribution of the HCC2D reference encoder. It is functionally
aligned with the public
[single-file C reference encoder](https://github.com/marco-querini/hcc2d-cli-c-encoder)
0.9.0, has no runtime dependencies, and can be used either as a command-line
application or as an importable library.

## Official links

- HCC2D website: <https://hcc2d.com/en/>
- HCC2D Code Specification 0.9.0: <https://doi.org/10.5281/zenodo.22206528>
- HCC2D API: <https://hcc2d.com/en/api>
- HCC2D Decoder on Google Play: <https://play.google.com/store/apps/details?id=com.hcc2d.decoder>
- HCC2D Decoder on Huawei AppGallery:
  <https://appgallery.cloud.huawei.com/marketshare/app/C117478101>
- HCC2D Decoder on the App Store: <https://apps.apple.com/app/id6762202762>
- HCC2D Encoder on the Mac App Store: <https://apps.apple.com/app/id6767833986>

## Supported features

- standard black/white QR Code
- HCC2D4 with 4 colours and 2 bits per module
- HCC2D8 with 8 colours and 3 bits per module
- EC levels `L`, `M`, `Q`, and `H`
- versions `1..40`, or `0` for automatic selection
- screen-oriented Model 1 and print-oriented Model 2 palettes
- raw payloads and optional HCC2DF wrapping
- text and binary-file inputs
- indexed PNG output

HCC2D16 is not included because it is not part of the HCC2D 0.9.0
specification or the public C reference encoder 0.9.0.

## Requirements

- Python 3.8 or later
- no third-party runtime packages

## Installation

From PyPI:

```bash
python3 -m pip install hcc2d-encoder
```

For an isolated command-line installation:

```bash
pipx install hcc2d-encoder
```

Before the first PyPI release, or when working from a clone, install the local
source tree instead:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
```

## Command-line usage

Show the complete help and legal notice:

```bash
hcc2d-encoder --help
```

The equivalent module entry point is:

```bash
python3 -m hcc2d_encoder --help
```

Generate a standard QR Code containing raw UTF-8 text:

```bash
hcc2d-encoder --text "https://hcc2d.com/spec" \
  --mode qr --file-format raw qr_spec_url.png
```

Generate an HCC2D4 symbol containing raw text bytes:

```bash
hcc2d-encoder --text "Batch=2026-06-16;Line=A3;Unit=004271" \
  --mode hcc2d4 --file-format raw hcc2d4_label.png
```

Generate an HCC2D8 symbol carrying a file in an HCC2DF container:

```bash
hcc2d-encoder --input-file report.pdf --mode hcc2d8 \
  --file-format hcc2df --ec-level L hcc2d8_report.png
```

Defaults are HCC2D4, EC level Q, automatic version selection, 12 pixels per
module, a 4-module quiet zone, Model 1 palette, and HCC2DF wrapping.

Run `hcc2d-encoder --help` for the complete option reference. Exactly one of
`--text` and `--input-file` is required. The destination PNG path is the final
positional argument.

### Raw versus HCC2DF

Use `raw` when the input bytes are already the complete payload and filename
metadata is unnecessary. This minimizes overhead.

Use `hcc2df` when the payload should carry a filename and may benefit from
automatic zlib compression. Compression is used only when the content is at
least 128 bytes and the compressed representation is strictly smaller than
90% of the original size. File input preserves the basename; text input uses
`text.txt` as its embedded filename.

## Python API

Generate an HCC2D4 PNG:

```python
from pathlib import Path

from hcc2d_encoder import encode_hcc2d, write_png

symbol = encode_hcc2d(
    b"hello",
    mode="hcc2d4",
    ec_level="Q",
    version=0,
    scale=12,
    quiet_zone=4,
)
write_png(Path("hello.png"), symbol)
```

Generate a standard QR PNG:

```python
from pathlib import Path

from hcc2d_encoder import encode_qr, write_png

symbol = encode_qr(b"https://hcc2d.com/", ec_level="Q")
write_png(Path("hcc2d-website.png"), symbol)
```

Both encoding functions return an `EncodedSymbol`. Pass that object to
`write_png`, or use `build_indexed_png` when the encoded PNG bytes are needed
in memory. The lower-level public helpers and palette constants are listed in
`hcc2d_encoder.__all__`.

## Compatibility and validation

The Python encoder was compared directly with the public C reference encoder
0.9.0. Validation covered:

- all versions from 1 through 40
- QR, HCC2D4, and HCC2D8
- EC levels L, M, Q, and H
- all applicable Model 1 and Model 2 palettes
- raw and HCC2DF text/file payloads
- automatic version selection and capacity failures
- controlled CLI errors without Python tracebacks

The exhaustive forced-version matrix produced 800 out of 800 PNG files that
were byte-identical to the C implementation. The automated tests also pin
known QR, HCC2D4, and HCC2D8 output hashes.

Run the package tests with:

```bash
python3 -m unittest discover -s tests -v
```

GitHub Actions runs the test suite on every declared Python version from 3.8
through 3.13 and verifies that both PyPI distribution formats build cleanly.

## Building PyPI artifacts locally

Use an isolated environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip build twine
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m build
.venv/bin/python -m twine check --strict dist/*
```

This produces a pure-Python wheel and a source distribution under `dist/`.
Before the first real release, test installation from the wheel in a fresh
virtual environment.

Production publication is performed by the release workflow through PyPI
Trusted Publishing, so no long-lived API token is stored in the repository or
in GitHub secrets. See [PUBLISHING.md](PUBLISHING.md) for the one-time PyPI
configuration and the complete release checklist.

## License and warranty

Copyright 2010-2026 Marco Querini.

SPDX-License-Identifier: Apache-2.0. See [LICENSE](LICENSE) for the complete
license text.

This software is provided "as is", without warranties or conditions of any
kind, express or implied, including but not limited to merchantability,
fitness for a particular purpose, and noninfringement. Use is entirely at your
own risk. The author assumes no responsibility or liability for damages,
losses, claims, unreadable or non-decodable codes, failed scans, data loss, or
other consequences arising from its use.

## Notice

The views expressed in connection with the HCC2D Code Specification, HCC2D
applications distributed through app stores, and HCC2D source code released
as open source are solely those of the author and do not necessarily reflect
the official position of any institution, organization, or employer with
which the author is or has been affiliated.
