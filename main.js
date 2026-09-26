const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { scrapeHits } = require('./scraper');
const { downloadFromYouTube } = require('./downloader');
const { convertToMp3 } = require('./converter');
const fs = require('fs');

let mainWindow;
let isRunning = false;
let shouldStop = false;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 900,
    height: 1100,
    title: 'Radio 2 Top 30 Hits',
    autoHideMenuBar: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  mainWindow.loadFile('index.html');
}

function log(message) {
  const timestamp = new Date().toLocaleTimeString('nl-NL');
  const line = `[${timestamp}] ${message}`;
  console.log(line);
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('log', line);
  }
}

async function runPipeline(config) {
  isRunning = true;
  shouldStop = false;

  const { workDir, muziekFolder } = config;
  const beginJaar = parseInt(config.beginJaar, 10);
  const eindJaar = parseInt(config.eindJaar, 10);

  try {
    // Valideer mappen
    if (!fs.existsSync(workDir)) {
      log(`Fout: WORKDIR bestaat niet: ${workDir}`);
      isRunning = false;
      return;
    }
    if (!fs.existsSync(muziekFolder)) {
      fs.mkdirSync(muziekFolder, { recursive: true });
      log(`Muziekfolder aangemaakt: ${muziekFolder}`);
    }

    // Maak mp4 en mp3 mappen aan
    const mp4Dir = path.join(workDir, 'mp4');
    const mp3Dir = path.join(workDir, 'mp3');
    fs.mkdirSync(mp4Dir, { recursive: true });
    fs.mkdirSync(mp3Dir, { recursive: true });

    const hitsFile = path.join(workDir, `hits_${beginJaar}_${eindJaar}.txt`);

    // Stap 1: Scrapen
    let hits = [];
    if (fs.existsSync(hitsFile)) {
      log(`Bestaande hits-file gevonden: ${hitsFile} — overslaan scrapen.`);
      const content = fs.readFileSync(hitsFile, 'utf-8');
      hits = content.split('\n').filter(l => l.trim());
      log(`${hits.length} hits uit bestaand bestand geladen.`);
    } else {
      log(`Start scrapen van ${beginJaar} t/m ${eindJaar}...`);
      hits = await scrapeHits(beginJaar, eindJaar, (msg) => {
        if (shouldStop) throw new Error('Gestopt door gebruiker');
        log(msg);
      });

      if (shouldStop) { isRunning = false; return; }

      // Schrijf unieke hits naar file
      const uniqueHits = [...new Set(hits)];
      fs.writeFileSync(hitsFile, uniqueHits.join('\n') + '\n', 'utf-8');
      log(`${uniqueHits.length} unieke hits geschreven naar ${hitsFile}`);
    }

    if (shouldStop) { isRunning = false; return; }

    // Stap 2: Downloaden van YouTube
    log(`Start downloaden van ${hits.length} songs van YouTube...`);
    const downloadResults = await downloadFromYouTube(hits, mp4Dir, (msg) => {
      if (shouldStop) throw new Error('Gestopt door gebruiker');
      log(msg);
    });

    if (shouldStop) { isRunning = false; return; }

    const successfulDownloads = downloadResults.filter(r => r.success);
    log(`${successfulDownloads.length}/${hits.length} songs succesvol gedownload.`);

    if (successfulDownloads.length === 0) {
      log('Geen downloads gelukt — pipeline gestopt.');
      isRunning = false;
      return;
    }

    // Stap 3: Converteren naar mp3
    log(`Start converteren van ${successfulDownloads.length} bestanden naar mp3...`);
    const convertResults = await convertToMp3(successfulDownloads, mp3Dir, {
      beginJaar,
      onProgress: (msg) => {
        if (shouldStop) throw new Error('Gestopt door gebruiker');
        log(msg);
      }
    });

    if (shouldStop) { isRunning = false; return; }

    const successfulConversions = convertResults.filter(r => r.success);
    log(`${successfulConversions.length}/${successfulDownloads.length} bestanden geconverteerd.`);

    // Stap 4: Verwijder mp4-bestanden
    log('Verwijderen van mp4-bestanden...');
    for (const r of successfulConversions) {
      try {
        fs.unlinkSync(r.mp4Path);
      } catch (e) { /* al verwijderd */ }
    }
    log('Mp4-bestanden verwijderd.');

    // Stap 5: Verplaatsen naar muziekfolder
    log(`Verplaatsen van mp3-bestanden naar ${muziekFolder}...`);
    let movedCount = 0;
    for (const r of successfulConversions) {
      try {
        const destPath = path.join(muziekFolder, path.basename(r.mp3Path));
        let finalDest = destPath;
        if (fs.existsSync(destPath)) {
          const ext = path.extname(destPath);
          const base = path.basename(destPath, ext);
          finalDest = path.join(muziekFolder, `${base}_${Date.now()}${ext}`);
        }
        fs.renameSync(r.mp3Path, finalDest);
        movedCount++;
      } catch (e) {
        log(`Fout bij verplaatsen ${r.mp3Path}: ${e.message}`);
      }
    }

    log(`Klaar! ${movedCount} mp3-bestanden verplaatst naar ${muziekFolder}`);
  } catch (err) {
    if (err.message === 'Gestopt door gebruiker') {
      log('Pipeline gestopt door gebruiker.');
    } else {
      log(`Fout: ${err.message}`);
    }
  }

  isRunning = false;
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('finished');
  }
}

ipcMain.handle('select-workdir', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory']
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('select-muziekfolder', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory', 'createDirectory']
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('start', async (event, config) => {
  if (isRunning) return { error: 'Programma is al actief' };
  log(`Pipeline gestart — WORKDIR: ${config.workDir}, MUZIEK: ${config.muziekFolder}, Jaren: ${config.beginJaar}-${config.eindJaar}`);
  runPipeline(config);
  return { ok: true };
});

ipcMain.handle('stop', () => {
  shouldStop = true;
  log('Stopverzoek ontvangen...');
  return { ok: true };
});

ipcMain.handle('is-running', () => isRunning);

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  app.quit();
});
