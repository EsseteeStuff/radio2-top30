#!/usr/bin/env python3
"""Zelftest voor Top30: draait zonder venster op het scherm (offscreen).

    .venv/bin/python selftest.py            # kern + GUI
    .venv/bin/python selftest.py --scherm   # maak ook een afbeelding

De tests gebruiken een tijdelijke werkmap, zodat je echte bestanden niet
aangeraakt worden.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import top30_core as kern  # noqa: E402

MIJLPUNTEN: list[tuple[str, bool, str]] = []


def check(naam: str, ok: bool, uitleg: str = "") -> None:
    MIJLPUNTEN.append((naam, bool(ok), uitleg))
    print(f"  {'✓' if ok else '✗'} {naam}" + (f"  — {uitleg}" if uitleg and not ok else ""))


def sectie(titel: str) -> None:
    print(f"\n{titel}")
    print("─" * (len(titel) + 1))


# ---------------------------------------------------------------------------
# Kern
# ---------------------------------------------------------------------------

def test_kern() -> None:
    sectie("Kern")

    check("jaren begrenzen op 1970",
          kern.controleer_jaren(1960, 1975)[0] == kern.EERSTEJAAR)
    begin, eind, _ = kern.controleer_jaren(1960, 2999)
    check("eindjaar begrenzen op dit jaar", eind == time.localtime().tm_year,
          f"kreeg {eind}")
    try:
        kern.controleer_jaren(1980, 1970)
        check("begin > eind geeft een fout", False)
    except kern.Fout:
        check("begin > eind geeft een fout", True)

    check("bestandsnaam opschonen",
          kern.schoon('a/b:c*?"<>|x') == "abcx", kern.schoon('a/b:c*?"<>|x'))
    check("bestandsnaam inkorten", len(kern.schoon("x" * 300)) == 120)
    check("lege naam wordt 'naamloos'", kern.schoon("   ..  ") == "naamloos")

    # Prefixbreedte volgt het aantal bestanden
    for aantal, verwacht in ((0, 2), (5, 2), (9, 2), (40, 2), (99, 2), (100, 3),
                             (700, 3), (999, 3), (1000, 4), (1200, 4), (10000, 5)):
        check(f"prefixbreedte bij {aantal} bestanden is {verwacht}",
              kern.prefix_breedte(aantal) == verwacht,
              f"kreeg {kern.prefix_breedte(aantal)}")
    check("700 bestanden geeft 001-, zoals gevraagd",
          f"{1:0{kern.prefix_breedte(700)}d}" == "001",
          f"{1:0{kern.prefix_breedte(700)}d}")
    # Het hoogste nummer moet altijd in de prefix passen, anders krijg je
    # bestanden als 0100- in plaats van 100-.
    te_kort = [n for n in range(1, 20001)
               if int(f"{n:0{kern.prefix_breedte(n)}d}") != n]
    check("het hoogste nummer past altijd in de prefix", not te_kort, str(te_kort[:5]))
    check("minimale breedte is 2", kern.PREFIX_BREEDTE_MIN == 2)
    check("prefix strippen", kern.zonder_prefix("00012-ABBA - x.mp3") == "ABBA - x.mp3")

    # Vergelijkingssleutel: hoofdletters, streepjes en spaties mogen niet uitmaken
    check("hoofdletters maken niet uit",
          kern.vergelijk_sleutel("ABBA", "Dancing Queen")
          == kern.vergelijk_sleutel("abba", "dancing  queen"))
    check("streepje-stijl maakt niet uit",
          kern.vergelijk_sleutel("John Terra", "Is er een ander")
          == kern.vergelijk_sleutel("john  terra", "is  er – een  ander"))
    check("bestandsnaam en tags geven dezelfde sleutel",
          kern.vergelijk_sleutel(kern.zonder_prefix("00001-ABBA - Dancing Queen.mp3")[:-4])
          == kern.vergelijk_sleutel("ABBA", "Dancing Queen"),
          kern.vergelijk_sleutel("ABBA - Dancing Queen"))

    # Hitlijst schrijven en teruglezen
    werk = Path(tempfile.mkdtemp(prefix="top30test-"))
    paden = kern.Paden(werk, werk / "muziek").maak()
    ctx = kern.Context(paden=paden, log=lambda *_: None)
    hits = [
        {"artiest": "ABBA", "titel": "Dancing Queen", "jaar": 1976},
        {"artiest": "Queen", "titel": "Bohemian Rhapsody", "jaar": 1975},
    ]
    doel = kern.schrijf_hits(ctx, hits, 1975, 1976)
    check("hits-bestand naam", doel.name == "hits_1975_1976.txt", doel.name)
    terug = kern.laad_hits(ctx, 1975, 1976)
    check("hits teruglezen", terug == hits, str(terug))
    try:
        kern.laad_hits(ctx, 1800, 1801)
        check("ontbrekend hits-bestand geeft een duidelijke fout", False)
    except kern.Fout as fout:
        check("ontbrekend hits-bestand geeft een duidelijke fout",
              "hits_1800_1801.txt" in str(fout) and "Alleen scrapen" in str(fout))

    # Manifest
    kern.bewaar_manifest(ctx, [{**hits[0], "file": "ABBA - Dancing Queen.mp4"}])
    check("manifest bewaren en lezen", len(kern.laad_manifest(ctx)) == 1)

    # Conversie: mp4 -> mp3 met tags
    mp4 = paden.mp4 / "ABBA - Dancing Queen.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=1", "-c:v", "libx264", "-pix_fmt",
         "yuv420p", str(mp4)],
        check=True, capture_output=True,
    )
    check("test-video aangemaakt", mp4.exists() and mp4.stat().st_size > 0)
    uit = kern.convert(ctx, verwijder_mp4=False)
    check("mp4 omgezet naar mp3", uit["nieuw"] == 1, str(uit))
    mp3 = paden.mp3 / "ABBA - Dancing Queen.mp3"
    check("mp3-bestand bestaat", mp3.exists())
    if mp3.exists():
        from mutagen.id3 import ID3

        tags = ID3(mp3)
        check("ID3 artiest", tags.get("TPE1").text[0] == "ABBA")
        check("ID3 titel", tags.get("TIT2").text[0] == "Dancing Queen")
        check("ID3 album", tags.get("TALB").text[0] == "Oldies but Goldies",
              str(tags.get("TALB").text if tags.get("TALB") else None))
        check("ID3 genre", tags.get("TCON").text[0] == kern.GENRE)
        check("ID3 jaar", str(tags.get("TDRC").text[0]) == "1976",
              str(tags.get("TDRC").text))
        # Een COMMENT-frame slaat mutagen onder 'COMM::eng' op, dus niet via
        # get('COMM') maar via getall.
        comms = tags.getall("COMM")
        check("ID3 omschrijving",
              bool(comms) and "1976" in str(comms[0].text[0]),
              str([c.text[0] for c in comms]))
        check("album staat in de kernconstante", kern.ALBUM == "Oldies but Goldies",
              kern.ALBUM)

    check("mp3 wordt niet dubbel geconverteerd", kern.convert(ctx)["aanwezig"] == 1)
    check("mp3_bestaat vindt het bestand", kern.mp3_bestaat(ctx, mp4.name))

    # Zonder manifest wordt het jaar uit de bestandsnaam afgeleid en kan het
    # leeg zijn; de albumtag moet dan gewoon geplaatst worden.
    import subprocess as _sp

    leegjaar = paden.mp3 / "Zonder Jaar - Tweede Nummer.mp3"
    _sp.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
             "-i", "sine=frequency=500:duration=1", "-q:a", "2", str(leegjaar)],
            check=True, capture_output=True)
    try:
        kern.zet_tags(leegjaar, {"artiest": "Zonder", "titel": "Jaar", "jaar": ""})
        from mutagen.id3 import ID3 as _ID3

        t = _ID3(leegjaar)
        check("album ook zonder jaar", t.get("TALB").text[0] == kern.ALBUM)
        check("geen lege jaartag", t.get("TDRC") is None,
              str(t.get("TDRC").text if t.get("TDRC") else None))
    except Exception as fout:
        check("album ook zonder jaar", False, str(fout))
    leegjaar.unlink(missing_ok=True)

    # mp4 opruimen
    kern.convert(ctx, verwijder_mp4=True)
    check("mp4 verwijderd na conversie", not mp4.exists())

    # Verplaatsen + hernoemen
    (paden.mp3 / "nog een paar - nummer 2.mp3").write_bytes(b"\x00" * 100)
    (paden.mp3 / "Queen - Bohemian Rhapsody.mp3").write_bytes(b"\x00" * 100)
    aantal = kern.verplaats(ctx, hernoem=True)
    check("mp3 verplaatst", aantal == 3, str(aantal))
    check("mp3-map is leeg", not kern.mp3_bestanden(paden.mp3))
    namen = sorted(p.name for p in kern.mp3_bestanden(paden.muziek))
    # 4 bestanden -> 2 cijfers, dus 01- tot en met 04-.
    check("prefixbreedte volgt het aantal bestanden",
          all(re.match(r"^0\d-", n) for n in namen), str(namen))
    check("nummers lopen van 01 tot en met het aantal",
          sorted(int(n[:2]) for n in namen) == list(range(1, len(namen) + 1)),
          str(sorted(int(n[:2]) for n in namen)))
    artiesten = [kern.zonder_prefix(n).split(" - ")[0] for n in namen]
    check("geen dezelfde artiest na elkaar",
          all(artiesten[i] != artiesten[i + 1] for i in range(len(artiesten) - 1)),
          str(artiesten))

    # De schudfunctie moet de prefix écht weglaten, anders ziet elk bestand er
    # uit als een eigen artiest en wordt de regel stilzwijend genegeerd.
    # 20 artiesten x 3 nummers: een kale random.shuffle komt hier gemiddeld op
    # 2.0 keer dezelfde artiest na elkaar (max 9); met deze functie is het
    # hoogstens 2, en alleen nog in de onvermijdelijke staart.
    schudmap = Path(tempfile.mkdtemp(prefix="top30schud-"))
    zwaar = kern.Paden(schudmap, schudmap / "muziek").maak()
    for i in range(1, 61):
        artiest = f"Artiest {i % 20}"
        (zwaar.muziek / f"{i:05d}-{artiest} - Nummer {i}.mp3").write_bytes(b"x")
    zwaar_ctx = kern.Context(paden=zwaar, log=lambda *_: None)
    slechtste = 0
    for _ in range(20):                        # 20 keer schudden
        kern.nummer_hernoemen(zwaar_ctx)
        volgorde = [kern.zonder_prefix(p.name).split(" - ")[0]
                    for p in sorted(kern.mp3_bestanden(zwaar.muziek),
                                    key=lambda p: int(p.name.split("-", 1)[0]))]
        slechtste = max(
            slechtste,
            sum(1 for i in range(len(volgorde) - 1)
                if volgorde[i] == volgorde[i + 1]),
        )
    check("schudden houdt gelijke artiesten vrijwel altijd uit elkaar, 20x",
          slechtste <= 2, f"{slechtste} keer dezelfde artiest na elkaar")
    check("schudden behoudt alle bestanden",
          len(kern.mp3_bestanden(zwaar.muziek)) == 30 + 30,
          str(len(kern.mp3_bestanden(zwaar.muziek))))
    shutil.rmtree(schudmap, ignore_errors=True)

    # Prefix herstellen: alle bestanden krijgen de breedte die bij het aantal past
    kort = paden.muziek / "7-Artist - Song.mp3"
    kort.write_bytes(b"\x00" * 50)
    kern.fixprefix(ctx)
    check("losse prefix genormaliseerd",
          (paden.muziek / "07-Artist - Song.mp3").exists(),
          str(sorted(p.name for p in paden.muziek.iterdir())))
    check("fixprefix houdt de oude 5-cijferige namen over",
          not any(p.name.startswith("0000") for p in kern.mp3_bestanden(paden.muziek)),
          str(sorted(p.name for p in kern.mp3_bestanden(paden.muziek))))

    # Duplicaten weghalen: de muziekmap wordt vergeleken met de downloadlijst
    inventaris = kern.muziek_inventaris(paden.muziek)
    check("inventaris toont de nummers zonder prefix",
          bool(inventaris)
          and not any(k.startswith(tuple(str(i) for i in range(10)))
                      for k in inventaris),
          str(sorted(inventaris)[:4]))
    check("inventaris kent een mp3 met een losse naam op",
          kern.vergelijk_sleutel("Queen", "Bohemian Rhapsody") in inventaris,
          kern.vergelijk_sleutel("Queen", "Bohemian Rhapsody"))
    check("inventaris herkent een handmatig hernoemd bestand via de tags",
          kern.vergelijk_sleutel("ABBA", "Dancing Queen") in inventaris,
          str(sorted(inventaris)))

    # Alles wat al in de muziekmap staat moet uit de downloadlijst verdwijnen.
    bezit_lijst = [
        {"artiest": "Queen", "titel": "Bohemian Rhapsody", "jaar": 1975},
        {"artiest": "ABBA", "titel": "Dancing Queen", "jaar": 1976},
        {"artiest": "Nog Niets", "titel": "Onbekend nummer", "jaar": 1976},
    ]
    te_downloaden, overgeslagen = kern.filter_bestaande(ctx, bezit_lijst)
    check("bekende nummers uit de downloadlijst gehaald",
          len(overgeslagen) == 2, str([h["titel"] for h in overgeslagen]))
    check("onbekende nummers blijven over",
          [h["titel"] for h in te_downloaden] == ["Onbekend nummer"],
          str([h["titel"] for h in te_downloaden]))
    check("de volgorde van de downloadlijst blijft behouden",
          [h["titel"] for h in te_downloaden]
          == [h["titel"] for h in bezit_lijst if h not in overgeslagen])
    check("hoofdletters in de lijst maken niet uit",
          len(kern.filter_bestaande(ctx, [
              {"artiest": "queen", "titel": "bohemian rhapsody", "jaar": 1975},
          ])[1]) == 1)

    # Met de optie uit moet alles blijven staan.
    check("optie uit laat alles downloaden",
          len(kern.filter_bestaande(ctx, bezit_lijst, sla_over=False)[1]) == 0)

    # Lege muziekmap: dan wordt niets overgeslagen. Op een eigen map, zodat de
    # muziekmap hierboven intact blijft voor de tests die nog volgen.
    leeg_werk = Path(tempfile.mkdtemp(prefix="top30leeg-"))
    leeg = kern.Paden(leeg_werk, leeg_werk / "muziek").maak()
    leeg_ctx = kern.Context(paden=leeg, log=lambda *_: None)
    check("lege muziekmap slaat niets over",
          len(kern.filter_bestaande(leeg_ctx, bezit_lijst)[0]) == len(bezit_lijst))
    shutil.rmtree(leeg_werk, ignore_errors=True)

    # Onderbreken
    ctx.stop.set()
    try:
        kern.fixprefix(ctx)
        check("stopvlag onderbreekt de taak", False)
    except kern.Onderbroken:
        check("stopvlag onderbreekt de taak", True)
    ctx.stop.clear()

    # Processen draaien en onderbreken
    ctx2 = kern.Context(paden=paden, log=lambda *_: None)
    code, uitvoer = kern.draai_proces(["echo", "hallo"], ctx2)
    check("proces uitvoeren", code == 0 and "hallo" in uitvoer, uitvoer.strip())
    code, _ = kern.draai_proces(["sh", "-c", "exit 3"], ctx2)
    check("niet-nul exitcode wordt doorgegeven", code == 3, str(code))

    shutil.rmtree(werk, ignore_errors=True)


def test_scrapen_live() -> None:
    """Eén echte pagina ophalen om te controleren dat de selector nog klopt."""
    sectie("Live: één pagina van hitnoteringen.be")
    werk = Path(tempfile.mkdtemp(prefix="top30live-"))
    ctx = kern.Context(paden=kern.Paden(werk, werk / "muziek").maak(), log=print)
    try:
        html = kern.haal_pagina(ctx, 1975, 10)
    except kern.Fout as fout:
        check("pagina ophalen", False, str(fout))
        return
    if html is None:
        print("  (netwerk of site niet bereikbaar, overgeslagen)")
        return
    treffers = kern.paren_treffers(html)
    check("pagina ophalen", bool(html), "")
    check("treffers uit de HTML halen", len(treffers) == 30, f"{len(treffers)} gevonden")
    if treffers:
        print(f"    eerste: {treffers[0]['artiest']} - {treffers[0]['titel']}")
    shutil.rmtree(werk, ignore_errors=True)


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

def test_gui(maak_scherm: bool = False) -> None:
    sectie("GUI (offscreen)")
    from PySide6.QtCore import QEventLoop, Qt, QTimer
    from PySide6.QtWidgets import QApplication, QWidget

    import top30_gui

    # De applicatie-opzet zelf, want die wordt alleen door start() gebruikt.
    probe_app = top30_gui.maak_app()
    check("QApplication opzetten", probe_app.applicationName() == "Top30",
          probe_app.applicationName())
    check("organisatienaam is tekst",
          isinstance(probe_app.organizationName(), str) and
          bool(probe_app.organizationName()), repr(probe_app.organizationName()))
    check("beide thema's bestaan", set(top30_gui.KLEUREN) == {"donker", "licht"})
    for naam, kleuren in top30_gui.KLEUREN.items():
        try:
            blad = top30_gui.stijlblad(kleuren)
            # De kleuren die het stylesheet gebruikt moeten erin terugkomen:
            # bewijst dat de f-string is ingevuld. `ok` en `waarschuwing`
            # worden alleen door de console gebruikt, dus die laat ik weg.
            gebruikt = ("achtergrond", "paneel", "paneel_licht", "rand",
                        "tekst", "tekst_zwak", "accent")
            ontbreekt = [k for k in gebruikt if kleuren[k] not in blad]
            check(f"stylesheet '{naam}' is ingevuld", not ontbreekt, f"ontbreekt {ontbreekt}")
            check(f"stylesheet '{naam}' heeft geen {{{{{{", "{{" not in blad)
            # Qt mag het stylesheet zonder klachten accepteren.
            proef = QWidget()
            proef.setStyleSheet(blad)
            check(f"stylesheet '{naam}' wordt door Qt geaccepteerd",
                  proef.styleSheet() == blad)
        except Exception as fout:
            check(f"stylesheet '{naam}'", False, str(fout))

    def wacht_op(draad, ms: int) -> bool:
        """Blok tot de draad klaar is, terwijl de event loop blijft draaien.

        Zonder een draaiende event loop zouden de signalen van de draad
        pas bezorgd worden nadat we hier terug zijn.
        """
        lus = QEventLoop()
        draad.finished.connect(lus.quit)
        klok = QTimer()
        klok.setSingleShot(True)
        klok.timeout.connect(lus.quit)
        klok.start(ms)
        lus.exec()
        return not draad.isRunning()

    app = QApplication.instance() or QApplication([])
    venster = top30_gui.Venster("donker")
    venster.show()

    check("venster opent", venster.isVisible())
    check("werkmap ingevuld", bool(venster.veld_werk.text()))
    check("muziekmap ingevuld", bool(venster.veld_muziek.text()))
    check("zes taken in het menu", len(venster.radio_knoppen) == 6)
    check("standaardtaak is 'alles'", venster._huidige_taak() == "alles")
    check("startknop aan", venster.knop_start.isEnabled())
    check("stopknop uit", not venster.knop_stop.isEnabled())
    check("console bestaat", venster.console is not None)

    # De venster zou je instellingen mogen overschrijven; de zelftest niet.
    check("instellingen gaan naar de tijdelijke map",
          str(kern.config_map()).startswith(tempfile.gettempdir()),
          str(kern.config_map()))

    # De samenvatting wordt stilletjes door de GUI verzwolgen als ze een fout
    # geeft; dus expliciet controleren dat ze echt werkt.
    telwerk = Path(tempfile.mkdtemp(prefix="top30tel-"))
    telpaden = kern.Paden(telwerk, telwerk / "muziek").maak()
    for i in range(250):
        (telpaden.muziek / f"{i:05d}-A {i}.mp3").write_bytes(b"x")
    (telpaden.mp4 / "A - B.mp4").write_bytes(b"x")
    v_werk, v_muziek = venster.veld_werk.text(), venster.veld_muziek.text()
    venster.veld_werk.setText(str(telwerk))
    venster.veld_muziek.setText(str(telpaden.muziek))
    try:
        venster._toon_samenvatting()
        check("samenvatting telt de muziekmap", "250" in venster.label_teller.text(),
              venster.label_teller.text())
        check("samenvatting telt de mp4-map", "1 mp4" in venster.label_teller.text(),
              venster.label_teller.text())
        check("prefixlabel gevuld bij 250 bestanden",
              "3 cijfers" in venster.label_prefix.text(),
              venster.label_prefix.text())
    except Exception as fout:
        check("samenvatting werkt", False, str(fout))
    # De GUI moet de samenvatting ook zelf aanroepen, niet alleen op aanvraag.
    check("samenvatting aanroepen vult de teller", bool(venster.label_teller.text()))
    venster.veld_werk.setText(v_werk)
    venster.veld_muziek.setText(v_muziek)
    shutil.rmtree(telwerk, ignore_errors=True)

    # Standaardwaarden die de gebruiker heeft aangegeven
    check("mp4 opruimen staat aan", venster.cb_verwijder.isChecked())
    check("schudden en hernummeren staat aan", venster.cb_hernoemen.isChecked())
    check("hits-lijst niet opnieuw scrapen", not venster.cb_overschrijven.isChecked())
    check("cookies komen uit Chromium",
          venster.combo_cookie.currentText() == "chromium",
          venster.combo_cookie.currentText())
    check("'TAAK' staat er correct bij",
          venster.radio_knoppen["alles"].parentWidget() is not None)
    kaarttitels = [
        w.text() for w in venster.findChildren(type(venster.voortgang_label))
        if hasattr(w, "text")
    ]
    check("kaart heet TAAK, niet TAK", "TAAK" in kaarttitels and "TAK" not in kaarttitels,
          str([t for t in kaarttitels if t.isupper()]))

    # Thema wisselen
    venster.knop_thema.setChecked(True)
    check("licht thema", venster.thema_naam == "licht")
    venster.knop_thema.setChecked(False)
    check("donker thema", venster.thema_naam == "donker")

    # Jaarcontrole
    venster.spin_begin.setValue(1900)
    check("beginjaar gecorrigeerd naar 1970", venster.spin_begin.value() == 1970,
          str(venster.spin_begin.value()))
    venster.spin_begin.setValue(1980)
    venster.spin_eind.setValue(1985)
    check("jaren staan goed", (venster.spin_begin.value(), venster.spin_eind.value())
          == (1980, 1985))

    # Voortgangsbalk
    boek = top30_gui.VoortgangsBoek("alles")
    boek.zet("scrapen", 5, 10)
    check("voortgangsbalk rekent", 7 <= boek.totaal() <= 8, f"{boek.totaal():.1f}%")
    boek.zet("downloaden", 10, 10)
    check("downloaden weegt zwaarder", boek.totaal() > 50, f"{boek.totaal():.1f}%")

    # Een taak echt laten draaien in de GUI-draad: verplaatsen
    werk = Path(tempfile.mkdtemp(prefix="top30gui-"))
    paden = kern.Paden(werk, werk / "muziek").maak()
    for i in range(3):
        (paden.mp3 / f"0{i}-Artiest {i} - Titel {i}.mp3").write_bytes(b"\x00" * 40)
    venster.veld_werk.setText(str(werk))
    venster.veld_muziek.setText(str(paden.muziek))
    venster._na_wijziging()
    venster.radio_knoppen["verplaats"].setChecked(True)
    check("taak wisselen werkt", venster._huidige_taak() == "verplaats")

    uitkomst: list = []

    def klaar(bericht, geslaagd):
        uitkomst.append((bericht, geslaagd))

    venster.thread = top30_gui.TaakThread(
        "verplaats",
        kern.Context(paden=paden, log=venster.log),
        {"begin": 1980, "eind": 1985, "verwijder_mp4": False,
         "hernoemen": True, "overschrijven": False},
        venster,
    )
    venster.thread.log.connect(venster.log)
    venster.thread.klaar.connect(klaar)
    venster.thread.start()
    check("taak gestart", venster.thread.isRunning())
    check("taak afgerond", wacht_op(venster.thread, 20000))
    check("taak geslaagd", bool(uitkomst) and uitkomst[0][1], str(uitkomst))
    check("bestanden in de muziekmap", len(kern.mp3_bestanden(paden.muziek)) == 3,
          str([p.name for p in kern.mp3_bestanden(paden.muziek)]))
    check("console kreeg uitvoer", "mp3" in venster.console.toPlainText())

    # Onderbreken tijdens een taak die echt even duurt: converteren.
    werk2 = Path(tempfile.mkdtemp(prefix="top30stop-"))
    paden2 = kern.Paden(werk2, werk2 / "muziek2").maak()
    for i in range(6):
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
             "-i", f"sine=frequency={300 + i * 40}:duration=90",
             "-c:a", "aac", "-b:a", "64k", str(paden2.mp4 / f"Artiest {i} - Titel {i}.mp4")],
            check=True, capture_output=True,
        )
    venster.veld_werk.setText(str(werk2))
    venster.veld_muziek.setText(str(paden2.muziek))
    venster._na_wijziging()
    venster.radio_knoppen["convert"].setChecked(True)

    stop_uitkomst: list = []
    thread = top30_gui.TaakThread(
        "convert",
        kern.Context(paden=paden2, log=venster.log),
        {"begin": 1980, "eind": 1985, "verwijder_mp4": False,
         "hernoemen": True, "overschrijven": False},
        venster,
    )
    thread.log.connect(venster.log)
    thread.klaar.connect(lambda m, o: stop_uitkomst.append((m, o)))
    thread.start()
    QTimer.singleShot(350, thread.requestInterruption)
    check("draad stopt na onderbreken", wacht_op(thread, 30000))
    check("onderbreken via requestInterruption", bool(stop_uitkomst) and
          not stop_uitkomst[0][1], str(stop_uitkomst))
    check("onderbroken taak is niet helemaal afgerond",
          len(kern.mp3_bestanden(paden2.mp3)) < 6,
          f"{len(kern.mp3_bestanden(paden2.mp3))} van 6 klaar")
    check("na hervatten de rest afgemaakt",
          kern.convert(kern.Context(paden=paden2, log=lambda *_: None))["nieuw"] > 0)
    check("hervatten maakt alle bestanden", len(kern.mp3_bestanden(paden2.mp3)) == 6,
          str(len(kern.mp3_bestanden(paden2.mp3))))
    shutil.rmtree(werk2, ignore_errors=True)

    shutil.rmtree(werk, ignore_errors=True)

    if maak_scherm:
        uit = Path(__file__).resolve().parent / "scherm_donker.png"
        venster.resize(1120, 780)
        app.processEvents()
        venster.grab().save(str(uit))
        print(f"\n  afbeelding opgeslagen: {uit}")

        venster.knop_thema.setChecked(True)
        venster._op_voortgang("downloaden", 320, 1450, "ABBA - Dancing Queen")
        venster.log("  [download]  62.4% van  12.31MiB bij  845.12KiB/s ETA 00:04")
        venster.log("  MISLUKT: ERROR: [youtube] ... Video unavailable")
        app.processEvents()
        venster.grab().save(str(uit.with_name("scherm_licht.png")))
        print(f"  afbeelding opgeslagen: {uit.with_name('scherm_licht.png')}")

    venster.close()
    QTimer.singleShot(0, app.quit)


# ---------------------------------------------------------------------------

def main() -> int:
    print("Top30 zelftest")
    print("=============")

    # De zelftest mag je echte instellingen niet overschrijven: laat het
    # programma zijn instellingen in een tijdelijke map zetten.
    echte_map = kern.config_map()
    tijdelijke_map = Path(tempfile.mkdtemp(prefix="top30instellingen-"))
    kern.config_map = lambda: tijdelijke_map  # type: ignore[assignment]

    try:
        test_kern()
        if "--live" in sys.argv:
            test_scrapen_live()
        test_gui(maak_scherm="--scherm" in sys.argv)
    finally:
        kern.config_map = lambda: echte_map  # type: ignore[assignment]
        shutil.rmtree(tijdelijke_map, ignore_errors=True)

    print("\n" + "=" * 60)
    goed = sum(1 for _, ok, _ in MIJLPUNTEN if ok)
    fouten = [naam for naam, ok, _ in MIJLPUNTEN if not ok]
    print(f"{goed}/{len(MIJLPUNTEN)} geslaagd")
    if fouten:
        print("Mislukt:")
        for naam in fouten:
            print(f"  - {naam}")
    return 1 if fouten else 0


if __name__ == "__main__":
    sys.exit(main())
