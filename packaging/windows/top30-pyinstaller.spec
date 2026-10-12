# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-spec voor Top30 (onefile).

Werkt zowel lokaal op Linux (smoke-test) als in de Windows-build op GitHub
Actions. Gebundelde hulpprogramma's (ffmpeg.exe, node.exe, deno.exe,
yt-dlp.exe) komen uit de map in $TOP30_BUNDLE_DIR en worden naast de app in
het pakket gezet; de runtime-hook (rthook_top30.py) voegt die map aan PATH
toe, zodat yt-dlp/ffmpeg/node vanaf hun gewone naam gevonden worden.

Gebruik (vanuit de projectroot, met een python die de dependencies heeft):
    TOP30_BUNDLE_DIR=/pad/naar/bundel .venv/bin/pyinstaller \\
        --noconfirm --clean --onefile packaging/windows/top30-pyinstaller.spec
"""
import os

BASEDIR = os.path.abspath(SPECPATH)
ROOT = os.path.abspath(os.path.join(BASEDIR, "..", ".."))

# Meegebundelde losstaande programma's (op Windows: .exe-versies).
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
    runtime_hooks=[os.path.join(BASEDIR, "..", "rthook_top30.py")],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="top30",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)