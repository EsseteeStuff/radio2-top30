# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-spec voor Top30 op macOS (dubbelklikbare .app).

Bouwt een Top30.app (onedir + BUNDLE) met daarin de gebundelde
hulpprogramma's ffmpeg, node en de zelfstandige yt-dlp. De runtime-hook
zet de juiste map vooraan in PATH, zodat 'ffmpeg'/'node'/'yt-dlp' gewoon
gevonden worden.

Gebruik (op de projectroot, met een python die de dependencies heeft):
    TOP30_BUNDLE_DIR=/pad/naar/bundel pyinstaller \\
        --noconfirm --clean packaging/macos/top30-app.spec

De bundelmap moet per architectuur het juiste trio bevatten:
  - yt-dlp   -> het zelfstandige yt-dlp_macos (universeel, beide archs)
  - node     -> uit node-v*-darwin-<arm64|x64>.tar.gz  (bin/node)
  - ffmpeg   -> ffmpeg-darwin-<arm64|x64> (https://github.com/eugeneware/ffmpeg-static)
"""
import os

BASEDIR = os.path.abspath(SPECPATH)
ROOT = os.path.abspath(os.path.join(BASEDIR, "..", ".."))

# Meegebundelde losstaande programma's (ffmpeg, node, yt-dlp).
datas: list[tuple[str, str]] = []
bundle_dir = os.environ.get("TOP30_BUNDLE_DIR", "")
if bundle_dir and os.path.isdir(bundle_dir):
    for naam in sorted(os.listdir(bundle_dir)):
        pad = os.path.join(bundle_dir, naam)
        if os.path.isfile(pad):
            datas.append((pad, "."))
    print("Top30: bundelen:", [pad for pad, _ in datas])
else:
    print("Top30: TOP30_BUNDLE_DIR niet gevonden; geen hulpprogramma's gebundeld.")

rthook = os.path.join(BASEDIR, "..", "rthook_top30.py")

a = Analysis(
    [os.path.join(ROOT, "top30.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    # Lazily geïmporteerd in top30_core.py, dus niet zichtbaar voor de
    # statische analyse van PyInstaller:
    hiddenimports=[
        "requests",
        "bs4",
        "mutagen",
        "mutagen.id3",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[rthook],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="top30",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="top30",
)

app = BUNDLE(
    coll,
    name="Top30.app",
    icon=None,
    bundle_identifier="be.serge.Radio2Top30",
    info_plist={
        "CFBundleName": "Top30",
        "CFBundleShortVersionString": "1.0",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "11.0",
    },
)