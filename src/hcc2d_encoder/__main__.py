"""Allow ``python -m hcc2d_encoder`` to run the command-line encoder."""

from .encoder import main


if __name__ == "__main__":
    raise SystemExit(main())

