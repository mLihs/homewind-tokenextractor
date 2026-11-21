The app icon is now the Homewind wind mark.

## Platform-specific notes

### macOS (Apple Silicon)

The Mac build runs on Apple Silicon (M1 or newer), not on Intel Macs.

- Download `HomewindTokenExtractor-macOS.dmg` from Releases
- Open the disk image. The app inside is `HomewindTokenExtractor.app`
- Drag it to your Applications folder, or open it from the disk image
- First launch: right-click the app and choose **Open**, then **Open** again. A normal double-click is blocked because the app is not signed with an Apple developer certificate
- If macOS still blocks it, open System Settings > Privacy & Security, scroll to Security, and click **Open Anyway**
- Optional, in Terminal: `xattr -cr /path/to/HomewindTokenExtractor.app`
- The first time you add a fan, allow the app to find devices on your local network

### Windows

- Download `HomewindTokenExtractor-Windows.zip` from Releases
- Extract the folder anywhere
- Open that folder and run `HomewindTokenExtractor.exe`

Antivirus warnings: the app may be flagged as unknown. Add an exception if needed.

No installation: just extract and run the `.exe`.

Dependencies: everything is bundled. No extra software is needed.

Compatibility: Windows 10 (1809+) and Windows 11.

### Linux

- Download `HomewindTokenExtractor-Linux.tar.gz` from Releases
- Extract: `tar -xzf HomewindTokenExtractor-Linux.tar.gz`
- Make executable: `chmod +x HomewindTokenExtractor/HomewindTokenExtractor`
- Run: `./HomewindTokenExtractor/HomewindTokenExtractor`

## General use

This software is provided "as is" without warranties. The authors are not liable for any damages or issues arising from use.

### Personal use only

You are responsible for complying with Xiaomi's terms of service and local laws. Use at your own risk.

### Hardware / firmware notice

This project interacts with physical devices and network services. Incorrect usage may lead to device malfunction, connection issues, or data loss.

### Reverse engineering notice

The app uses reverse-engineered protocols (miIO). Behavior may change because of vendor updates.

### Brand independence

Not affiliated with or endorsed by Xiaomi, SmartMi, Aqara, or any mentioned brands. All trademarks belong to their respective owners.
