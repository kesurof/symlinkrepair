import puppeteer from '/usr/lib/node_modules/pageres-cli/node_modules/puppeteer-core/lib/esm/puppeteer/puppeteer-core.js';

const BASE = 'http://localhost:8005';
const OUTPUT = '/home/kesurof/projets/symlinkrepair/docs/screenshots';

const pages = [
  { path: '/?dark=1', name: 'dashboard', blur: blurDashboard },
  { path: '/scan?dark=1', name: 'scan', blur: blurScan },
  { path: '/results?dark=1', name: 'results', blur: blurResults },
  { path: '/reports?dark=1', name: 'reports', blur: null },
  { path: '/config?dark=1', name: 'config', blur: blurConfig },
];

function blurConfig(page) {
  return page.addStyleTag({
    content: `
      input[x-model="cfg.radarr.url"],
      input[x-model="cfg.radarr.api_key"],
      input[x-model="cfg.sonarr.url"],
      input[x-model="cfg.sonarr.api_key"],
      input[x-model="cfg.discord.webhook"],
      section span.font-mono.text-xs,
      div[x-show="wizardStep === 3"] span.font-mono,
      div[x-show="wizardStep === 4"] span.font-medium {
        filter: blur(6px) !important;
        -webkit-filter: blur(6px) !important;
      }
      input[x-model="cfg.radarr.container"]::placeholder,
      input[x-model="cfg.sonarr.container"]::placeholder {
        color: transparent !important;
      }
    `
  });
}

function blurResults(page) {
  return page.addStyleTag({
    content: `
      span.font-mono,
      div[data-ep-id] span.font-mono,
      button[data-path] {
        filter: blur(5px) !important;
        -webkit-filter: blur(5px) !important;
      }
    `
  });
}

function blurDashboard(page) {
  return page.addStyleTag({
    content: `
      span.text-sm.font-medium.truncate,
      span.text-xs.font-mono.text-gray-500 {
        filter: blur(4px) !important;
        -webkit-filter: blur(4px) !important;
      }
    `
  });
}

function blurScan(page) {
  return page.addStyleTag({
    content: `
      td.font-mono {
        filter: blur(5px) !important;
        -webkit-filter: blur(5px) !important;
      }
    `
  });
}

async function waitForStable(page) {
  await page.waitForNetworkIdle({ idleTime: 1500, timeout: 15000 }).catch(() => {});
  await page.evaluate(() => new Promise(resolve => {
    if (document.readyState === 'complete') {
      setTimeout(resolve, 500);
    } else {
      window.addEventListener('load', () => setTimeout(resolve, 500));
    }
  }));
}

const browser = await puppeteer.launch({
  executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || '/usr/bin/chromium-browser',
  headless: true,
  args: ['--no-sandbox', '--disable-setuid-sandbox'],
});

try {
  for (const pageDef of pages) {
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 800 });

    console.log(`  → ${pageDef.name}...`);
    await page.goto(BASE + pageDef.path, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await waitForStable(page);

    if (pageDef.blur) {
      await pageDef.blur(page);
      await new Promise(r => setTimeout(r, 200));
    }

    const filePath = `${OUTPUT}/${pageDef.name}.png`;
    await page.screenshot({ path: filePath, fullPage: true });
    await page.close();

    const fs = await import('fs');
    const size = fs.statSync(filePath).size;
    console.log(`    ✔ ${(size / 1024).toFixed(0)} Ko`);
  }
} finally {
  await browser.close();
}

console.log('✅ Captures terminées');
