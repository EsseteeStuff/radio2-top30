const puppeteer = require('puppeteer-core');

// Rotatie van User-Agents om blokkades te omzeilen
const USER_AGENTS = [
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
  'Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0'
];

// Bronnen in volgorde van voorkeur — bij 403 automatisch de volgende proberen
const SOURCES = [
  {
    name: 'hitnoteringen.be (www)',
    buildUrl: (jaar, week) =>
      `https://www.hitnoteringen.be/hitlijsten/vrt-radio-2-top-30/${jaar}-${week}`
  },
  {
    name: 'hitnoteringen.be (zonder www)',
    buildUrl: (jaar, week) =>
      `https://hitnoteringen.be/hitlijsten/vrt-radio-2-top-30/${jaar}-${week}`
  },
  {
    name: 'hitnoteringen.be (http)',
    buildUrl: (jaar, week) =>
      `http://www.hitnoteringen.be/hitlijsten/vrt-radio-2-top-30/${jaar}-${week}`
  }
];

function isForbiddenError(err) {
  const msg = (err.message || '').toLowerCase();
  return msg.includes('403') || msg.includes('forbidden') || msg.includes('access denied');
}

async function scrapeHits(beginJaar, eindJaar, onProgress) {
  const browser = await puppeteer.launch({
    executablePath: '/usr/bin/chromium',
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
  });

  const page = await browser.newPage();
  const allHits = [];
  const seen = new Set();
  let uaIndex = 0;

  // Stel User-Agent in
  await page.setUserAgent(USER_AGENTS[uaIndex]);

  // Extra headers om er meer "menselijk" uit te zien
  await page.setExtraHTTPHeaders({
    'Accept-Language': 'nl-NL,nl;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
  });

  for (let jaar = beginJaar; jaar <= eindJaar; jaar++) {
    const startWeek = (jaar === 1970) ? 18 : 1;
    const maxWeek = 53;

    for (let week = startWeek; week <= maxWeek; week++) {
      const weekStr = String(week).padStart(2, '0');
      onProgress(`Scrapen: ${jaar} week ${weekStr}...`);

      let entries = null;
      let lastError = null;

      // Doorloop bronnen tot iets zonder 403 werkt
      for (const source of SOURCES) {
        const url = source.buildUrl(jaar, weekStr);

        try {
          const response = await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });

          if (response && response.status() === 403) {
            onProgress(`  403 op ${source.name} — volgende bron proberen...`);
            lastError = new Error('403 Forbidden');
            continue;
          }

          if (response && response.status() >= 400) {
            onProgress(`  HTTP ${response.status()} op ${source.name} — volgende bron...`);
            lastError = new Error(`HTTP ${response.status()}`);
            continue;
          }

          // Succesvol — haal entries op
          entries = await page.evaluate(() => {
            const cards = document.querySelectorAll('.card-body.chartentry');
            const results = [];
            for (const card of cards) {
              const artiestEl = card.querySelector('.artiest.text-truncate');
              const titelEl = card.querySelector('.titel.text-truncate');
              if (artiestEl && titelEl) {
                const artiest = artiestEl.textContent.trim();
                const titel = titelEl.textContent.trim();
                if (artiest && titel) {
                  results.push({ artiest, titel });
                }
              }
            }
            return results;
          });

          if (entries.length > 0) break;
          // 0 entries kan ook betekenen: geen data voor deze week — proef volgende bron
        } catch (e) {
          if (isForbiddenError(e)) {
            onProgress(`  403 op ${source.name} — User-Agent wisselen en opnieuw...`);
            // Wissel User-Agent voor de volgende poging
            uaIndex = (uaIndex + 1) % USER_AGENTS.length;
            await page.setUserAgent(USER_AGENTS[uaIndex]);
            lastError = e;
          } else {
            onProgress(`  Fout op ${source.name}: ${e.message}`);
            lastError = e;
          }
        }

        // Kleine vertraging tussen bronnen
        await new Promise(r => setTimeout(r, 800));
      }

      if (entries === null) {
        onProgress(`  Alle bronnen faalden voor ${jaar}-${weekStr}${lastError ? ` (${lastError.message})` : ''}`);
        continue;
      }

      if (entries.length === 0) {
        onProgress(`  0 entries in alle bronnen voor ${jaar}-${weekStr}`);
        continue;
      }

      let newCount = 0;
      for (const entry of entries) {
        const key = `${entry.artiest.toLowerCase()}|${entry.titel.toLowerCase()}`;
        if (!seen.has(key)) {
          seen.add(key);
          allHits.push(`${entry.artiest} - ${entry.titel} - ${jaar}`);
          newCount++;
        }
      }

      onProgress(`  ${entries.length} entries gevonden, ${newCount} nieuw (totaal: ${allHits.length})`);

      // Kleine vertraging om de server te ontlasten
      await new Promise(r => setTimeout(r, 500));
    }
  }

  await browser.close();

  onProgress(`Scrapen voltooid — ${allHits.length} unieke hits verzameld.`);
  return allHits;
}

module.exports = { scrapeHits };
