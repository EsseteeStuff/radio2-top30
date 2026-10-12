"""PyInstaller-runtime-hook voor Top30 (gedeeld door alle platformen).

Zet de map(len) waarin PyInstaller de meegebundelde hulpprogramma's neerzet
vooraan in PATH, zodat de app 'ffmpeg', 'node'/'deno' en de zelfstandige
'yt-dlp' kan vinden:

- onefile:  sys._MEIPASS is de map waaruit de gebundelde datas worden
            uitgepakt tijdens opstarten;
- onedir/-app: de datas liggen in de map met de gebundelde bestanden
            (macOS-.app: Contents/Frameworks) en het opstartprogramma in
            Contents/MacOS (dirname(sys.executable)).

Beide mappen worden toegevoegd om elke pakketvorm te dekken.
"""
import os
import sys

if getattr(sys, "frozen", False):
    paden = []
    if hasattr(sys, "_MEIPASS"):
        paden.append(sys._MEIPASS)
    paden.append(os.path.dirname(sys.executable))
    omgeving = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    os.environ["PATH"] = os.pathsep.join(paden + omgeving)