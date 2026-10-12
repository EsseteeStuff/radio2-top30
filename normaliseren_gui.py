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
"""Grafisch venster rond normaliseren.py.

    python normaliseren.py --gui      (of: python normaliseren_gui.py)

Het venster gebruikt dezelfde stijl en console als de Top30-app. De
normalisatie draait in een achtergronddraad, zodat het venster niet blijft
hangen en je met Stoppen kunt onderbreken.
"""
from __future__ import annotations

import sys
import threading
import traceback
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread, Signal, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QDoubleSpinBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QVBoxLayout, QWidget,
)

import normaliseren as nm
import top30_core as kern
from top30_gui import Console, KLEUREN, maak_app, maak_icoon, stijlblad

APP_TITEL = "Luidheid normaliseren"


# --------------------------------------------------------------------------
# Achtergronddraad
# --------------------------------------------------------------------------

class NormaliseerThread(QThread):
    """Draait één normaliseerronde; alles gaat via signalen terug."""

    log = Signal(str)
    voortgang = Signal(int, int)     # klaar, totaal
    klaar = Signal(str, bool)        # bericht, geslaagd?

    def __init__(self, map_: Path, opties: nm.Opties, parent=None):
        super().__init__(parent)
        self.map_ = map_
        self.opties = opties
        self.ctx = kern.Context(paden=kern.Paden(map_, map_), log=self.log.emit)
        # De kern kijkt naar ctx.stop; die vullen we met een eigen Event.
        self.ctx.stop = threading.Event()

    def requestInterruption(self) -> None:
        self.ctx.stop.set()
        super().requestInterruption()

    def run(self) -> None:
        opties = self.opties
        try:
            bestanden = nm.audio_bestanden(self.map_, opties.recursief, opties.ook_mp3)
            self.log.emit(f"{len(bestanden)} bestand(en) in {self.map_}")
            self.log.emit(
                f"Doel: {opties.lufs:.0f} LUFS, max {opties.tp} dBTP"
                + ("" if opties.ja else "   (droge proef, nog niets gewijzigd)")
            )
            self.log.emit("")
            if not bestanden:
                if not opties.ook_mp3:
                    self.log.emit("(mp3's worden standaard overgeslagen; vink "
                                  "'Ook mp3's' aan om ze toch te doen.)")
                self.klaar.emit("Niets te doen.", True)
                return

            veranderd, al_goed, mislukt = nm.verwerk(
                self.ctx, bestanden, opties, self.log.emit, self.voortgang.emit)
            self.log.emit("")
            if not opties.ja:
                self.log.emit(f"{veranderd} te normaliseren, {al_goed} al goed."
                              "  (Droge proef.)")
            else:
                self.log.emit(f"{veranderd} genormaliseerd, {al_goed} al goed, "
                              f"{mislukt} mislukt.")
            self.klaar.emit("Klaar.", mislukt == 0)
        except kern.Onderbroken:
            self.log.emit("\n⛔ Onderbroken.")
            self.klaar.emit("Onderbroken door de gebruiker.", False)
        except Exception:
            self.log.emit("\n" + traceback.format_exc())
            self.klaar.emit("Er ging iets onverwachts mis (zie de console).", False)


# --------------------------------------------------------------------------
# Het venster
# --------------------------------------------------------------------------

class Venster(QMainWindow):
    """Hoofdvenster met instellingen, console en knoppen."""

    def __init__(self, thema: str = "donker", map_: Path | None = None):
        super().__init__()
        self.setWindowTitle(APP_TITEL)
        self.setMinimumSize(820, 560)
        self.resize(960, 640)
        self.setWindowIcon(maak_icoon("muziek", KLEUREN[thema], 32))

        self.kleuren = KLEUREN[thema]
        self.thema_naam = thema
        self.thread: NormaliseerThread | None = None

        instellingen = kern.laad_instellingen()
        self._map = Path(
            map_ or instellingen.get("final_folder") or kern.standaard_muziekmap()
        )

        self._bouw()
        self._pas_stijl_toe()
        self._sneltoetsen()
        self.log("Kies een map en druk op 'Droge proef' of 'Normaliseren'.\n"
                 f"Map: {self._map}")

    # ---------------------------------------------------------------- opbouw
    def _bouw(self) -> None:
        centraal = QWidget()
        self.setCentralWidget(centraal)
        root = QVBoxLayout(centraal)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._kop())

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 12)
        body_layout.setSpacing(16)
        body_layout.addWidget(self._optieskaart())
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
        titel = QLabel("Luidheid normaliseren")
        titel.setObjectName("kop_titel")
        sub = QLabel("Even hard afspelen met ffmpeg loudnorm")
        sub.setObjectName("kop_sub")
        teksten.addWidget(titel)
        teksten.addWidget(sub)
        rij.addLayout(teksten)
        rij.addStretch(1)

        self.status_label = QLabel("Gereed")
        self.status_label.setObjectName("kop_sub")
        self.status_label.setMinimumWidth(200)
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

    def _maprij(self) -> QWidget:
        vak = QFrame()
        vak.setObjectName("rij")
        rij = QHBoxLayout(vak)
        rij.setContentsMargins(0, 0, 0, 0)
        rij.setSpacing(8)

        kol = QVBoxLayout()
        kol.setSpacing(4)
        naam = QLabel("Map")
        naam.setObjectName("kaart_titel")
        self.veld_map = QLineEdit(str(self._map))
        self.veld_map.setToolTip("De map met audiobestanden die genormaliseerd worden.")
        self.veld_map.setMinimumWidth(120)
        kol.addWidget(naam)
        kol.addWidget(self.veld_map)

        self.knop_map = QPushButton()
        self.knop_map.setIcon(maak_icoon("map", self.kleuren, 16))
        self.knop_map.setIconSize(QSize(16, 16))
        self.knop_map.setFixedWidth(42)
        self.knop_map.setToolTip("Kies de map")
        self.knop_map.clicked.connect(self._kies_map)

        rij.addLayout(kol, 1)
        rij.addWidget(self.knop_map, 0, Qt.AlignBottom)
        return vak

    def _veld(self, label: str, widget: QWidget, hulp: str) -> QVBoxLayout:
        kol = QVBoxLayout()
        kol.setSpacing(4)
        naam = QLabel(label)
        naam.setObjectName("kaart_titel")
        widget.setToolTip(hulp)
        kol.addWidget(naam)
        kol.addWidget(widget)
        return kol

    def _getalveld(self, waarde: float, laag: float, hoog: float, stap: float,
                   suffix: str) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(laag, hoog)
        spin.setDecimals(1)
        spin.setSingleStep(stap)
        spin.setSuffix(suffix)
        spin.setValue(waarde)
        return spin

    def _optieskaart(self) -> QWidget:
        kaart, layout = self._kaart("INSTELLINGEN")
        layout.addWidget(self._maprij())

        rij = QHBoxLayout()
        rij.setSpacing(12)
        self.spin_lufs = self._getalveld(
            -16.0, -40.0, -5.0, 0.5, " LUFS")
        self.spin_tp = self._getalveld(
            -1.5, -9.0, 0.0, 0.5, " dBTP")
        self.spin_lra = self._getalveld(
            11.0, 1.0, 30.0, 1.0, "")
        rij.addLayout(self._veld("Doelluidheid", self.spin_lufs,
                                 "Doelniveau in LUFS. Streaming gebruikt -14, "
                                 "ReplayGain -18."))
        rij.addLayout(self._veld("Max. true peak", self.spin_tp,
                                 "Boven deze dBTP mag het niet uitkomen."))
        rij.addLayout(self._veld("Loudness-range", self.spin_lra,
                                 "Doel voor de loudness-range (standaard 11)."))
        layout.addLayout(rij)

        keuzes = QHBoxLayout()
        keuzes.setSpacing(16)
        self.cb_recursief = QCheckBox("Ook onderliggende mappen")
        self.cb_mp3 = QCheckBox("Ook mp3's")
        self.cb_mp3.setToolTip("Her codeert en kost kwaliteit; voor mp3 is mp3gain "
                               "de betere keuze.")
        self.cb_backup = QCheckBox("Originelen bewaren (.bak)")
        keuzes.addWidget(self.cb_recursief)
        keuzes.addWidget(self.cb_mp3)
        keuzes.addWidget(self.cb_backup)
        keuzes.addStretch(1)
        layout.addLayout(keuzes)

        hint = QLabel("Droge proef laat zien wat er zou gebeuren; Normaliseren "
                      "wijzigt de bestanden echt.")
        hint.setObjectName("kop_sub")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return kaart

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
        kop_rij.addStretch(1)

        self.knop_knip = QPushButton("Kopieer")
        self.knop_knip.clicked.connect(self._kopieer_console)
        self.knop_knip.setToolTip("Kopieer de hele uitvoer naar het klembord")
        self.knop_wis = QPushButton("Wis")
        self.knop_wis.clicked.connect(self.console_leeg)
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

        self.knop_proef = QPushButton("Droge proef")
        self.knop_proef.setIcon(maak_icoon("console", self.kleuren, 16))
        self.knop_proef.setIconSize(QSize(16, 16))
        self.knop_proef.setCursor(Qt.PointingHandCursor)
        self.knop_proef.clicked.connect(lambda: self._start(proef=True))

        self.knop_start = QPushButton("  Normaliseren  ")
        self.knop_start.setObjectName("hoofd_knop")
        self.knop_start.setIcon(maak_icoon("start", self.kleuren, 16))
        self.knop_start.setIconSize(QSize(16, 16))
        self.knop_start.setCursor(Qt.PointingHandCursor)
        self.knop_start.clicked.connect(lambda: self._start(proef=False))

        self.knop_stop = QPushButton("Stoppen")
        self.knop_stop.setObjectName("stop_knop")
        self.knop_stop.setIcon(maak_icoon("stop", self.kleuren, 16))
        self.knop_stop.setIconSize(QSize(16, 16))
        self.knop_stop.setCursor(Qt.PointingHandCursor)
        self.knop_stop.setEnabled(False)
        self.knop_stop.clicked.connect(self._stop)

        rij.addWidget(self.knop_proef)
        rij.addWidget(self.knop_start)
        rij.addWidget(self.knop_stop)
        return voeten

    def _sneltoetsen(self) -> None:
        QShortcut(QKeySequence("Ctrl+Return"), self,
                  lambda: self._start(proef=False))
        QShortcut(QKeySequence("Ctrl+P"), self, lambda: self._start(proef=True))
        QShortcut(QKeySequence("Ctrl+."), self, self._stop)
        QShortcut(QKeySequence("Ctrl+K"), self, self.console_leeg)

    # ---------------------------------------------------------------- stijl
    def _pas_stijl_toe(self) -> None:
        self.setStyleSheet(stijlblad(self.kleuren))
        licht = self.thema_naam == "licht"
        self.knop_thema.setText("Donker thema" if licht else "Licht thema")
        self.setWindowIcon(maak_icoon("muziek", self.kleuren, 32))
        self.knop_map.setIcon(maak_icoon("map", self.kleuren, 16))
        self.knop_proef.setIcon(maak_icoon("console", self.kleuren, 16))
        self.knop_start.setIcon(maak_icoon("start", self.kleuren, 16))
        self.knop_stop.setIcon(maak_icoon("stop", self.kleuren, 16))
        self.console.zet_kleuren(self.kleuren)

    @Slot(bool)
    def _wissel_thema(self, licht: bool) -> None:
        self.thema_naam = "licht" if licht else "donker"
        self.kleuren = KLEUREN[self.thema_naam]
        self._pas_stijl_toe()

    # ------------------------------------------------------------- acties
    def log(self, regel: str) -> None:
        self.console.schrijf(regel)

    def console_leeg(self) -> None:
        self.console.leeg()

    def _kopieer_console(self) -> None:
        self.console.selectAll()
        self.console.copy()
        cursor = self.console.textCursor()
        cursor.clearSelection()
        self.console.setTextCursor(cursor)

    def _kies_map(self) -> None:
        keuze = QFileDialog.getExistingDirectory(
            self, "Kies de map met muziek", str(self._map))
        if keuze:
            self._map = Path(keuze)
            self.veld_map.setText(keuze)

    def _start(self, proef: bool) -> None:
        if self.thread is not None:
            return
        map_ = Path(self.veld_map.text().strip() or ".")
        if not map_.is_dir():
            QMessageBox.warning(self, APP_TITEL,
                                f"Deze map bestaat niet:\n{map_}")
            return
        self._map = map_
        opties = nm.Opties(
            lufs=self.spin_lufs.value(),
            tp=self.spin_tp.value(),
            lra=self.spin_lra.value(),
            ja=not proef,
            recursief=self.cb_recursief.isChecked(),
            ook_mp3=self.cb_mp3.isChecked(),
            backup=self.cb_backup.isChecked(),
        )
        self.thread = NormaliseerThread(map_, opties)
        self.thread.log.connect(self.log)
        self.thread.voortgang.connect(self._op_voortgang)
        self.thread.klaar.connect(self._op_klaar)
        self.thread.finished.connect(self._draad_klaar)
        self.balk.setRange(0, 100)
        self.balk.setValue(0)
        self.voortgang_label.setText("Droge proef…" if proef else "Normaliseren…")
        self.status_label.setText("Bezig…")
        self._zet_draaiend(True)
        self.thread.start()

    def _stop(self) -> None:
        if self.thread is not None:
            self.thread.requestInterruption()
            self.knop_stop.setEnabled(False)
            self.voortgang_label.setText("Stoppen…")

    @Slot(int, int)
    def _op_voortgang(self, klaar: int, totaal: int) -> None:
        if totaal:
            self.balk.setValue(int(klaar / totaal * 100))
            self.voortgang_label.setText(f"Bezig: {klaar}/{totaal}")

    @Slot(str, bool)
    def _op_klaar(self, bericht: str, ok: bool) -> None:
        self.voortgang_label.setText(bericht)
        self.status_label.setText("Gereed" if ok else bericht)

    @Slot()
    def _draad_klaar(self) -> None:
        self.thread = None
        self._zet_draaiend(False)

    def _zet_draaiend(self, bezig: bool) -> None:
        self.knop_proef.setEnabled(not bezig)
        self.knop_start.setEnabled(not bezig)
        self.knop_stop.setEnabled(bezig)
        for widget in (self.veld_map, self.knop_map, self.spin_lufs,
                       self.spin_tp, self.spin_lra, self.cb_recursief,
                       self.cb_mp3, self.cb_backup):
            widget.setEnabled(not bezig)


def start(thema: str | None = None, map_: Path | None = None) -> int:
    app = maak_app()
    if thema is None:
        thema = kern.laad_instellingen().get("thema", "donker")
    if thema not in KLEUREN:
        thema = "donker"
    venster = Venster(thema, map_)
    venster.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(start())
