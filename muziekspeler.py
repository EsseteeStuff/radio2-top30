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
"""Muziekspeler in de stijl van de Top30-app, een "Winamp-light".

    .venv/bin/python muziekspeler.py

Opent een map met muziek (of sleep bestanden in het venster) en speelt ze
af. De vormgeving, thema's en sneltoetsen passen bij Top30: donker en licht
thema, een afspeellijst, voortgangsbalk, volume, willekeurig en herhalen.

Sneltoetsen:
    Spatie          afspelen / pauzeren
    Ctrl+O          een map kiezen
    Ctrl+Links      vorige nummer
    Ctrl+Rechts     volgende nummer
    Ctrl+H          herhalen (uit → één → alle)
    Ctrl+M          dempen
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QUrl, Signal
from PySide6.QtGui import QFontDatabase, QKeySequence, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMainWindow, QPushButton, QSlider, QVBoxLayout, QWidget,
)

import top30_gui as gui

APP_TITEL = "Muziekspeler"

# Bestandstypen die de afspeellijst herkent. QtMultimedia speelt op
# macOS/Windows/Linux alles af wat het systeem aankan; hier worden alleen
# de gangbare muziekbestanden opgeraapt.
MEDIA_EXTENSIES = {
    ".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".opus", ".wma",
}

# "uit" → de afspeellijst stopt na het laatste nummer; "een" → herhaal
# hetzelfde nummer; "alle" → de hele lijst opnieuw.
HERHALEN_MODES = ["uit", "een", "alle"]


# --------------------------------------------------------------------------
# Tijd- en naamhulpen (los gehouden van het venster, zodat de zelftest ze
# snel kan draaien)
# --------------------------------------------------------------------------

def formaat_tijd(ms: int) -> str:
    """Milliseconden als m:ss, of u:mm:ss vanaf een uur."""
    totaal_s = max(0, round(ms / 1000))
    uren, rest = divmod(totaal_s, 3600)
    minuten, seconden = divmod(rest, 60)
    if uren:
        return f"{uren}:{minuten:02d}:{seconden:02d}"
    return f"{minuten}:{seconden:02d}"


def toon_naam(pad: Path) -> str:
    """Een leesbare naam: artiest - titel uit de tags, anders de bestandsnaam.

    Bij de Top30-bestanden staat er een nummer voor ("0017-ABBA - …"); dat
    wordt er voor de weergave afgehaald.
    """
    try:
        import mutagen
        bestand = mutagen.File(str(pad), easy=True)
    except Exception:
        bestand = None
    if bestand is not None:
        artiest = str(bestand.get("artist", [""])[0]).strip() if bestand.get("artist") else ""
        titel = str(bestand.get("title", [""])[0]).strip() if bestand.get("title") else ""
        if artiest and titel:
            return f"{artiest} - {titel}"
        if artiest or titel:
            return artiest or titel
    import re
    return re.sub(r"^\d+[\s_-]+", "", pad.stem)


def zoek_muziek(map_pad: Path, extensies: set[str] | None = None) -> list[Path]:
    """Alle muziekbestanden onder map_pad, op naam gesorteerd.

    Verborgen mappen (namen die met een punt beginnen) worden overgeslagen.
    """
    kegels = set(extensies or MEDIA_EXTENSIES)
    gevonden: list[Path] = []
    for pad in sorted(map_pad.rglob("*")):
        if pad.is_file() and pad.suffix.lower() in kegels:
            if any(deel.startswith(".") for deel in pad.parts[len(map_pad.parts):]):
                continue  # verborgen map overgeslagen
            gevonden.append(pad)
    return gevonden


def _extra_stijl(kleuren: dict) -> str:
    """De stijl voor de speler-onderdelen, bovenop het Top30-palet."""
    mono = QFontDatabase.systemFont(QFontDatabase.FixedFont).family()
    return f"""
    /* ---------- muziekspeler ---------- */
    #playlist {{
        background: {kleuren['paneel_licht']};
        border: 1px solid {kleuren['rand']};
        border-radius: 8px;
        padding: 4px;
        outline: none;
    }}
    #playlist::item {{ padding: 4px 8px; border-radius: 5px; }}
    #playlist::item:hover {{ background: {kleuren['paneel']}; }}
    #playlist::item:selected {{
        background: {kleuren['accent']};
        color: {kleuren['accent_tekst']};
    }}
    #playlist::item:selected:hover {{ background: {kleuren['accent_hover']}; }}
    #nu_naam {{
        font-size: 12.5pt; font-weight: 600; background: transparent;
        border-bottom: 1px solid {kleuren['rand']}; padding-bottom: 8px;
    }}
    #tijd {{
        font-family: "{mono}"; font-size: 9pt; color: {kleuren['tekst_zwak']};
        background: transparent;
    }}
    QSlider::groove:horizontal {{
        background: {kleuren['paneel_licht']}; height: 6px; border-radius: 3px;
    }}
    QSlider::sub-page:horizontal {{ background: {kleuren['accent']}; border-radius: 3px; }}
    QSlider::handle:horizontal {{
        background: {kleuren['tekst']}; width: 14px; height: 14px;
        margin: -5px 0; border-radius: 7px;
    }}
    QSlider::handle:horizontal:hover {{ background: {kleuren['accent']}; }}
    QSlider::handle:horizontal:pressed {{ background: {kleuren['accent_hover']}; }}
    QPushButton:checked {{
        background: {kleuren['accent']}; color: {kleuren['accent_tekst']};
        border-color: {kleuren['accent']};
    }}
    """


def speler_stijlblad(kleuren: dict) -> str:
    """Het volledige stylesheet: Top30-basis plus de speler-regels."""
    return gui.stijlblad(kleuren) + _extra_stijl(kleuren)


# --------------------------------------------------------------------------
# De afspeellijst, met het accepteren van gesleepte bestanden en mappen
# --------------------------------------------------------------------------

class Afspeellijst(QListWidget):
    bestanden = Signal(list)  # lijst van paden (str), uit slepen of dialoog

    def __init__(self, ouder: QWidget | None = None) -> None:
        super().__init__(ouder)
        self.setObjectName("playlist")
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DropOnly)

    def dragEnterEvent(self, gebeurtenis) -> None:
        if gebeurtenis.mimeData().hasUrls():
            gebeurtenis.acceptProposedAction()

    def dragMoveEvent(self, gebeurtenis) -> None:
        if gebeurtenis.mimeData().hasUrls():
            gebeurtenis.acceptProposedAction()

    def dropEvent(self, gebeurtenis) -> None:
        paden: list[str] = []
        for url in gebeurtenis.mimeData().urls():
            if url.isLocalFile():
                paden.append(url.toLocalFile())
        if paden:
            self.bestanden.emit(paden)
        gebeurtenis.acceptProposedAction()


# --------------------------------------------------------------------------
# Het venster
# --------------------------------------------------------------------------

class Muziekvenster(QMainWindow):
    def __init__(self, thema: str = "donker") -> None:
        super().__init__()
        self.setWindowTitle(APP_TITEL)
        self.setMinimumSize(900, 520)
        self.resize(1040, 640)

        # Geluid: de speler speelt via de systeem-uitgang.
        self.speler = QMediaPlayer(self)
        self.uitvoer = QAudioOutput(self)
        self.uitvoer.setVolume(0.8)
        self.speler.setAudioOutput(self.uitvoer)

        self.thema_naam = thema if thema in gui.KLEUREN else "donker"
        self.kleuren = gui.KLEUREN[self.thema_naam]

        self.huidige_index = -1
        self.herhaal_mode = 0      # stand "uit"
        self.willekeurig = False
        self._sleept = False       # de gebruiker sleept de voortgangsbalk
        self._onthouden = True     # de zelftest zet dit uit via _onthoud()

        self._bouw_venster()
        self._koppel_geluid()
        self._laad_instellingen()
        self._geef_stijl()

    # ------------------------------------------------------------ opbouw

    def _bouw_venster(self) -> None:
        centraal = QWidget()
        kolom = QVBoxLayout(centraal)
        kolom.setContentsMargins(0, 0, 0, 0)
        kolom.setSpacing(0)

        # Kopbalk, net als in Top30.
        kop = QFrame()
        kop.setObjectName("kop")
        kopbalk = QHBoxLayout(kop)
        kopbalk.setContentsMargins(16, 10, 16, 10)
        kop_titel = QLabel(APP_TITEL)
        kop_titel.setObjectName("kop_titel")
        kop_sub = QLabel("Een Winamp-light in Python, in de Top30-stijl")
        kop_sub.setObjectName("kop_sub")
        kop_tekst = QVBoxLayout()
        kop_tekst.setSpacing(0)
        kop_tekst.addWidget(kop_titel)
        kop_tekst.addWidget(kop_sub)
        kopbalk.addLayout(kop_tekst)
        kopbalk.addStretch(1)
        self.knop_thema = QPushButton()
        self.knop_thema.setCheckable(True)
        self.knop_thema.clicked.connect(self._wissel_thema)
        kopbalk.addWidget(self.knop_thema)
        kolom.addWidget(kop)

        # Twee kaarten: links de afspeellijst, rechts de bediening.
        inhoud = QHBoxLayout()
        inhoud.setContentsMargins(16, 14, 16, 14)
        inhoud.setSpacing(14)

        links = QFrame()
        links.setObjectName("kaart")
        links_rij = QVBoxLayout(links)
        links_rij.setContentsMargins(14, 12, 14, 14)
        links_titel = QLabel("AFSPELLIJST")
        links_titel.setObjectName("kaart_titel")
        links_rij.addWidget(links_titel)

        self.playlist = Afspeellijst()
        self.playlist.itemDoubleClicked.connect(
            lambda item: self.speel(self.playlist.row(item)))
        links_rij.addWidget(self.playlist, 1)

        rij_knop = QHBoxLayout()
        self.knop_map = QPushButton("Map kiezen…")
        self.knop_map.clicked.connect(self._kies_map)
        self.knop_bestanden = QPushButton("Bestanden…")
        self.knop_bestanden.clicked.connect(self._kies_bestanden)
        self.knop_wis = QPushButton("Wis")
        self.knop_wis.clicked.connect(self._wis_lijst)
        rij_knop.addWidget(self.knop_map)
        rij_knop.addWidget(self.knop_bestanden)
        rij_knop.addStretch(1)
        rij_knop.addWidget(self.knop_wis)
        links_rij.addLayout(rij_knop)

        inhoud.addWidget(links, 3)

        rechts = QFrame()
        rechts.setObjectName("kaart")
        rechts_rij = QVBoxLayout(rechts)
        rechts_rij.setContentsMargins(14, 12, 14, 14)
        speler_titel = QLabel("SPELER")
        speler_titel.setObjectName("kaart_titel")
        rechts_rij.addWidget(speler_titel)

        self.nu_naam = QLabel("— kies een nummer —")
        self.nu_naam.setObjectName("nu_naam")
        self.nu_naam.setWordWrap(True)
        self.nu_naam.setMinimumHeight(46)
        rechts_rij.addWidget(self.nu_naam)

        # Voortgang: positie, balk en totale duur.
        voortgang = QHBoxLayout()
        voortgang.setSpacing(8)
        self.tijd_huidig = QLabel("0:00")
        self.tijd_huidig.setObjectName("tijd")
        self.tijd_totaal = QLabel("0:00")
        self.tijd_totaal.setObjectName("tijd")
        self.tijd_totaal.setAlignment(Qt.AlignRight)
        self.schuif_voortgang = QSlider(Qt.Horizontal)
        self.schuif_voortgang.sliderMoved.connect(self._mors_balk)
        self.schuif_voortgang.sliderPressed.connect(
            lambda: setattr(self, "_sleept", True))
        self.schuif_voortgang.sliderReleased.connect(self._los_balk)
        voortgang.addWidget(self.tijd_huidig)
        voortgang.addWidget(self.schuif_voortgang, 1)
        voortgang.addWidget(self.tijd_totaal)
        rechts_rij.addLayout(voortgang)

        # Openen-van: vorige, speel/pauze, volgende, stoppen.
        open = QHBoxLayout()
        open.setSpacing(8)
        self.knop_vorige = QPushButton("⏮ Vorige")
        self.knop_vorige.clicked.connect(self.vorige)
        self.knop_afspelen = QPushButton("Afspelen")
        self.knop_afspelen.setObjectName("hoofd_knop")
        self.knop_afspelen.clicked.connect(self.afspelen_of_pauzeren)
        self.knop_volgende = QPushButton("Volgende ⏭")
        self.knop_volgende.clicked.connect(self.volgende)
        self.knop_stop = QPushButton("Stoppen")
        self.knop_stop.setObjectName("stop_knop")
        self.knop_stop.clicked.connect(self.stoppen)
        open.addWidget(self.knop_vorige)
        open.addWidget(self.knop_afspelen, 1)
        open.addWidget(self.knop_volgende)
        open.addWidget(self.knop_stop)
        rechts_rij.addLayout(open)

        # Opties en volume.
        opties = QHBoxLayout()
        opties.setSpacing(8)
        self.knop_willekeurig = QPushButton("Willekeurig")
        self.knop_willekeurig.setCheckable(True)
        self.knop_willekeurig.toggled.connect(
            lambda aan: setattr(self, "willekeurig", aan))
        self.knop_herhalen = QPushButton()
        self.knop_herhalen.setCheckable(True)
        self.knop_herhalen.clicked.connect(self._wissel_herhalen)
        opties.addWidget(self.knop_willekeurig)
        opties.addWidget(self.knop_herhalen)
        opties.addStretch(1)
        self.knop_dempen = QPushButton("Dempen")
        self.knop_dempen.setCheckable(True)
        self.knop_dempen.toggled.connect(self.uitvoer.setMuted)
        self.schuif_volume = QSlider(Qt.Horizontal)
        self.schuif_volume.setRange(0, 100)
        self.schuif_volume.setValue(80)
        self.schuif_volume.setFixedWidth(170)
        self.schuif_volume.valueChanged.connect(self._zet_volume)
        self.volume_tekst = QLabel("80%")
        self.volume_tekst.setObjectName("tijd")
        opties.addWidget(self.knop_dempen)
        opties.addWidget(self.schuif_volume)
        opties.addWidget(self.volume_tekst)
        rechts_rij.addLayout(opties)
        rechts_rij.addStretch(1)

        inhoud.addWidget(rechts, 4)
        kolom.addLayout(inhoud, 1)
        self.setCentralWidget(centraal)

        # Sneltoetsen.
        QShortcut(QKeySequence("Space"), self, self.afspelen_of_pauzeren)
        QShortcut(QKeySequence("Ctrl+O"), self, self._kies_map)
        QShortcut(QKeySequence("Ctrl+Left"), self, self.vorige)
        QShortcut(QKeySequence("Ctrl+Right"), self, self.volgende)
        QShortcut(QKeySequence("Ctrl+H"), self, lambda: self._wissel_herhalen())
        QShortcut(QKeySequence("Ctrl+M"), self, self.knop_dempen.click)

    def _koppel_geluid(self) -> None:
        self.speler.positionChanged.connect(self._bij_voortgang)
        self.speler.durationChanged.connect(self._bij_duur)
        self.speler.playbackStateChanged.connect(self._bij_toestand)
        self.speler.mediaStatusChanged.connect(self._bij_status)
        self.speler.errorOccurred.connect(self._bij_fout)

    # --------------------------------------------------------- instellingen

    def _laad_instellingen(self) -> None:
        opslag = QSettings("Top30", APP_TITEL)
        self.schuif_volume.setValue(int(opslag.value("volume", 80)))
        self.knop_willekeurig.setChecked(opslag.value("willekeurig", False) in
                                         (True, "true", "1"))
        self.herhaal_mode = 0
        self.knop_herhalen.setChecked(False)
        self._zet_herhalen_tekst()
        if self.thema_naam == "licht":
            self.knop_thema.setChecked(True)

    def _onthoud(self) -> None:
        if not self._onthouden:
            return
        opslag = QSettings("Top30", APP_TITEL)
        opslag.setValue("thema", self.thema_naam)
        opslag.setValue("volume", self.schuif_volume.value())
        opslag.setValue("willekeurig", self.willekeurig)

    def closeEvent(self, gebeurtenis) -> None:  # noqa: N802 (Qt-naam)
        self._onthoud()
        super().closeEvent(gebeurtenis)

    # --------------------------------------------------------------- stijl

    def _geef_stijl(self) -> None:
        self.setStyleSheet(speler_stijlblad(self.kleuren))
        licht = self.thema_naam == "licht"
        self.knop_thema.setText("Donker thema" if licht else "Licht thema")

    def _wissel_thema(self, licht: bool) -> None:
        self.thema_naam = "licht" if licht else "donker"
        self.kleuren = gui.KLEUREN[self.thema_naam]
        self._geef_stijl()

    # ---------------------------------------------------------- afspeellijst

    def aantal(self) -> int:
        return self.playlist.count()

    def _pad_van(self, rij: int) -> str | None:
        item = self.playlist.item(rij)
        if item is None:
            return None
        return item.data(Qt.UserRole)

    def voeg_bestanden_toe(self, paden: list[str]) -> int:
        """Bestanden of mappen toevoegen; geeft het aantal nieuwe nummers terug."""
        was_leeg = self.aantal() == 0
        nieuw = 0
        bestaande = {
            self._pad_van(i) for i in range(self.aantal())
        }
        for ruw in paden:
            pad = Path(ruw)
            if pad.is_dir():
                kandidaten = zoek_muziek(pad)
            elif pad.is_file() and pad.suffix.lower() in MEDIA_EXTENSIES:
                kandidaten = [pad]
            else:
                continue
            for bestand in kandidaten:
                sleutel = str(bestand)
                if sleutel in bestaande:
                    continue
                item = QListWidgetItem(
                    f"{self.aantal() + 1}. {toon_naam(bestand)}")
                item.setData(Qt.UserRole, sleutel)
                self.playlist.addItem(item)
                bestaande.add(sleutel)
                nieuw += 1
        van_start_af = (
            self.speler.playbackState() == QMediaPlayer.PlaybackState.StoppedState
            and self.huidige_index == -1)
        if was_leeg and nieuw and van_start_af:
            self.speel(0)  # alsof Winamp: meteen beginnen
        self._zet_besturing()
        return nieuw

    def _kies_map(self) -> None:
        map_naam = QFileDialog.getExistingDirectory(self, "Kies een map met muziek")
        if map_naam:
            self.playlist.bestanden.emit([map_naam])

    def _kies_bestanden(self) -> None:
        soorten = " ".join(f"*{v}" for v in sorted(MEDIA_EXTENSIES))
        namen, _ = QFileDialog.getOpenFileNames(
            self, "Kies muziekbestanden", "", f"Muziek ({soorten})")
        if namen:
            self.playlist.bestanden.emit(namen)

    def _wis_lijst(self) -> None:
        self.stoppen()
        self.playlist.clear()
        self.huidige_index = -1
        self.nu_naam.setText("— kies een nummer —")
        self.schuif_voortgang.setValue(0)
        self.tijd_huidig.setText("0:00")
        self.tijd_totaal.setText("0:00")
        self._zet_besturing()

    # ----------------------------------------------------------- afspelen

    def speel(self, rij: int) -> None:
        if not 0 <= rij < self.aantal():
            return
        self.huidige_index = rij
        item = self.playlist.item(rij)
        self.playlist.setCurrentRow(rij)
        self.playlist.scrollToItem(item)
        pad = self._pad_van(rij)
        self.nu_naam.setText(self._naam_van(rij))
        self.nu_naam.setToolTip(pad or "")
        self.speler.stop()
        self.speler.setSource(QUrl.fromLocalFile(pad or ""))
        self.speler.play()
        self._zet_besturing()

    def _naam_van(self, rij: int) -> str:
        item = self.playlist.item(rij)
        return item.text() if item is not None else ""

    def afspelen_of_pauzeren(self) -> None:
        if self.aantal() == 0:
            return
        if self.huidige_index == -1:
            self.speel(0)
            return
        if self.speler.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.speler.pause()
        else:
            self.speler.play()

    def stoppen(self) -> None:
        self.speler.stop()
        self.nu_naam.setText("— gestopt —" if self.aantal() else "— kies een nummer —")

    def vorige(self) -> None:
        if self.huidige_index == -1:
            self.speel(0)
            return
        if self.speler.position() > 3000:
            self.speler.setPosition(0)  # langer dan 3 s: opnieuw beginnen
            return
        volgend = self.huidige_index - 1
        if volgend < 0:
            volgend = (self.aantal() - 1 if self.herhaal_mode == 2 else 0)
        self.speel(volgend)

    def volgende(self) -> None:
        volgend = self._volgende_index()
        if volgend is None:
            self.stoppen()  # einde van de lijst en niet herhalen
            return
        self.speel(volgend)

    def _volgende_index(self) -> int | None:
        """Het volgende indexnummer, rekening houdend met willekeurig en herhalen."""
        if self.aantal() == 0:
            return None
        if self.willekeurig and self.aantal() > 1:
            over = [i for i in range(self.aantal()) if i != self.huidige_index]
            return random.choice(over)
        volgend = self.huidige_index + 1
        if volgend < self.aantal():
            return volgend
        if self.herhaal_mode == 2:  # "alle"
            return 0
        return None

    # ------------------------------------------------------------ geluidsdraden

    def _bij_toestand(self, stand: QMediaPlayer.PlaybackState) -> None:
        speelt = stand == QMediaPlayer.PlaybackState.PlayingState
        self.knop_afspelen.setText("Pauze" if speelt else "Afspelen")
        self._zet_besturing()

    def _bij_voortgang(self, positie: int) -> None:
        if not self._sleept:
            self.schuif_voortgang.setValue(positie)
        self.tijd_huidig.setText(formaat_tijd(positie))

    def _bij_duur(self, duur: int) -> None:
        self.schuif_voortgang.setRange(0, duur)
        self.tijd_totaal.setText(formaat_tijd(duur))

    def _bij_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.herhaal_mode == 1:
                self.speel(self.huidige_index)  # "één"
            else:
                self.volgende()

    def _bij_fout(self, fout: QMediaPlayer.Error, boodschap: str) -> None:
        if fout == QMediaPlayer.Error.NoError:
            return
        self.nu_naam.setText(f"Kan dit nummer niet afspelen:\n{boodschap}")
        self.stoppen()

    def _mors_balk(self, positie: int) -> None:
        self._sleept = True
        self.tijd_huidig.setText(formaat_tijd(positie))

    def _los_balk(self) -> None:
        self._sleept = False
        self.speler.setPosition(self.schuif_voortgang.value())

    def _zet_herhalen_tekst(self) -> None:
        etiket = {"uit": "Herhalen: uit", "een": "Herhalen: één",
                  "alle": "Herhalen: alle"}
        self.knop_herhalen.setText(etiket[HERHALEN_MODES[self.herhaal_mode]])
        self.knop_herhalen.setChecked(self.herhaal_mode != 0)

    def _wissel_herhalen(self, _aan: bool | None = None) -> None:
        self.herhaal_mode = (self.herhaal_mode + 1) % len(HERHALEN_MODES)
        self._zet_herhalen_tekst()

    def _zet_volume(self, waarde: int) -> None:
        self.uitvoer.setVolume(waarde / 100)
        self.volume_tekst.setText(f"{waarde}%")

    def _zet_besturing(self) -> None:
        heeft = self.aantal() > 0
        voorbij = heeft and self.huidige_index != -1
        self.knop_afspelen.setEnabled(heeft)
        self.knop_vorige.setEnabled(heeft)
        self.knop_volgende.setEnabled(heeft)
        self.knop_stop.setEnabled(voorbij)
        self.schuif_voortgang.setEnabled(voorbij)


# --------------------------------------------------------------------------
# Starten
# --------------------------------------------------------------------------

def maak_app() -> QApplication:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_TITEL)
    return app


def start(thema: str | None = None) -> int:
    app = maak_app()
    opslag = QSettings("Top30", APP_TITEL)
    if thema is None:
        thema = str(opslag.value("thema", "donker"))
    venster = Muziekvenster(thema)
    venster.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(start())