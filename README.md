# Homewind Token Extractor

This app is a helper app for [Homewind](https://homewind.io). It adds Xiaomi fans to Homewind with one click, or it gets the fan token so you can add a fan to Homewind manually.

## What you do

1. Open the app and sign in to Xiaomi Home with your email and password, or with a QR code from the Xiaomi Home app on your phone. The password is not saved.
2. You see your fans. Only fans that Homewind can control are listed.
3. Click **Add to Homewind** on a fan. The app looks for your Homewind and sends the token. The next time, it tries that same Homewind first.
4. **Reload fans** loads the list again without asking for the password again.

The first time you open the app on a Mac, a normal double-click may be blocked. Right-click the app, choose **Open**, then choose **Open** again. The first time you add a fan, macOS or Windows may ask if the app may look for devices on your local network. Allow that.

A step-by-step guide, including several Homewinds and the messages on a fan, is in [Using the app](docs/USAGE.md).

## Get the app

When a version is published, open the Releases page of this repository and download the file for your computer. You do not need to install Python.

- Mac: `HomewindTokenExtractor-macOS.dmg`. Open the disk image, then open **HomewindTokenExtractor**.
- Windows: `HomewindTokenExtractor-Windows.zip`. Unzip it and run **HomewindTokenExtractor.exe** inside the folder.
- Linux: `HomewindTokenExtractor-Linux.tar.gz`. Unpack it and run the program inside.

## For developers

Pushes to `main` and pull requests run [GitHub Actions](.github/workflows/build.yml), which uploads a Mac, Windows, and Linux build. A version tag such as `v0.1.1` also publishes those files as a GitHub Release: a Mac disk image, a Windows zip, and a Linux archive.

### Run from source

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install .
homewind-tokenextractor        # or: python -m homewind_tokenextractor
```

### Build

```bash
pip install pyinstaller pillow
pyinstaller HomewindTokenExtractor.spec --clean -y
```

On macOS, Pillow is required because PyInstaller converts `icon.ico` into an `.icns` file. The GitHub Actions build installs it the same way.

### Fans shown

`src/homewind_tokenextractor/assets/fans/catalog.json` lists known models with a product name and an image. Fans whose model starts with `dmaker.fan.`, `zhimi.fan.`, or `xiaomi.fan.` also appear, because SmartMiFanAsync accepts them. Without a catalog entry they show a placeholder and the model ID. `enabled: false` hides a model (for example `dmaker.fan.1c`, which has only 3 speeds). Images are square PNGs on white, 352 px.

### Tests

```bash
pip install pytest && PYTHONPATH=src pytest -q
```

## Docs

- [Using the app](docs/USAGE.md) — sign-in, fan list, adding a fan, what is stored, and what the error texts mean.
- [Add to Homewind concept](docs/ADD_TO_HOMEWIND_CONCEPT.md) — design notes for the LAN API (German). Stage A is what the app does today. Stage B (showing that a fan is already in Homewind, and updating its token) is not built yet.

## Credits

Xiaomi Cloud login from [GUI-Miio-Tokenextrator-All-Plattforms](https://github.com/mLihs/GUI-Miio-Tokenextrator-All-Plattforms), based on [Xiaomi-cloud-tokens-extractor](https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor). MIT License.
