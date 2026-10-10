"""PyInstaller-runtime-hook voor Top30.

Zet de map waarin PyInstaller de meegebundelde hulpprogramma's uitpakt
(sys._MEIPASS) vooraan in PATH, zodat de app 'ffmpeg', 'node'/'deno' en de
losstaande 'yt-dlp' (.exe) kan vinden.
"""
import os
import sys

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    os.environ["PATH"] = (
        sys._MEIPASS + os.pathsep + os.environ.get("PATH", "")
    )