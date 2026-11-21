# -*- mode: python ; coding: utf-8 -*-
# pyinstaller HomewindTokenExtractor.spec --clean -y

a = Analysis(
    ['src/homewind_tokenextractor/app.py'],
    pathex=['src'],
    datas=[('src/homewind_tokenextractor/assets', 'homewind_tokenextractor/assets')],
    hiddenimports=['PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets', 'PySide6.QtSvg', 'zeroconf'],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.Qt3DCore'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='HomewindTokenExtractor',
    console=False,
    upx=True,
    icon=['src/homewind_tokenextractor/assets/icon.ico'],
)
coll = COLLECT(exe, a.binaries, a.datas, upx=True, name='HomewindTokenExtractor')
app = BUNDLE(
    coll,
    name='HomewindTokenExtractor.app',
    icon='src/homewind_tokenextractor/assets/icon.icns',
    bundle_identifier='io.homewind.tokenextractor',
    # Needed once "Add to Homewind" browses the local network (macOS 15+ asks for permission).
    info_plist={
        'NSLocalNetworkUsageDescription': 'Finds your Homewind in your home network to add fans.',
        'NSBonjourServices': ['_homewind._tcp', '_http._tcp'],
    },
)
