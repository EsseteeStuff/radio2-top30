#!/usr/bin/env python3
"""Top30 kern: scrapen, downloaden, converteren en verplaatsen.

Deze module bevat geen GUI-code en werkt zowel vanuit de GUI als vanuit de
commandoregel. Elke stap is een functie die een :class:`Context` krijgt met

* ``log(str)``      - schrijf een regel naar de console
* ``voortgang(...)`` - meld de voortgang van de lopende stap
* ``stop``          - een ``threading.Event``; de GUI zet dit op om te stoppen

De stappen zijn hervatbaar: elk slaat zijn voortgang op (hits-bestand,
manifest.json, bestaande mp3's) zodat je na een onderbreking gewoon opnieuw
kunt starten en alleen het ontbrekende werk doet.
"""
from __future__ import annotations

import json
import os
import queue
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

# --------------------------------------------------------------------------
# Constanten
# --------------------------------------------------------------------------

BRON = "https://www.hitnoteringen.be/hitlijsten/vrt-radio-2-top-30/{jaar}-{week:02d}"
EERSTEJAAR = 1970
EERSTE_WEEK_1970 = 18
MAX_WEEK = 53
GENRE = "Pop"
ALBUM = "Oldies but Goldies"
OMSCHRIJVING = "Oldies but goldies {jaar}"
PREFIX_BREEDTE_MIN = 2
PREFIX_LAGEN = 6  # max. aantal nummerlagen dat uit één naam wordt gehaald

# Een YouTube-video-id is altijd precies 11 tekens. Zo'n id dat aan een titel
# vastzit komt in de muziekmap terecht wanneer een bestand ooit met het id is
# hernoemd om het uniek te maken. Zomaar weghalen is gevaarlijk: `Bat-Te-Ring-Ram`
# en `D-I-V-O-R-C-E` zijn echte titels die er ook aan voldoen. Daarom wordt er
# alleen een id afgehaald als de hitlijst bewijst dat het een id is; kijk daarvoor
# in `match_hitlijst()`.
YOUTUBE_ID = re.compile(r"-[A-Za-z0-9_-]{11}\s*$")
# 'onbekende titel' is de plekhouder die het programma zet als het de titel van
# een YouTube-video niet kon achterhalen. Die staat nooit in een echte titel.
ONBEKENDE_TITEL = re.compile(r"\s*-\s*onbekende titel\s*$", re.IGNORECASE)
# Bij het gokken op een insluiting moet er genoeg tekst overblijven om het
# zeker te weten dat je het juiste nummer te pakken hebt.
INSLUITING_MIN = 10

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
)

# Fouten van YouTube die het waard zijn om later opnieuw te proberen.
TIJDELIJK = (
    "the page needs to be reloaded", "request throttling", "http error 403",
    "unable to download video data", "timed out", "connection reset",
    "connection refused", "read timed out", "429",
    "waiting for the stream to start", "temporarily unavailable",
)
# Fouten waarna je beter naar een ander video kunt zoeken.
INLOGFOUT = (
    "403", "sign in to confirm", "not a bot", "login required",
    "age-restricted", "age restriction", "private video", "removed",
)

COOKIE_BROWSERS = ("geen", "chrome", "chromium", "firefox", "edge", "brave", "opera", "vivaldi")
COOKIE_STANDAARD = "chromium"


class Onderbroken(Exception):
    """Gecontroleerde afbreking op verzoek van de gebruiker."""


class Fout(Exception):
    """Fout die de gebruiker in de GUI moet zien."""


# --------------------------------------------------------------------------
# Instellingen en mappen
# --------------------------------------------------------------------------

def config_map() -> Path:
    """Map waarin settings.json staat."""
    try:
        from PySide6.QtCore import QStandardPaths

        return Path(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.ConfigLocation
            )
        ) / "Top30"
    except Exception:
        pass
    if sys.platform == "win32":
        basis = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        basis = Path.home() / "Library" / "Application Support"
    else:
        basis = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return basis / "Top30"


@dataclass
class Paden:
    """Alle mappen die het programma gebruikt."""

    werk: Path
    muziek: Path

    def __post_init__(self) -> None:
        # Strings mag je ook meegeven; werk ze meteen om.
        self.werk = Path(self.werk).expanduser()
        self.muziek = Path(self.muziek).expanduser()

    @property
    def mp4(self) -> Path:
        return self.werk / "mp4"

    @property
    def mp3(self) -> Path:
        return self.werk / "mp3"

    @property
    def cookies(self) -> Path:
        return self.werk / "cookies.txt"

    @property
    def manifest(self) -> Path:
        return self.mp4 / "manifest.json"

    @property
    def foutenlog(self) -> Path:
        return self.mp4 / "download_fouten.log"

    def hits_bestand(self, begin: int, eind: int) -> Path:
        return self.werk / f"hits_{begin}_{eind}.txt"

    def maak(self) -> "Paden":
        for pad in (self.werk, self.muziek, self.mp3, self.mp4):
            pad.mkdir(parents=True, exist_ok=True)
        return self


# Alles wat het programma wegschrijft komt in een map met deze naam te staan.
# Zo raakt het nooit een map aan die een ander programma beheert.
EIGEN_MAP = "Top30"


def standaard_werkmap() -> Path:
    """De werkmap als er nog geen instelling is.

    Een plek die het programma zelf toebehoort, in de gegevensmap van het
    systeem. Niet in `temp`: daar mag een besturingssysteem zomaar wissen.
    """
    try:
        from PySide6.QtCore import QStandardPaths

        basis = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.GenericDataLocation
        )
        if basis:
            return Path(basis) / EIGEN_MAP
    except Exception:
        pass
    if sys.platform == "win32":
        basis = Path(os.environ.get("LOCALAPPDATA")
                     or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        basis = Path.home() / "Library" / "Application Support"
    else:
        basis = Path(os.environ.get("XDG_DATA_HOME")
                     or Path.home() / ".local" / "share")
    return basis / EIGEN_MAP


def standaard_muziekmap() -> Path:
    """De muziekmap als er nog geen instelling is.

    Bewust een eigen map in de standaard muziekmap van het systeem, en nadrukkelijk
    geen bestaande verzameling: valt het programma hier terug, dan herschudt en
    hernoemt het alleen zijn eigen bestanden en niet die van iemand anders.

    De muziekmap van het systeem verschilt per besturingssysteem en per taal
    (`~/Music`, `~/Muziek`, `C:\\Users\\...\\Music`), dus die laten we Qt bepalen.
    """
    try:
        from PySide6.QtCore import QStandardPaths

        basis = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.MusicLocation
        )
        if basis:
            return Path(basis) / EIGEN_MAP
    except Exception:
        pass
    if sys.platform == "win32":
        basis = Path(os.environ.get("USERPROFILE") or Path.home()) / "Music"
    else:
        basis = Path.home() / "Music"
    return basis / EIGEN_MAP


def laad_instellingen() -> dict:
    pad = config_map() / "settings.json"
    if pad.is_file():
        try:
            return json.loads(pad.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
    return {}


def bewaar_instellingen(werk: Path, muziek: Path, cookie_browser: str,
                        extra: dict | None = None) -> None:
    """Sla de instellingen op, met de sleutels uit `extra` erbij.

    Bestaande sleutels die hier niet genoemd worden blijven staan, zodat er
    later dingen bij kunnen (zoals de venstergrootte) zonder dat het
    overschrijven van de paden ze per ongeluk weghaalt.
    """
    map_ = config_map()
    map_.mkdir(parents=True, exist_ok=True)
    gegevens = dict(laad_instellingen())
    gegevens.update(
        {
            "work_dir": str(werk),
            "mp3_folder": str(Path(werk) / "mp3"),
            "mp4_folder": str(Path(werk) / "mp4"),
            "final_folder": str(muziek),
            "cookie_browser": cookie_browser,
        }
    )
    if extra:
        gegevens.update({k: v for k, v in extra.items() if v is not None})
    (map_ / "settings.json").write_text(json.dumps(gegevens, indent=1), encoding="utf-8")


def paden_uit_instellingen() -> Paden:
    instellingen = laad_instellingen()
    werk = Path(instellingen.get("work_dir") or standaard_werkmap())
    muziek = Path(instellingen.get("final_folder") or standaard_muziekmap())
    return Paden(werk, muziek)


# --------------------------------------------------------------------------
# Context: log, voortgang en stop
# --------------------------------------------------------------------------

@dataclass
class Context:
    """Voert de stappen uit en meldt wat er gebeurt."""

    paden: Paden
    log: Callable[[str], None] = print
    voortgang: Callable[[str, int, int, str], None] = lambda *_: None
    deelvoortgang: Callable[[float, str], None] = lambda *_: None
    stop: threading.Event = field(default_factory=threading.Event)
    cookie_browser: str = COOKIE_STANDAARD
    mp3_kwaliteit: int = 2

    # -------------------------------------------------------------- hulpjes
    def check(self) -> None:
        if self.stop.is_set():
            raise Onderbroken()

    def zet_voortgang(self, fase: str, index: int, totaal: int, label: str = "") -> None:
        self.check()
        self.voortgang(fase, index, totaal, label)

    def sub(self, fractie: float, label: str = "") -> None:
        self.check()
        self.deelvoortgang(max(0.0, min(1.0, fractie)), label)


# --------------------------------------------------------------------------
# Processen draaien (met de mogelijkheid om te onderbreken)
# --------------------------------------------------------------------------

def draai_proces(
    cmd: list[str],
    ctx: Context,
    cwd: Path | None = None,
    toon_regels: Callable[[str], None] | None = None,
    time_out: float | None = None,
) -> tuple[int, str]:
    """Draai een commando en geef (returncode, uitvoer).

    De uitvoer wordt regel voor regel gelezen in een aparte thread, zodat we
    kunnen reageren op de stopknop zonder het proces te blokkeren.
    """
    ctx.check()
    try:
        proces = subprocess.Popen(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            bufsize=1,
        )
    except FileNotFoundError as fout:
        raise Fout(f"{cmd[0]} niet gevonden: {fout}") from fout

    regels: list[str] = []
    bak: queue.Queue[str | None] = queue.Queue()

    def lees() -> None:
        try:
            if proces.stdout is not None:
                for regel in proces.stdout:
                    bak.put(regel)
        finally:
            bak.put(None)

    lezer = threading.Thread(target=lees, daemon=True)
    lezer.start()
    start = time.monotonic()
    afgerond = False

    while True:
        if ctx.stop.is_set():
            _dood_proces(proces)
            raise Onderbroken()
        if time_out and time.monotonic() - start > time_out:
            _dood_proces(proces)
            raise Fout(f"{cmd[0]} duurde te lang ({time_out:.0f} s) en is gestopt.")
        try:
            regel = bak.get(timeout=0.25)
        except queue.Empty:
            continue
        if regel is None:
            afgerond = True
            break
        regels.append(regel)
        if toon_regels:
            toon_regels(regel.rstrip())

    lezer.join(timeout=2)
    returncode = proces.wait(timeout=10)
    if not afgerond:  # pragma: no cover - alleen bij vreemde uitvoer
        regels.append("")
    return returncode, "".join(regels)


def _dood_proces(proces: subprocess.Popen) -> None:
    """Stop een proces en al zijn kinderen."""
    try:
        proces.terminate()
        proces.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            proces.kill()
            proces.wait(timeout=5)
        except Exception:
            pass
    except Exception:
        pass


def beschikbare_js_runtimes() -> list[str]:
    gevonden = [naam for naam in ("deno", "node") if shutil.which(naam)]
    if gevonden:
        return ["--js-runtimes", ",".join(gevonden)]
    return []


# --------------------------------------------------------------------------
# Kleine hulpfuncties
# --------------------------------------------------------------------------

def schoon(tekst: str) -> str:
    """Maak een tekst geschikt voor een bestandsnaam."""
    tekst = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", tekst)
    tekst = re.sub(r"\s+", " ", tekst).strip(" .")
    return (tekst[:120].strip(" .")) or "naamloos"


def sleutel(artiest: str, titel: str) -> str:
    return re.sub(r"\s+", " ", f"{artiest.casefold()} – {titel.casefold()}")


def vergelijk_sleutel(*delen: str) -> str:
    """Maak een naam vergelijkbaar, ongeacht hoofdletters en streepjes.

    Hiermee vallen `John Terra - Is er een ander` (zoals het in de bestandsnaam
    staat) en `John Terra` + `Is er een ander` (zoals het in de tags staat) op
    precies dezelfde sleutel. Spaties, liggende streepjes en underscores
    worden allemaal hetzelfde.
    """
    tekst = " ".join(d for d in delen if d)
    return re.sub(r"[\s\-–—_]+", " ", tekst.casefold()).strip()


# Gebogen leestekens (`You’re`) en rechte (`You're`) zijn dezelfde apostrof, maar
# een programma dat ze vergelijkt op bytes ziet ze als twee woorden. Hetzelfde
# geldt voor accenten: `Besame` en `Bésame` zijn hetzelfde nummer. Vooral de
# hitlijst en de bestandsnaam gebruiken ze allebei, dus voor het terugzoeken van
# de juiste titel maken we ze gelijk. Let op: de naam die uit de hitlijst komt
# houdt zijn accenten, alleen de vergelijking negeert ze.
GEBOGEN_LEESTEKENS = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u02bc": "'", "\u00b4": "'",
    "\u201c": '"', "\u201d": '"', "\uff02": '"',
})


def titel_sleutel(*delen: str) -> str:
    """Zoals `vergelijk_sleutel()`, maar leestekens en accenten gelijkstelt."""
    def kaal(tekst: str) -> str:
        tekst = tekst.translate(GEBOGEN_LEESTEKENS)
        return "".join(t for t in unicodedata.normalize("NFKD", tekst)
                       if not unicodedata.combining(t))
    return vergelijk_sleutel(*(kaal(d) for d in delen))


def _tags_van(pad: Path) -> list[tuple[str, str]]:
    """Lees artiest en titel uit de ID3-tags; lege lijst als er geen zijn."""
    try:
        from mutagen.id3 import ID3, ID3NoHeaderError
    except ImportError:
        return []
    try:
        tags = ID3(pad)
    except (ID3NoHeaderError, OSError):
        return []
    try:
        artiest = str(tags.get("TPE1").text[0]) if tags.get("TPE1") else ""
        titel = str(tags.get("TIT2").text[0]) if tags.get("TIT2") else ""
    except (AttributeError, IndexError, ValueError):
        return []
    return [(artiest.strip(), titel.strip())] if artiest or titel else []


def muziek_inventaris(map_: Path | None = None, met_tags: bool = True) -> set[str]:
    """Een lijst van alle nummers in de muziekmap, zonder de prefix.

    Vergelijk met `vergelijk_sleutel()`. Neemt de bestandsnaam zonder de
    numerieke prefix, en daar ook de ID3-tags bij: wie een bestand in een
    muziekspeler hebt hernoemd, wordt zo toch herkend.
    """
    if isinstance(map_, Context):
        map_ = map_.paden.muziek
    namen: set[str] = set()
    for pad in mp3_bestanden(map_ if map_ is not None else Path()):
        stam = zonder_prefix(pad.stem)
        if stam:
            namen.add(vergelijk_sleutel(stam))
        if met_tags:
            for artiest, titel in _tags_van(pad):
                namen.add(vergelijk_sleutel(artiest, titel))
    return namen


def filter_bestaande(ctx: Context, hits: list[dict],
                    sla_over: bool = True) -> tuple[list[dict], list[dict]]:
    """Haal de nummers eruit die al in de muziekmap staan.

    Geeft (te_downloaden, overgeslagen) terug. Vergelijkt de lijst met de
    nummers uit de muziekmap, zodat een jaar dat je al hebt niet opnieuw
    gedownload hoeft te worden.
    """
    if not sla_over:
        ctx.log("Bestaande nummers meegedownload (optie staat uit).")
        return list(hits), []
    bezit = muziek_inventaris(ctx.paden.muziek)
    if not bezit:
        return list(hits), []

    ctx.check()
    te_downloaden: list[dict] = []
    overgeslagen: list[dict] = []
    for hit in hits:
        artiest = str(hit.get("artiest", ""))
        titel = str(hit.get("titel", ""))
        kandidaten = {vergelijk_sleutel(artiest, titel),
                      vergelijk_sleutel(schoon(f"{artiest} - {titel}"))}
        (overgeslagen if kandidaten & bezit else te_downloaden).append(hit)

    if overgeslagen:
        ctx.log(
            f"{len(overgeslagen)} van de {len(hits)} nummers staan al in "
            f"{ctx.paden.muziek} en worden overgeslagen; "
            f"{len(te_downloaden)} moeten nog gedownload worden."
        )
        for hit in overgeslagen[:5]:
            ctx.log(f"  · al aanwezig: {hit['artiest']} - {hit['titel']}")
        if len(overgeslagen) > 5:
            ctx.log(f"  · … nog {len(overgeslagen) - 5} andere")
    elif hits:
        ctx.log(f"Geen van de {len(hits)} nummers staat al in {ctx.paden.muziek}.")
    return te_downloaden, overgeslagen


def is_mp3(pad: Path) -> bool:
    """Is dit bestand een mp3? Ook als er geen of een rare extensie aan hangt.

    De extensie alleen is niet te vertrouwen: `Mr. Soft` en `B.T. Express`
    lijken op een extensie te eindigen, en duizenden bestanden in een muziekmap
    blijven soms helemaal zonder. Daarom geldt een bestand als mp3 zodra het
    `ID3` of een MPEG-framesynchronisatie (`0xFF 0xEx`) begint. Daarmee raakt
    het programma een afbeelding of een m3u-bestand niet aan.
    """
    if pad.suffix.lower() == ".mp3":
        return True
    try:
        with open(pad, "rb") as fh:
            kop = fh.read(4)
    except OSError:
        return False
    # Een ID3-tag is 'ID3' plus een versiebyte (2, 3 of 4). Die versiebyte
    # meechecken voorkomt dat een tekstbestand dat toevallig met 'ID3' begint
    # voor een mp3 wordt aangezien.
    if kop[:3] == b"ID3" and len(kop) == 4 and kop[3] in (2, 3, 4):
        return True
    return len(kop) >= 3 and kop[0] == 0xFF and kop[1] & 0xE0 == 0xE0


def mp3_bestanden(map_: Path) -> list[Path]:
    """Alle mp3's in een map, ook bestanden waarvan de extensie ontbreekt."""
    if not map_.is_dir():
        return []
    return sorted(p for p in map_.iterdir() if p.is_file() and is_mp3(p))


def mp4_bestanden(map_: Path) -> list[Path]:
    if not map_.is_dir():
        return []
    return sorted(p for p in map_.iterdir() if p.is_file() and p.suffix.lower() == ".mp4")


def grootte_van(pad: Path) -> str:
    """Mooie bestandsgrootte, bijvoorbeeld '3,4 MB'."""
    try:
        bytes_ = pad.stat().st_size
    except OSError:
        return "? B"
    for eenheid, stap in (("GB", 1024**3), ("MB", 1024**2), ("kB", 1024)):
        if bytes_ >= stap:
            waarde = bytes_ / stap
            return f"{waarde:.1f} {eenheid}".replace(".", ",")
    return f"{bytes_} B"


def unieke_naam(map_: Path, naam: str) -> Path:
    doel = map_ / naam
    if not doel.exists():
        return doel
    pad = Path(naam)
    n = 2
    while True:
        doel = map_ / f"{pad.stem} ({n}){pad.suffix}"
        if not doel.exists():
            return doel
        n += 1


def zonder_prefix(naam: str) -> str:
    """Haal alle nummering aan het begin van een bestandsnaam weg.

    Niet één laag, maar zoveel lagen er in de naam zitten, en met of zonder
    spatie rond het streepje:

    ================================  =========================
    naam                             zonder_prefix
    ================================  =========================
    `00012-ABBA - x.mp3`             `ABBA - x.mp3`
    `0423 - ABBA - x.mp3`            `ABBA - x.mp3`
    `001-0423 - ABBA - x.mp3`        `ABBA - x.mp3`
    `00001-00042-0007-ABBA - x.mp3`  `ABBA - x.mp3`
    ================================  =========================

    Een titel die met cijfers begint blijft heel, want er moet een streepje
    achter die cijfers staan: `10cc - Donna` en `3 Doors Down - Here Without
    You` blijven dus precies zoals ze zijn.
    """
    for _ in range(PREFIX_LAGEN):
        korter = re.sub(r"^\d{1,9}\s*-\s*", "", naam, count=1).lstrip("- ")
        if not korter or korter == naam:
            break
        naam = korter
    return naam


def zonder_mp3(naam: str) -> str:
    """Haal de mp3-extensie van een bestandsnaam af, als hij er echt is.

    `Alice Cooper - No More Mr. Nice Guy` heeft geen extensie, maar `Path` zou
    er `. Nice Guy` van maken. Daarom kijken we naar het hele einde van de naam
    in plaats van naar de laatste punt.
    """
    return naam[:-4] if naam.casefold().endswith(".mp3") else naam


def naamvarianten(naam: str) -> list[str]:
    """Voorstellen voor dezelfde titel, steeds verder opgeruimd.

    Geeft de naam zelf terug, dan de naam zonder 'onbekende titel', dan zonder
    een YouTube-id aan het eind, enzovoort, tot de naam niet meer verder
    opgeruimd kan worden. De eerste variant die precies in de hitlijst staat is
    de juiste; de rest wordt alleen gebruikt als er verder niets klopt.
    """
    naam = zonder_mp3(naam.strip())
    varianten: list[str] = []
    vorige = ""
    while naam and naam != vorige:
        varianten.append(naam)
        vorige = naam
        naam = ONBEKENDE_TITEL.sub("", naam)
        naam = YOUTUBE_ID.sub("", naam).rstrip(" -_")
    return varianten


def hitlijst_tabel(paden: Paden) -> dict[str, dict]:
    """Alle nummers uit de hits-bestanden van de werkmap, op sleutel.

    De hitlijst is de enige bron die zegt hoe een nummer hoort te heten, en dus
    de enige die het waag is een rommelige bestandsnaam te vervangen. De sleutel
    is die van `titel_sleutel()`, zodat hoofdletters, streepjes, leestekens en
    accenten niet uitmaken. Geeft een lege dictie terug als er geen hits-bestanden
    liggen; het programma hoeft dan alleen te nummeren.
    """
    tabel: dict[str, dict] = {}
    for pad in sorted(paden.werk.glob("hits_*_*.json")):
        try:
            regels = json.loads(pad.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for regel in regels if isinstance(regels, list) else []:
            if isinstance(regel, dict) and regel.get("artiest") and regel.get("titel"):
                tabel.setdefault(
                    titel_sleutel(regel["artiest"], regel["titel"]),
                    {"artiest": regel["artiest"], "titel": regel["titel"]},
                )
    for pad in sorted(paden.werk.glob("hits_*_*.txt")):
        try:
            inhoud = pad.read_text(encoding="utf-8")
        except OSError:
            continue
        for regel in inhoud.splitlines():
            if not regel.strip():
                continue
            try:
                hit = uit_regel(regel)
            except (ValueError, TypeError):
                continue
            if hit["artiest"] and hit["titel"]:
                tabel.setdefault(
                    titel_sleutel(hit["artiest"], hit["titel"]),
                    {"artiest": hit["artiest"], "titel": hit["titel"]},
                )
    return tabel


def _kandidaten_sleutels(pad: Path) -> list[str]:
    """Alle manieren waarop dit bestand naar een titel genoemd kan worden."""
    bronnen = [zonder_mp3(zonder_prefix(pad.name))]
    for artiest, titel in _tags_van(pad):
        if titel:
            bronnen.append(titel)
        if artiest and not titel:
            bronnen.append(artiest)
    sleutels: list[str] = []
    for bron in bronnen:
        for variant in naamvarianten(bron):
            kunstenaar, _, titel = variant.partition(" - ")
            if kunstenaar and titel:
                sleutels.append(titel_sleutel(kunstenaar, titel))
            sleutels.append(titel_sleutel(variant))
    return sleutels


def match_hitlijst(pad: Path, tabel: dict[str, dict],
                   sleutels: list[str] | None = None) -> tuple[str, dict] | None:
    """Zoek in de hitlijst welk nummer dit bestand hoort te zijn.

    Geeft (soort, nummer) terug, of None als de hitlijst het niet weet. Er wordt
    nooit een naam verzonnen: gevonden betekent dat er écht zo'n nummer in de
    hitlijst staat, dus dat de naam ernaar mag worden bijgewerkt.

    Eerst wordt er exact gekeken, en pas als dat niks oplevert wordt er gekeken
    of het ene nummer in het andere voorkomt. Dat tweede is nodig omdat de
    bestandsnaam vaak nog wat YouTube-gehak aan de titel plakt: `Sing a Song
    (Official Audio)`. Dat mag alleen als er precies één nummer in de lijst
    overblijft, anders zou het een gok zijn.
    """
    if not tabel:
        return None
    kandidaten = _kandidaten_sleutels(pad)
    for kandidaat in kandidaten:
        nummer = tabel.get(kandidaat)
        if nummer is not None:
            return "exact", nummer

    if sleutels is None:
        sleutels = list(tabel)
    for kandidaat in kandidaten:
        if len(kandidaat) < INSLUITING_MIN:
            continue
        treffers = {
            tabel[s]["artiest"] + " - " + tabel[s]["titel"]
            for s in sleutels
            if (len(s) >= INSLUITING_MIN and s in kandidaat) or kandidaat in s
        }
        if len(treffers) == 1:
            naam = treffers.pop().split(" - ", 1)
            return "insluiting", {"artiest": naam[0], "titel": naam[1]}
    return None


def schone_stam(pad: Path, tabel: dict[str, dict],
                sleutels: list[str] | None = None) -> str:
    """De naam die dit bestand hoort te krijgen, zonder prefix en zonder `.mp3`.

    Is de titel in de hitlijst te vinden, dan wint die altijd: zo verdwijnen
    YouTube-ids, kapotte tekens en een fout omgekeerde artiest-titel. Anders
    blijft de bestandsnaam zoals hij is, op de prefix na. In beide gevallen
    verdwijnt een eventuele mp3-extensie, die wordt er door de nummering weer
    aan gehangen.
    """
    if tabel:
        gevonden = match_hitlijst(pad, tabel, sleutels)
        if gevonden is not None:
            _, nummer = gevonden
            return schoon(f"{nummer['artiest']} - {nummer['titel']}")
    return schoon(zonder_mp3(zonder_prefix(pad.name)))


# --------------------------------------------------------------------------
# Stap 1: scrapen
# --------------------------------------------------------------------------

_sess = None


def _http() -> "object":
    global _sess
    if _sess is None:
        import requests

        _sess = requests.Session()
        _sess.headers["User-Agent"] = USER_AGENT
    return _sess


def haal_pagina(ctx: Context, jaar: int, week: int) -> str | None:
    """Haal één hitlijstpagina op; None als die week niet bestaat."""
    url = BRON.format(jaar=jaar, week=week)
    laatste_fout: Exception | None = None
    for poging in range(3):
        ctx.check()
        try:
            antwoord = _http().get(url, timeout=25)
        except Exception as fout:  # netwerkfout
            laatste_fout = fout
            time.sleep(2**poging)
            continue
        if antwoord.status_code == 404:
            return None
        if antwoord.status_code == 200:
            return antwoord.text
        if antwoord.status_code in (429, 500, 502, 503, 504) and poging < 2:
            time.sleep(2**poging)
            continue
        raise Fout(f"HTTP {antwoord.status_code} bij {url}")
    ctx.log(f"  {url} niet bereikbaar: {laatste_fout}")
    return None


def paren_treffers(html: str) -> list[dict]:
    from bs4 import BeautifulSoup

    sop = BeautifulSoup(html, "html.parser")
    lijst = sop.select_one("ol.chart")
    if lijst is not None:
        knopen = lijst.select("li.entry")
    else:
        knopen = sop.select(".chartentry")
    uit: list[dict] = []
    for knoop in knopen:
        artiest_el = knoop.select_one("span.artiest")
        titel_el = knoop.select_one("span.titel")
        if not artiest_el or not titel_el:
            continue
        uit.append(
            {
                "artiest": artiest_el.get_text(" ", strip=True),
                "titel": titel_el.get_text(" ", strip=True),
            }
        )
    return uit


def weken_voor(jaar: int) -> Iterable[int]:
    start = EERSTE_WEEK_1970 if jaar == EERSTEJAAR else 1
    return range(start, MAX_WEEK + 1)


def controleer_jaren(begin: int, eind: int) -> tuple[int, int, list[str]]:
    """Zet de grenzen goed en geef de waarschuwingen terug."""
    waarschuwingen: list[str] = []
    huidig_jaar = time.localtime().tm_year
    if begin < EERSTEJAAR:
        waarschuwingen.append(
            f"De hitlijst begint pas in {EERSTEJAAR} (week {EERSTE_WEEK_1970}); "
            f"beginjaar wordt {EERSTEJAAR}."
        )
        begin = EERSTEJAAR
    if eind > huidig_jaar:
        waarschuwingen.append(f"Eindjaar wordt {huidig_jaar} (het lopende jaar).")
        eind = huidig_jaar
    if begin > eind:
        raise Fout("Beginjaar mag niet groter zijn dan eindjaar.")
    return begin, eind, waarschuwingen


def scrape(ctx: Context, begin: int, eind: int, overschrijven: bool = False) -> list[dict]:
    """Lees de hitlijsten van hitnoteringen.be en schrijf het hits-bestand."""
    doel = ctx.paden.hits_bestand(begin, eind)
    if doel.exists() and not overschrijven:
        ctx.log(f"{doel.name} bestaat al; ik gebruik de bestaande lijst.")
        return laad_hits(ctx, begin, eind)

    ctx.log(f"Scrapen van {begin} tot en met {eind} ...")
    gezien: set[str] = set()
    hits: list[dict] = []
    jaren = list(range(begin, eind + 1))
    for nr, jaar in enumerate(jaren, 1):
        ctx.zet_voortgang("scrapen", nr - 1, len(jaren), f"{jaar}")
        nieuw = 0
        for week in weken_voor(jaar):
            ctx.check()
            html = haal_pagina(ctx, jaar, week)
            if html is None:
                continue
            for treffer in paren_treffers(html):
                k = sleutel(treffer["artiest"], treffer["titel"])
                if k in gezien:
                    continue
                gezien.add(k)
                hits.append({**treffer, "jaar": jaar})
                nieuw += 1
            time.sleep(0.15)
        ctx.log(f"  {jaar}: {nieuw} nieuwe nummers ({len(hits)} uniek tot nu toe)")
    ctx.zet_voortgang("scrapen", len(jaren), len(jaren), "klaar")

    if not hits:
        raise Fout("Scrapen leverde geen nummers op. Klopt de website nog?")

    schrijf_hits(ctx, hits, begin, eind)
    ctx.log(f"{len(hits)} unieke nummers weggeschreven naar {doel.name}")
    return hits


def schrijf_hits(ctx: Context, hits: list[dict], begin: int, eind: int) -> Path:
    doel = ctx.paden.hits_bestand(begin, eind)
    regels = [f"{h['artiest']} - {h['titel']} - {h['jaar']}" for h in hits]
    doel.write_text("\n".join(regels) + "\n", encoding="utf-8")
    doel.with_suffix(".json").write_text(
        json.dumps(hits, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return doel


def uit_regel(regel: str) -> dict:
    hoofd, jaartal = regel.rsplit(" - ", 1)
    artiest, _, titel = hoofd.partition(" - ")
    return {"artiest": artiest, "titel": titel, "jaar": int(jaartal)}


def laad_hits(ctx: Context, begin: int, eind: int) -> list[dict]:
    """Lees het hits-bestand voor het gegeven jaarspanne."""
    doel = ctx.paden.hits_bestand(begin, eind)
    if not doel.exists():
        raise Fout(
            f"{doel.name} ontbreekt in {ctx.paden.werk}.\n"
            "Kies 'Alleen scrapen' om hem eerst te maken."
        )
    json_bestand = doel.with_suffix(".json")
    if json_bestand.exists():
        hits = json.loads(json_bestand.read_text(encoding="utf-8"))
    else:
        hits = [
            uit_regel(r) for r in doel.read_text(encoding="utf-8").splitlines() if r.strip()
        ]
    ctx.log(f"{len(hits)} nummers geladen uit {doel.name}")
    return hits


# --------------------------------------------------------------------------
# Manifest: welke mp4's zijn er al?
# --------------------------------------------------------------------------

def laad_manifest(ctx: Context) -> list[dict]:
    pad = ctx.paden.manifest
    if pad.exists():
        try:
            return json.loads(pad.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
    return []


def bewaar_manifest(ctx: Context, items: list[dict]) -> None:
    pad = ctx.paden.manifest
    tmp = pad.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(pad)


# --------------------------------------------------------------------------
# Stap 2: downloaden van YouTube
# --------------------------------------------------------------------------

# Zoekvoortgang binnen de video die bezig is (voor de voortgangsbalk).
_voortgang_meter = re.compile(r"\[download\]\s+(\d{1,3}(?:[.,]\d+)?)%")


def _cookie_opties(ctx: Context) -> list[str]:
    """Welke cookie-bron gebruikt yt-dlp?"""
    if ctx.paden.cookies.exists():
        return ["--cookies", str(ctx.paden.cookies)]
    browser = (ctx.cookie_browser or "geen").strip().lower()
    if browser in ("", "geen", "none"):
        return []
    return ["--cookies-from-browser", browser]


def _basis_opties() -> list[str]:
    return [
        "--ignore-config",
        "--no-colors",
        *beschikbare_js_runtimes(),
        "--no-playlist",
        "--sleep-requests", "1",
        "--retries", "5",
        "--fragment-retries", "5",
    ]


def _download_cmd(ctx: Context, bron: str, doel: Path) -> list[str]:
    return [
        sys.executable, "-m", "yt_dlp",
        *_basis_opties(),
        "--remote-components", "ejs:github",
        "-f", "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4]/b[ext=m4a]/b",
        "--merge-output-format", "mp4",
        "--remux-video", "mp4",
        "--no-mtime",
        "-o", str(doel.with_suffix("").with_name(doel.stem + ".%(ext)s")),
        *_cookie_opties(ctx),
        bron,
    ]


def _zoek_cmd(ctx: Context, artiest: str, titel: str, aantal: int) -> list[str]:
    return [
        sys.executable, "-m", "yt_dlp",
        *_basis_opties(),
        "--remote-components", "ejs:github",
        "--flat-playlist",
        "--print", "%(id)s",
        f"ytsearch{aantal}:{artiest} {titel}",
        *_cookie_opties(ctx),
    ]


def _vind_eindbestand(ctx: Context, doel: Path) -> Path | None:
    """Na een download ligt het bestand soms met een andere extensie."""
    if doel.exists() and doel.stat().st_size > 0:
        return doel
    toegestaan = {".mp4", ".webm", ".mkv", ".m4a", ".mov"}
    kandidaten = [
        p for p in doel.parent.glob(doel.stem + ".*")
        if p.suffix.lower() in toegestaan and p.stat().st_size > 0
    ]
    if len(kandidaten) != 1:
        return None
    bron = kandidaten[0]
    code, uitvoer = draai_proces(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(bron),
         "-c", "copy", str(doel)],
        ctx,
    )
    if code == 0 and doel.exists():
        bron.unlink(missing_ok=True)
        return doel
    if bron.suffix.lower() == ".mp4":
        bron.rename(doel)
        return doel
    return None


def _laatste_fout(uitvoer: str) -> str:
    regels = [r for r in uitvoer.splitlines() if r.strip()]
    laatste = next((r for r in reversed(regels) if "ERROR" in r or "WARNING" in r), None)
    return (laatste or (regels[-1] if regels else "onbekende fout")).strip()


def _yt_dlp_luister(ctx: Context, laatste: list[str]):
    """Callback voor de yt-dlp-uitvoer.

    yt-dlp is heel erg geschreeuwd; alleen de voortgang (voor de balk) en echte
    fouten worden doorgegeven, zodat de console leesbaar blijft.
    """
    def luister(regel: str) -> None:
        if not regel:
            return
        laatste.append(regel)
        m = _voortgang_meter.search(regel)
        if m:
            ctx.sub(float(m.group(1).replace(",", ".")) / 100.0, regel.strip())
            return
        schoon = regel.strip()
        if schoon.startswith(("ERROR", "WARNING")):
            ctx.log("  " + schoon)
    return luister


def _download_een(ctx: Context, bron: str, doel: Path) -> tuple[Path | None, str]:
    """Download één video. Geeft (pad of None, foutmelding)."""
    for poging in range(1, 4):
        fragmenten: list[str] = []
        try:
            code, uitvoer = draai_proces(
                _download_cmd(ctx, bron, doel),
                ctx,
                toon_regels=_yt_dlp_luister(ctx, fragmenten),
            )
        except Onderbroken:
            _verwijder_gespletst(ctx, doel)
            raise
        volledig = uitvoer + "\n" + "\n".join(fragmenten)
        if code == 0:
            eindpad = _vind_eindbestand(ctx, doel)
            if eindpad:
                return eindpad, ""
            volledig += "\n geen eindbestand gevonden na het downloaden"
        laag = volledig.lower()
        if poging < 3 and any(x in laag for x in TIJDELIJK):
            wacht = poging * 5
            ctx.log(f"  tijdelijke YouTube-fout; {wacht} s wachten en opnieuw proberen ...")
            for _ in range(wacht * 4):
                ctx.check()
                time.sleep(0.25)
            continue
        with ctx.paden.foutenlog.open("a", encoding="utf-8") as f:
            f.write(f"\n=== {bron} ===\n{volledig[-4000:]}\n")
        _verwijder_gespletst(ctx, doel)
        return None, _laatste_fout(volledig)
    return None, "onbekende fout"


def _verwijder_gespletst(ctx: Context, doel: Path) -> None:
    """Ruim half gedownloade brokstukken op."""
    for patroon in ("*.part", "*.ytdl", "*.f*.mp4", "*.temp.mp4"):
        for pad in doel.parent.glob(doel.stem + patroon):
            pad.unlink(missing_ok=True)


def _zoek_videos(ctx: Context, artiest: str, titel: str, aantal: int) -> list[str]:
    try:
        code, uitvoer = draai_proces(_zoek_cmd(ctx, artiest, titel, aantal), ctx)
    except Onderbroken:
        raise
    if code != 0:
        return []
    return [
        f"https://www.youtube.com/watch?v={r.strip()}"
        for r in uitvoer.splitlines()
        if r.strip() and len(r.strip()) >= 11
    ]


def download(ctx: Context, hits: list[dict], sla_bestaande_over: bool = True) -> list[dict]:
    """Download elk nummer als mp4 naar de mp4-map.

    Nummer je al in de muziekmap hebt worden overgeslagen; dat scheelt het
    downloaden van uren bij een jaar dat je al hebt.
    """
    hits, _ = filter_bestaande(ctx, hits, sla_over=sla_bestaande_over)
    if not hits:
        ctx.log("Niets te downloaden: elk nummer staat al in de muziekmap.")
        return laad_manifest(ctx)

    mp4 = ctx.paden.mp4
    mp4.mkdir(parents=True, exist_ok=True)
    eerdere = {sleutel(h["artiest"], h["titel"]): h for h in laad_manifest(ctx)}
    manifest: list[dict] = []
    gebruikte_stems: dict[str, str] = {}
    mislukt: list[tuple[dict, str]] = []
    totaal = len(hits)

    for i, hit in enumerate(hits, 1):
        k = sleutel(hit["artiest"], hit["titel"])
        ctx.zet_voortgang("downloaden", i - 1, totaal, f"{hit['artiest']} - {hit['titel']}")
        ctx.sub(0.0, f"{i}/{totaal}")

        # Al gedownload? Dan overslaan maar wel in het manifest houden.
        oud = eerdere.get(k)
        if oud and _klaar(ctx, oud):
            gebruikte_stems.setdefault(Path(oud["file"]).stem, k)
            manifest.append(oud)
            ctx.log(f"  · al aanwezig: {oud['file']}")
            continue

        # Unieke bestandsnaam maken binnen de mp4-map.
        basis = schoon(f"{hit['artiest']} - {hit['titel']}")
        stem = basis
        n = 2
        while stem in gebruikte_stems and gebruikte_stems[stem] != k:
            stem = f"{basis} ({n})"
            n += 1
        gebruikte_stems[stem] = k
        doel = mp4 / f"{stem}.mp4"

        if doel.exists() and doel.stat().st_size > 0:
            manifest.append({**hit, "file": doel.name})
            bewaar_manifest(ctx, manifest)
            continue

        eindpad, fout = _download_een(ctx, f"ytsearch1:{hit['artiest']} {hit['titel']}", doel)

        # YouTube wil misschien inloggen: zoek dan naar alternatieve video's.
        if eindpad is None and fout and any(x in fout.lower() for x in INLOGFOUT):
            ctx.log(f"  YouTube wil inloggen ({fout[:120]}); ik zoek een alternatief ...")
            for url in _zoek_videos(ctx, hit["artiest"], hit["titel"], 5):
                eindpad, fout = _download_een(ctx, url, doel)
                if eindpad is not None:
                    break

        if eindpad is None:
            mislukt.append((hit, fout))
            ctx.log(f"  MISLUKT: {fout}")
            continue

        manifest.append({**hit, "file": eindpad.name})
        bewaar_manifest(ctx, manifest)
        ctx.log(f"  ✓ {eindpad.name} ({grootte_van(eindpad)})")
        wacht = random.uniform(0.4, 1.2)
        for _ in range(int(wacht * 4)):
            ctx.check()
            time.sleep(0.25)

    ctx.zet_voortgang("downloaden", totaal, totaal, "klaar")
    bewaar_manifest(ctx, manifest)
    ctx.log(f"Downloaden klaar: {len(manifest)} klaar, {len(mislukt)} mislukt.")
    if mislukt:
        ctx.log(
            f"Mislukte nummers staan in {ctx.paden.foutenlog.name}; "
            "start 'Alleen downloaden' opnieuw om ze opnieuw te proberen."
        )
    return manifest


def _klaar(ctx: Context, record: dict) -> bool:
    """Is dit nummer al gedownload óf al geconverteerd?"""
    pad = ctx.paden.mp4 / record["file"]
    if pad.exists() and pad.stat().st_size > 0:
        return True
    return mp3_bestaat(ctx, record["file"])


def mp3_bestaat(ctx: Context, mp4_naam: str) -> bool:
    """Komt er al een mp3 met dezelfde naam bestaan (in mp3-map of muziekmap)?"""
    stam = Path(mp4_naam).stem
    for map_ in (ctx.paden.mp3, ctx.paden.muziek):
        if not map_.is_dir():
            continue
        for pad in map_.iterdir():
            if pad.suffix.lower() != ".mp3" or not pad.is_file():
                continue
            if not pad.stat().st_size:
                continue
            if pad.stem == stam or zonder_prefix(pad.name) == stam:
                return True
    return False


# --------------------------------------------------------------------------
# Stap 3: converteren naar mp3
# --------------------------------------------------------------------------

def zet_tags(pad: Path, record: dict) -> None:
    from mutagen.id3 import (
        COMM, ID3, ID3NoHeaderError, TALB, TCON, TDRC, TIT2, TPE1,
    )

    try:
        tags = ID3(pad)
    except ID3NoHeaderError:
        tags = ID3()
    for frame in ("TPE1", "TIT2", "TALB", "TCON", "TDRC", "COMM", "TSSE"):
        tags.delall(frame)
    tags.add(TPE1(encoding=3, text=[record["artiest"]]))
    tags.add(TIT2(encoding=3, text=[record["titel"]]))
    tags.add(TALB(encoding=3, text=[ALBUM]))
    tags.add(TCON(encoding=3, text=[GENRE]))
    jaar = str(record.get("jaar") or "").strip()
    if jaar:
        tags.add(TDRC(encoding=3, text=[jaar]))
        tags.add(COMM(encoding=3, lang="eng", desc="",
                      text=[OMSCHRIJVING.format(jaar=jaar)]))
    tags.save(pad)


def convert(ctx: Context, verwijder_mp4: bool = False) -> dict:
    """Zet alle mp4's uit de mp4-map om naar mp3 in de mp3-map."""
    ctx.paden.mp3.mkdir(parents=True, exist_ok=True)
    bronnen = laad_manifest(ctx)

    # Zonder manifest: neem gewoon alles dat in de mp4-map ligt en leid de
    # artiest/titel uit de bestandsnaam af.
    if not bronnen:
        bronnen = []
        for p in mp4_bestanden(ctx.paden.mp4):
            delen = p.stem.split(" - ", 1)
            bronnen.append(
                {
                    "file": p.name,
                    "artiest": delen[0],
                    "titel": delen[1] if len(delen) > 1 else delen[0],
                    "jaar": "",
                }
            )
        if bronnen:
            ctx.log(
                f"{len(bronnen)} mp4-bestanden gevonden (zonder manifest); "
                "ik leid de tags af uit de bestandsnaam."
            )

    totaal = len(bronnen)
    nieuw = al_aanwezig = fout = 0
    for i, record in enumerate(bronnen, 1):
        ctx.zet_voortgang("converteren", i - 1, totaal,
                          f"{record.get('artiest', '')} - {record.get('titel', '')}")
        bron = ctx.paden.mp4 / record["file"]
        doel = ctx.paden.mp3 / (Path(record["file"]).stem + ".mp3")

        if (doel.exists() and doel.stat().st_size > 0) or mp3_bestaat(ctx, record["file"]):
            al_aanwezig += 1
            continue
        if not bron.exists() or not bron.stat().st_size:
            ctx.log(f"  ontbreekt in {ctx.paden.mp4.name}/: {record['file']}")
            fout += 1
            continue

        try:
            code, uitvoer = draai_proces(
                ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                 "-i", str(bron), "-vn", "-map_metadata", "-1",
                 "-codec:a", "libmp3lame", "-q:a", str(ctx.mp3_kwaliteit), str(doel)],
                ctx,
            )
        except Onderbroken:
            doel.unlink(missing_ok=True)
            raise
        if code != 0 or not doel.exists():
            regels = [r for r in uitvoer.splitlines() if r.strip()]
            ctx.log(f"  ffmpeg-fout op {record['file']}: {regels[-1] if regels else 'onbekend'}")
            doel.unlink(missing_ok=True)
            fout += 1
            continue
        try:
            zet_tags(doel, record)
        except Exception as tag_fout:
            ctx.log(f"  tags konden niet geschreven worden: {tag_fout}")
        nieuw += 1

    ctx.zet_voortgang("converteren", totaal, totaal, "klaar")

    verwijderd = 0
    if verwijder_mp4:
        verwijderd = _ruim_mp4_op(ctx)
        if verwijderd:
            ctx.log(f"Opgeruimd: {verwijderd} mp4-bestanden verwijderd (mp3 is klaar).")

    ctx.log(f"Converteren klaar: {nieuw} nieuw, {al_aanwezig} al aanwezig, {fout} fout/overgeslagen.")
    return {"nieuw": nieuw, "aanwezig": al_aanwezig, "fout": fout, "verwijderd": verwijderd}


def _ruim_mp4_op(ctx: Context) -> int:
    """Verwijder mp4's waarvan het mp3-bestand al klaarstaat."""
    klaar = {p.stem for p in mp3_bestanden(ctx.paden.mp3)}
    for p in mp3_bestanden(ctx.paden.muziek):
        # p.stem, niet de hele naam: bij een bestand zonder extensie zou
        # het afknippen van de suffix een lege string opleveren.
        klaar.add(zonder_prefix(p.stem))
    verwijderd = 0
    for pad in mp4_bestanden(ctx.paden.mp4):
        if pad.stem in klaar:
            pad.unlink(missing_ok=True)
            verwijderd += 1
    return verwijderd


# --------------------------------------------------------------------------
# Stap 4: verplaatsen naar de muziekmap
# --------------------------------------------------------------------------

def verplaats(ctx: Context, hernoem: bool = True, startnummer: int = 1) -> int:
    """Verplaats de mp3's uit de mp3-map naar de muziekmap."""
    bestanden = mp3_bestanden(ctx.paden.mp3)
    if not bestanden:
        ctx.log(f"Geen mp3-bestanden om te verplaatsen in {ctx.paden.mp3}.")
        return 0
    ctx.paden.muziek.mkdir(parents=True, exist_ok=True)
    totaal = len(bestanden)
    for i, pad in enumerate(bestanden, 1):
        ctx.zet_voortgang("verplaatsen", i, totaal, pad.name)
        shutil.move(str(pad), str(unieke_naam(ctx.paden.muziek, pad.name)))
    ctx.log(f"{totaal} mp3-bestanden verplaatst naar {ctx.paden.muziek}.")

    if hernoem and mp3_bestanden(ctx.paden.muziek):
        nummer_hernoemen(ctx, startnummer=startnummer)
    return totaal


def prefix_breedte(aantal: int, minimum: int = PREFIX_BREEDTE_MIN) -> int:
    """Hoeveel cijfers de prefix nodig heeft voor `aantal` bestanden.

    Zoveel cijfers als het hoogste nummer nodig heeft, met een minimum van twee:

    ==========  ==========  ==============
    bestanden   breedte     voorbeeld
    ==========  ==========  ==============
    40          2           01-
    99          2           99-
    100         3           100-
    700         3           001-
    1200        4           0001-
    ==========  ==========  ==============

    Omdat het programma de hele map bij elke run opnieuw nummert, past de
    breedte zich automatisch aan zodra het aantal verandert.
    """
    if aantal <= 0:
        return minimum
    return max(minimum, len(str(aantal)))


def nummer_hernoemen(ctx: Context, map_: Path | None = None,
                     startnummer: int = 1,
                     breedte: int | None = None) -> list[tuple[Path, Path]]:
    """Schud de bestanden en zet ze opnieuw onder een numerieke prefix.

    De breedte van de prefix volgt automatisch uit het aantal bestanden in de
    map, tenzij je die met `breedte` vastzet.
    """
    map_ = ctx.paden.muziek if map_ is None else map_
    bestanden = mp3_bestanden(map_)
    if not bestanden:
        raise Fout(f"Geen mp3-bestanden gevonden in {map_}.")
    volgorde = _schud_zonder_twee_keer_zelfde_artiest(bestanden)
    hoogste = startnummer + len(volgorde) - 1
    if breedte is None:
        breedte = prefix_breedte(hoogste)
    plan: list[tuple[Path, Path]] = []
    gebruikt: set[str] = set()
    for i, pad in enumerate(volgorde):
        naam = f"{startnummer + i:0{breedte}d}-{zonder_prefix(pad.name)}"
        n = 2
        while naam.casefold() in gebruikt:
            naam = f"{startnummer + i:0{breedte}d}-{zonder_prefix(pad.stem)} ({n}){pad.suffix}"
            n += 1
        gebruikt.add(naam.casefold())
        plan.append((pad, pad.with_name(naam)))

    ctx.log(f"{len(plan)} bestanden in {map_} gaan opnieuw geschud en genummerd.")
    verwerk_nummerplan(ctx, map_, plan)
    ctx.log(
        f"Klaar: bestanden voorzien van een nieuwe prefix vanaf "
        f"{startnummer:0{breedte}d} (tot {hoogste:0{breedte}d})."
    )
    return plan


def _schud_zonder_twee_keer_zelfde_artiest(bestanden: list[Path]) -> list[Path]:
    random.shuffle(bestanden)
    if len(bestanden) < 3:
        return bestanden
    groepen: dict[str, list[Path]] = {}
    for pad in bestanden:
        # De prefix er nog af, anders is elk bestand zijn eigen 'artiest'.
        artiest = zonder_prefix(pad.stem).split(" - ", 1)[0].casefold()
        groepen.setdefault(artiest, []).append(pad)
    volgorde: list[Path] = []
    vorige: str | None = None
    while groepen:
        keuzes = [a for a in groepen if a != vorige] or list(groepen)
        artiest = random.choice(sorted(keuzes))
        volgorde.append(groepen[artiest].pop())
        if not groepen[artiest]:
            del groepen[artiest]
        vorige = artiest
    return volgorde


def verwerk_nummerplan(ctx: Context, map_: Path, plan: list[tuple[Path, Path]]) -> int:
    """Voer een hernoemplan uit via een tijdelijke map, met terugdraaien."""
    doers = [(oud, nieuw) for oud, nieuw in plan if oud != nieuw]
    if not doers:
        return 0
    tmp = map_ / f".top30_nummer_{os.getpid()}"
    tmp.mkdir()
    totaal = len(doers)
    try:
        for i, (oud, nieuw) in enumerate(doers):
            ctx.check()
            ctx.zet_voortgang("hernoemen", i, totaal, nieuw.name)
            oud.rename(tmp / f"{i:08d}.mp3")
        for (oud, nieuw), bron in zip(doers, sorted(tmp.iterdir())):
            bron.rename(map_ / nieuw.name)
        tmp.rmdir()
    except BaseException:
        for i, (oud, nieuw) in enumerate(doers):
            bron = tmp / f"{i:08d}.mp3"
            try:
                if bron.exists():
                    bron.rename(oud)
                elif nieuw.exists() and nieuw != oud:
                    nieuw.rename(oud)
            except OSError:
                pass
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return len(doers)


def _log_naamherstel(ctx: Context, bestanden: list[Path],
                     stam_per_pad: dict[Path, str], tabel: dict[str, dict]) -> None:
    """Vertel welke namen de hitlijst heeft hersteld, zodat het te controleren is."""
    if not tabel:
        ctx.log(
            "Geen hits-bestanden in de werkmap gevonden, dus ik kan de titels "
            "niet controleren. Ik haal de prefixen weg en zet overal .mp3 achter."
        )
        return
    hersteld = [
        (oud, stam_per_pad[pad])
        for oud, pad in ((schoon(zonder_mp3(zonder_prefix(p.name))), p) for p in bestanden)
        if oud and vergelijk_sleutel(oud) != vergelijk_sleutel(stam_per_pad[pad])
    ]
    if not hersteld:
        ctx.log(f"Alle {len(bestanden)} namen kloppen al met de hitlijst.")
        return
    ctx.log(
        f"{len(hersteld)} van de {len(bestanden)} namen klopten niet met de "
        f"hitlijst en zijn hersteld:"
    )
    for oud, nieuw in hersteld:
        ctx.log(f"  {oud}  ->  {nieuw}")


def fixprefix(ctx: Context) -> int:
    """Herstel de nummering van de hele muziekmap.

    Eerst wordt het aantal bestanden geteld om de breedte van de prefix te
    bepalen (700 bestanden wordt bijvoorbeeld 3 cijfers: 001- in plaats van
    00001-). Daarna worden de namen opgeschoond: wat in de hitlijst staat krijgt
    de naam uit die lijst, zodat YouTube-ids, een fout omgekeerde artiest-titel
    en een ontbrekende extensie verdwijnen. Vervolgens gaan alle prefixen eraf,
    wordt de lijst geschud, en krijgt elk bestand van 1 tot en met het aantal
    een nieuwe prefix, oplopend van voren naar achteren.
    """
    map_ = ctx.paden.muziek
    ctx.check()
    if not map_.is_dir():
        raise Fout(f"{map_} bestaat niet.")
    bestanden = mp3_bestanden(map_)
    if not bestanden:
        ctx.log(f"Geen mp3-bestanden gevonden in {map_}.")
        return 0

    aantal = len(bestanden)
    breedte = prefix_breedte(aantal)
    volgorde = _schud_zonder_twee_keer_zelfde_artiest(bestanden)
    ctx.zet_voortgang("hernoemen", 0, aantal, "namen opruimen")

    # De namen worden eerst opgeschoond, nog zonder prefix. Zo kan er geen
    # dubbele naam ontstaan doordat twee bestanden na het hernoemen pas blijken
    # hetzelfde te heten: het nummer komt er in één keer bij.
    tabel = hitlijst_tabel(ctx.paden)
    sleutels = list(tabel)
    stam_per_pad: dict[Path, str] = {}
    for i, pad in enumerate(volgorde, 1):
        ctx.check()
        ctx.zet_voortgang("hernoemen", i, aantal, "namen opruimen")
        stam_per_pad[pad] = schone_stam(pad, tabel, sleutels)
    _log_naamherstel(ctx, volgorde, stam_per_pad, tabel)

    # Oude prefixen weg, daarna een oplopende nummering in de geschudde volgorde.
    # Alleen bestanden die NIET hernoemd worden komen in `bezet`: elk mp3 in
    # deze map krijgt immers een nieuwe naam, en die is dus straks vrij. Zo kan
    # een nieuwe naam nooit een plaatje of tekstbestand overschrijven.
    plan: list[tuple[Path, Path]] = []
    bezet = {p.name.casefold() for p in map_.iterdir()
             if p.is_file() and not is_mp3(p)}
    for i, pad in enumerate(volgorde, 1):
        ctx.check()
        stam = stam_per_pad[pad]
        naam = f"{i:0{breedte}d}-{stam}.mp3"
        n = 2
        while naam.casefold() in bezet:
            naam = f"{i:0{breedte}d}-{stam} ({n}).mp3"
            n += 1
        bezet.add(naam.casefold())
        plan.append((pad, pad.with_name(naam)))

    hernoemd = verwerk_nummerplan(ctx, map_, plan)
    ctx.log(
        f"{hernoemd} van {aantal} bestanden in {map_} opnieuw genummerd "
        f"naar een oplopende {breedte}-cijferige prefix "
        f"({1:0{breedte}d}- t/m {aantal:0{breedte}d}-)."
    )
    return hernoemd


# --------------------------------------------------------------------------
# De hele rit
# --------------------------------------------------------------------------

def voer_alles(ctx: Context, begin: int, eind: int, verwijder_mp4: bool = True,
               hernoem: bool = True, sla_bestaande_over: bool = True) -> None:
    """De volledige route: scrapen, downloaden, converteren, verplaatsen."""
    ctx.log("=" * 62)
    ctx.log("1/4  Hitlijsten ophalen")
    ctx.log("=" * 62)
    hits = scrape(ctx, begin, eind)

    ctx.log("")
    ctx.log("=" * 62)
    ctx.log("2/4  Downloaden van YouTube")
    ctx.log("=" * 62)
    download(ctx, hits, sla_bestaande_over=sla_bestaande_over)

    ctx.log("")
    ctx.log("=" * 62)
    ctx.log("3/4  Converteren naar mp3")
    ctx.log("=" * 62)
    convert(ctx, verwijder_mp4=verwijder_mp4)

    ctx.log("")
    ctx.log("=" * 62)
    ctx.log("4/4  Verplaatsen naar de muziekmap")
    ctx.log("=" * 62)
    verplaats(ctx, hernoem=hernoem)


def samenvatting(paden: Paden | Context) -> dict:
    """Tellen wat er al op schijf staat (voor de GUI).

    Aanvaardt zowel een `Paden` als een `Context`, zodat de GUI niet eerst een
    volledige context hoeft te bouwen.
    """
    if isinstance(paden, Context):
        paden = paden.paden
    hits_bestanden = sorted(paden.werk.glob("hits_*_*.json"))
    aantal_hits = 0
    for pad in hits_bestanden:
        try:
            aantal_hits = max(aantal_hits, len(json.loads(pad.read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            continue
    return {
        "hits": aantal_hits,
        "mp4": len(mp4_bestanden(paden.mp4)),
        "mp3": len(mp3_bestanden(paden.mp3)),
        "muziek": len(mp3_bestanden(paden.muziek)),
    }
