# Release Packaging

PRL-Today uses PyInstaller for native desktop artifacts. Build each target platform on that platform: Windows builds the `.exe`, macOS builds the `.app`, and Linux builds the ELF executable. The GitHub Actions workflow in `.github/workflows/release.yml` does this with a matrix.

## Local Build

```powershell
python -m pip install -e ".[build]"
python -m PyInstaller PRL-Today.spec --noconfirm --clean
python scripts/package_release.py --output release
```

Expected local outputs:

- Windows: `release/PRL-Today-windows-x64.zip`
- macOS: `release/PRL-Today-macos-<arch>.tar.gz`
- Linux: `release/PRL-Today-linux-x64.tar.gz`

## GitHub Release Build

The release workflow runs on:

- `windows-latest` for Windows x64.
- `macos-15-intel` for macOS x64.
- `macos-14` for macOS arm64.
- `ubuntu-latest` for Linux x64.

Run it manually from GitHub Actions, or push a version tag:

```powershell
git tag v0.1.3
git push origin v0.1.3
```

For tag builds, the workflow uploads all packaged assets to the GitHub Release for the tag. For manual builds, download artifacts from the workflow run.

## Current Release Limits

- Windows artifacts are not code-signed.
- macOS artifacts are not code-signed or notarized.
- Linux artifacts are raw tarballs, not AppImage, deb, rpm, or Flatpak packages.
- Runtime smoke testing is still manual; the workflow verifies that PyInstaller produces archives, not that the GUI launches on every desktop environment.
