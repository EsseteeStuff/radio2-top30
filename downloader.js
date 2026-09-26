const { execFile } = require('child_process');
const path = require('path');
const fs = require('fs');

function sanitizeFilename(name) {
  return name.replace(/[<>:"/\\|?*]/g, '_').substring(0, 200);
}

function getYtDlpPath() {
  const possiblePaths = [
    path.join(process.env.HOME || '/home/serge', '.local/bin/yt-dlp'),
    '/usr/local/bin/yt-dlp',
    '/usr/bin/yt-dlp'
  ];
  for (const p of possiblePaths) {
    if (fs.existsSync(p)) return p;
  }
  return 'yt-dlp';
}

function runYtDlp(args) {
  return new Promise((resolve, reject) => {
    execFile(getYtDlpPath(), args, { timeout: 300000 }, (error, stdout, stderr) => {
      if (error) reject(new Error(stderr || error.message));
      else resolve(stdout);
    });
  });
}

function downloadFromYouTube(hits, outputDir, onProgress) {
  return new Promise((resolve) => {
    const results = [];
    let index = 0;

    function processNext() {
      if (index >= hits.length) {
        resolve(results);
        return;
      }

      const hit = hits[index];
      index++;

      const parts = hit.split(' - ');
      const artiest = parts[0] || 'Onbekend';
      const titel = parts.slice(1, -1).join(' - ') || 'Onbekend';
      const jaar = parts[parts.length - 1] || '';
      const safeName = sanitizeFilename(`${artiest} - ${titel}`);
      const outputTemplate = path.join(outputDir, `${safeName}.%(ext)s`);

      onProgress(`Downloaden [${index}/${hits.length}]: ${artiest} - ${titel}`);

      // Zoekquery's in volgorde van voorkeur; bij 403 volgende proberen
      const queries = [
        `${artiest} ${titel} ${jaar}`,
        `${artiest} ${titel} official video`,
        `${artiest} ${titel} audio`,
        `${artiest} ${titel}`
      ];

      let queryIndex = 0;

      function tryNextQuery() {
        if (queryIndex >= queries.length) {
          onProgress(`  Alle zoekpogingen mislukt voor: ${artiest} - ${titel}`);
          results.push({ hit, success: false, error: 'Alle zoekpogingen mislukt' });
          processNext();
          return;
        }

        const query = queries[queryIndex];
        queryIndex++;

        const args = [
          '--no-playlist',
          '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
          '--merge-output-format', 'mp4',
          '-o', outputTemplate,
          '--no-warnings',
          '--no-progress',
          `ytsearch1:${query}`
        ];

        runYtDlp(args).then(() => {
          const files = fs.readdirSync(outputDir);
          const mp4File = files.find(f => f.startsWith(safeName) && f.endsWith('.mp4'));
          if (mp4File) {
            onProgress(`  OK: ${mp4File}`);
            results.push({
              hit,
              success: true,
              mp4Path: path.join(outputDir, mp4File),
              artiest,
              titel,
              jaar
            });
          } else {
            onProgress(`  Fout: mp4-bestand niet gevonden`);
            results.push({ hit, success: false, error: 'mp4 niet gevonden' });
          }
          processNext();
        }).catch((error) => {
          const msg = error.message || '';
          if (msg.includes('403') || msg.includes('Forbidden') || msg.includes('private') || msg.includes('sign in')) {
            onProgress(`  403/authenticatie-fout bij poging ${queryIndex}, probeer volgende...`);
            tryNextQuery();
          } else {
            onProgress(`  Fout: ${msg}`);
            results.push({ hit, success: false, error: msg });
            processNext();
          }
        });
      }

      tryNextQuery();
    }

    processNext();
  });
}

module.exports = { downloadFromYouTube };
