// Renderiza anim.html cuadro por cuadro con Chromium (Playwright) y lo codifica con ffmpeg.
//   node render.cjs video <ffmpeg> <fps> <workers>   -> build/seg_<i>.mp4 + build/sfx.json
//   node render.cjs stills <t1> <t2> ...             -> build/stills/<t>.png
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = __dirname;
const BUILD = path.join(ROOT, 'build');
const URL = 'file://' + path.join(ROOT, 'anim.html') + '?render';

async function open(browser) {
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  page.on('console', m => { if (m.type() === 'warning' || m.type() === 'error') console.log('[página]', m.text()); });
  page.on('pageerror', e => { console.error('[página]', e); process.exit(1); });
  await page.goto(URL);
  await page.evaluate(() => window.READY);
  return page;
}

const frame = (page, t, type, q) => page.evaluate(([t, type, q]) => {
  window.render(t);
  return document.getElementById('c').toDataURL(type, q).split(',')[1];
}, [t, type, q]);

async function worker(browser, i, from, to, fps, ffmpeg) {
  const page = await open(browser);
  const out = path.join(BUILD, `seg_${i}.mp4`);
  const ff = spawn(ffmpeg, ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-r', String(fps), out], { stdio: ['pipe', 'inherit', 'inherit'] });
  for (let f = from; f < to; f++) {
    const b64 = await frame(page, f / fps, 'image/jpeg', 0.94);
    if (!ff.stdin.write(Buffer.from(b64, 'base64'))) await new Promise(r => ff.stdin.once('drain', r));
    if (i === 0 && (f - from) % 60 === 0) console.log(`  cuadro ${f - from}/${to - from} (worker 0)`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  await page.close();
  return out;
}

(async () => {
  const [mode, ...args] = process.argv.slice(2);
  const browser = await chromium.launch();
  if (mode === 'stills') {
    const page = await open(browser);
    fs.mkdirSync(path.join(BUILD, 'stills'), { recursive: true });
    for (const t of args) {
      const b64 = await frame(page, +t, 'image/png');
      fs.writeFileSync(path.join(BUILD, 'stills', `${(+t).toFixed(1).padStart(6, '0')}.png`), Buffer.from(b64, 'base64'));
    }
  } else {
    const [ffmpeg, fps, nw] = [args[0], +args[1], +args[2]];
    const page = await open(browser);
    const total = await page.evaluate(() => window.TL.total);
    fs.writeFileSync(path.join(BUILD, 'sfx.json'), JSON.stringify(await page.evaluate(() => window.sfxCues())));
    await page.close();
    const n = Math.ceil(total * fps), per = Math.ceil(n / nw);
    console.log(`${n} cuadros, ${nw} workers`);
    const segs = await Promise.all([...Array(nw).keys()].map(i => worker(browser, i, i * per, Math.min(n, (i + 1) * per), fps, ffmpeg)));
    fs.writeFileSync(path.join(BUILD, 'segs.txt'), segs.map(s => `file '${s}'\n`).join(''));
  }
  await browser.close();
})();
