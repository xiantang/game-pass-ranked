// Fetches the PlayStation Plus catalogs (monthly games, Game Catalog, Ubisoft
// Classics, Classics Catalog) and writes data/psplus.json. The endpoint is the
// one playstation.com's own PS Plus game finder requests.
import { writeFile, mkdir } from 'node:fs/promises';

const MARKET = process.env.MARKET || 'SG';
const LOCALE = `en-${MARKET.toLowerCase()}`;
// zh-hans-cn has no PS Plus page; Hong Kong carries Simplified Chinese titles.
const ZH_LOCALE = process.env.ZH_LOCALE || 'zh-hans-hk';

// Minimum plan per list, mirroring the game finder's TIER_10/20/30 ribbons:
// Essential gets the monthly games, Extra adds the Game Catalog and Ubisoft
// Classics, Premium adds the Classics Catalog. Tiers are cumulative.
const LISTS = [
  { id: 'plus-monthly-games-list', key: 'monthly', tier: 1 },
  { id: 'plus-games-list', key: 'catalog', tier: 2 },
  { id: 'ubisoft-classics-list', key: 'ubisoft', tier: 2 },
  { id: 'plus-classics-list', key: 'classics', tier: 3 },
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

// "Arcade Paradise PS4™ & PS5™", "GTA V (PS4™ & PS5™)", "Bloodborne™ PlayStation®Hits":
// platform suffixes the page already shows as tags.
const cleanTitle = (t) => t
  .replace(/\s*[([]?\s*PS4[™®]?\s*[&＆]\s*PS5[™®]?\s*[)\]]?/g, '')
  .replace(/\s*-?\s*PlayStation®\s*Hits/g, '')
  .trim();

// The response is grouped by first letter: [{ catalogKey, count, games }].
async function fetchList(id, locale) {
  const url = `https://www.playstation.com/bin/imagic/gameslist?locale=${locale}&categoryList=${id}`;
  const groups = await getJSON(url);
  return groups.flatMap((g) => g.games || []);
}

console.log(`Fetching PS Plus lists (${LOCALE})...`);
const byId = new Map();
for (const list of LISTS) {
  const rows = await fetchList(list.id, LOCALE);
  console.log(`  ${list.key}: ${rows.length} entries`);
  for (const r of rows) {
    const prev = byId.get(r.conceptId);
    const device = r.device || [];
    if (prev) {
      prev.tier = Math.min(prev.tier, list.tier);
      if (!prev.lists.includes(list.key)) prev.lists.push(list.key);
      prev.ps4 ||= device.includes('PS4');
      prev.ps5 ||= device.includes('PS5');
      continue;
    }
    byId.set(r.conceptId, {
      productId: String(r.conceptId),
      title: cleanTitle(r.nameEn || r.name),
      developer: null,
      publisher: null,
      categories: r.genre || [],
      releaseDate: r.releaseDate || null,
      image: r.imageUrl || null,
      storeUrl: r.conceptUrl,
      ps4: device.includes('PS4'),
      ps5: device.includes('PS5'),
      tier: list.tier,
      lists: [list.key],
    });
  }
}

// Chinese titles: same lists in the zh locale, joined on conceptId. The HK
// catalog is not identical to SG, so a missing entry just stays English.
const zh = new Map();
for (const list of LISTS) {
  try {
    for (const r of await fetchList(list.id, ZH_LOCALE)) zh.set(r.conceptId, cleanTitle(r.name));
  } catch (err) {
    console.warn(`  ! ${ZH_LOCALE} ${list.id}: ${err.message}`);
  }
}

const games = [...byId.values()]
  .map((g) => {
    const titleZh = zh.get(Number(g.productId));
    return { ...g, titleZh: titleZh && titleZh !== g.title ? titleZh : null };
  })
  .sort((a, b) => a.title.localeCompare(b.title));

await mkdir(new URL('../data/', import.meta.url), { recursive: true });
await writeFile(
  new URL('../data/psplus.json', import.meta.url),
  JSON.stringify({ service: 'psplus', market: MARKET, fetchedAt: new Date().toISOString(), games }, null, 2),
);
const tiers = [1, 2, 3].map((t) => games.filter((g) => g.tier === t).length);
console.log(`Wrote data/psplus.json (${games.length} games · tier 1/2/3: ${tiers.join('/')} · ${games.filter((g) => g.titleZh).length} Chinese titles)`);
