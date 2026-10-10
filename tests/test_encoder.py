import contextlib
import hashlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from hcc2d_encoder import (
    PALETTE_4_MODEL1,
    PALETTE_8_MODEL2,
    __version__,
    build_hcc2df_payload,
    build_indexed_png,
    encode_hcc2d,
    encode_qr,
    write_png,
)
from hcc2d_encoder.encoder import main


class EncoderTests(unittest.TestCase):
    def test_package_version(self):
        self.assertEqual(__version__, "0.9.0")

    def test_qr_known_output(self):
        symbol = encode_qr(b"hello", scale=6, quiet_zone=0)
        png = build_indexed_png(symbol.width, symbol.height, symbol.pixels, symbol.palette)
        self.assertEqual(symbol.version, 1)
        self.assertEqual(symbol.mask_pattern, 7)
        self.assertEqual(
            hashlib.sha256(png).hexdigest(),
            "ec991c96b237863b88cfc016613fe235bf0805df63c17523363e668b7440cebf",
        )

    def test_hcc2d_modes_and_palettes(self):
        four = encode_hcc2d(b"hello", mode="hcc2d4", scale=6, quiet_zone=0)
        eight = encode_hcc2d(
            b"hello",
            mode="hcc2d8",
            scale=6,
            quiet_zone=0,
            palette=PALETTE_8_MODEL2,
        )
        self.assertEqual(four.full_dimension, four.inner_dimension + 2)
        self.assertEqual(eight.full_dimension, eight.inner_dimension + 2)
        self.assertEqual(len(four.palette), 4)
        self.assertEqual(len(eight.palette), 8)
        self.assertEqual(four.palette, PALETTE_4_MODEL1)
        self.assertEqual(four.version, 1)
        self.assertEqual(four.mask_pattern, 0)
        self.assertEqual(eight.version, 1)
        self.assertEqual(eight.mask_pattern, 4)
        self.assertEqual(
            hashlib.sha256(
                build_indexed_png(four.width, four.height, four.pixels, four.palette)
            ).hexdigest(),
            "4a1c07ad11d49f383ee84de44dd20caac84d2b9fef627a9ac0de7c561a1a32bd",
        )
        self.assertEqual(
            hashlib.sha256(
                build_indexed_png(eight.width, eight.height, eight.pixels, eight.palette)
            ).hexdigest(),
            "020835a99fa64c46e35cd97d842316e85c2390fd585064a07299e8aed9813542",
        )

    def test_hcc2df_wrapper(self):
        payload = build_hcc2df_payload("folder/example.txt", b"A" * 512)
        self.assertEqual(payload[:6], b"HCC2DF")
        self.assertEqual(payload[6], 1)
        self.assertEqual(payload[7], 1)
        name_length = payload[8]
        self.assertEqual(payload[9 : 9 + name_length], b"example.txt")

    def test_hcc2df_wrapper_without_compression(self):
        content = b"short payload"
        payload = build_hcc2df_payload("example.bin", content)
        name_length = payload[8]
        self.assertEqual(payload[7], 0)
        self.assertEqual(payload[9 + name_length :], content)

    def test_hcc2df_filename_validation(self):
        with self.assertRaisesRegex(ValueError, "non-empty"):
            build_hcc2df_payload("", b"x")
        with self.assertRaisesRegex(ValueError, "at most 127"):
            build_hcc2df_payload("x" * 128, b"x")

    def test_validation(self):
        with self.assertRaisesRegex(ValueError, "payload is empty"):
            encode_qr(b"")
        with self.assertRaisesRegex(ValueError, "6 to 1000"):
            encode_hcc2d(b"x", scale=5)
        with self.assertRaisesRegex(ValueError, "hcc2d4 or hcc2d8"):
            encode_hcc2d(b"x", mode="hcc2d16")

    def test_write_png(self):
        symbol = encode_hcc2d(b"file output")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "symbol.png"
            write_png(output, symbol)
            self.assertTrue(output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))

    def test_cli_and_help(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "symbol.png"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                status = main(
                    [
                        "--text",
                        "hello",
                        "--mode",
                        "qr",
                        "--file-format",
                        "raw",
                        str(output),
                    ]
                )
            self.assertEqual(status, 0)
            self.assertIn("mode=qr", stdout.getvalue())
            self.assertTrue(output.is_file())

    def test_cli_error_has_no_traceback(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            status = main(
                [
                    "--text",
                    "hello",
                    "--mode",
                    "qr",
                    "--file-format",
                    "raw",
                    "--version",
                    "41",
                    "unused.png",
                ]
            )
        self.assertEqual(status, 1)
        self.assertIn("Error: version", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_empty_argument_list_shows_help(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as raised:
                main([])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("usage: hcc2d-encoder", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
