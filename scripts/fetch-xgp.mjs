// Fetches the full Xbox Game Pass catalog (console + PC) from Microsoft's public
// catalog + display-catalog endpoints and writes data/xgp.json.
import { writeFile, mkdir } from 'node:fs/promises';

const MARKET = process.env.MARKET || 'SG';
const LANG = process.env.LANG_TAG || 'en-us';

// SIGL = "Store Item Group List". These ids are the ones xbox.com itself requests.
const LISTS = [
  { id: 'f6f1f99f-9b49-4ccd-b3bf-4d9767a77f5e', platform: 'console' },
  { id: 'fdd9e2a7-0fee-49f6-ad69-4354098401ff', platform: 'pc' },
];

async function getJSON(url, tries = 4) {
  for (let i = 0; i < tries; i++) {
    try {
      const res = await fetch(url, { headers: { 'user-agent': 'Mozilla/5.0', accept: 'application/json' } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      if (i === tries - 1) throw err;
      await new Promise((r) => setTimeout(r, 600 * 2 ** i));
    }
  }
}

async function fetchList({ id, platform }) {
  const url = `https://catalog.gamepass.com/sigls/v2?id=${id}&language=${LANG}&market=${MARKET}`;
  const rows = await getJSON(url);
  const ids = rows.filter((r) => r.id).map((r) => r.id);
  console.log(`  ${platform}: ${ids.length} product ids`);
  return { platform, ids };
}

function pickImage(images = []) {
  const by = (purpose) => images.find((i) => i.ImagePurpose === purpose);
  const img = by('Poster') || by('BoxArt') || by('SuperHeroArt') || by('BrandedKeyArt') || images[0];
  return img ? `https:${img.Uri}`.replace(/^https:https:/, 'https:') : null;
}

async function fetchProducts(ids) {
  const out = new Map();
  for (let i = 0; i < ids.length; i += 20) {
    const batch = ids.slice(i, i + 20);
    const url = `https://displaycatalog.mp.microsoft.com/v7.0/products?bigIds=${batch.join(',')}` +
      `&market=${MARKET}&languages=${LANG}&MS-CV=DGU1mcuYo0WMMp`;
    const json = await getJSON(url);
    for (const p of json.Products || []) {
      const loc = p.LocalizedProperties?.[0] || {};
      out.set(p.ProductId, {
        productId: p.ProductId,
        title: loc.ProductTitle || loc.ShortTitle || '(unknown)',
        developer: loc.DeveloperName || null,
        publisher: loc.PublisherName || null,
        shortDescription: loc.ShortDescription || loc.ProductDescription?.slice(0, 400) || '',
        categories: p.Properties?.Categories || [],
        releaseDate: p.MarketProperties?.[0]?.OriginalReleaseDate || null,
        image: pickImage(loc.Images),
        storeUrl: `https://www.xbox.com/${LANG}/games/store/_/${p.ProductId}`,
      });
    }
    process.stdout.write(`\r  products ${Math.min(i + 20, ids.length)}/${ids.length}`);
  }
  process.stdout.write('\n');
  return out;
}

const platformsById = new Map();
const allIds = new Set();
console.log(`Fetching Game Pass lists (market ${MARKET})...`);
for (const list of LISTS) {
  const { platform, ids } = await fetchList(list);
  for (const id of ids) {
    allIds.add(id);
    platformsById.set(id, [...(platformsById.get(id) || []), platform]);
  }
}
console.log(`Unique products: ${allIds.size}`);

const products = await fetchProducts([...allIds]);
const games = [...products.values()]
  .map((g) => ({ ...g, platforms: platformsById.get(g.productId) || [] }))
  .sort((a, b) => a.title.localeCompare(b.title));

await mkdir(new URL('../data/', import.meta.url), { recursive: true });
await writeFile(
  new URL('../data/xgp.json', import.meta.url),
  JSON.stringify({ market: MARKET, fetchedAt: new Date().toISOString(), games }, null, 2),
);
console.log(`Wrote data/xgp.json (${games.length} games)`);
