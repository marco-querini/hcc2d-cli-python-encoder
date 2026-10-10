# Changelog

## 0.9.0

- packaged the Python HCC2D reference encoder for PyPI
- aligned encoding behavior with the public C reference encoder 0.9.0
- added standard QR, HCC2D4, and HCC2D8 output
- added raw and HCC2DF payload formats for both text and files
- aligned defaults, validation limits, palettes, help, copyright, license,
  disclaimer, and specification references
- verified byte-identical PNG output against the C reference across all symbol
  versions, error-correction levels, and supported palettes
- added an importable API, `python -m hcc2d_encoder`, and the
  `hcc2d-encoder` console command
- added regression tests for known QR, HCC2D4, and HCC2D8 outputs
- added GitHub Actions CI for Python 3.8 through 3.13
- added a PyPI Trusted Publishing release workflow and publication guide
