# Radio 2 Top 30 Hits

Programma om muziek te scrapen van hitnoteringen.be, te downloaden van YouTube, te converteren naar mp3 en te verplaatsen naar een muziekmap.

## Vereisten

### Linux

| Software | Installatie |
|----------|-------------|
| Node.js 18+ | Via package manager of nvm |
| npm | Meegeleverd met Node.js |
| Python 3.8+ | `sudo apt install python3` (Debian/Ubuntu) |
| pip | `sudo apt install python3-pip` |
| ffmpeg | `sudo apt install ffmpeg` |
| Chromium | `sudo apt install chromium-browser` |
| yt-dlp | `pip3 install --user yt-dlp` |

### Windows

| Software | Installatie |
|----------|-------------|
| Node.js 18+ | Download van nodejs.org |
| Python 3.8+ | Download van python.org |
| ffmpeg | Download van gyan.dev of via Chocolatey: `choco install ffmpeg` |
| Chromium | Meegeleverd met Chrome, of download van chromium.org |
| yt-dlp | `pip install yt-dlp` |

### macOS

| Software | Installatie |
|----------|-------------|
| Node.js 18+ | `brew install node` of download van nodejs.org |
| Python 3.8+ | `brew install python@3.11` |
| ffmpeg | `brew install ffmpeg` |
| Chromium | `brew install --cask chromium` |
| yt-dlp | `brew install yt-dlp` of `pip3 install yt-dlp` |

## Installatie

1. Clone of download dit project

2. Installeer Node.js-afhankelijkheden:

```bash
cd radio2-top30
npm install
```

3. Controleer of yt-dlp werkt:

```bash
yt-dlp --version
```

## Gebruik

Start het programma:

```bash
npm start
```

### Stappen

1. **WORKDIR** kiezen — map waar tijdelijke bestanden komen (mp4, mp3, hits-file)
2. **Muziekfolder** kiezen — map waar uiteindelijjke mp3-bestanden terechtkomen
3. **Beginjaar** invullen (min. 1970)
4. **Eindjaar** invullen
5. Op **Start** klikken

### Wat gebeurt er?

1. **Scrapen** — hits worden verzameld van hitnoteringen.be (week 18 bij 1970, week 1 bij andere jaren)
2. **Opslaan** — unieke hits worden geschreven naar `hits_BEGINJAAR_EINDJAAR.txt` in de WORKDIR
3. **Downloaden** — elke song wordt gezocht en gedownload van YouTube als mp4
4. **Converteren** — mp4 wordt omgezet naar mp3 met ID3-tags (Artist, Title, Album, Year, Comment)
5. **Opruimen** — mp4-bestanden worden verwijderd
6. **Verplaatsen** — mp3-bestanden worden verplaatst naar de Muziekfolder

### Herstarten

Als `hits_BEGINJAAR_EINDJAAR.txt` bestaat, wordt het scrapen overgeslagen. Het programma gaat direct door naar downloaden.

## Foutafhandeling

| Fout | Oorzake | Oplossing |
|------|---------|-----------|
| 403/Forbidden | Video is privé of geblokkeerd | Programma probeert automatisch andere zoekopdrachten |
| mp4 niet gevonden | Download mislukt | Controleer internetverbinding |
| Geen hits gevonden | Verkeerd jaar of week | Controleer jaartallen |
| ffmpeg niet gevonden | ffmpeg niet geïnstalleerd | Zie hierboven |

## Structuur

```
radio2-top30/
├── main.js          # Electron hoofdproces
├── index.html       # Gebruikersinterface
├── style.css        # Stijlen
├── scraper.js       # Hitnoteringen scraper
├── downloader.js    # YouTube downloader
├── converter.js     # MP3 converter
├── preload.js       # IPC brug
└── package.json     # Node.js configuratie
```

## Opmerkingen

- Werkt alleen met Node.js 18 of nieuwer
- Vereist internetverbinding voor scrapen en downloaden
- YouTube-downloads kunnen sommige videos weigeren (privé, leeftijd, regio)
- Het programma probeert automatisch alternatieve zoekopdrachten bij 403-errors
