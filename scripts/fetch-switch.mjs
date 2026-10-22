// Fetches every Nintendo Switch and Switch 2 game in the US eShop and writes
// data/switch.json. The endpoint is the Algolia index nintendo.com's own store
// search queries, with the public search key its front end ships.
import { writeFile, mkdir } from 'node:fs/promises';

// The index is the US store's; other regions run on different backends.
const MARKET = 'US';
const URL_QUERY = 'https://U3B6GR4UA3-dsn.algolia.net/1/indexes/store_game_en_us/query';
const HEADERS = {
  'x-algolia-application-id': 'U3B6GR4UA3',
  'x-algolia-api-key': 'a29c6927638bfd8cee23993e51e721c9',
  'content-type': 'application/json',
};
// Base games only: no DLC, no Switch 2 upgrade packs, no game + DLC bundles.
const FILTER = 'topLevelCategoryCode:GAMES AND NOT editions:DLC AND NOT editions:"Upgrade pack"' +
  ' AND NOT dlcType:Individual AND NOT dlcType:Bundle AND NOT dlcType:"ROM Bundle"';
const FIELDS = ['title', 'nsuid', 'url', 'corePlatforms', 'releaseDate', 'softwareDeveloper',
  'softwarePublisher', 'gameGenres', 'productImageSquare', 'productImage'];
// Algolia caps any one query at 1000 hits, and /browse is closed to this key.
const CAP = 1000;

async function query(filters, body, tries = 4) {
  for (let i = 0; i < tries; i++) {
    try {
      const res = await fetch(URL_QUERY, {
        method: 'POST', headers: HEADERS,
        // distinct must be off for a 1000-hit page; it changes no counts here.
        body: JSON.stringify({ query: '', distinct: false, filters, attributesToRetrieve: FIELDS, ...body }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${(await res.text()).slice(0, 200)}`);
      return await res.json();
    } catch (err) {
      if (i === tries - 1) throw err;
      await new Promise((r) => setTimeout(r, 600 * 2 ** i));
    }
  }
}

// Facets to split on when a slice is over the cap. Neither popularityRank nor price
// is set on every game, and thousands share a price, so numeric windows cannot
// reach everything. "attr:value" and "NOT attr:value" always cover the whole slice.
const SPLIT_FACETS = ['corePlatforms', 'contentRating.code', 'gameGenres.combined', 'playerCount',
  'gameFeatures.combined', 'softwarePublisher', 'softwareDeveloper', 'priceRange', 'hasDlc'];
const quote = (v) => `"${String(v).replace(/"/g, '\\"')}"`;

async function collect(filters, into) {
  const res = await query(filters, { hitsPerPage: CAP, facets: SPLIT_FACETS, maxValuesPerFacet: 50 });
  if (res.nbHits <= CAP) {
    for (const h of res.hits) into.set(h.nsuid, h);
    return;
  }
  // The value closest to half the slice splits it most evenly.
  let best = null;
  for (const [attr, values] of Object.entries(res.facets || {})) {
    for (const [value, n] of Object.entries(values)) {
      if (n >= res.nbHits) continue;
      const balance = Math.min(n, res.nbHits - n);
      if (!best || balance > best.balance) best = { attr, value, balance };
    }
  }
  if (!best) throw new Error(`Cannot split ${res.nbHits} hits under ${filters}`);
  const term = `${best.attr}:${quote(best.value)}`;
  await collect(`${filters} AND ${term}`, into);
  await collect(`${filters} AND NOT ${term}`, into);
}

// The Switch 2 Edition is its own product with the base game's name plus a suffix.
const SWITCH2_EDITION = /\s*[-–—:]?\s*Nintendo Switch\s*2 Edition\b.*$/i;
const cleanTitle = (t) => t.replace(/[™®©]/g, '').replace(SWITCH2_EDITION, '').replace(/\s+/g, ' ').trim();
const NOT_GAMES = /\b(soundtrack|OST|art ?book|artbook|wallpapers?)\b/i;
const plainTitle = (t) => t.replace(/[™®©]/g, '');

// Cards are 3:4, so have Nintendo's Cloudinary crop and shrink the cover. Square
// covers are "image/fetch/q_auto/f_auto/<source>" URLs; the rest only have the
// 16:9 key art as an "image/upload" public ID.
const COVER = 'c_fill,ar_3:4,w_400,q_auto,f_auto';
function cover(h) {
  if (h.productImageSquare) return h.productImageSquare.replace(/\/image\/(fetch|upload)\/(?:[a-z]_[^/]*\/)*/, `/image/$1/${COVER}/`);
  return h.productImage ? `https://assets.nintendo.com/image/upload/${COVER}/${h.productImage}` : null;
}

console.log(`Fetching Nintendo eShop games (${MARKET})...`);
const { nbHits: total } = await query(FILTER, { hitsPerPage: 0 });
const hits = new Map();
await collect(FILTER, hits);
console.log(`  ${hits.size}/${total} fetched`);
// A partial catalog would silently drop games, so fail and keep the last data instead.
if (hits.size < total * 0.99) throw new Error(`Only ${hits.size} of ${total} games fetched`);

const games = [...hits.values()]
  .filter((h) => h.nsuid && h.title)
  .map((h) => {
    const platforms = h.corePlatforms || [];
    return {
      productId: String(h.nsuid),
      title: cleanTitle(h.title),
      developer: h.softwareDeveloper || null,
      publisher: h.softwarePublisher || null,
      categories: (h.gameGenres || []).map((g) => g.label).filter(Boolean),
      releaseDate: h.releaseDate || null,
      image: cover(h),
      storeUrl: `https://www.nintendo.com${h.url}`,
      switch1: platforms.includes('Nintendo Switch'),
      switch2: platforms.includes('Nintendo Switch 2'),
      switch2Edition: SWITCH2_EDITION.test(plainTitle(h.title)),
    };
  })
  // The eShop sells soundtracks and art books as software too.
  .filter((g) => (g.switch1 || g.switch2) && !NOT_GAMES.test(g.title))
  .sort((a, b) => a.title.localeCompare(b.title));

await mkdir(new URL('../data/', import.meta.url), { recursive: true });
await writeFile(
  new URL('../data/switch.json', import.meta.url),
  JSON.stringify({ service: 'switch', market: MARKET, fetchedAt: new Date().toISOString(), games }, null, 2),
);
const count = (f) => games.filter(f).length;
console.log(`Wrote data/switch.json (${games.length} games · Switch ${count((g) => g.switch1)} · ` +
  `Switch 2 ${count((g) => g.switch2)} · Switch 2 Edition ${count((g) => g.switch2Edition)})`);
