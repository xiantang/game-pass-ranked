// Downloads small PS Plus cover images into covers/ps/<productId>.jpg.
//
// Share images are exported by drawing the frame onto a canvas, which the browser
// only allows for images served with CORS headers. Xbox's image CDN sends them;
// image.api.playstation.com does not, so PS covers are served from this site
// instead. Only missing covers are fetched, and covers for games that left the
// catalog are deleted.
import { mkdir, readdir, readFile, unlink, writeFile } from 'node:fs/promises';

const DIR = new URL('../covers/ps/', import.meta.url);
// 300px wide is plenty for a share frame card and keeps each file around 30KB.
const WIDTH = 300;
const CONCURRENCY = 6;

const catalog = JSON.parse(await readFile(new URL('../data/psplus.json', import.meta.url), 'utf8'));
await mkdir(DIR, { recursive: true });
const have = new Set(await readdir(DIR));
const wanted = new Map(catalog.games.filter((g) => g.image).map((g) => [`${g.productId}.jpg`, g.image]));

const queue = [...wanted].filter(([file]) => !have.has(file));
let done = 0, failed = 0;
if (queue.length) console.log(`Downloading ${queue.length} PS Plus covers...`);
await Promise.all(Array.from({ length: CONCURRENCY }, async () => {
  while (queue.length) {
    const [file, image] = queue.shift();
    try {
      const res = await fetch(`${image}?w=${WIDTH}`, { signal: AbortSignal.timeout(20_000) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await writeFile(new URL(file, DIR), Buffer.from(await res.arrayBuffer()));
    } catch (err) {
      failed++;
      console.warn(`  ! ${file}: ${err.message}`);
    }
    if (++done % 50 === 0) console.log(`  ${done} downloaded`);
  }
}));

let removed = 0;
for (const file of have) {
  if (!wanted.has(file)) { await unlink(new URL(file, DIR)); removed++; }
}
console.log(`Covers: ${wanted.size} in catalog · ${done - failed} new · ${failed} failed · ${removed} removed`);
