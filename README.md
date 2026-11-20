# Homewind Token Extractor

Reads the tokens of your Xiaomi fans so you can add them to [Homewind](https://github.com/mLihs/Homewind).

1. Sign in with your Xiaomi Home account (email and password, or QR code from the Xiaomi Home app).
2. You see only fans Homewind can control.
3. Click **Add to Homewind** to send the fan to a Homewind on your home network, or **Copy token** and paste it in the web UI.
4. **Reload fans** loads the list again with the same sign-in.

Your sign-in goes straight to Xiaomi. The password is not stored. The app remembers the last Homewind you added a fan to.

## Download a build

Pushes to `main` and pull requests run [GitHub Actions](.github/workflows/build.yml). Open the workflow run and download the macOS, Windows, or Linux artifact. A tag `v*` (for example `v0.1.0`) also publishes those files as a GitHub Release.

On macOS, the first launch of a new build is blocked because the app is not signed with an Apple developer certificate. Right-click the app, choose **Open**, then **Open** again.

## Run from source

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install .
homewind-tokenextractor        # or: python -m homewind_tokenextractor
```

## Build

```bash
pip install pyinstaller pillow
pyinstaller HomewindTokenExtractor.spec --clean -y
```

Pillow is required on macOS: PyInstaller converts `icon.ico` to an `.icns`. The same install is used by the GitHub Actions build.

## Fans shown

`src/homewind_tokenextractor/assets/fans/catalog.json` lists known models with product name and image. Fans whose model starts with `dmaker.fan.`, `zhimi.fan.` or `xiaomi.fan.` also appear, because SmartMiFanAsync accepts them; without a catalog entry they show a placeholder and the model ID. `enabled: false` hides a model (e.g. `dmaker.fan.1c`, 3 speeds only). Images are square PNGs on white, 352 px.

## Tests

```bash
pip install pytest && PYTHONPATH=src pytest -q
```

## Credits

Xiaomi Cloud login from [GUI-Miio-Tokenextrator-All-Plattforms](https://github.com/mLihs/GUI-Miio-Tokenextrator-All-Plattforms), based on [Xiaomi-cloud-tokens-extractor](https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor). MIT License.
