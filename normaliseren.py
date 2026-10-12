#!/usr/bin/env python3
# Copyright (C) 2026 EsseteeStuff
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Luidheid van muziek normaliseren met ffmpeg (EBU R128 / loudnorm).

`mp3gain` werkt alleen op mp3: het verandert de 'global gain' in het bestand
zonder het geluid opnieuw te coderen, dus verliesloos. Voor m4a/aac (en andere
formaten) bestaat die truc niet en moet de audio opnieuw door de encoder. Dit
script doet dat met het loudnorm-filter van ffmpeg, in twee passes: eerst
meten, dan toepassen. Zo klinken alle nummers ongeveer even luid.

    python normaliseren.py Muziek/Jaren70             # droge proef
    python normaliseren.py Muziek/Jaren70 --ja        # echt uitvoeren
    python normaliseren.py Muziek/Jaren70 --ja --mp3  # ook mp3's

Standaard pakt het alleen formaten die mp3gain niet aankan (m4a, aac, ...).
Met --mp3 doet het ook mp3's, maar dat hercodeert en kost kwaliteit; voor mp3
is `mp3gain` de betere keuze. Elk bestand wordt naar een tijdelijk bestand
geschreven in dezelfde map en in hetzelfde formaat; pas als dat lukt, wordt
het origineel vervangen. Met --backup blijft het origineel als .bak bewaard.
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import top30_core as k  # noqa: E402

# Per extensie hoe we het geluid terugschrijven. De extensie van het tijdelijke
# bestand blijft gelijk aan het origineel, zodat ffmpeg het juiste 'muxer' kiest.
CODECS: dict[str, list[str]] = {
    ".mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
    ".m4a": ["-c:a", "aac", "-b:a", "256k"],
    ".aac": ["-c:a", "aac", "-b:a", "256k"],
    ".ogg": ["-c:a", "libvorbis", "-q:a", "6"],
    ".opus": ["-c:a", "libopus", "-b:a", "160k"],
    ".flac": ["-c:a", "flac"],
    ".wav": ["-c:a", "pcm_s16le"],
}
# Formaten die mp3gain al aankan (en die we dus standaard overslaan).
MP3GAIN_DOET = {".mp3"}


def audio_bestanden(map_: Path, recursief: bool, ook_mp3: bool) -> list[Path]:
    """Alle ondersteunde audiobestanden in (of onder) een map."""
    if not map_.is_dir():
        return []
    kandidaten = map_.rglob("*") if recursief else map_.iterdir()
    return sorted(
        p for p in kandidaten
        if p.is_file()
        and p.suffix.lower() in CODECS
        and (ook_mp3 or p.suffix.lower() not in MP3GAIN_DOET)
    )


def _ontleed_json(uitvoer: str) -> dict | None:
    """Het loudnorm-rapport (JSON) uit de ffmpeg-uitvoer vissen."""
    for blok in re.findall(r"\{[^{}]*\}", uitvoer):
        if '"input_i"' in blok:
            try:
                return json.loads(blok)
            except ValueError:
                continue
    return None


def meet(ctx: k.Context, pad: Path, lufs: float, tp: float, lra: float) -> dict | None:
    """Eerste pass: meet hoe luid het bestand nu is."""
    _, uitvoer = k.draai_proces([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(pad),
        "-af", f"loudnorm=I={lufs}:TP={tp}:LRA={lra}:print_format=json",
        "-f", "null", "-",
    ], ctx)
    return _ontleed_json(uitvoer)


def pas_toe(ctx: k.Context, pad: Path, meting: dict, lufs: float, tp: float,
            lra: float) -> Path | None:
    """Tweede pass: normaliseren naar een tijdelijk bestand.

    Geeft het pad van het tijdelijke bestand terug, of None als het mislukte.
    """
    tmp = pad.with_name(pad.stem + ".loudness" + pad.suffix)
    tmp.unlink(missing_ok=True)
    filter_ = (
        f"loudnorm=I={lufs}:TP={tp}:LRA={lra}:"
        f"measured_I={meting['input_i']}:measured_TP={meting['input_tp']}:"
        f"measured_LRA={meting['input_lra']}:measured_thresh={meting['input_thresh']}:"
        f"offset={meting['target_offset']}:linear=true"
    )
    code, _ = k.draai_proces([
        "ffmpeg", "-hide_banner", "-nostats", "-y", "-i", str(pad),
        "-map", "0:a", "-map", "0:v?", "-c:v", "copy",
        "-af", filter_, *CODECS[pad.suffix.lower()],
        "-map_metadata", "0", str(tmp),
    ], ctx)
    if code != 0 or not tmp.exists() or tmp.stat().st_size == 0:
        tmp.unlink(missing_ok=True)
        return None
    return tmp


def vervang(pad: Path, tmp: Path, backup: bool) -> None:
    """Zet het tijdelijke bestand op zijn plaats (en bewaar eventueel een .bak)."""
    if backup:
        bak = pad.with_name(pad.name + ".bak")
        bak.unlink(missing_ok=True)
        pad.replace(bak)
    else:
        pad.unlink(missing_ok=True)
    tmp.replace(pad)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Normaliseer de luidheid van audiobestanden met ffmpeg loudnorm.",
    )
    ap.add_argument("map", nargs="?", default=".", type=Path,
                    help="map met muziek (standaard: de huidige map)")
    ap.add_argument("--ja", action="store_true",
                    help="echt uitvoeren (zonder deze optie: droge proef)")
    ap.add_argument("--mp3", action="store_true",
                    help="ook mp3's aanpakken (hercodeert; mp3gain is beter)")
    ap.add_argument("--recursief", action="store_true",
                    help="ook in onderliggende mappen kijken")
    ap.add_argument("--lufs", type=float, default=-16.0,
                    help="doel-luidheid in LUFS (standaard -16; streaming: -14)")
    ap.add_argument("--tp", type=float, default=-1.5,
                    help="maximale true peak in dBTP (standaard -1.5)")
    ap.add_argument("--lra", type=float, default=11.0,
                    help="doel-loudness-range (standaard 11)")
    ap.add_argument("--backup", action="store_true",
                    help="bewaar het origineel als <naam>.bak")
    opties = ap.parse_args(argv)

    if shutil.which("ffmpeg") is None:
        print("ffmpeg niet gevonden. Installeer het bijvoorbeeld met:\n"
              "    brew install ffmpeg", file=sys.stderr)
        return 1

    map_ = opties.map.expanduser()
    bestanden = audio_bestanden(map_, opties.recursief, opties.mp3)
    if not bestanden:
        print(f"Geen audiobestanden gevonden in {map_}.")
        if not opties.mp3:
            print("(mp3's worden standaard overgeslagen; voeg --mp3 toe om ze "
                  "toch te doen.)")
        return 0

    ctx = k.Context(paden=k.Paden(map_, map_), log=print)
    print(f"{len(bestanden)} bestand(en) in {map_}")
    print(f"Doel: {opties.lufs:.0f} LUFS, max {opties.tp} dBTP"
          + ("" if opties.ja else "   (droge proef, nog niets gewijzigd)"))
    print()

    al_goed = veranderd = mislukt = 0
    try:
        for pad in bestanden:
            ctx.check()
            meting = meet(ctx, pad, opties.lufs, opties.tp, opties.lra)
            naam = pad.name
            if meting is None:
                print(f"  ? {naam}  (geen meting, overgeslagen)")
                mislukt += 1
                continue

            nu = float(meting["input_i"])
            piek = float(meting["input_tp"])
            # De winst die loudnorm lineair zal toepassen: naar het doel, maar
            # niet zo veel dat de true peak boven de limiet uitkomt.
            winst = opties.lufs - nu
            begrensd = piek + winst > opties.tp
            if begrensd:
                winst = opties.tp - piek
            if abs(winst) <= 0.5 and piek <= opties.tp:
                print(f"  = {naam}  {nu:6.1f} LUFS  al goed")
                al_goed += 1
                continue
            extra = "  (piek begrenst)" if begrensd else ""

            if not opties.ja:
                print(f"  · {naam}  {nu:6.1f} LUFS  →  {winst:+.1f} dB{extra}")
                veranderd += 1
                continue

            tmp = pas_toe(ctx, pad, meting, opties.lufs, opties.tp, opties.lra)
            if tmp is None:
                print(f"  ✗ {naam}  mislukt")
                mislukt += 1
                continue
            vervang(pad, tmp, opties.backup)
            print(f"  ✓ {naam}  {nu:6.1f} → {opties.lufs:.0f} LUFS "
                  f"({winst:+.1f} dB{extra})")
            veranderd += 1
    except k.Onderbroken:
        print("\nOnderbroken.")
        return 130
    except KeyboardInterrupt:
        print("\nOnderbroken.")
        return 130

    print()
    if not opties.ja:
        print(f"{veranderd} te normaliseren, {al_goed} al goed."
              "  (Droge proef; voeg --ja toe om het echt te doen.)")
    else:
        print(f"{veranderd} genormaliseerd, {al_goed} al goed, {mislukt} mislukt.")
    return 1 if mislukt else 0


if __name__ == "__main__":
    raise SystemExit(main())
