#!/usr/bin/env python3
"""Opschonen: dubbele nummers uit de muziekmap halen en opnieuw nummeren.

Per groep met dezelfde artiest+titel blijft het bestand met de hoogste
bitrate over. Daarna wordt de hele map opnieuw geschud en genummerd.
"""
import collections
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/home/serge/Projecten/Python3/top30")
import top30_core as k

MUZIEK = Path("/home/serge/Muziek/DeJaren70")


def bitrate(pad: Path) -> int:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=bit_rate", "-of", "default=nw=1:nk=1", str(pad)],
        capture_output=True, text=True)
    try:
        return int(r.stdout.strip())
    except ValueError:
        return pad.stat().st_size * 8 // 1000


def duur(pad: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(pad)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def main(werkelijk: bool) -> int:
    groepen: dict[str, list[Path]] = collections.defaultdict(list)
    for pad in k.mp3_bestanden(MUZIEK):
        groepen[k.vergelijk_sleutel(k.zonder_prefix(pad.stem))].append(pad)
    dubbel = {s: v for s, v in groepen.items() if len(v) > 1}

    print(f"{len(k.mp3_bestanden(MUZIEK))} mp3's, {len(groepen)} unieke nummers, "
          f"{len(dubbel)} groepen met dubbels")
    print()

    weg: list[Path] = []
    for sleutel, paden in sorted(dubbel.items()):
        # hoogste bitrate wint; bij gelijkspel het laagste nummer
        winnaar = max(paden, key=lambda p: (bitrate(p), -int(p.name.split("-", 1)[0])))
        losers = [p for p in paden if p != winnaar]
        weg.extend(losers)
        print(f"  {'+'.join(str(bitrate(p)) for p in paden):>15}  "
              f"{sleutel[:44]:44}  blijft {winnaar.name.split('-', 1)[0]}")

    print()
    print(f"te verwijderen: {len(weg)}")
    print(f"blijven over : {len(k.mp3_bestanden(MUZIEK)) - len(weg)}")

    if not werkelijk:
        print("\n(Droge proef. Nog niets verwijderd.)")
        return 0

    # Eerst de hele lijst vaststellen, pas dan verwijderen: een crash
    # halverwege mag geen halvering achterlaten.
    for pad in weg:
        pad.unlink()
    print(f"\n{len(weg)} bestanden verwijderd")

    # Nummering dichtmaken en opnieuw schudden, via de geteste kernfunctie.
    ctx = k.Context(paden=k.Paden(Path("/tmp/opschonen_werk"), MUZIEK), log=print)
    plan = k.nummer_hernoemen(ctx)
    print(f"\n{len(plan)} bestanden opnieuw geschud en genummerd")
    print(f"breedte nu: {k.prefix_breedte(len(k.mp3_bestanden(MUZIEK)))} cijfers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--ja" in sys.argv))
