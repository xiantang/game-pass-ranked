// Gives every game in data/games.json and data/psplus-games.json a Simplified Chinese
// title where one exists, and converts the ones the stores ship in Traditional.
//
// The stores only publish a Chinese title for about 40% of the catalog, so missing
// titles are looked up on Wikidata (the commonly used name) and then on Steam (the
// publisher's localized name). Wikidata goes first because it tolerates parallel
// requests; Steam's search rate-limits hard, so it only sees Wikidata's misses.
// Lookups are cached in data/zh-name-cache.json, shared by both services, so a
// weekly run only queries games it has not seen.
import { readFile, writeFile } from 'node:fs/promises';
import OpenCC from 'opencc-js';

const FILES = ['games.json', 'psplus-games.json'];
const CACHE_PATH = new URL('../data/zh-name-cache.json', import.meta.url);
const UA = 'game-pass-ranked/1.0 (https://games.vim0.com)';
// Wikidata items that are a video game, a remake/remaster, or an expansion.
const GAME_TYPES = new Set(['Q7889', 'Q21125433', 'Q64170203', 'Q209163', 'Q1066707', 'Q4393107']);

// twp also converts Taiwan-specific phrasing, not just characters.
const toSimplified = OpenCC.Converter({ from: 'twp', to: 'cn' });
const HAS_CJK = /[一-鿿]/;

async function getJSON(url, tries = 4) {
  for (let i = 0; i < tries; i++) {
    try {
      // Without a timeout, one hung connection stalls its worker for good.
      const res = await fetch(url, {
        headers: { 'user-agent': UA, accept: 'application/json' },
        signal: AbortSignal.timeout(15_000),
      });
      // Steam answers bursts with 429 for about a minute; waiting it out beats backing off in steps.
      if (res.status === 429) { await new Promise((r) => setTimeout(r, 60_000)); i--; continue; }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      if (i === tries - 1) throw err;
      await new Promise((r) => setTimeout(r, 800 * 2 ** i));
    }
  }
}

const norm = (s) => String(s).toLowerCase().replace(/[®™©]/g, '').replace(/&/g, 'and').replace(/[^a-z0-9]/g, '');

// Light cleanup only: trademark marks, a "(Windows)" platform suffix, and 《》 that
// wrap the whole name ("《战地风云3》" -> "战地风云3", "《刺客信条IV：黑旗》- 黄金版" kept readable).
function tidy(name) {
  let s = toSimplified(name).replace(/[®™©]/g, '').replace(/\s*[(（]\s*windows\s*[)）]\s*$/i, '').trim();
  s = s.replace(/^《([^《》]+)》(?=\s*$|\s*[-–—:：]|\s*\S*版$)/, '$1');
  return s.replace(/\s+/g, ' ').trim();
}

// Steam names often carry both languages: "BALL x PIT — 球比伦战记",
// "辛特堡传说 / Dungeons of Hinterberg", "猫咪斗恶龙3 Cat Quest III". Keep the Chinese part.
function chinesePart(name, english) {
  const parts = name.split(/\s+[\/|—–-]\s+/).filter((p) => HAS_CJK.test(p));
  let s = (parts[0] || name).trim();
  const tail = s.toLowerCase().lastIndexOf(english.toLowerCase());
  if (tail > 0 && HAS_CJK.test(s.slice(0, tail))) s = s.slice(0, tail).trim();
  return HAS_CJK.test(s) ? s : null;
}

async function fromSteam(query) {
  const search = (lang) =>
    getJSON(`https://store.steampowered.com/api/storesearch/?term=${encodeURIComponent(query)}&l=${lang}&cc=US`);
  const en = await search('english');
  const app = (en.items || []).find((i) => norm(i.name) === norm(query));
  if (!app) return null;
  const zh = await search('schinese');
  const localized = (zh.items || []).find((i) => i.id === app.id)?.name;
  return localized && HAS_CJK.test(localized) ? chinesePart(localized, app.name) : null;
}

async function fromWikidata(query) {
  const found = await getJSON('https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json' +
    `&language=en&type=item&limit=5&search=${encodeURIComponent(query)}`);
  const ids = (found.search || []).map((i) => i.id);
  if (!ids.length) return null;
  const details = await getJSON('https://www.wikidata.org/w/api.php?action=wbgetentities&format=json' +
    `&props=labels|aliases|claims&languages=en&ids=${ids.join('|')}`);
  const match = ids.map((id) => details.entities[id]).find((e) => {
    const types = (e?.claims?.P31 || []).map((c) => c.mainsnak?.datavalue?.value?.id);
    if (!types.some((t) => GAME_TYPES.has(t))) return false;
    const names = [e.labels?.en?.value, ...(e.aliases?.en || []).map((a) => a.value)].filter(Boolean);
    return names.some((n) => norm(n) === norm(query));
  });
  if (!match) return null;
  const zh = await getJSON('https://www.wikidata.org/w/api.php?action=wbgetentities&format=json' +
    `&props=labels|sitelinks&sitefilter=zhwiki&languages=zh-cn&languagefallback=1&ids=${match.id}`);
  const entity = zh.entities[match.id];
  // The plain "zh" label is often the Taiwan name (碧血狂殺2 for Red Dead Redemption 2),
  // and character conversion cannot fix that. The Chinese Wikipedia article carries
  // per-region title rules, so its mainland display title is 荒野大镖客：救赎2.
  const article = entity?.sitelinks?.zhwiki?.title;
  if (article) {
    const parsed = await getJSON('https://zh.wikipedia.org/w/api.php?action=parse&format=json' +
      `&prop=displaytitle&variant=zh-cn&redirects=1&page=${encodeURIComponent(article)}`);
    const title = String(parsed.parse?.displaytitle || '')
      .replace(/<[^>]+>/g, '')
      // Disambiguation suffixes: "蜘蛛侠2 (2023年游戏)".
      .replace(/\s*[(（][^()（）]*(游戏|遊戲|电子游戏|版)[)）]\s*$/, '')
      .trim();
    if (HAS_CJK.test(title)) return title;
  }
  // No article: languagefallback converts the "zh" label to Simplified characters.
  const label = entity?.labels?.['zh-cn']?.value;
  return label && HAS_CJK.test(label) ? label : null;
}

let cache = {};
try { cache = JSON.parse(await readFile(CACHE_PATH, 'utf8')); } catch {}

const datasets = await Promise.all(FILES.map(async (file) => {
  const url = new URL(`../data/${file}`, import.meta.url);
  return { file, url, data: JSON.parse(await readFile(url, 'utf8')) };
}));

// Queries are the Metacritic title when matched (clean, canonical English) and the
// store title otherwise.
const queryOf = (g) => (g.metacritic?.title || g.title).replace(/[®™©]/g, '').trim();
const pending = [...new Set(datasets.flatMap(({ data }) => data.games)
  .filter((g) => !g.titleZh || (g.titleZhSource && g.titleZhSource !== 'store'))
  .map(queryOf)
  .filter((q) => !(norm(q) in cache)))];

// Runs `lookup` over `queries` with a small worker pool, saving the cache as it goes
// so an interrupted run keeps what it found.
async function pass(label, queries, lookup, workers) {
  if (!queries.length) return;
  console.log(`${label}: ${queries.length} titles`);
  const queue = [...queries];
  let done = 0, found = 0;
  await Promise.all(Array.from({ length: workers }, async () => {
    while (queue.length) {
      const query = queue.shift();
      try {
        const name = await lookup(query);
        if (name) { cache[norm(query)] = { name, source: label }; found++; }
        else if (label === 'steam') cache[norm(query)] = null; // last source: a miss is final
      } catch (err) {
        console.warn(`  ! ${label} ${query}: ${err.message}`); // left uncached, retried next run
      }
      if (++done % 20 === 0 || done === queries.length) {
        console.log(`  ${label} ${done}/${queries.length} · found ${found}`);
        await writeFile(CACHE_PATH, JSON.stringify(cache, null, 2));
      }
    }
  }));
}

await pass('wikidata', pending, fromWikidata, 6);
await pass('steam', pending.filter((q) => !cache[norm(q)]), fromSteam, 2);

for (const { file, url, data } of datasets) {
  for (const g of data.games) {
    // A re-run over already-processed files must not relabel looked-up names as store ones.
    if (g.titleZhSource && g.titleZhSource !== 'store') g.titleZh = null;
    if (g.titleZh) {
      g.titleZh = tidy(g.titleZh);
      g.titleZhSource = 'store';
    } else {
      const hit = cache[norm(queryOf(g))];
      g.titleZh = hit ? tidy(hit.name) : null;
      g.titleZhSource = hit ? hit.source : null;
    }
    // A name that tidies down to the English title adds nothing.
    if (g.titleZh && !HAS_CJK.test(g.titleZh)) { g.titleZh = null; g.titleZhSource = null; }
  }
  await writeFile(url, JSON.stringify(data, null, 2));
  const by = (s) => data.games.filter((g) => g.titleZhSource === s).length;
  const withZh = data.games.filter((g) => g.titleZh).length;
  // Any character that changes under conversion is Traditional left behind.
  const traditional = data.games.filter((g) => g.titleZh && toSimplified(g.titleZh) !== g.titleZh).length;
  console.log(`${file}: ${withZh}/${data.games.length} Chinese titles ` +
    `(store ${by('store')}, steam ${by('steam')}, wikidata ${by('wikidata')}) · ${traditional} still Traditional`);
}
