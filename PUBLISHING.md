# PyPI publication procedure

This repository builds the `hcc2d-encoder` distribution. PyPI releases and
their filenames are immutable, so never upload a test build with a version
number intended for a later production release.

## One-time account and repository setup

1. Create an account at <https://pypi.org/account/register/>.
2. Verify the account email address, enable two-factor authentication, and
   store the recovery codes securely.
3. Push the reviewed repository to
   `marco-querini/hcc2d-cli-python-encoder` on GitHub.
4. In the GitHub repository, create an environment named `pypi`. Requiring
   manual approval for that environment is strongly recommended.
5. In the PyPI account, open **Publishing**, add a pending GitHub publisher,
   and enter these exact values:

   ```text
   PyPI project name: hcc2d-encoder
   Owner: marco-querini
   Repository: hcc2d-cli-python-encoder
   Workflow: release.yml
   Environment: pypi
   ```

A pending publisher does not reserve the project name. Complete the first
release soon after configuring it. Trusted Publishing uses short-lived OIDC
credentials; no PyPI API token or GitHub secret is required.

Official references:

- <https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/>
- <https://docs.pypi.org/trusted-publishers/using-a-publisher/>

## Pre-release checks

1. Work from the exact clean, reviewed commit that will be released.
2. Confirm that `pyproject.toml`, `hcc2d_encoder.__version__`, the changelog,
   and the source header all contain the same release number.
3. Confirm that no credentials, private keys, build environments, generated
   PNG files, or local build output are tracked.
4. Run the tests and build locally.
5. Confirm that GitHub CI passes.
6. Verify the project name on PyPI immediately before the first publication.

## Local build and validation

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip build twine
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m build
.venv/bin/python -m twine check --strict dist/*
```

Expected artifacts for version 0.9.0:

```text
dist/hcc2d_encoder-0.9.0-py3-none-any.whl
dist/hcc2d_encoder-0.9.0.tar.gz
```

Install the wheel in a fresh environment without consulting a package index:

```bash
python3 -m venv /tmp/hcc2d-wheel-test
/tmp/hcc2d-wheel-test/bin/python -m pip install \
  --no-index dist/hcc2d_encoder-0.9.0-py3-none-any.whl
/tmp/hcc2d-wheel-test/bin/hcc2d-encoder --help
```

Generate at least one QR symbol and one HCC2D symbol before publishing.

## Production release

1. Create a GitHub release for the exact commit, using a version tag such as
   `v0.9.0`.
2. Publishing the GitHub release triggers `.github/workflows/release.yml`.
3. The workflow reruns the tests, builds the wheel and source distribution,
   validates both with Twine, and publishes them through the protected `pypi`
   environment.
4. Verify the PyPI project page and uploaded hashes.
5. Install from PyPI into a new environment and generate both QR and HCC2D
   sample images.

## TestPyPI and emergency manual upload

TestPyPI is optional and uses a separate account and credentials. Do not test
with the production version number, because repositories do not allow an
uploaded filename to be reused.

If Trusted Publishing is unavailable and a manual upload is deliberately
authorized, use a project-scoped PyPI API token supplied interactively:

```bash
.venv/bin/python -m twine upload dist/*
```

Never place a token in this repository, the shell history, a command line,
`pyproject.toml`, or a committed `.pypirc`.
