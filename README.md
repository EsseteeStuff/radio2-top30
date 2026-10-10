# Top30 — handleiding

Een archief van de VRT Radio 2 Top 30. Het programma haalt de historische
hitlijsten op van hitnoteringen.be, zoekt elk nummer op YouTube, zet het om
naar mp3 met de juiste tags en legt het klaar in je muziekmap.

Deze handleiding bestaat uit twee delen:

* **[Installeren](#installeren)** — wat je op elke computer en elk
  besturingssysteem nodig hebt om het programma te kunnen starten.
* **[Gebruiken](#gebruiken)** — wat de vensteronderdelen doen en hoe je een
  run uitvoert, onderbreekt en hervat.

---

## Inhoud

* [Wat je nodig hebt](#wat-je-nodig-hebt)
* [Installeren](#installeren)
  * [1. Python](#1-python)
  * [2. ffmpeg](#2-ffmpeg)
  * [3. De projectmap](#3-de-projectmap)
  * [4. De pakketten](#4-de-pakketten)
  * [5. Controleren of het werkt](#5-controleren-of-het-werkt)
  * [6. Een JavaScript-runtime](#6-een-javascript-runtime)
  * [7. Extra op Linux](#7-extra-op-linux)
* [Alles bij elkaar per besturingssysteem](#alles-bij-elkaar-per-besturingssysteem)
* [Gebruiken](#gebruiken)
  * [Starten](#starten)
  * [Instellingen](#instellingen)
    * [De venstergrootte](#de-venstergrootte)
    * [Het thema](#het-thema)
  * [Taak](#taak)
  * [Opties](#opties)
  * [Console en voortgang](#console-en-voortgang)
  * [Starten en stoppen](#starten-en-stoppen)
  * [Een run stap voor stap](#een-run-stap-voor-stap)
  * [Onderbreken en hervatten](#onderbreken-en-hervatten)
  * [De nummering](#de-nummering)
  * [De mp3-tags](#de-mp3-tags)
  * [Sneltoetsen](#sneltoetsen)
  * [Thema](#thema)
* [Commandoregel](#commandoregel)
* [Bestanden en mappen](#bestanden-en-mappen)
* [Veelgestelde problemen](#veelgestelde-problemen)
* [Zelf testen](#zelf-testen)
* [Overzicht projectmap](#overzicht-projectmap)

---

## Wat je nodig hebt

| | Wat | Verplicht |
| --- | --- | --- |
| 1 | **Python 3.10 of nieuwer** | ja |
| 2 | **ffmpeg** op het systeem | ja |
| 3 | De pakketten uit `requirements.txt` (PySide6, yt-dlp, mutagen, requests, beautifulsoup4) | ja |
| 4 | Een internetverbinding | ja |
| 5 | Een **JavaScript-runtime** (Deno, of Node 22 of nieuwer) | ja, voor het downloaden |
| 6 | Een browser waar je op YouTube mee ingelogd bent | alleen als YouTube om een login vraagt |
| 7 | Een GUI-omgeving (X11, Wayland of Windows/macOS-desktop) | alleen voor het venster |

Alles behalve de laatste drie is eenmalig werk bij het installeren. Daarna
start het programma met één commando.

---

## Installeren

### 1. Python

Het programma vraagt **Python 3.10 of nieuwer**. Controleer wat je hebt:

```bash
python3 --version
```

* **Linux** — Debian en Ubuntu leveren `python3` mee, maar die is soms te oud.
  Doe dan:

  ```bash
  sudo apt install python3-venv python3-pip
  ```

* **macOS** — Apple levert een oude versie mee die je zelf niet mag gebruiken.
  Installeer de officiële build van [python.org](https://www.python.org/downloads/macos/).
  Kies bij de installatie "Add python3 to PATH".

* **Windows** — installeer vanaf
  [python.org/downloads/windows/](https://www.python.org/downloads/windows/).
  **Zet het vinkje `Add python.exe to PATH` aan** anders vindt de computer het
  programma niet.

Controleer de versie opnieuw; je moet `3.10` of hoger zien.

### 2. ffmpeg

ffmpeg zet de mp4 om naar mp3. Dit is een systeemprogramma en staat dus
**buiten** `requirements.txt`.

| Besturingssysteem | Commando |
| --- | --- |
| Debian, Ubuntu, Mint | `sudo apt install ffmpeg` |
| Fedora | `sudo dnf install ffmpeg` |
| Arch, Manjaro | `sudo pacman -S ffmpeg` |
| macOS | `brew install ffmpeg` |
| Windows | `winget install ffmpeg` of download via [gyan.dev/ffmpeg](https://www.gyan.dev/ffmpeg/builds/) |

Controleer:

```bash
ffmpeg -version
```

Krijg je "command not found", dan staat ffmpeg niet in je `PATH`. Zie
[Probleem 1](#probleem-1-ffmpeg-is-niet-gevonden).

### 3. De projectmap

Kopieer de map met het programma naar de plek waar je hem wilt hebben,
bijvoorbeeld `~/Programmen/top30`. Zorg dat Python er een *map* van maakt, niet
één bestand.

```bash
cd ~/Programmen/top30
```

Op Windows heet het pad bijvoorbeeld `C:\Users\jouwnaam\top30`.

### 4. De pakketten

Maak een **virtual environment** aan — een map waarin de Python-pakketten
blijven die je speciaal voor dit programma installeert. Zo raak je de
pakketten van de rest van je computer niet.

**Linux en macOS**

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Op Windows is het pad naar de interpreter `.venv\Scripts\python.exe` in plaats
van `.venv/bin/python`. Het programma houdt daar zelf rekening mee; je hoeft
die paden alleen te kennen voor de commando's in deze handleiding.

**macOS met Apple Silicon** — als de installatie misgaat met een fout over
`libomp` of een crash bij het openen van het venster, gebruik dan de Rosetta- of
Brew-versie van Python in plaats van de officiële build.

Je hoeft de virtual environment nooit handmatig te "activeren". Het programma
springt bij het opstarten vanzelf naar `.venv`. Je hebt dus nooit
`source .venv/bin/activate` nodig.

### 5. Controleren of het werkt

Voer de zelftest uit. Die doet niets met je muziek aan en controleert alle
onderdelen van het programma:

**Linux en macOS**

```bash
.venv/bin/python selftest.py
```

**Windows (PowerShell)**

```powershell
.\.venv\Scripts\python.exe selftest.py
```

Je zou aan het einde iets moeten zien als:

```
============================================================
95/95 geslaagd
```

Staan er punten tussen met een kruis, dan staat er achter elke regel waarom.
Zie [Veelgestelde problemen](#veelgestelde-problemen).

### 6. Een JavaScript-runtime

YouTube stuurt sinds 2025 een uitdaging (`n`-challenge) die opgelost moet
worden door JavaScript. yt-dlp kan die alleen oplossen als er een
JavaScript-runtime aanwezig is. Zonder runtime zie je dit in de console:

```
WARNING: [youtube] n challenge solving failed: Some formats may be missing.
ERROR:   [youtube] <id>: The page needs to be reloaded.
```

Het programma zoekt zelf een runtime en geeft 'm door met `--js-runtimes`.
Geen van beide gevonden? Dan mislukt het downloaden.

**Deno (aanbevolen)** — geen systeempakketten, geen sudo, en dit is de runtime
die yt-dlp standaard accepteert:

```bash
curl -fsSL https://deno.land/install.sh | sh
```

Dat zet `deno` in `~/.deno/bin`. Het install-script zet die map **niet** in je
PATH; het programma kijkt daar toch naar, dus je hoeft niets te configureren.
Voor de volledigheid kun je 'm zelf toevoegen aan `~/.bashrc`:

```bash
echo 'export PATH="$HOME/.deno/bin:$PATH"' >> ~/.bashrc
```

**Node.js** — werkt ook, maar let op de versie: yt-dlp eist **Node 22 of
nieuwer**. Oudere versies worden stil genegeerd en dan faalt de challenge
alsnog, met precies dezelfde foutmelding.

| Besturingssysteem | Commando |
| --- | --- |
| Debian / Ubuntu (oudere versies) | voeg eerst de [NodeSource](https://github.com/nodesource/distributions)-bron toe, dan `sudo apt install nodejs` |
| Debian / Ubuntu (Verse 13 en hoger) | `sudo apt install nodejs` — controleer daarna of het 22 of hoger is |
| Fedora | `sudo dnf install nodejs` |
| Arch | `sudo pacman -S nodejs` |
| macOS | `brew install node` |
| Windows | installeer vanaf [nodejs.org](https://nodejs.org/) |

Controleer wat het programma ervan vindt:

```bash
.venv/bin/python -c "import top30_core as k; print(k.beschikbare_js_runtimes())"
```

Krijg je `['--js-runtimes', 'deno:/pad/naar/deno']`, dan zit het goed. Krijg je
`[]`, dan is er geen bruikbare runtime gevonden. Is er wél een runtime maar is
die te oud, dan zegt het programma dat op stderr, bijvoorbeeld
`node 20.19.2 is te oud voor yt-dlp (minimaal 22.0.0)`.

### 7. Extra op Linux

Sommige Linux-systemen missen de systeembibliotheken die het venster nodig
heeft. Verschijnt bij het starten een fout over `libEGL`, `libxkbcommon` of
`libGL`, installeer dan:

```bash
sudo apt install libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0 \
                 libxcb-xinerama0 libxcb-icccm4 libxcb-image0 \
                 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 \
                 libxcb-shape0 libxcb-xkb1 libdbus-1-3
```

Op Fedora heet dat pakket `qt6-qtbase-gui` en op Arch `pyside6`.

### Alles bij elkaar per besturingssysteem

Kopieer-en-plakoverzicht. Voer de regels uit vanuit de projectmap.

**Debian / Ubuntu / Mint / Linux Mint**

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip ffmpeg

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

.venv/bin/python selftest.py
```

Starten met `./top30`. Krijg je `Permission denied`, doe dan eerst `chmod +x top30`.
Fout over `libEGL` of `libxkbcommon`? Zie [stap 6](#6-extra-op-linux).

**Fedora**

```bash
sudo dnf install python3 python3-pip ffmpeg qt6-qtbase-gui

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

.venv/bin/python selftest.py
```

**Arch / Manjaro**

```bash
sudo pacman -S python python-pip ffmpeg pyside6

python -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

.venv/bin/python selftest.py
```

**macOS**

Installeer eerst Python van
[python.org/downloads/macos/](https://www.python.org/downloads/macos/) en
zet "Add python3 to PATH" aan. Homebrew nodig voor ffmpeg:

```bash
brew install ffmpeg

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

.venv/bin/python selftest.py
```

Starten met `./top30`. Blijft het venster onvindbaar, dan staat het op een
scherm dat er niet meer is. macOS onthoudt die plek; zet hem terug met
`defaults delete org.python.python Top30` en start opnieuw, of sleep het venster
terug met ingedrukte Option-toets.

**Windows (PowerShell)**

Installeer eerst Python van
[python.org/downloads/windows/](https://www.python.org/downloads/windows/) met
het vinkje `Add python.exe to PATH` **aan**, en ffmpeg met
`winget install ffmpeg`.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

.\.venv\Scripts\python.exe selftest.py
```

Starten met `top30` of `.\.venv\Scripts\python.exe top30.py`. De map
`.venv\Scripts` moet niet met de hand in je `PATH`; het programma vindt zijn
eigen interpreter zelf. Sluit de terminal en open hem opnieuw na het
installeren van ffmpeg, zodat de nieuwe `PATH` wordt ingelezen.

**Alles wat het programma nodig heeft, in één lijst**

| | Linux | macOS | Windows |
| --- | --- | --- | --- |
| Python ≥ 3.10 | `python3`, `python3-venv` | van python.org | van python.org, met PATH |
| ffmpeg | `apt` / `dnf` / `pacman` | `brew` | `winget` |
| GUI-bibliotheken | `libegl1` e.a. (stap 6) | bij de installatie in | bij de installatie in |
| Python-pakketten | `pip install -r requirements.txt` | idem | idem |
| Voor het venster | X11 of Wayland | de desktop | idem |
| Voor de cookies | een ingelogde browser | idem | idem |

---

## Gebruiken

### Starten

Eén commando, vanuit de projectmap:

```bash
./top30
```

Werkt dat niet met *"Permission denied"*, geef het script dan één keer
uitvoerrecht:

```bash
chmod +x top30
```

Je kunt het programma ook meteen vanaf elke plek starten door het volledige pad
te typen, bijvoorbeeld `~/Programmen/top30/top30`.

**Alternatieven die hetzelfde doen:**

```bash
python3 top30.py     # via de systeem-Python; springt zelf naar .venv
./top30 --cli        # de commandoregel, zie verderop
```

**Op Windows** werkt `./top30` niet; gebruik daar:

```
top30
```

of

```
.venv\Scripts\python.exe top30.py
```

### Instellingen

De **linkerkant** van het venster heeft drie kaarten: INSTELLINGEN, TAAK en
OPTIES. Rechts staat de console. Alles wat je wijzigt wordt meteen onthouden,
ook na het afsluiten van het programma.

De kaart **INSTELLINGEN** heeft vier velden:

| Veld | Wat het doet |
| --- | --- |
| **Werkmap** | De plek waar de tussenbestanden komen: het hits-bestand en de submappen `mp3` en `mp4`. Kies bijvoorbeeld een snelle schijf, want daar komen alle video's terecht. |
| **Muziekmap** | Waar de afgewerkte mp3's uiteindelijk worden neergezet. |
| **Beginjaar** | Het eerste jaar dat je wilt ophalen. |
| **Eindjaar** | Het laatste jaar. |

Bij elk pad staat een knop **Bladeren** om het snel in te kiezen.

**Wat de programma zelf corrigeert:**

* De eerste hitlijst bestaat uit **week 18 van 1970**. Kies je 1965, dan wordt
  dat vanzelf 1970, met een melding in de console.
* Kies je een eindjaar in de toekomst, dan wordt dat het huidige jaar.
* Kies je een beginjaar na het eindjaar, dan krijg je een duidelijke foutmelding
  in plaats van een lege run.
* Een jaar heeft maximaal 53 weken; alle 53 worden nagekeken.

### Taak

De kaart **TAAK** bepaalt wat er gebeurt. Er is één samenvattende taak en vijf
losse stappen.

| Taak | Wat er gebeurt |
| --- | --- |
| **Alles doen** *(standaard)* | De vier stappen hieronder, in volgorde. |
| **Alleen scrapen** | De hitlijsten van hitnoteringen.be ophalen naar `hits_BEGINJAAR_ENDJAAR.txt`. |
| **Alleen downloaden** | De nummers uit het hits-bestand van de gekozen jaren op YouTube opzoeken en als mp4 opslaan. |
| **Alleen converteren** | Alle mp4's uit de mp4-map omzetten naar mp3. |
| **Alleen verplaatsen** | De mp3's uit de mp3-map naar je muziekmap zetten, met nummering. |
| **Prefixen herstellen** | Je muziekmap helemaal opnieuw nummeren: namen herstellen met de hitlijst, alle bestaande nummering eraf, dan schudden, dan `0001-` tot en met het aantal. |

**Waarom de losse stappen?** Ze zijn er voor als het programma onderbroken is
of als er iets misging. Kies dan dezelfde stappen opnieuw, alleen begin je bij
de stap waar het was gestopt. Het programma slaat zijn voortgang op en doet
alleen het werk dat nog ontbreekt — zie
[Onderbreken en hervatten](#onderbreken-en-hervatten).

De losse stappen werken ook los van elkaar:

* **Alleen downloaden** heeft het hits-bestand van de gekozen jaren nodig. Dat
  moet er al zijn; anders zegt het programma dat. Begin dan bij *Alleen scrapen*.
* **Alleen converteren** en **Alleen verplaatsen** werken op wat er op dat
  moment in de mappen ligt, en hebben geen jaartallen nodig.

### Opties

Vier schakelaars onder de taken.

| Optie | Standaard | Wat het doet |
| --- | --- | --- |
| **Alleen nummers downloaden die ik nog niet heb** | aan | Vergelijkt de lijst met je muziekmap en slaat over wat er al staat. Zie onderaan deze pagina. |
| **mp4's opruimen na converteren** | aan | De mp3 blijft, de video verdwijnt. Zet het uit als je de mp4's wilt bewaren of nog een keer wilt converteren. |
| **Schudden en hernummeren** | aan | Bij het verplaatsen krijgt elk bestand een willekeurige nieuwe volgorde met een numerieke prefix, zodat hetzelfde nummer nooit twee keer achter elkaar staat. Let op: dit doet **alle** bestanden in de muziekmap, niet alleen de net gedownloade. De breedte van de prefix volgt het totale aantal bestanden, dus bij 9072 bestanden wordt `00001-` ineens `0001-`. Zet het uit als je de muziekmap met andere programma's deelt. Zet het uit als je de bestanden in de volgorde van de hitlijst wilt houden. |
| **Hits-lijst opnieuw scrapen** | uit | Standaard wordt een bestaand hits-bestand hergebruikt, zodat je een onderbroken run kunt hervatten. Zet het aan als je denkt dat de lijst niet klopt. |
| **YouTube-cookies** | `chromium` | Uit welke browser yt-dlp de cookies mag lezen. Zie hieronder. |

#### Alleen nieuwe nummers downloaden

Het programma maakt vóór het downloaden een lijst van alles wat er al in je
muziekmap staat, zonder de nummering:

```
00012-Albert West - Put Your Head on My Shoulder.mp3
   └──────┬───────┘  └──────────────┬───────────────┘
    die nummering       wordt weggestreept
```

Daarna vergelijkt het die lijst met de lijst die je wilt downloaden, en haalt
de dubbele nummers eruit. In de console zie je hoeveel er overblijven:

```
250 van de 250 nummers staan al in /home/jouwnaam/Muziek/DeJaren70
en worden overgeslagen; 0 moeten nog gedownload worden.
  · al aanwezig: Freddy Breck - Uberall auf der Welt
  · al aanwezig: The Osmonds - Crazy Horses
  … nog 245 andere
```

Dat scheelt uren: een jaar dat je al hebt hoeft niet opnieuw van YouTube.

**Waarop wordt vergeleken.** De vergelijking let niet op hoofdletters,
spaties of de soort streepje. Dus `ABBA - Dancing Queen`, `abba  dancing
queen` en `ABBA – Dancing Queen` zijn allemaal hetzelfde nummer.

**Ook via de tags.** Naast de bestandsnaam kijkt het programma in de ID3-tags
van elk mp3. Heb je een bestand in een muziekspeler hernoemd van
`Thin Lizzy - Whiskey in the Jar` naar `Mijn favoriet nummer 1`, dan herkent
het die toch, zolang de tags nog kloppen.

**Let op.** Vergelijkt wordt de titel, niet het jaar of de week. Een nummer dat
in drie verschillende jaren in de lijst stond, wordt dus één keer bewaard en
daarna overgeslagen. Wil je dat juist niet, zet het vakje dan uit.

#### YouTube-cookies

YouTube vraagt soms om een login ("Sign in to confirm you're not a bot") voor
een video die normaal openstaat. Met cookies uit een browser waarin je
ingelogd bent, is dat meestal opgelost.

Kies hier de browser waarin je op YouTube ingelogd bent:

`geen` · `chrome` · `chromium` · `firefox` · `edge` · `brave` · `opera` · `vivaldi`

Let op:

* De browser hoeft niet open te staan, maar **sluit hem wel even** als het niet
  werkt — anders is het bestand met de cookies op slot.
* Je hoeft geen wachtwoord in te typen; yt-dlp leest de bestaande cookies.
* Kies `geen` als je liever geen cookies gebruikt. Het programma werkt dan
  prima, maar je kunt vaker tegen de loginprompt aanlopen.
* Sinds de Firefox-versies met een versleuteld profiel kan het zijn dat Firefox
  gesloten moet zijn.

Onder de opties staat een regeltje dat live meezegt welke prefixbreedte op dat
moment geldt, bijvoorbeeld *"Nummering: 3 cijfers (000-…), passend bij 250
bestanden in de muziekmap."*

### Console en voortgang

De **CONSOLE** laat zien wat het programma doet. Ze is niet leeg te maken
terwijl er gewerkt wordt; dat kan tussentijds zichtbaar werk overschrijven.

* **Fouten en waarschuwingen** staan in het rood of geel en worden nooit
  verborgen.
* Voortgang staat in het groen, één regel per gedownload nummer.
* De teller naast **CONSOLE** toont wat er op schijf staat: hoeveel hits, mp4's,
  mp3's en bestanden in de muziekmap.

De **voortgangsbalk** onderaan toont de fase (`Scrapen 12/30`, `Downloaden
145/1450`, …) en heeft per fase een eigen gewicht, omdat het downloaden het
meeste tijd duurt.

Naast de titel **CONSOLE** staan twee knoppen: **Kopieer** zet de hele uitvoer
op je klembord, **Wis** maakt het scherm leeg.

### Starten en stoppen

Onderaan staat links de voortgangsbalk en rechts **Start** en **Stoppen**.
Starten begint de gekozen taak, stoppen onderbreekt hem.

Stoppen werkt ook **tijdens het downloaden**: het lopende proces wordt
beëindigd en het halve bestand wordt opgeruimd, zodat er geen kapotte mp4's
achterblijven. De tweede keer starten gaat verder waar je was.

De knoppen reageren ook op:

| Sneltoets | Werkt als |
| --- | --- |
| `Ctrl+Enter` | Start |
| `Ctrl+.` | Stoppen |
| `Ctrl+L` | Focus in de console |
| `Ctrl+K` | Console leegmaken |

### Een run stap voor stap

Een typische eerste run:

1. **Start** het programma met `./top30`.
2. Zet de **werkmap** op een map met veel vrije ruimte (bv. `~/temp/Top30`).
3. Zet de **muziekmap** op de map waar je de mp3's wilt hebben.
4. Vul **beginjaar** en **eindjaar** in. Begin klein om te testen, bijvoorbeeld
   1971 tot 1971.
5. Laat **Taak** op *Alles doen* staan.
6. Controleer de opties; vooral **YouTube-cookies** als je die hebt.
7. Klik op **Start** en laat het lopen. Bij vijf jaar downloaden duurt dat
   uren; dat is normaal.
8. Kies je eerst maar één jaar om het uit te proberen, verander daarna het
   eindjaar en start opnieuw. De al gedownloade nummers worden herkend en
   overgeslagen.
9. Kijk in de console naar het slotbericht. Verschijnt daar geen fout, dan is
   het goed gegaan.

Wat je in de werkmap ziet ontstaan:

```
<werkmap>/
├── hits_1971_1971.txt    de hitlijst
├── hits_1971_1971.json   idem, met gestructureerde gegevens
├── mp4/                  de gedownloade video's + manifest.json
└── mp3/                  de mp3's, nog niet verplaatst
```

### Onderbreken en hervatten

Elke stap onthoudt waar hij was:

* **Scrapen** schrijft het hits-bestand meteen klaar.
* **Downloaden** vergelijkt de lijst eerst met je muziekmap en slaat over wat
  je al hebt (zie [Alleen nieuwe nummers
  downloaden](#alleen-nieuwe-nummers-downloaden)). Daarna noteert het elk
  gedownload bestand in `mp4/manifest.json`. Bij een herstart wordt de lijst
  opnieuw doorgenomen en alleen het ontbrekende gedownload.
* **Converteren** slaat de mp3 op in de mp3-map en slaat het mp4-bestand over
  als dat er nog staat.
* **Verplaatsen** verplaatst bestand per bestand en hernoemt in één keer aan
  het eind.

Dus: gewoon opnieuw dezelfde taak starten. Er wordt niets dubbel gedaan en
niets wordt overgeslagen.

**Mislukte nummers** — komt een video niet mee (weggehaald, of YouTube eist een
login), dan slaat het programma dat nummer over, gaat door met de volgende en
zet de reden in `mp4/download_fouten.log`. Aan het einde staat hoeveel er
klaar waren en hoeveel niet. Start je *Alleen downloaden* opnieuw, dan worden
alleen de nog ontbrekende nummers opnieuw geprobeerd; ook de mislukte. Dat is
de handigste manier om ze alsnog te krijgen: zet eerst *YouTube-cookies* goed.

Staat er één video blijvend dwars, laat het dan los — de rest gaat gewoon door.
Bij een volgende run over hetzelfde jaar komt dat nummer opnieuw aan de beurt.

Kijk na afloop of het aantal in de teller klopt met wat je verwachtte. Zo niet,
dan helpt de foutenlog bij het achterhalen waar het misging.

### De nummering

Bij het verplaatsen krijgt elk bestand een nummer als `001-John Terra - Is er
een ander (tussen jou en mij).mp3`.

De breedte van het nummer past zichzelf aan aan het aantal bestanden in je
muziekmap, met een minimum van twee cijfers:

| Aantal bestanden | Breedte | Voorbeeld |
| --- | --- | --- |
| 1 – 99 | 2 | `01-John Terra - …` |
| 100 – 999 | 3 | `001-John Terra - …` |
| 1000 – 9999 | 4 | `0001-John Terra - …` |
| 10000 en meer | 5 | `00001-John Terra - …` |

Het programma nummert de **hele muziekmap bij elke run opnieuw**, met een
willekeurige volgorde. Twee dingen daarvan:

* **Je nummers veranderen bij elke run.** Dat is de bedoeling — zo valt het niet
  op dat je een nummer uit 1972 tussen twee uit 1975 hoort.
* **Twee dezelfde artiesten komen nooit direct na elkaar te staan.** Dat is
  een extra prettigheid van de schud-optie.

Bij 250 bestanden in je map krijg je dus `001-` t/m `250-` in plaats van
`00001-` t/m `00250-`.

#### Prefixen herstellen

De taak *Prefixen herstellen* repareert je hele muziekmap, in deze volgorde:

1. **Tellen.** Het aantal bestanden bepaalt de breedte van de prefix. Bij 1365
   bestanden zijn dat vier cijfers, dus `0001-` tot en met `1365-`.
2. **Namen opruimen.** Voor elk bestand wordt de hitlijst in de werkmap
   geraadpleegd. Wat daarin staat krijgt de naam uit die lijst; zie
   [Namen herstellen](#namen-herstellen) hieronder.
3. **Alle bestaande prefixen eraf.** Ook dubbel gestapelde nummering als
   `001-0423 - Bonnie St. Claire - …` en losse varianten als `0423 - …` of `7-…`
   verdwijnen volledig. Een titel die toevallig met cijfers begint blijft heel:
   `10cc - Donna` en `3 Doors Down - Here Without You` veranderen niet.
4. **Schudden.** De volgorde wordt opnieuw bepaald, zodat dezelfde artiest niet
   twee keer achter elkaar komt te staan.
5. **Oplopend nummeren** van `0001-` tot en met het aantal.

Bestanden die helemaal geen nummer hadden krijgen er dus ook een, en bestanden
zonder extensie (`10cc - Donna`) worden meegeteld als het programma ze als mp3
herkent aan de ID3-tag. Je krijgt er vanaf nu in elk geval een `.mp3` achter. Het
is een hernoeming: er verdwijnt niets en er komt niets bij.

> Let op bij het overstappen: je huidige bestanden met `00001-` heten straks
> `001-`. Voor programma's die op de bestandsnaam sorteren is dat een andere
> volgorde, maar het nummer zelf verandert niet.

#### Namen herstellen

Veel bestanden heten naar de YouTube-video waar ze vandaan komen, in plaats van
naar het nummer zelf:

```
0012-Rod Stewart - Tonight's The Night (Official Video)-IZr6AE-u2UM - onbekende titel.mp3
```

Daar zit een video-id in, de aanduiding `(Official Video)`, en `onbekende titel`
in plaats van de echte titel. Het programma herstelt de naam door de nummers uit
de hitlijst te vergelijken met de bestandsnaam én met de ID3-tags. Wat er
daarbij gebeurt:

* **Een treffer in de hitlijst wint altijd.** De bestandsnaam wordt dan
  `0012-Rod Stewart - Tonight's the Night (Gonna Be Alright).mp3`. Het gaat
  hierbij om hoofdletters, liggende streepjes, gebogen leestekens (`You’re`) en
  accenten: die maken niet uit.
* **Een YouTube-id wordt nooit op gok afgehaald.** Een video-id is precies 11
  tekens, en daar zijn titels als `Bat-Te-Ring-Ram` en `D-I-V-O-R-C-E` in te
  herkennen. Het programma haalt zo'n stuk er alleen af als de hitlijst bevestigt
  dat het een id is.
* **Blijft de titel dubbelzinnig, dan blijft de naam staan.** `Bésame Mucho` staat
  in de hitlijst vier keer (van Apollo 100, Dalida, Dennie Christian en Trini
  Lopez). Zo'n bestand wordt niet gokt: het houdt zijn naam en krijgt alleen een
  nummer. De taak logt welke namen hersteld zijn, zodat je het kunt nalopen.

Is er geen hitlijst in de werkmap (of staat het nummer er niet in), dan blijft
de bestandsnaam zoals hij is. Ook dan verdwijnen de prefixen, komt er `.mp3`
achter en wordt alles opnieuw genummerd.

Tekens die in een bestandsnaam niet mogen worden gehaald de titel op de laatste
plaats. De hitlijst zegt bijvoorbeeld `Gary Glitter - Do You Wanna Touch Me?`,
maar een vraagteken mag niet in een bestandsnaam op Windows. Die haalt `schoon()`
eraf, net als een `/` of een punt op het einde: `Pinball Wizard / See Me, Feel Me`
wordt `Pinball Wizard See Me, Feel Me`.

> De ID3-tags zelf worden *niet* metgeschreven. Een tag als
> `Banapple Gas 1976 4K-KIoUO_3pXwY.mp3` blijft dus rommelig. Dat is geen probleem
> voor het programma: `muziek_inventaris()` leest zowel de bestandsnaam als de
> tags, dus zo'n nummer wordt niet opnieuw gedownload.

### De mp3-tags

Elke mp3 krijgt bij de conversie:

| Tag | Inhoud |
| --- | --- |
| Artiest | De artiest van de hitlijst |
| Titel | De titel van de hitlijst |
| Album | `Oldies but Goldies` |
| Genre | `Pop` |
| Jaar | Het jaar van de hitlijst |
| Omschrijving | `Oldies but goldies 1972` |

Het jaar en de omschrijving worden alleen gezet als er een jaartal bekend is.

### Sneltoetsen

| Sneltoets | Werkt als |
| --- | --- |
| `Ctrl+Enter` | Start |
| `Ctrl+.` | Stoppen |
| `Ctrl+L` | Focus in de console |
| `Ctrl+K` | Console leegmaken |

### Thema

Rechtsboven in de bovenste balk staat een knop om tussen het donkere en het
lichte thema te wisselen. De keuze blijft je.

---

## Commandoregel

Alles wat het venster kan, kan ook zonder venster. Handig in scripts, op een
server zonder scherm, of om een onderbroken run over te nemen.

```bash
python3 top30.py --cli <stap> [opties]
```

of via de launcher:

```bash
./top30 --cli <stap> [opties]
```

### Stappen

| Stap | Wat het doet |
| --- | --- |
| `alles` | Alle vier de stappen achter elkaar. |
| `scrape` | Alleen de hitlijsten ophalen. |
| `download` | Alleen downloaden, uit het hits-bestand van de opgegeven jaren. |
| `convert` | Alleen de mp4's omzetten. |
| `verplaats` | Alleen de mp3's naar je muziekmap zetten. |
| `fixprefix` | De muziekmap opnieuw nummeren: namen herstellen met de hitlijst, alle nummering eraf, schudden, `0001-` tot en met het aantal. |

### Opties

| Optie | Betekenis |
| --- | --- |
| `--beginjaar 1971` | Eerste jaar. |
| `--eindjaar 1975` | Laatste jaar. |
| `--startnummer 1` | Vanaf welk nummer de nummering begint. |
| `--verwijder-mp4` | Mp4's opruimen na de conversie. |
| `--nee-hernoemen` | Bij verplaatsen niet schudden en nummeren. |
| `--overschrijven` | Het hits-bestand opnieuw scrapen. |
| `--geen-skip` | Niets overslaan: ook de nummers downloaden die al in je muziekmap staan. |
| `--cookies firefox` | Browser voor de cookies. |

Zonder `--geen-skip` slaat de commandoregel net als het venster over wat er al
in de muziekmap staat.

### Voorbeelden

```bash
# Alles voor 1971 t/m 1975, met het opschonen van de mp4's
./top30 --cli alles --beginjaar 1971 --eindjaar 1975 --verwijder-mp4

# Alleen de download afmaken na een onderbreking
./top30 --cli download --beginjaar 1971 --eindjaar 1975

# Alles converteren en de mp4's bewaren
./top30 --cli convert

# Alleen verplaatsen, beginnend bij nummer 1
./top30 --cli verplaats --startnummer 1

# Alleen de nummers gelijk maken
./top30 --cli fixprefix

# Een heel jaar opnieuw ophalen, ook al heb je het al
./top30 --cli download --beginjaar 1971 --eindjaar 1971 --geen-skip
```

Laat je de jaren weg bij `scrape` of `alles`, dan vraagt het programma ze
interactief uit. `Ctrl+C` onderbreekt ook hier netjes; dezelfde stap herstarten
gaat verder.

---

## Bestanden en mappen

```
<werkmap>/
├── hits_BEGINJAAR_ENDJAAR.txt    de hitlijst als platte tekst
├── hits_BEGINJAAR_ENDJAAR.json   dezelfde lijst, gestructureerd
├── mp4/
│   ├── manifest.json             welke video bij welk nummer hoort
│   ├── download_fouten.log       waarom een video niet mee is gekomen
│   └── *.mp4                     de gedownloade video's
└── mp3/                          de mp3's, nog niet verplaatst
```

`manifest.json` is het geheugen van het programma: het weet daardoor na een
onderbreking wat er al klaar is, en het weet welke artiest en titel bij welk
bestand horen, zodat de mp3 de juiste tags krijgt. **Verwijder dit bestand
niet** tenzij je helemaal opnieuw wilt beginnen.

### Standaardmappen

Staat er nog geen instelling — bijvoorbeeld op een verse computer — dan
zoekt het programma zijn mappen op de plek die bij dat besturingssysteem en
die taal gebruikelijk is:

| Besturingssysteem | Werkmap | Muziekmap |
| --- | --- | --- |
| Linux | `~/.local/share/Top30` | `~/Muziek/Top30` — in een Nederlandse taal `Muziek`, anders `Music` |
| macOS | `~/Library/Application Support/Top30` | `~/Music/Top30` |
| Windows | `%LOCALAPPDATA%\Top30` | `…\Music\Top30` of `…\Muziek\Top30` |

Je kunt ze allebei verzetten; het programma onthoudt wat je hebt ingesteld.

Twee dingen zijn bewust zo gekozen. De werkmap staat **niet** in `temp`, want
een besturingssysteem mag die zomaar leegmaken en dan zijn je hitlijsten
kwijt. En de muziekmap is een **eigen map binnen** de muziekmap van het
systeem, nooit een verzameling die een ander programma beheert.

### Instellingen

Je instellingen staan in een map `Top30` in je gebruikersmap:

| Besturingssysteem | Pad |
| --- | --- |
| Linux | `~/.config/Top30/settings.json` |
| macOS | `~/Library/Preferences/Top30/settings.json` |
| Windows | een map `Top30` onder `%APPDATA%` of `%LOCALAPPDATA%` |

Wil je helemaal opnieuw beginnen met standaardwaarden, verwijder dat bestand
dan; het programma maakt het opnieuw aan.

#### De venstergrootte

Het venster onthoudt hoe groot je het hebt gemaakt. Je hoeft het niet elke
keer opnieuw op maat te slepen: de grootte wordt bewaard als je het venster
afsluit, en de volgende keer opent het op die grootte.

Dit werkt ook als je het venster gemaximeraliseerd hebt gehad. Dan onthoudt
het programma de grootte die je had vóór het maximaliseren, zodat je niet de
volgende keer ineens een gigantisch venster op je scherm hebt staan.

De allereerste keer dat je een nieuwe versie start, is de oude grootte nog
niet bekend: die wordt pas bewaard als je het venster die ene keer sluit.
Daarna gaat het vanzelf.

Wil je de venstergrootte eenmalig op een andere waarde zetten, dan kan dat
gewoon door de twee regels hieronder in `settings.json` te zetten of te
veranderen:

```json
 "venster_breedte": 1200,
 "venster_hoogte": 800
```

Getallen moeten het zijn, en mogen niet kleiner zijn dan 940 bij 660. Staat er
iets anders — een woord, `null`, of helemaal niets — dan negeert het programma
dat en pakt het de normale grootte, in plaats van te klagen.

#### Het thema

Of je het donkere of het lichte thema gebruikt, wordt ook onthouden.

### De muziekmap

Daar belanden de afgewerkte bestanden:

```
001-John Terra - Is er een ander (tussen jou en mij).mp3
002-Thin Lizzy - Whiskey in the Jar.mp3
003-Mort Shuman - Le Lac Majeur.mp3
```

**Gebruik hiervoor een eigen map.** Het programma gaat namelijk willekeurig
schudden en hernummeren zodra *Schudden en hernummeren* aan staat — en dat
doet het met álle mp3's die er al staan, niet alleen met de net gedownloade.
De breedte van de prefix volgt het totale aantal bestanden, dus bij 9072
bestanden wordt `00001-` ineens `0001-` en krijgt je hele map een andere
volgorde. Een map die je met een ander programma beheert, gaat daar dus
volledig onderdoor.

Staat er nog geen instelling, dan gebruikt het programma `~/Muziek/Top30`.
Dat is bewust een lege, eigen map en nooit een bestaande verzameling.

De mp4's worden standaard na de conversie verwijderd. Wil je ze bewaren, zet
*mp4's opruimen na converteren* uit — ze blijven dan in de mp4-map staan tot
je ze zelf wegraait.

---

## Veelgestelde problemen

### Probleem 1: ffmpeg is niet gevonden

**Symptoom:** bij het converteren staan alle regels op `ffmpeg-fout op …` of de
taak faalt met "ffmpeg niet gevonden".

**Oplossing:** installeer ffmpeg (stap 2) en controleer met `ffmpeg -version`.
Krijg je dat niet, dan staat het niet in je `PATH`. Zet het pad ernaar toe in je
shell, of verwijder `ffmpeg` en installeer het opnieuw. Op Windows: herstart de
terminal na het installeren, zodat de nieuwe `PATH` wordt ingelezen.

### Probleem 2: het venster opent niet

**Symptoom:** na `./top30` sluit het venster meteen, of je krijgt een fout over
een ontbrekende `libEGL.so.1`, `libxkbcommon` of `libGL`.

**Oplossing:** installeer de systeembibliotheken uit stap 6. Kijk daarna in de
console welke bibliotheek precies ontbreekt. Op macOS: controleer of het
venster niet buiten beeld staat op een scherm dat niet meer aanwezig is.

**Op een server zonder scherm** werkt het venster niet; gebruik de
commandoregel: `./top30 --cli …`.

### Probleem 3: YouTube vraagt steeds om in te logen

**Symptoom:** regels met *"Sign in to confirm you're not a bot"*, en dan slaat
het programma het nummer over.

Het programma reageert daar al zelf op: zodra het zo'n fout ziet, zoekt het
opnieuw naar een andere video van dezelfde artiest en titel. Dat lost het vaak
al op. Lukt het ook daarmee niet, doe dan dit, in deze volgorde:

1. Zet *YouTube-cookies* op de browser waarin je op YouTube bent ingelogd.
2. Sluit die browser volledig en probeer het opnieuw.
3. Werk yt-dlp bij — YouTube verandert vaak van techniek en dan werkt een
   oudere yt-dlp niet meer:
   ```bash
   .venv/bin/pip install --upgrade yt-dlp
   ```
4. Kies een ander jaar; sommige video's zijn nu eenmaal weggehaald en daar valt
   niets aan te doen.

### Probleem 4: "n challenge solving failed" of "The page needs to be reloaded"

**Symptoom:** herhaalde regels in de console als

```
WARNING: [youtube] n challenge solving failed: …
ERROR:   [youtube] <id>: The page needs to be reloaded.
```

**Oorzaak:** YouTube vraagt om een uitdaging op te lossen die JavaScript
nodig heeft, en er is geen JavaScript-runtime gevonden. Dit heeft niets te
maken met je internetverbinding of met inloggen.

**Oplossing:** installeer één runtime, zie
[Een JavaScript-runtime](#6-een-javascript-runtime). Het makkelijkst is Deno:

```bash
curl -fsSL https://deno.land/install.sh | sh
```

Daarna controleren of het programma 'm ziet:

```bash
.venv/bin/python -c "import top30_core as k; print(k.beschikbare_js_runtimes())"
```

`['--js-runtimes', 'deno:/…/deno']` betekent dat het goed is. Krijg je `[]`, dan
is er nog geen runtime gevonden. Gebruik je Node, houd dan rekening met de
versie: yt-dlp eist **22 of hoger** en negeert oudere versies zonder iets te
zeggen — met dezelfde foutmelding als resultaat.

Let op: deze fout is iets anders dan
[Probleem 3](#probleem-3-youtube-vraagt-steeds-om-in-te-loggen). Die gaat om
`Sign in to confirm you're not a bot` en heeft met cookies te maken.

### Probleem 5: het downloaden gaat langzaam

Dat is meestal gewoon YouTube die het tempo afremt. Wat helpt:

* Cookies aanzetten (zien probleem 3).
* Een kleiner jaarrange per keer, zodat het programma tussentijds kan pauzeren.
* De werkmap op een **snelle schijf**. Een trage schijf is vaak de bottleneck,
  veel meer dan de internetsnelheid.

### Probleem 6: "…ontbreekt in …" of "Geen mp3-bestanden gevonden"

**Symptoom 1:** *"hits_1971_1975.txt ontbreekt in /home/jouwnaam/temp/Top30.
Kies 'Alleen scrapen' om hem eerst te maken."*

Dat is geen fout maar een vraag om in de juiste volgorde te werken. Kies
*Alleen scrapen* met dezelfde jaren, en daarna *Alleen downloaden*. Let op dat
de bestandsnaam de precieze jaren bevat: met 1971–1975 en daarna 1971–1972
verandert de naam, en het programma zoekt de tweede dus niet.

**Symptoom 2:** *"Geen mp3-bestanden gevonden in …"*

Dat komt bij *Alleen verplaatsen* wanneer de muziekmap leeg zou blijven terwijl
er wel mp3's klaarstaan. Bij *Prefixen herstellen* zegt het programma alleen
dat er nog niets in je muziekmap ligt en stopt het zonder fout. Kijk in de teller
naast **CONSOLE** wat er wél staat, en kies de taak die daarop volgt.

**Symptoom 3:** *"Scrapen leverde geen nummers op."*

Meestal een netwerkprobleem of het is even offline. Probeer het later nog eens.

### Probleem 7: bestanden krijgen een dubbele naam

Twee nummers in de lijst kunnen dezelfde artiest én titel hebben. Het programma
zet dan een `(2)` achter de titel:

```
012-Abba - Dancing Queen.mp3
013-Abba - Dancing Queen (2).mp3
```

Dat is bedoeld; anders zou het tweede bestand het eerste overschrijven.

Een `(2)` die in de oude bestandsnaam stond kan na *Prefixen herstellen* verdwijnen
(`The Trammps - Where Do We Go From Here (2)` wordt
`The Trammps - Where Do We Go From Here`). Kwam dat `(2)` doordat de titels toen
nog verschilden, bijvoorbeeld door een YouTube-id, dan was het niet nodig. Kwam
het doordat je twee keer hetzelfde nummer hebt gedownload, dan zet het programma
het `(2)` alsnog terug.

### Probleem 8: een bestandsnaam blijft rommelig

Bij *Prefixen herstellen* krijgt een bestand alleen een nieuwe naam als de
hitlijst in je werkmap weet hoe het heet. Soms is dat er niet:

* **Het nummer staat niet in de hitlijst** (buiten het jaarbereik dat je gescraped
  hebt). Haal dan *Hits-lijst opnieuw scrapen* aan met een ruimer jaarbereik.
* **De titel staat er wel, maar ook van iemand anders.** `Bésame Mucho` bestaat in
  de hitlijst vier keer; het programma kiest dan liever niets dan het verkeerde
  en laat de naam staan.

De taak logt welke namen hersteld zijn, dus je kunt precies zien wat er is
gebeurd. Zie [Namen herstellen](#namen-herstellen).

### Probleem 9: ik wil helemaal opnieuw beginnen

Verwijder de inhoud van je werkmap (of verwijder en hernoem het
hits-bestand) en zet *Hits-lijst opnieuw scrapen* aan. Je muziekmap wordt
daarbij niet aangeraakt. Om ook alles opnieuw te beginnen, verwijder je de
mp3's uit je muziekmap apart.

### Probleem 10: de zelftest faalt

Voer hem opnieuw uit met de details:

```bash
.venv/bin/python selftest.py
```

Elke mislukte regel toont zelf de reden. De vaakste oorzaak is dat de virtual
environment niet (meer) klopt; herinstalleer dan met
`.venv/bin/pip install -r requirements.txt`. De zelftest werkt op tijkelijke
mappen en raakt je muziek nooit aan.

---

## Zelf testen

```bash
.venv/bin/python selftest.py             # kern + venster, 107 punten
.venv/bin/python selftest.py --live      # ook echt één pagina ophalen
.venv/bin/python selftest.py --scherm    # maakt scherm_donker.png / scherm_licht.png
```

De zelftest is volledig geautomatiseerd: hij maakt een tijdelijke werkmap,
maakt nepbestanden aan, voert elke stap uit en ruimt alles weer op. Hij
gebruikt een eigen instellingenbestand en raakt je muziek of je echte
instellingen niet aan.

De `--live`-test gebruikt het internet; die slaagt alleen als je netwerk en de
website meewerken.

---

## Overzicht projectmap

| Bestand | Wat het doet |
| --- | --- |
| `top30` | De launcher. Start het programma met de juiste Python, ook zonder de virtual environment te activeren. |
| `top30.py` | Het toegangspunt. Start het venster, of de commandoregel met `--cli`. |
| `top30_gui.py` | Het venster: instellingen, taken, opties, console, voortgang. |
| `top30_core.py` | De logica: scrapen, downloaden, converteren, verplaatsen, nummeren, tags. Bevat geen GUI-code. |
| `selftest.py` | De zelftest. |
| `requirements.txt` | De Python-pakketten. |
| `.venv/` | De virtual environment. Aangemaakt bij het installeren; kunt die map gewoon verwijderen en opnieuw aanmaken. |

De GUI en de commandoregel gebruiken dezelfde kern. Wat het ene kan, kan het
andere dus ook.
