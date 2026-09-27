const { execFile } = require('child_process');
const https = require('https');
const http = require('http');
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

// Alternatieve bron: Cobalt API
function downloadFromCobalt(query, outputPath) {
  return new Promise((resolve, reject) => {
    const postData = JSON.stringify({
      url: `https://www.youtube.com/results?search_query=${encodeURIComponent(query)}`,
      downloadMode: 'audio',
      audioFormat: 'mp3'
    });

    const options = {
      hostname: 'api.cobalt.tools',
      port: 443,
      path: '/',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Content-Length': Buffer.byteLength(postData)
      },
      timeout: 30000
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          if (json.url) {
            downloadFile(json.url, outputPath).then(resolve).catch(reject);
          } else {
            reject(new Error(json.error || 'Cobalt API-fout'));
          }
        } catch (e) {
          reject(new Error('Cobalt API: ongeldig antwoord'));
        }
      });
    });

    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('Cobalt API time-out')); });
    req.write(postData);
    req.end();
  });
}

// Alternatieve bron: Invidious
function downloadFromInvidious(query, outputPath) {
  return new Promise((resolve, reject) => {
    const instances = [
      'https://vid.puffyan.us',
      'https://invidious.fdn.fr',
      'https://yewtu.be'
    ];

    const tryInstance = (index) => {
      if (index >= instances.length) {
        reject(new Error('Geen Invidious-instanties beschikbaar'));
        return;
      }

      const inst = instances[index];
      const searchUrl = `${inst}/api/v1/search?q=${encodeURIComponent(query)}&type=video`;

      https.get(searchUrl, { timeout: 15000 }, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
          try {
            const results = JSON.parse(data);
            if (results && results.length > 0) {
              const videoId = results[0].videoId;
              const streamUrl = `${inst}/latest_version?id=${videoId}&itag=18`;

              downloadFile(streamUrl, outputPath).then(resolve).catch(() => {
                tryInstance(index + 1);
              });
            } else {
              tryInstance(index + 1);
            }
          } catch (e) {
            tryInstance(index + 1);
          }
        });
      }).on('error', () => tryInstance(index + 1));
    };

    tryInstance(0);
  });
}

function downloadFile(url, outputPath) {
  return new Promise((resolve, reject) => {
    const proto = url.startsWith('https') ? https : http;
    const file = fs.createWriteStream(outputPath);

    proto.get(url, { timeout: 60000 }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        downloadFile(res.headers.location, outputPath).then(resolve).catch(reject);
        return;
      }
      if (res.statusCode !== 200) {
        file.close();
        reject(new Error(`HTTP ${res.statusCode}`));
        return;
      }
      res.pipe(file);
      file.on('finish', () => { file.close(); resolve(); });
      file.on('error', reject);
    }).on('error', reject);
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

      const queries = [
        `${artiest} ${titel} ${jaar}`,
        `${artiest} ${titel} official video`,
        `${artiest} ${titel} audio`,
        `${artiest} ${titel}`
      ];

      let queryIndex = 0;

      function tryNextQuery() {
        if (queryIndex >= queries.length) {
          onProgress(`  yt-dlp gefaald, probeer alternatieve bronnen...`);
          tryAlternativeSources();
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
          if (msg.includes('403') || msg.includes('Forbidden') || msg.includes('private') || msg.includes('sign in') || msg.includes('Sign in')) {
            onProgress(`  ${msg.includes('Sign in') ? 'Bot-blokkade' : '403'}-fout, probeer volgende...`);
            tryNextQuery();
          } else {
            onProgress(`  Fout: ${msg}`);
            results.push({ hit, success: false, error: msg });
            processNext();
          }
        });
      }

      function tryAlternativeSources() {
        const mp4Path = path.join(outputDir, `${safeName}.mp4`);
        const query = `${artiest} ${titel} ${jaar}`.trim();

        downloadFromCobalt(query, mp4Path).then(() => {
          onProgress(`  OK (via Cobalt): ${safeName}.mp4`);
          results.push({
            hit,
            success: true,
            mp4Path,
            artiest,
            titel,
            jaar
          });
          processNext();
        }).catch(() => {
          downloadFromInvidious(query, mp4Path).then(() => {
            onProgress(`  OK (via Invidious): ${safeName}.mp4`);
            results.push({
              hit,
              success: true,
              mp4Path,
              artiest,
              titel,
              jaar
            });
            processNext();
          }).catch((err) => {
            onProgress(`  Alle bronnen gefaald voor: ${artiest} - ${titel}`);
            results.push({ hit, success: false, error: err.message });
            processNext();
          });
        });
      }

      tryNextQuery();
    }

    processNext();
  });
}

module.exports = { downloadFromYouTube };
