#!/usr/bin/env python3
"""Top30 - VRT Radio 2 hitlijsten ophalen, downloaden en omzetten naar mp3.

Start het programma met één commando:

    ./top30                 start het grafisch venster
    python top30.py         idem, maar dan via de venv-interpreter

De kern van het werk zit in top30_core.py, het venster in top30_gui.py.

Wie toch liever de oude commandoregel wil (handig in scripts, of om een
onderbroken run zonder venster over te nemen) gebruikt:

    python top30.py --cli scrape    --beginjaar 1971 --eindjaar 1975
    python top30.py --cli download
    python top30.py --cli convert   --verwijder-mp4
    python top30.py --cli alles
"""
import os
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# Zorg dat we in de virtual environment draaien. Zo hoeft de gebruiker geen
# `source .venv/bin/activate` te typen; één commando is genoeg.
# --------------------------------------------------------------------------
BASE = Path(__file__).resolve().parent
VENV_PY = BASE / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
if VENV_PY.exists() and Path(sys.executable).resolve() != VENV_PY.resolve():
    os.execv(str(VENV_PY), [str(VENV_PY), str(Path(__file__).resolve()), *sys.argv[1:]])

sys.path.insert(0, str(BASE))

import top30_core as kern  # noqa: E402  (na de venv-swap, dus imports zijn veilig)


# --------------------------------------------------------------------------
# Commandoregel (optie)
# --------------------------------------------------------------------------

def _vraag_jaar(tekst: str, standaard: int) -> int:
    while True:
        antwoord = input(f"{tekst} [{standaard}]: ").strip()
        if not antwoord:
            return standaard
        if antwoord.isdigit() and len(antwoord) == 4:
            return int(antwoord)
        print("Geef een jaartal met vier cijfers, bijv. 1971.")


def cli(args: list[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="top30 --cli",
        description="Top30 via de commandoregel (de GUI is de standaard).",
    )
    ap.add_argument(
        "stap", nargs="?", default="alles",
        choices=["alles", "scrape", "download", "convert", "verplaats", "fixprefix"],
        help="welke stap uitgevoerd moet worden",
    )
    ap.add_argument("--beginjaar", type=int, help="bv. --beginjaar 1971")
    ap.add_argument("--eindjaar", type=int, help="bv. --eindjaar 1975")
    ap.add_argument("--startnummer", type=int, default=1, help="eerste nummer bij hernoemen")
    ap.add_argument("--verwijder-mp4", action="store_true", help="mp4's opruimen na conversie")
    ap.add_argument("--nee-hernoemen", action="store_true", help="niet hernoemen bij verplaatsen")
    ap.add_argument("--overschrijven", action="store_true", help="hits-bestand opnieuw scrapen")
    ap.add_argument("--alleen-nieuwe", action="store_true",
                    help="sla over wat al in de muziekmap staat (default)")
    ap.add_argument("--geen-skip", dest="alleen_nieuwe", action="store_false",
                    help="download ook de nummers die al in de muziekmap staan")
    ap.set_defaults(alleen_nieuwe=True)
    ap.add_argument("--cookies", default=kern.COOKIE_STANDAARD,
                    choices=list(kern.COOKIE_BROWSERS),
                    help="browser waarvan yt-dlp cookies mag gebruiken")
    opties = ap.parse_args()

    paden = kern.paden_uit_instellingen().maak()
    ctx = kern.Context(
        paden=paden,
        cookie_browser=opties.cookies,
    )

    if opties.stap in ("alles", "scrape"):
        begin = opties.beginjaar or _vraag_jaar("Beginjaar", 1971)
        eind = opties.eindjaar or _vraag_jaar("Eindjaar", 1975)
        begin, eind, waarschuwingen = kern.controleer_jaren(begin, eind)
        for w in waarschuwingen:
            print(f"Let op: {w}")
    else:
        begin = opties.beginjaar or 0
        eind = opties.eindjaar or 0

    try:
        if opties.stap == "scrape":
            hits = kern.scrape(ctx, begin, eind, overschrijven=opties.overschrijven)
            print(f"{len(hits)} nummers in {paden.hits_bestand(begin, eind).name}")
        elif opties.stap == "download":
            if not begin or not eind:
                print("Geef --beginjaar en --eindjaar mee: het script heeft die nodig "
                      "om hits_BEGINJAAR_ENDJAAR.txt te vinden.")
                return 2
            kern.download(ctx, kern.laad_hits(ctx, begin, eind),
                          sla_bestaande_over=opties.alleen_nieuwe)
        elif opties.stap == "convert":
            kern.convert(ctx, verwijder_mp4=opties.verwijder_mp4)
        elif opties.stap == "verplaats":
            kern.verplaats(ctx, hernoem=not opties.nee_hernoemen,
                            startnummer=opties.startnummer)
        elif opties.stap == "fixprefix":
            kern.fixprefix(ctx)
        elif opties.stap == "alles":
            kern.voer_alles(
                ctx, begin, eind,
                verwijder_mp4=opties.verwijder_mp4,
                hernoem=not opties.nee_hernoemen,
                sla_bestaande_over=opties.alleen_nieuwe,
            )
    except kern.Fout as fout:
        print(f"\nFout: {fout}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nOnderbroken. Dezelfde stap herstarten gaat verder waar het stopte.")
        return 130
    print("Klaar.")
    return 0


# --------------------------------------------------------------------------

def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in ("--cli", "cli"):
        return cli(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        print("Met --cli krijg je dezelfde stappen via de commandoregel.")
        return 0
    if len(sys.argv) > 1 and sys.argv[1] in ("--thema",):
        thema = sys.argv[2] if len(sys.argv) > 2 else "donker"
    else:
        thema = None

    try:
        from PySide6 import QtWidgets  # noqa: F401
    except ImportError:
        print("PySide6 ontbreekt. Installeer de dependencies met:\n"
              "    .venv/bin/pip install -r requirements.txt", file=sys.stderr)
        return 1

    import top30_gui

    return top30_gui.start(thema)


if __name__ == "__main__":
    sys.exit(main())
