#!/usr/bin/env python3
"""Top30 grafische scherm: een modern venster rond de top30_core-stappen.

Starten met één commando:

    ./top30            (Linux/macOS)
    python top30.py    (alle platformen)

De GUI draait de stappen in een achtergronddraad, toont alles wat de kern
via `log` schrijft in een console-venster en kan op elk moment onderbroken
worden. Alles is hervatbaar: na een stop of een crash kun je met een van de
afzonderlijke taken verdergaan.
"""
from __future__ import annotations

import re
import sys
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread, Signal, Slot
from PySide6.QtGui import (
    QColor, QFont, QFontDatabase, QIcon, QKeySequence, QPixmap, QShortcut,
    QSyntaxHighlighter, QTextCharFormat,
)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QRadioButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

import top30_core as kern

APP_NAAM = "Top30"
APP_TITEL = "Top30 — VRT Radio 2 hitlijsten"
ORG_VENSTER = "Top30"

FASEN = {
    "scrapen": "Scrapen",
    "downloaden": "Downloaden",
    "converteren": "Converteren",
    "verplaatsen": "Verplaatsen",
    "hernoemen": "Hernoemen",
}

TAKEN = [
    "alles", "scrape", "download", "convert", "verplaats", "fixprefix",
]

# Korte naam plus een uitleg die eronder staat, zodat de zijbalk smal blijft.
TAAL = {
    "alles": ("Alles doen", "Scrapen, downloaden, converteren en verplaatsen."),
    "scrape": ("Alleen scrapen", "De hitlijsten van hitnoteringen.be ophalen."),
    "download": ("Alleen downloaden", "YouTube → mp4, uit het hits-bestand van de gekozen jaren."),
    "convert": ("Alleen converteren", "Alle mp4's uit de mp4-map omzetten naar mp3."),
    "verplaats": ("Alleen verplaatsen", "De mp3's uit de mp3-map naar je muziekmap zetten."),
    "fixprefix": ("Prefixen herstellen", "Alle nummers dezelfde breedte geven, passend bij het aantal bestanden."),
}


# --------------------------------------------------------------------------
# Stijl
# --------------------------------------------------------------------------

DONKER = {
    "achtergrond": "#0f1116",
    "paneel": "#161a23",
    "paneel_licht": "#1d222d",
    "rand": "#262c3a",
    "tekst": "#e8ecf4",
    "tekst_zwak": "#98a1b3",
    "accent": "#5b8cff",
    "accent_hover": "#7aa2ff",
    "accent_tekst": "#0b1020",
    "ok": "#3ecf8e",
    "fout": "#ff6b6b",
    "waarschuwing": "#f2b544",
}

LICHT = {
    "achtergrond": "#f2f4f8",
    "paneel": "#ffffff",
    "paneel_licht": "#f7f9fc",
    "rand": "#d8dee9",
    "tekst": "#131722",
    "tekst_zwak": "#5c6675",
    "accent": "#3b6ef5",
    "accent_hover": "#2c58d8",
    "accent_tekst": "#ffffff",
    "ok": "#128a5b",
    "fout": "#c62b2b",
    "waarschuwing": "#a86a00",
}

KLEUREN = {"donker": DONKER, "licht": LICHT}


def _als_getal(waarde: object) -> int:
    """Een getal uit de instellingen, of 0 als het er geen is.

    De settings.json is met de hand te wijzigen, dus hier kan van alles in
    staan: een getal, een tekst, `null`, of helemaal niets. Vandaar de
    omzettiging in plaats van `int(...)` dat om een exception zou vragen.
    """
    try:
        getal = int(waarde)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    return getal if getal > 0 else 0


def stijlblad(kleuren: dict) -> str:
    """Bouw het stylesheet op uit het kleurenpalet."""
    return f"""
    QWidget {{
        background: {kleuren['achtergrond']};
        color: {kleuren['tekst']};
        font-size: 10pt;
    }}
    QMainWindow, QDialog {{ background: {kleuren['achtergrond']}; }}

    /* ---------- kopbalk ---------- */
    #kop {{
        background: {kleuren['paneel']};
        border-bottom: 1px solid {kleuren['rand']};
    }}
    #kop_titel {{ font-size: 15pt; font-weight: 600; background: transparent; }}
    #kop_sub {{ color: {kleuren['tekst_zwak']}; font-size: 9pt; background: transparent; }}

    /* ---------- kaarten ---------- */
    #rij {{ background: transparent; border: none; }}
    #kaart {{
        background: {kleuren['paneel']};
        border: 1px solid {kleuren['rand']};
        border-radius: 10px;
    }}
    #kaart_titel {{
        font-size: 9pt; font-weight: 600; color: {kleuren['tekst_zwak']};
        background: transparent; padding: 2px 0;
    }}

    /* ---------- invoer ---------- */
    QLineEdit, QSpinBox, QComboBox {{
        background: {kleuren['paneel_licht']};
        border: 1px solid {kleuren['rand']};
        border-radius: 7px;
        padding: 7px 10px;
        color: {kleuren['tekst']};
        selection-background-color: {kleuren['accent']};
        selection-color: {kleuren['accent_tekst']};
    }}
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
        border: 1px solid {kleuren['accent']};
    }}
    QLineEdit:disabled, QSpinBox:disabled {{ color: {kleuren['tekst_zwak']}; }}
    QSpinBox::up-button, QSpinBox::down-button {{
        background: {kleuren['rand']}; border: none; width: 16px;
    }}
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
        background: {kleuren['accent']};
    }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox::down-arrow {{ image: none; width: 0; height: 0; }}
    QComboBox QAbstractItemView {{
        background: {kleuren['paneel']};
        border: 1px solid {kleuren['rand']};
        selection-background-color: {kleuren['accent']};
        outline: none; padding: 4px;
    }}

    /* ---------- knoppen ---------- */
    QPushButton {{
        background: {kleuren['paneel_licht']};
        border: 1px solid {kleuren['rand']};
        border-radius: 7px;
        padding: 8px 14px;
        color: {kleuren['tekst']};
    }}
    QPushButton:hover {{
        border-color: {kleuren['accent']};
        background: {kleuren['paneel']};
    }}
    QPushButton:pressed {{ background: {kleuren['rand']}; }}
    QPushButton:disabled {{ color: {kleuren['tekst_zwak']}; border-color: {kleuren['rand']}; }}
    QPushButton#hoofd_knop {{
        background: {kleuren['accent']};
        color: {kleuren['accent_tekst']};
        border: none;
        font-weight: 600;
        padding: 10px 22px;
        font-size: 10.5pt;
    }}
    QPushButton#hoofd_knop:hover {{ background: {kleuren['accent_hover']}; }}
    QPushButton#hoofd_knop:disabled {{ background: {kleuren['rand']}; color: {kleuren['tekst_zwak']}; }}
    QPushButton#stop_knop {{
        background: transparent;
        border: 1px solid {kleuren['fout']};
        color: {kleuren['fout']};
        font-weight: 600;
        padding: 10px 18px;
    }}
    QPushButton#stop_knop:hover {{ background: {kleuren['fout']}; color: #ffffff; }}
    QPushButton#stop_knop:disabled {{ border-color: {kleuren['rand']}; color: {kleuren['tekst_zwak']}; }}

    /* ---------- keuzes ---------- */
    QRadioButton, QCheckBox {{ background: transparent; spacing: 8px; padding: 2px; }}
    QRadioButton::indicator, QCheckBox::indicator {{
        width: 17px; height: 17px;
        border: 1px solid {kleuren['rand']};
        background: {kleuren['paneel_licht']};
    }}
    QRadioButton::indicator {{ border-radius: 9px; }}
    QCheckBox::indicator {{ border-radius: 5px; }}
    QRadioButton::indicator:hover, QCheckBox::indicator:hover {{ border-color: {kleuren['accent']}; }}
    QRadioButton::indicator:checked {{
        background: {kleuren['accent']};
        border: 3px solid {kleuren['paneel_licht']};
    }}
    QCheckBox::indicator:checked {{ background: {kleuren['accent']}; border-color: {kleuren['accent']}; }}
    QRadioButton:disabled, QCheckBox:disabled {{ color: {kleuren['tekst_zwak']}; }}

    /* ---------- voortgang ---------- */
    QProgressBar {{
        background: {kleuren['paneel_licht']};
        border: none; border-radius: 6px;
        height: 12px; text-align: center;
        color: transparent;
    }}
    QProgressBar::chunk {{
        background: {kleuren['accent']};
        border-radius: 6px;
    }}

    /* ---------- console ---------- */
    #console {{
        background: {kleuren['paneel']};
        border: 1px solid {kleuren['rand']};
        border-radius: 10px;
        font-family: "{QFontDatabase.systemFont(QFontDatabase.FixedFont).family()}";
        font-size: 9pt;
    }}

    /* ---------- groepen ---------- */
    QGroupBox {{
        border: 1px solid {kleuren['rand']};
        border-radius: 10px;
        margin-top: 14px;
        background: transparent;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 12px; padding: 0 6px;
        color: {kleuren['tekst_zwak']};
    }}

    QScrollArea {{ border: none; background: transparent; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}
    QScrollBar:vertical {{
        background: transparent; width: 10px; margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {kleuren['rand']}; border-radius: 5px; min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {kleuren['tekst_zwak']}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    QToolTip {{
        background: {kleuren['paneel']};
        color: {kleuren['tekst']};
        border: 1px solid {kleuren['accent']};
        padding: 4px;
    }}
    """


# --------------------------------------------------------------------------
# Kleine iconen (vector, dus scherp op elke schermdichtheid)
# --------------------------------------------------------------------------

ICONEN = {
    "map": (
        '<path d="M3 6.5 9 4l6 2.5L15 4v11.5L9 13l-6 2.5V6.5Z" />'
        '<path d="M9 4v9M15 6.5v9" opacity=".55" />'
    ),
    "muziek": (
        '<path d="M9 15.5V5.2l7-1.3v9.1" />'
        '<circle cx="6.6" cy="15.6" r="2.6" />'
        '<circle cx="13.6" cy="13" r="2.6" />'
    ),
    "jaar": (
        '<rect x="3" y="5" width="14" height="12" rx="2" />'
        '<path d="M3 9h14M7 3v4M13 3v4" />'
    ),
    "console": (
        '<rect x="2.5" y="4" width="15" height="12" rx="2" />'
        '<path d="M5.5 9 7.5 11 5.5 13M9.5 13.5h4" />'
    ),
    "start": '<path d="M5 3.5v11l9-5.5-9-5.5Z" />',
    "stop": '<rect x="5" y="5" width="8" height="8" rx="1.5" />',
    "klaar": '<path d="M3.5 9.5 7.5 13.5 14.5 5" />',
    "fout": '<path d="M9 3.5 16 15H2L9 3.5Z" /><path d="M9 8v3.5M9 13.2v.1" />',
}


def maak_icoon(naam: str, kleuren: dict, grootte: int = 18) -> QIcon:
    """Bouw een QIcon uit een inline SVG."""
    kleur = kleuren["accent"]
    if naam == "fout":
        kleur = kleuren["fout"]
    elif naam == "klaar":
        kleur = kleuren["ok"]
    elif naam == "stop":
        kleur = kleuren["fout"]
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{grootte}" '
        f'height="{grootte}" viewBox="0 0 18 18" fill="none" '
        f'stroke="{kleur}" stroke-width="1.6" stroke-linecap="round" '
        f'stroke-linejoin="round">{ICONEN[naam]}</svg>'
    )
    pixmap = QPixmap()
    pixmap.loadFromData(svg.encode("utf-8"), "SVG")
    if pixmap.isNull():  # pragma: no cover - alleen als SVG-ondersteuning ontbreekt
        pixmap = QPixmap(grootte, grootte)
        pixmap.fill(Qt.transparent)
    return QIcon(pixmap)


# --------------------------------------------------------------------------
# Console
# --------------------------------------------------------------------------

class ConsoleKleuren(QSyntaxHighlighter):
    """Kleur de console-uitvoer op woordniveau."""

    REGELS = [
        (re.compile(r"^\s*(ERROR|WARNING|MISLUKT|Mislukt|FOUT|Fout)", re.I), "fout"),
        (re.compile(r"\b(fout|error|failed|mislukt|exception|traceback)\b", re.I), "fout"),
        (re.compile(r"^\s*(Let op|Let op:|WARN)", re.I), "waarschuwing"),
        (re.compile(r"\b(let op|waarschuwing|overslagen|wordt overgeslagen)\b", re.I), "waarschuwing"),
        (re.compile(r"^\s*(Klaar|klaar|✓)", ), "ok"),
        (re.compile(r"\b(klaar|gelukt|geslaagd|opgeslagen|nieuw|verplaatst|gedownload)\b", re.I), "ok"),
        (re.compile(r"^=+$|^-{3,}$"), "zebra"),
    ]

    def __init__(self, document, kleuren: dict):
        super().__init__(document)
        self.kleuren = kleuren
        self.herbouw()

    def herbouw(self) -> None:
        self.formaat = {}
        for sleutel in ("fout", "waarschuwing", "ok", "zebra", "commandoregel", "info"):
            kleur = {
                "fout": self.kleuren["fout"],
                "waarschuwing": self.kleuren["waarschuwing"],
                "ok": self.kleuren["ok"],
                "zebra": self.kleuren["tekst_zwak"],
                "commandoregel": self.kleuren["accent"],
                "info": self.kleuren["tekst"],
            }[sleutel]
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(kleur))
            if sleutel == "commandoregel":
                fmt.setFontWeight(QFont.DemiBold)
            elif sleutel in ("fout", "waarschuwing"):
                fmt.setFontWeight(QFont.DemiBold)
            self.formaat[sleutel] = fmt

    def highlightBlock(self, tekst: str) -> None:
        self.setFormat(0, len(tekst), self.formaat["info"])
        for patroon, sleutel in self.REGELS:
            for match in patroon.finditer(tekst):
                self.setFormat(match.start(), match.end() - match.start(), self.formaat[sleutel])


class Console(QPlainTextEdit):
    """Console-venster dat de uitvoer van het programma toont."""

    def __init__(self, kleuren: dict, max_regels: int = 4000):
        super().__init__()
        self.setObjectName("console")
        self.setReadOnly(True)
        self.setMaximumBlockCount(max_regels)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.kleuren = kleuren
        self.highlighter = ConsoleKleuren(self.document(), kleuren)

    def zet_kleuren(self, kleuren: dict) -> None:
        self.kleuren = kleuren
        self.highlighter.kleuren = kleuren
        self.highlighter.herbouw()
        self.highlighter.rehighlight()

    def schrijf(self, regel: str) -> None:
        self.appendPlainText(regel.rstrip("\n"))
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

    def leeg(self) -> None:
        self.clear()


# --------------------------------------------------------------------------
# Voortgang
# --------------------------------------------------------------------------

GEWICHTEN = {
    "alles": {"scrapen": 15, "downloaden": 65, "converteren": 12, "verplaatsen": 8},
    "scrape": {"scrapen": 100},
    "download": {"downloaden": 100},
    "convert": {"converteren": 100},
    "verplaats": {"verplaatsen": 70, "hernoemen": 30},
    "fixprefix": {"verplaatsen": 100},
}

# De eerste fase van elke taak; bepaalt wat de voortgangsbalk doet.
STAP_VOOR_STAP = {
    "alles": "scrapen",
    "scrape": "scrapen",
    "download": "downloaden",
    "convert": "converteren",
    "verplaats": "verplaatsen",
    "fixprefix": "verplaatsen",
}


class VoortgangsBoek:
    """Zet de voortgang van elke fase om naar één Overall-percentage."""

    def __init__(self, taak: str):
        self.gewichten = GEWICHTEN.get(taak, {"scrapen": 100})
        self.klaar: dict[str, float] = {fase: 0.0 for fase in self.gewichten}
        self.deel: dict[str, float] = {fase: 0.0 for fase in self.gewichten}

    def zet(self, fase: str, index: int, totaal: int) -> float:
        if fase in self.klaar:
            self.klaar[fase] = 0.0 if totaal <= 0 else min(1.0, index / totaal)
            self.deel[fase] = 0.0
        return self.totaal()

    def deelvoortgang(self, fase: str, fractie: float) -> float:
        if fase in self.deel:
            self.deel[fase] = max(0.0, min(1.0, fractie))
        return self.totaal()

    def totaal(self) -> float:
        if not self.gewichten:
            return 0.0
        totaal_gewicht = sum(self.gewichten.values())
        optel = 0.0
        for fase, gewicht in self.gewichten.items():
            fractie = min(1.0, self.klaar.get(fase, 0.0) + self.deel.get(fase, 0.0))
            optel += fractie * gewicht
        return 100.0 * optel / totaal_gewicht


# --------------------------------------------------------------------------
# De taak die in een draad loopt
# --------------------------------------------------------------------------

class TaakThread(QThread):
    """Voert één stap uit; alles gaat via signalen terug naar de GUI."""

    log = Signal(str)
    voortgang = Signal(str, int, int, str)   # fase, index, totaal, label
    deelvoortgang = Signal(str, float, str)  # fase, fractie, label
    klaar = Signal(str, bool)                # bericht, geslaagd?
    samenvatting = Signal(dict)

    def __init__(self, taak: str, ctx: kern.Context, opties: dict, parent=None):
        super().__init__(parent)
        self.taak = taak
        self.ctx = ctx
        self.opties = opties
        self.onderbroken = False

    def requestInterruption(self) -> None:
        """Zet de stopvlag van de kern, zodat de taak daadwerkelijk stopt.

        De kern kijkt naar `ctx.stop`; alleen de Qt-interruptie-vlag zetten zou
        dus niets doen. Daarom zetten we beide.
        """
        self.ctx.stop.set()
        super().requestInterruption()

    def isOnderbroken(self) -> bool:
        return self.ctx.stop.is_set() or self.isInterruptionRequested()

    def run(self) -> None:
        ctx = self.ctx
        self._huidige_fase = STAP_VOOR_STAP.get(self.taak, "scrapen")
        ctx.log = self.log.emit
        ctx.voortgang = self.voortgang.emit
        ctx.deelvoortgang = (
            lambda fractie, label="": self.deelvoortgang.emit(
                self._huidige_fase, fractie, label
            )
        )
        try:
            self._uitvoeren()
        except kern.Onderbroken:
            self.onderbroken = True
            self.log.emit(
                "\n⛔ Onderbroken. Je kunt verdergaan met een van de taken hierboven."
            )
            self.klaar.emit("Onderbroken door de gebruiker.", False)
        except kern.Fout as fout:
            self.log.emit(f"\n✖ {fout}")
            self.klaar.emit(str(fout), False)
        except Exception:
            self.log.emit("\n" + traceback.format_exc())
            self.klaar.emit("Er ging iets onverwachts mis (zie de console).", False)
        else:
            self.log.emit("\n✔ Klaar.")
            self.klaar.emit("Klaar.", True)
        finally:
            self.samenvatting.emit(self.samenvatting_van())

    def samenvatting_van(self) -> dict:
        try:
            return kern.samenvatting(self.ctx)
        except Exception:
            return {}

    # ------------------------------------------------------------- stappen
    def _uitvoeren(self) -> None:
        ctx = self.ctx
        begin = int(self.opties["begin"])
        eind = int(self.opties["eind"])
        taak = self.taak
        self._huidige_fase = STAP_VOOR_STAP[taak]

        if taak == "scrape":
            hits = kern.scrape(ctx, begin, eind, overschrijven=self.opties["overschrijven"])
            ctx.log(f"Gereed: {len(hits)} nummers uit de lijst.")
        elif taak == "download":
            hits = kern.laad_hits(ctx, begin, eind)
            kern.download(ctx, hits, sla_bestaande_over=self.opties["sla_over"])
        elif taak == "convert":
            kern.convert(ctx, verwijder_mp4=self.opties["verwijder_mp4"])
        elif taak == "verplaats":
            kern.verplaats(ctx, hernoem=self.opties["hernoemen"])
        elif taak == "fixprefix":
            kern.fixprefix(ctx)
        elif taak == "alles":
            kern.voer_alles(
                ctx, begin, eind,
                verwijder_mp4=self.opties["verwijder_mp4"],
                hernoem=self.opties["hernoemen"],
                sla_bestaande_over=self.opties["sla_over"],
            )
        else:
            raise kern.Fout(f"Onbekende taak: {taak}")


# --------------------------------------------------------------------------
# Het venster
# --------------------------------------------------------------------------

class Venster(QMainWindow):
    """Hoofdvenster met instellingen, taakkeuze, console en knoppen."""

    def __init__(self, thema: str = "donker", afmetingen: dict | None = None):
        super().__init__()
        self.setWindowTitle(APP_TITEL)
        self.setMinimumSize(940, 660)
        self.resize(1080, 760)
        self.setWindowIcon(maak_icoon("muziek", KLEUREN[thema], 32))

        self.kleuren = KLEUREN[thema]
        self.thema_naam = thema
        self.thread: TaakThread | None = None
        self._voortgang_boek: VoortgangsBoek | None = None
        # De grootte die de gebruiker had bij het vorige afsluiten. Toegepast
        # wordt die in _pas_afmetingen_toe(), na _bouw().
        self._afmetingen = dict(afmetingen or {})

        instellingen = kern.laad_instellingen()
        if not self._afmetingen:
            self._afmetingen = {
                "venster_breedte": instellingen.get("venster_breedte"),
                "venster_hoogte": instellingen.get("venster_hoogte"),
                "venster_max": instellingen.get("venster_max"),
            }
        self._werk = Path(instellingen.get("work_dir") or kern.standaard_werkmap())
        self._muziek = Path(instellingen.get("final_folder") or kern.standaard_muziekmap())
        self._cookie_browser = instellingen.get("cookie_browser") or kern.COOKIE_STANDAARD

        self._bouw()
        self._pas_afmetingen_toe()
        self._pas_stijl_toe()
        self._sneltoetsen()
        self._toon_samenvatting()
        self.log(
            f"{APP_NAAM} klaar. Kies een taak en druk op Start.\n"
            f"Werkmap: {self._werk}\nMuziekmap: {self._muziek}"
        )

    # --------------------------------------------------------------- afmetingen

    def _pas_afmetingen_toe(self) -> None:
        """Zet het venster op de grootte van de vorige keer.

        Kleiner dan het minimum mag niet, want dan knipt Qt het venster af.
        Onzin (0, negatief, of iets dat geen getal is) wordt genegeerd.
        """
        kleinste = self.minimumSize()
        breedte = _als_getal(self._afmetingen.get("venster_breedte"))
        hoogte = _als_getal(self._afmetingen.get("venster_hoogte"))
        if breedte:
            breedte = max(breedte, kleinste.width())
        if hoogte:
            hoogte = max(hoogte, kleinste.height())
        if breedte or hoogte:
            self.resize(breedte or self.width(), hoogte or self.height())
        if self._afmetingen.get("venster_max"):
            # Nog niet zichtbaar; setWindowState werkt dan en wordt bij show()
            # toegepast. showMaximized() zou in dit stadium niets doen.
            self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)

    def onthoud_afmetingen(self) -> dict:
        """De huidige venstergrootte, in de vorm van instellingen.

        Staat het venster gemaximimaliseerd, dan is `width()`/`height()` de
        hele scherm. Dan is `normalGeometry()` interessanter: dat is de
        grootte die je terugkrijgt zodra je het venster uit maximaliseren
        haalt, en die wil je onthouden in plaats van het hele scherm.
        """
        if self.isMaximized():
            rect = self.normalGeometry()
            breedte, hoogte = rect.width(), rect.height()
        else:
            breedte, hoogte = self.width(), self.height()
        return {
            "venster_breedte": breedte,
            "venster_hoogte": hoogte,
            "venster_max": self.isMaximized(),
        }

    # ---------------------------------------------------------------- opbouw
    def _bouw(self) -> None:
        centraal = QWidget()
        self.setCentralWidget(centraal)
        root = QVBoxLayout(centraal)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._kop())

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 12)
        body_layout.setSpacing(16)
        body_layout.addWidget(self._zijbalk(), 0)
        body_layout.addWidget(self._consolepaneel(), 1)
        root.addWidget(body, 1)

        root.addWidget(self._voeten())

    def _kop(self) -> QWidget:
        kop = QFrame()
        kop.setObjectName("kop")
        kop.setFixedHeight(66)
        rij = QHBoxLayout(kop)
        rij.setContentsMargins(18, 0, 14, 0)
        rij.setSpacing(12)

        icoon = maak_icoon("muziek", self.kleuren, 24)
        plaatje = QLabel()
        plaatje.setPixmap(icoon.pixmap(24, 24))
        rij.addWidget(plaatje)

        teksten = QVBoxLayout()
        teksten.setSpacing(1)
        teksten.setContentsMargins(0, 0, 0, 0)
        titel = QLabel("Top30")
        titel.setObjectName("kop_titel")
        sub = QLabel("VRT Radio 2 hitlijsten archiveren")
        sub.setObjectName("kop_sub")
        teksten.addWidget(titel)
        teksten.addWidget(sub)
        rij.addLayout(teksten)
        rij.addStretch(1)

        self.status_label = QLabel("Gereed")
        self.status_label.setObjectName("kop_sub")
        self.status_label.setMinimumWidth(230)
        self.status_label.setMaximumWidth(420)
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        rij.addWidget(self.status_label)

        self.knop_thema = QPushButton("Licht thema")
        self.knop_thema.setCheckable(True)
        self.knop_thema.setChecked(self.thema_naam == "licht")
        self.knop_thema.toggled.connect(self._wissel_thema)
        rij.addWidget(self.knop_thema)
        return kop

    def _kaart(self, titel: str) -> tuple[QFrame, QVBoxLayout]:
        kaart = QFrame()
        kaart.setObjectName("kaart")
        layout = QVBoxLayout(kaart)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(10)
        if titel:
            label = QLabel(titel)
            label.setObjectName("kaart_titel")
            layout.addWidget(label)
        return kaart, layout

    def _zijbalk(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFixedWidth(370)

        inhoud = QWidget()
        kolom = QVBoxLayout(inhoud)
        kolom.setContentsMargins(0, 0, 8, 0)
        kolom.setSpacing(12)

        # --- mappen + jaren
        kaart, layout = self._kaart("INSTELLINGEN")

        rij_werk, self.veld_werk, self.knop_werk = self._maprij(
            "Werkmap", self._werk, self._kies_werk,
            "Hier komen de mp4- en mp3-bestanden en de hits-lijst.\n"
            "De submappen mp3 en mp4 worden automatisch aangemaakt.",
        )
        layout.addWidget(rij_werk)

        rij_muziek, self.veld_muziek, self.knop_muziek = self._maprij(
            "Muziekmap", self._muziek, self._kies_muziek,
            "Hierheen worden de geconverteerde mp3's verplaatst.",
        )
        layout.addWidget(rij_muziek)

        jaar_rij = QHBoxLayout()
        jaar_rij.setSpacing(10)
        begin_vak = QVBoxLayout()
        begin_vak.setSpacing(5)
        begin_label = QLabel("Beginjaar")
        begin_label.setObjectName("kaart_titel")
        self.spin_begin = self._jaarveld(kern.EERSTEJAAR)
        begin_vak.addWidget(begin_label)
        begin_vak.addWidget(self.spin_begin)
        eind_vak = QVBoxLayout()
        eind_vak.setSpacing(5)
        eind_label = QLabel("Eindjaar")
        eind_label.setObjectName("kaart_titel")
        self.spin_eind = self._jaarveld(time.localtime().tm_year)
        eind_vak.addWidget(eind_label)
        eind_vak.addWidget(self.spin_eind)
        jaar_rij.addLayout(begin_vak, 1)
        jaar_rij.addLayout(eind_vak, 1)
        layout.addSpacing(4)
        layout.addLayout(jaar_rij)

        self.label_jaren = QLabel("")
        self.label_jaren.setObjectName("kop_sub")
        self.label_jaren.setWordWrap(True)
        layout.addWidget(self.label_jaren)
        self.spin_begin.valueChanged.connect(self._check_jaren)
        self.spin_eind.valueChanged.connect(self._check_jaren)
        self._check_jaren()
        kolom.addWidget(kaart)

        # --- taakkeuze
        kaart_taak, layout_taak = self._kaart("TAAK")
        self.radio_knoppen: dict[str, QRadioButton] = {}
        for taak in TAKEN:
            naam, uitleg = TAAL[taak]
            radio = QRadioButton(naam)
            radio.setToolTip(uitleg)
            if taak == "alles":
                radio.setChecked(True)
            radio.toggled.connect(self._taak_gewijzigd)
            layout_taak.addWidget(radio)
            self.radio_knoppen[taak] = radio
        layout_taak.addSpacing(2)
        self.label_taak_info = QLabel("")
        self.label_taak_info.setObjectName("kop_sub")
        self.label_taak_info.setWordWrap(True)
        layout_taak.addWidget(self.label_taak_info)
        self.label_taak_info.setText(TAAL["alles"][1])
        kolom.addWidget(kaart_taak)

        # --- opties
        kaart_opties, layout_opties = self._kaart("OPTIES")
        self.cb_verwijder = QCheckBox("mp4's opruimen na converteren")
        self.cb_verwijder.setToolTip(
            "Spaart schijfruimte. De mp3 blijft, alleen de video verdwijnt.\n"
            "Staat standaard aan; zet het uit als je de mp4's wilt bewaren."
        )
        self.cb_verwijder.setChecked(True)
        self.cb_hernoemen = QCheckBox("Schudden en hernummeren")
        self.cb_hernoemen.setToolTip(
            "Bij het verplaatsen: willekeurige volgorde met een numerieke prefix,\n"
            "zodat hetzelfde nummer nooit twee keer achter elkaar staat.\n"
            "De breedte van de prefix volgt het aantal bestanden."
        )
        self.cb_hernoemen.setChecked(True)
        self.cb_overschrijven = QCheckBox("Hits-lijst opnieuw scrapen")
        self.cb_overschrijven.setToolTip(
            "Standaard wordt een bestaand hits-bestand hergebruikt, "
            "zodat je een onderbroken run kunt hervatten."
        )
        self.cb_overschrijven.setChecked(False)
        self.cb_sla_over = QCheckBox("Alleen nummers downloaden die ik nog niet heb")
        self.cb_sla_over.setToolTip(
            "Vergelijkt de lijst met je muziekmap en slaat over wat er al staat.\n"
            "Voorkomt dat je een jaar opnieuw downloadt.\n"
            "Staat standaard aan; zet het uit om een heel jaar opnieuw te halen."
        )
        self.cb_sla_over.setChecked(True)
        layout_opties.addWidget(self.cb_verwijder)
        layout_opties.addWidget(self.cb_hernoemen)
        layout_opties.addWidget(self.cb_overschrijven)
        layout_opties.addWidget(self.cb_sla_over)

        cookie_rij = QHBoxLayout()
        cookie_rij.setSpacing(10)
        cookie_label = QLabel("YouTube-cookies")
        cookie_label.setObjectName("kaart_titel")
        self.combo_cookie = QComboBox()
        self.combo_cookie.addItems(list(kern.COOKIE_BROWSERS))
        if self._cookie_browser in kern.COOKIE_BROWSERS:
            self.combo_cookie.setCurrentText(self._cookie_browser)
        self.combo_cookie.setToolTip(
            "Standaard leest yt-dlp de cookies uit Chromium.\n"
            "Dat helpt bij video's waarvoor YouTube een login vraagt.\n"
            "Kies 'geen' als je geen cookies wilt gebruiken."
        )
        cookie_rij.addWidget(cookie_label)
        cookie_rij.addWidget(self.combo_cookie, 1)
        layout_opties.addSpacing(4)
        layout_opties.addLayout(cookie_rij)

        layout_opties.addSpacing(6)
        self.label_prefix = QLabel("")
        self.label_prefix.setObjectName("kop_sub")
        self.label_prefix.setWordWrap(True)
        layout_opties.addWidget(self.label_prefix)
        kolom.addWidget(kaart_opties)

        kolom.addStretch(1)
        scroll.setWidget(inhoud)
        return scroll

    def _maprij(self, label: str, waarde: Path, kies, hulp: str):
        """Maak een rij met label, pad-veld en Bladeren-knop."""
        vak = QFrame()
        vak.setObjectName("rij")
        rij = QHBoxLayout(vak)
        rij.setContentsMargins(0, 0, 0, 0)
        rij.setSpacing(8)

        kol = QVBoxLayout()
        kol.setSpacing(4)
        naam = QLabel(label)
        naam.setObjectName("kaart_titel")
        veld = QLineEdit(str(waarde))
        veld.setToolTip(hulp)
        veld.setMinimumWidth(120)
        kol.addWidget(naam)
        kol.addWidget(veld)

        knop = QPushButton()
        knop.setIcon(maak_icoon("map", self.kleuren, 16))
        knop.setIconSize(QSize(16, 16))
        knop.setFixedWidth(42)
        knop.setToolTip(f"Kies de {label.lower()}")
        knop.clicked.connect(kies)

        rij.addLayout(kol, 1)
        rij.addWidget(knop, 0, Qt.AlignBottom)
        return vak, veld, knop

    def _jaarveld(self, waarde: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(kern.EERSTEJAAR, 2100)
        spin.setValue(waarde)
        spin.setButtonSymbols(QSpinBox.UpDownArrows)
        return spin

    def _consolepaneel(self) -> QWidget:
        vak = QWidget()
        layout = QVBoxLayout(vak)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        kop_rij = QHBoxLayout()
        kop_rij.setSpacing(8)
        console_label = QLabel("CONSOLE")
        console_label.setObjectName("kaart_titel")
        kop_rij.addWidget(console_label)
        self.label_teller = QLabel("")
        self.label_teller.setObjectName("kop_sub")
        kop_rij.addWidget(self.label_teller)
        kop_rij.addStretch(1)

        self.knop_knip = QPushButton("Kopieer")
        self.knop_knip.clicked.connect(self._kopieer_console)
        self.knop_knip.setToolTip("Kopieer de hele uitvoer naar het klembord")
        self.knop_wis = QPushButton("Wis")
        self.knop_wis.clicked.connect(self._wis_console)
        kop_rij.addWidget(self.knop_knip)
        kop_rij.addWidget(self.knop_wis)
        layout.addLayout(kop_rij)

        self.console = Console(self.kleuren)
        layout.addWidget(self.console, 1)
        return vak

    def _voeten(self) -> QWidget:
        voeten = QFrame()
        voeten.setObjectName("kop")
        voeten.setFixedHeight(74)
        rij = QHBoxLayout(voeten)
        rij.setContentsMargins(18, 12, 18, 12)
        rij.setSpacing(14)

        links = QVBoxLayout()
        links.setSpacing(6)
        self.voortgang_label = QLabel("Gereed")
        self.voortgang_label.setObjectName("kaart_titel")
        self.balk = QProgressBar()
        self.balk.setRange(0, 100)
        self.balk.setValue(0)
        self.balk.setTextVisible(False)
        links.addWidget(self.voortgang_label)
        links.addWidget(self.balk)
        rij.addLayout(links, 1)

        self.knop_start = QPushButton("  Start  ")
        self.knop_start.setObjectName("hoofd_knop")
        self.knop_start.setIcon(maak_icoon("start", self.kleuren, 16))
        self.knop_start.setIconSize(QSize(16, 16))
        self.knop_start.setCursor(Qt.PointingHandCursor)
        self.knop_start.clicked.connect(self._start)

        self.knop_stop = QPushButton("Stoppen")
        self.knop_stop.setObjectName("stop_knop")
        self.knop_stop.setIcon(maak_icoon("stop", self.kleuren, 16))
        self.knop_stop.setIconSize(QSize(16, 16))
        self.knop_stop.setCursor(Qt.PointingHandCursor)
        self.knop_stop.setEnabled(False)
        self.knop_stop.clicked.connect(self._stop)

        rij.addWidget(self.knop_start)
        rij.addWidget(self.knop_stop)
        return voeten

    def _sneltoetsen(self) -> None:
        QShortcut(QKeySequence("Ctrl+Return"), self, self._start)
        QShortcut(QKeySequence("Ctrl+."), self, self._stop)
        QShortcut(QKeySequence("Ctrl+L"), self, self.console.setFocus)
        QShortcut(QKeySequence("Ctrl+K"), self, self._wis_console)

    # ---------------------------------------------------------------- stijl
    def _pas_stijl_toe(self) -> None:
        self.setStyleSheet(stijlblad(self.kleuren))
        licht = self.thema_naam == "licht"
        self.knop_thema.setText("Donker thema" if licht else "Licht thema")
        self.setWindowIcon(maak_icoon("muziek", self.kleuren, 32))
        self.knop_start.setIcon(maak_icoon("start", self.kleuren, 16))
        self.knop_stop.setIcon(maak_icoon("stop", self.kleuren, 16))
        for knop in (self.knop_werk, self.knop_muziek):
            knop.setIcon(maak_icoon("map", self.kleuren, 16))
        self.console.zet_kleuren(self.kleuren)

    @Slot(bool)
    def _wissel_thema(self, licht: bool) -> None:
        self.thema_naam = "licht" if licht else "donker"
        self.kleuren = KLEUREN[self.thema_naam]
        self._pas_stijl_toe()

    # ------------------------------------------------------------- acties
    def log(self, regel: str) -> None:
        self.console.schrijf(regel)

    def _kies_werk(self) -> None:
        keuze = QFileDialog.getExistingDirectory(
            self, "Kies de werkmap", str(self._werk)
        )
        if keuze:
            self.veld_werk.setText(keuze)
            self._werk = Path(keuze)
            self._na_wijziging()

    def _kies_muziek(self) -> None:
        keuze = QFileDialog.getExistingDirectory(
            self, "Kies de muziekmap", str(self._muziek)
        )
        if keuze:
            self.veld_muziek.setText(keuze)
            self._muziek = Path(keuze)
            self._na_wijziging()

    def _check_jaren(self) -> None:
        begin = self.spin_begin.value()
        eind = self.spin_eind.value()
        try:
            b, e, waarschuwingen = kern.controleer_jaren(begin, eind)
        except kern.Fout as fout:
            self.label_jaren.setText(f"⚠ {fout}")
            return
        self.spin_begin.blockSignals(True)
        self.spin_eind.blockSignals(True)
        self.spin_begin.setValue(b)
        self.spin_eind.setValue(e)
        self.spin_begin.blockSignals(False)
        self.spin_eind.blockSignals(False)
        self.label_jaren.setText(" ".join(waarschuwingen) if waarschuwingen else "")

    def _na_wijziging(self) -> None:
        self._werk = Path(self.veld_werk.text().strip() or kern.standaard_werkmap())
        self._muziek = Path(self.veld_muziek.text().strip() or kern.standaard_muziekmap())
        self._bewaar(met_venster=False)
        self._toon_samenvatting()

    def _bewaar(self, met_venster: bool = True) -> None:
        """Instellingen wegschrijven.

        Het thema gaat altijd mee. De venstergrootte alleen als `met_venster`:
        `_na_wijziging()` roept dit ook aan bij het typen in een veld, en dan is
        de grootte van het venster toevallig veranderd. Bij het afsluiten wil je
        die juist wél onthouden, en dat is wat `closeEvent` vraagt.
        """
        extra = {"thema": self.thema_naam}
        if met_venster:
            extra.update(self.onthoud_afmetingen())
        try:
            kern.bewaar_instellingen(
                self._werk,
                self._muziek,
                self.combo_cookie.currentText(),
                extra=extra,
            )
        except OSError as fout:
            self.log(f"⚠ Instellingen konden niet bewaard worden: {fout}")

    def _taak_gewijzigd(self) -> None:
        taak = self._huidige_taak()
        self._voortgang_boek = VoortgangsBoek(taak)
        self.label_taak_info.setText(TAAL[taak][1])

    def _huidige_taak(self) -> str:
        for taak, radio in self.radio_knoppen.items():
            if radio.isChecked():
                return taak
        return "alles"

    # ---------------------------------------------------------------- start
    def _start(self) -> None:
        if self.thread and self.thread.isRunning():
            return
        self._check_jaren()
        begin = self.spin_begin.value()
        eind = self.spin_eind.value()
        if begin > eind:
            QMessageBox.warning(
                self, "Jaren",
                "Beginjaar mag niet groter zijn dan eindjaar.",
            )
            return

        werk = Path(self.veld_werk.text().strip())
        muziek = Path(self.veld_muziek.text().strip())
        if not werk or not muziek:
            QMessageBox.warning(self, "Mappen", "Vul beide mappen in.")
            return
        try:
            werk = werk.expanduser()
            muziek = muziek.expanduser()
            paden = kern.Paden(werk, muziek).maak()
        except OSError as fout:
            QMessageBox.critical(self, "Mappen", f"Deze mappen zijn niet bruikbaar:\n{fout}")
            return

        self._werk, self._muziek = werk, muziek
        self._bewaar()
        taak = self._huidige_taak()

        ctx = kern.Context(
            paden=paden,
            cookie_browser=self.combo_cookie.currentText(),
        )
        opties = {
            "begin": begin,
            "eind": eind,
            "verwijder_mp4": self.cb_verwijder.isChecked(),
            "hernoemen": self.cb_hernoemen.isChecked(),
            "overschrijven": self.cb_overschrijven.isChecked(),
            "sla_over": self.cb_sla_over.isChecked(),
        }

        self._voortgang_boek = VoortgangsBoek(taak)
        self.balk.setValue(0)
        self._zet_draaiend(True)
        self.console.appendPlainText("")

        self.log(f"{'─' * 58}")
        self.log(f"▶ {TAAL[taak][0]} — {TAAL[taak][1]}")
        self.log(f"  Periode: {begin}–{eind}")
        self.log(f"  Werkmap: {werk}")
        self.log(f"  Muziekmap: {muziek}")
        self.log("─" * 58)

        self.thread = TaakThread(taak, ctx, opties, self)
        self.thread.log.connect(self.log)
        self.thread.voortgang.connect(self._op_voortgang)
        self.thread.deelvoortgang.connect(self._op_deelvoortgang)
        self.thread.klaar.connect(self._op_klaar)
        self.thread.samenvatting.connect(self._toon_samenvatting)
        self.thread.finished.connect(lambda: self._zet_draaiend(False))
        self.thread.start()

    def _stop(self) -> None:
        if self.thread and self.thread.isRunning():
            self.thread.requestInterruption()
            self.status_label.setText("Stoppen…")
            self.voortgang_label.setText("Bezig met stoppen…")
            self.log("\n■ Stoppen aangevraagd…")

    # ------------------------------------------------------------- signalen
    def _zet_draaiend(self, draait: bool) -> None:
        self.knop_start.setEnabled(not draait)
        self.knop_stop.setEnabled(draait)
        for widget in (
            self.veld_werk, self.veld_muziek, self.spin_begin, self.spin_eind,
            self.cb_verwijder, self.cb_hernoemen, self.cb_overschrijven,
            self.combo_cookie,
        ):
            widget.setEnabled(not draait)
        for radio in self.radio_knoppen.values():
            radio.setEnabled(not draait)
        if not draait:
            self.status_label.setText("Gereed")

    @Slot(str, int, int, str)
    def _op_voortgang(self, fase: str, index: int, totaal: int, label: str) -> None:
        if self._voortgang_boek is None:
            self._voortgang_boek = VoortgangsBoek(self._huidige_taak())
        self._voortgang_boek.zet(fase, index, totaal)
        self.balk.setValue(int(self._voortgang_boek.totaal()))
        naam = FASEN.get(fase, fase)
        if totaal > 0:
            self.voortgang_label.setText(f"{naam}  {index}/{totaal}")
        else:
            self.voortgang_label.setText(naam)
        self.status_label.setText(label or naam)

    @Slot(str, float, str)
    def _op_deelvoortgang(self, fase: str, fractie: float, label: str) -> None:
        if self._voortgang_boek is None:
            return
        self._voortgang_boek.deelvoortgang(fase, fractie)
        self.balk.setValue(int(self._voortgang_boek.totaal()))

    @Slot(str, bool)
    def _op_klaar(self, bericht: str, geslaagd: bool) -> None:
        self._voortgang_label.setText(bericht)
        self.status_label.setText(bericht)
        if geslaagd:
            self.balk.setValue(100)
        self._zet_draaiend(False)
        self._toon_samenvatting()

    def _toon_samenvatting(self, telling: dict | None = None) -> None:
        try:
            paden = kern.Paden(
                Path(self.veld_werk.text().strip() or self._werk),
                Path(self.veld_muziek.text().strip() or self._muziek),
            )
            telling = telling or kern.samenvatting(paden)
        except Exception:
            return
        if not telling:
            return
        self.label_teller.setText(
            f"{telling['hits']} hits   ·   {telling['mp4']} mp4   ·   "
            f"{telling['mp3']} mp3   ·   {telling['muziek']} in de muziekmap"
        )
        self._toon_prefix(telling["muziek"])

    def _toon_prefix(self, aantal: int | None = None) -> None:
        """Laat zien welke prefixbreedte bij het huidige aantal hoort."""
        if aantal is None:
            try:
                aantal = len(kern.mp3_bestanden(Path(self.veld_muziek.text().strip())))
            except OSError:
                aantal = 0
        breedte = kern.prefix_breedte(aantal)
        voorbeeld = "0" * breedte
        if aantal:
            self.label_prefix.setText(
                f"Nummering: {breedte} cijfers ({voorbeeld}-…), "
                f"passend bij {aantal} bestanden in de muziekmap."
            )
        else:
            self.label_prefix.setText(
                f"Nummering: {breedte} cijfers ({voorbeeld}-…) "
                "zodra de muziekmap bestanden bevat."
            )

    def _wis_console(self) -> None:
        self.console.leeg()

    def _kopieer_console(self) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self.console.toPlainText())
        self.status_label.setText("Console gekopieerd naar het klembord")

    # ---------------------------------------------------------------- sloten
    def closeEvent(self, event) -> None:
        if self.thread and self.thread.isRunning():
            antwoord = QMessageBox.question(
                self, "Top30",
                "Er is nog een taak bezig.\n\nWil je stoppen en sluiten?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if antwoord != QMessageBox.Yes:
                event.ignore()
                return
            self.thread.requestInterruption()
            self.thread.wait(15000)
        # Hier ook de venstergrootte onthouden, zodat de volgende keer het
        # venster zo groot opent als de gebruiker het nu heeft gemaakt.
        self._bewaar(met_venster=True)
        event.accept()


# --------------------------------------------------------------------------
# Starten
# --------------------------------------------------------------------------

def maak_app() -> QApplication:
    """Zet de QApplication op (of pak de bestaande).

    Apart van `start` gehouden zodat de zelftest dit kan controleren zonder
    de event loop te hoeven starten.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setApplicationName(APP_NAAM)
    app.setOrganizationName(ORG_VENSTER)
    return app


def start(thema: str | None = None) -> int:
    app = maak_app()
    if thema is None:
        thema = kern.laad_instellingen().get("thema", "donker")
    if thema not in KLEUREN:
        thema = "donker"
    venster = Venster(thema)
    venster.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(start())
