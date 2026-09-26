const { execFile } = require('child_process');
const path = require('path');
const fs = require('fs');

function sanitizeFilename(name) {
  return name.replace(/[<>:"/\\|?*]/g, '_').substring(0, 200);
}

function convertToMp3(downloads, outputDir, options) {
  return new Promise((resolve) => {
    const results = [];
    let index = 0;

    function processNext() {
      if (index >= downloads.length) {
        resolve(results);
        return;
      }

      const dl = downloads[index];
      index++;

      const safeName = sanitizeFilename(`${dl.artiest} - ${dl.titel}`);
      const mp3Path = path.join(outputDir, `${safeName}.mp3`);
      const { beginJaar, onProgress } = options;

      onProgress(`Converteren [${index}/${downloads.length}]: ${dl.artiest} - ${dl.titel}`);

      // Converteer met ffmpeg en zet ID3v2-tags
      const args = [
        '-i', dl.mp4Path,
        '-vn',
        '-codec:a', 'libmp3lame',
        '-q:a', '2',
        '-metadata', `artist=${dl.artiest}`,
        '-metadata', `title=${dl.titel}`,
        '-metadata', 'album=Oldies but Goldies',
        '-metadata', `year=${beginJaar}`,
        '-metadata', 'comment=Mijn Muziek Collectie',
        '-metadata', 'genre=Pop',
        '-id3v2_version', '3',
        '-write_id3v1', '1',
        '-y',
        mp3Path
      ];

      execFile('ffmpeg', args, { timeout: 120000 }, (error, stdout, stderr) => {
        if (error) {
          onProgress(`  Fout: ${error.message}`);
          results.push({ ...dl, success: false, error: error.message });
        } else {
          onProgress(`  OK: ${path.basename(mp3Path)}`);
          results.push({ ...dl, success: true, mp3Path });
        }
        processNext();
      });
    }

    processNext();
  });
}

module.exports = { convertToMp3 };
