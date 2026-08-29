// Looks up each Game Pass title on Metacritic's public search backend and writes
// data/games.json (catalog + critic score). Results are cached in data/mc-cache.json
// so re-runs only hit the network for titles that are new.
import { readFile, writeFile } from 'node:fs/promises';

const API_KEY = process.env.MC_API_KEY || '1MOZgmNFxvmljaQR1X9KAij9Mo4xAY3u';
const CACHE_PATH = new URL('../data/mc-cache.json', import.meta.url);
const USER_CACHE_PATH = new URL('../data/mc-user-cache.json', import.meta.url);
const CONCURRENCY = 6;

// Store titles carry a lot of noise Metacritic never has: platform tags, edition
// suffixes, trademark symbols. Strip it before comparing.
const NOISE = /\b(xbox (series x\|s|series x\/s|one|360)?|windows \d*|pc|for windows|game preview|cross[- ]?gen|standalone|digital version|console version|pc version|version|standard|deluxe|ultimate|complete|definitive|enhanced|remastered|anniversary|goty|game of the year|digital|bundle|edition|editions)\b/g;

const ROMAN = { ii: 2, iii: 3, iv: 4, v: 5, vi: 6, vii: 7, viii: 8, ix: 9, x: 10, xi: 11, xii: 12, xiii: 13 };

function normalize(title) {
  return title
    .toLowerCase()
    .replace(/[®™©]/g, ' ')
    .replace(/\((?:[^)]*)\)/g, ' ')
    .replace(/\b(\d{4})\b(?!\s*$)/g, ' $1 ')
    .replace(NOISE, ' ')
    .replace(/[:\-–—_'’`."!?,+*/\\|]/g, ' ')
    .replace(/&/g, ' and ')
    .replace(/\s+/g, ' ')
    .trim()
    // "Assassin's Creed II" and "Assassin's Creed 2" are the same game.
    .split(' ')
    .map((w) => (ROMAN[w] ? String(ROMAN[w]) : w))
    .join(' ')
    .trim();
}

// Sequel numbers only (1-99); 4-digit years are edition noise, not identity.
function sequelNumbers(s) {
  return new Set((s.match(/\b\d{1,2}\b/g) || []));
}
function sameEntry(a, b) {
  const A = sequelNumbers(a), B = sequelNumbers(b);
  if (A.size !== B.size) return false;
  for (const n of A) if (!B.has(n)) return false;
  return true;
}

// Dice coefficient over character bigrams — cheap and forgiving of small
// spelling/spacing differences between the two catalogs.
function bigrams(s) {
  const set = new Map();
  for (let i = 0; i < s.length - 1; i++) {
    const g = s.slice(i, i + 2);
    set.set(g, (set.get(g) || 0) + 1);
  }
  return set;
}
function similarity(a, b) {
  if (!a || !b) return 0;
  if (a === b) return 1;
  const A = bigrams(a), B = bigrams(b);
  let hits = 0, total = 0;
  for (const [g, n] of A) { total += n; hits += Math.min(n, B.get(g) || 0); }
  for (const n of B.values()) total += n;
  return total ? (2 * hits) / total : 0;
}

async function search(query, tries = 4) {
  const url = `https://backend.metacritic.com/finder/metacritic/search/${encodeURIComponent(query)}/web` +
    `?apiKey=${API_KEY}&limit=24&offset=0&componentName=search&componentDisplayName=Search&componentType=SearchResults`;
  for (let i = 0; i < tries; i++) {
    try {
      const res = await fetch(url, { headers: { 'user-agent': 'Mozilla/5.0', accept: 'application/json' } });
      if (res.status === 429) throw new Error('rate limited');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      return json?.data?.items || [];
    } catch (err) {
      if (i === tries - 1) { console.warn(`\n  ! ${query}: ${err.message}`); return []; }
      await new Promise((r) => setTimeout(r, 800 * 2 ** i));
    }
  }
}

// `queries` is [{ q, weight }]: the full store title plus trimmed fallbacks
// ("Spiritfarer: Farewell Edition" -> "Spiritfarer"). Fallbacks carry a slight
// weight discount so a full-title match always wins a tie.
function bestMatch(queries, items, storeYear) {
  let best = null;
  for (const it of items) {
    if (it.type !== 'game-title') continue;
    const other = normalize(it.title);
    let score = 0, matchedQuery = null;
    for (const { q, weight } of queries) {
      if (!sameEntry(q, other)) continue;
      // "FARCRY 6" vs "Far Cry 6": compare with spaces collapsed too.
      const s = weight * Math.max(
        similarity(q, other),
        similarity(q.replace(/ /g, ''), other.replace(/ /g, '')),
      );
      if (s > score) { score = s; matchedQuery = q; }
    }
    if (!matchedQuery) continue;
    // Remakes and same-named sequels ("Modern Warfare 2", 2009 vs 2022) tie on
    // title alone; nudge toward the entry released near the store listing.
    const year = Number(String(it.releaseDate || '').slice(0, 4)) || null;
    const penalty = storeYear && year ? Math.min(0.03, Math.abs(storeYear - year) * 0.004) : 0;
    // A scoreless entry is useless here, so break remaining ties toward a scored one.
    const bonus = it.criticScoreSummary?.score ? 0.02 : 0;
    const ranked = score - penalty + bonus;
    if (!best || ranked > best.ranked) best = { item: it, score, ranked };
  }
  // 0.82 keeps sequels apart ("Forza Horizon 4" vs "Forza Horizon 5" score ~0.93
  // on raw text, but the digit split in normalize() pushes them apart).
  if (!best || best.score < 0.82) return null;
  return best;
}

// The search endpoint carries only the critic score; the user score lives on the
// game page's own component payload, one request per matched slug.
async function userScore(slug, tries = 3) {
  const url = `https://backend.metacritic.com/composer/metacritic/pages/games/${encodeURIComponent(slug)}/web?apiKey=${API_KEY}`;
  for (let i = 0; i < tries; i++) {
    try {
      const res = await fetch(url, { headers: { 'user-agent': 'Mozilla/5.0', accept: 'application/json' } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      const item = json?.components?.find((c) => c.meta?.componentName === 'user-score-summary')?.data?.item;
      if (!item?.score) return null;
      return { score: item.score, reviewCount: item.reviewCount ?? 0, sentiment: item.sentiment || null };
    } catch (err) {
      if (i === tries - 1) { console.warn(`\n  ! user score ${slug}: ${err.message}`); return null; }
      await new Promise((r) => setTimeout(r, 800 * 2 ** i));
    }
  }
}

const catalog = JSON.parse(await readFile(new URL('../data/xgp.json', import.meta.url), 'utf8'));
let cache = {};
try { cache = JSON.parse(await readFile(CACHE_PATH, 'utf8')); } catch {}

const queue = [...catalog.games];
let done = 0, hits = 0, misses = 0, fromCache = 0;

async function worker() {
  while (queue.length) {
    const game = queue.shift();
    const key = normalize(game.title);
    if (!(key in cache)) {
      const storeYear = Number(String(game.releaseDate || '').slice(0, 4)) || null;
      const queries = [{ q: key, weight: 1 }];
      let items = await search(key || game.title);
      let match = bestMatch(queries, items, storeYear);
      // Search recall is the weak spot: a re-release query can bury the modern
      // entry past the result window. Widen the candidate pool when the best hit
      // is imperfect or lands far from the store's release year.
      const shaky = () => !match || match.score < 0.98 ||
        (storeYear && Math.abs(storeYear - (Number(String(match.item.releaseDate || '').slice(0, 4)) || storeYear)) > 3);
      // Second chance: the raw store title sometimes searches better than the
      // stripped one (short names, subtitles that matter).
      const variants = [game.title, game.title.split(/ [-–—] /)[0], game.title.split(':')[0]];
      const seen = new Set([key]);
      for (const variant of variants) {
        if (!shaky()) break;
        const q = normalize(variant);
        if (!q || seen.has(q)) continue;
        seen.add(q);
        queries.push({ q, weight: 0.97 });
        items = items.concat(await search(variant));
        match = bestMatch(queries, items, storeYear);
      }
      cache[key] = match
        ? {
            title: match.item.title,
            slug: match.item.slug,
            // Metacritic returns 0 for "no critic score yet" — treat it as absent.
        score: match.item.criticScoreSummary?.score || null,
            url: `https://www.metacritic.com/game/${match.item.slug}/`,
            releaseDate: match.item.releaseDate || null,
            genres: (match.item.genres || []).map((g) => g.name).filter(Boolean),
            mustPlay: !!match.item.mustPlay,
            confidence: Number(match.score.toFixed(3)),
          }
        : null;
      await new Promise((r) => setTimeout(r, 120));
    } else fromCache++;
    cache[key] ? hits++ : misses++;
    done++;
    if (done % 10 === 0) process.stdout.write(`\r  ${done}/${catalog.games.length} matched=${hits} unmatched=${misses}`);
  }
}

console.log(`Looking up ${catalog.games.length} titles on Metacritic...`);
await Promise.all(Array.from({ length: CONCURRENCY }, worker));
process.stdout.write(`\r  ${done}/${catalog.games.length} matched=${hits} unmatched=${misses} (cached ${fromCache})\n`);

await writeFile(CACHE_PATH, JSON.stringify(cache, null, 2));

// --- phase 2: user scores, keyed by slug so console/PC SKUs share one lookup ---
let userCache = {};
try { userCache = JSON.parse(await readFile(USER_CACHE_PATH, 'utf8')); } catch {}

const slugs = [...new Set(Object.values(cache).filter(Boolean).map((m) => m.slug))]
  .filter((slug) => !(slug in userCache));
if (slugs.length) {
  console.log(`Fetching user scores for ${slugs.length} games...`);
  let n = 0;
  await Promise.all(Array.from({ length: CONCURRENCY }, async () => {
    while (slugs.length) {
      const slug = slugs.shift();
      userCache[slug] = await userScore(slug);
      if (++n % 10 === 0) process.stdout.write(`\r  ${n} fetched`);
      await new Promise((r) => setTimeout(r, 120));
    }
  }));
  process.stdout.write(`\r  ${n} fetched\n`);
  await writeFile(USER_CACHE_PATH, JSON.stringify(userCache, null, 2));
}

const games = catalog.games.map((g) => {
  const mc = cache[normalize(g.title)] || null;
  return {
    ...g,
    metacritic: mc && mc.score != null
      ? {
          score: mc.score, title: mc.title, url: mc.url, mustPlay: mc.mustPlay,
          genres: mc.genres, confidence: mc.confidence,
          // Original release, which is what "how old is this game" should mean —
          // the store date is often a re-release or the Game Pass listing date.
          releaseDate: mc.releaseDate,
          // 0-10 scale, unlike the critic score — the page renders it as such.
          userScore: userCache[mc.slug]?.score ?? null,
          userReviewCount: userCache[mc.slug]?.reviewCount ?? null,
        }
      : null,
  };
});

const scored = games.filter((g) => g.metacritic);
await writeFile(
  new URL('../data/games.json', import.meta.url),
  JSON.stringify({
    market: catalog.market,
    fetchedAt: catalog.fetchedAt,
    scoredAt: new Date().toISOString(),
    total: games.length,
    scored: scored.length,
    games,
  }, null, 2),
);
const withUser = scored.filter((g) => g.metacritic.userScore != null).length;
console.log(`Wrote data/games.json — ${scored.length}/${games.length} with a critic score, ${withUser} with a user score`);
