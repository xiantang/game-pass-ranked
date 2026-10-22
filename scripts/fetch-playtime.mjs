// Adds HowLongToBeat play times to both scored catalogs (data/games.json and
// data/psplus-games.json) as `playtime: { main, extra, complete }` in hours.
//
// The search itself runs in scripts/hltb.py (howlongtobeatpy, see requirements.txt);
// this side picks the right result with the same rules as the Metacritic match.
// Results are cached in data/hltb-cache.json, keyed by normalized store title, so a
// re-run only searches titles it has not seen. If Python, the library or HLTB itself
// is unavailable, the step warns and re-applies the cache, so the build still passes
// and keeps the last known times.
import { spawn } from 'node:child_process';
import { readFile, writeFile } from 'node:fs/promises';
import { createInterface } from 'node:readline';
import { normalize, sameEntry, sameStart, similarity } from './match.mjs';

const CACHE_PATH = new URL('../data/hltb-cache.json', import.meta.url);
const FILES = ['games.json', 'psplus-games.json'];
const PYTHON = process.env.HLTB_PYTHON || 'python3';
// Fewer reports than this and one odd run decides the number.
const MIN_REPORTS = 3;

const readJson = async (name) => JSON.parse(await readFile(new URL(`../data/${name}`, import.meta.url), 'utf8'));
const yearOf = (d) => Number(String(d || '').slice(0, 4)) || null;
const saveCache = () => writeFile(CACHE_PATH, JSON.stringify(cache, null, 2));

// Same rules as the Metacritic match: same sequel number, same first word, bigram
// similarity of 0.82+, ties toward the release year ("God of War" 2018, not 2005).
// HLTB's alias field carries the other name a game goes by, so it counts too.
function bestMatch(queries, items, year) {
  let best = null;
  for (const it of items) {
    if (it.type === 'dlc' || it.type === 'mod') continue;
    let score = 0;
    for (const name of [it.name, ...String(it.alias || '').split(',')]) {
      const other = normalize(name || '');
      if (!other) continue;
      for (const q of queries) {
        if (!sameEntry(q, other) || !sameStart(q, other)) continue;
        score = Math.max(score, similarity(q, other), similarity(q.replace(/ /g, ''), other.replace(/ /g, '')));
      }
    }
    if (!score) continue;
    const ranked = score - (year && it.year ? Math.min(0.03, Math.abs(year - it.year) * 0.004) : 0);
    if (!best || ranked > best.ranked) best = { item: it, score, ranked };
  }
  return best && best.score >= 0.82 ? best : null;
}

// Runs one batch of searches through hltb.py and hands each result line to onLine
// as it arrives. Resolves false if the helper could not run at all.
function search(queries, onLine) {
  return new Promise((resolve) => {
    const child = spawn(PYTHON, [new URL('./hltb.py', import.meta.url).pathname], { stdio: ['pipe', 'pipe', 'inherit'] });
    child.on('error', (err) => { console.warn(`  ! cannot run ${PYTHON}: ${err.message}`); resolve(false); });
    createInterface({ input: child.stdout }).on('line', (line) => {
      try { onLine(JSON.parse(line)); } catch {}
    });
    child.on('close', (code) => resolve(code === 0));
    child.stdin.end(JSON.stringify(queries));
  });
}

const datasets = await Promise.all(FILES.map(readJson));
let cache = {};
try { cache = JSON.parse(await readFile(CACHE_PATH, 'utf8')); } catch {}

// One lookup per title: console and PC SKUs, and the same game on both services,
// share it.
const todo = new Map();
for (const { games } of datasets) {
  for (const g of games) {
    const key = normalize(g.title);
    if (key && !(key in cache) && !todo.has(key)) todo.set(key, g);
  }
}

if (todo.size) {
  // Metacritic's title is the cleanest name we have; the store title is the
  // second try for the ones it misses.
  const passes = [
    (g) => g.metacritic?.title || g.title,
    (g) => g.title,
  ];
  console.log(`Searching HowLongToBeat for ${todo.size} titles (about ${Math.ceil(todo.size / 60)} min)...`);
  let pending = new Map(todo);
  for (const [i, pick] of passes.entries()) {
    const queries = [...pending].map(([key, g]) => ({ key, q: pick(g) }));
    if (!queries.length) break;
    const missed = new Map();
    let done = 0, errors = 0;
    const ok = await search(queries, ({ key, items, error }) => {
      const g = pending.get(key);
      if (error) { errors++; console.warn(`\n  ! ${g.title}: ${error}`); return; }
      const year = yearOf(g.metacritic?.releaseDate) || yearOf(g.releaseDate);
      const match = bestMatch([...new Set([normalize(pick(g)), key])].filter(Boolean), items, year);
      if (match) {
        const { id, name, main, extra, complete, count } = match.item;
        cache[key] = { id, name, main, extra, complete, count, confidence: Number(match.score.toFixed(3)) };
      } else missed.set(key, g);
      if (++done % 10 === 0) { process.stdout.write(`\r  ${done}/${queries.length}`); if (done % 100 === 0) saveCache(); }
    });
    process.stdout.write(`\r  ${done}/${queries.length}${errors ? ` (${errors} failed, retried next run)` : ''}\n`);
    if (!ok && !done) {
      console.warn('HowLongToBeat search unavailable — applying cached play times only.');
      break;
    }
    // A miss is final only after the last pass; until then it gets another query.
    if (i === passes.length - 1) for (const key of missed.keys()) cache[key] = null;
    else for (const [key, g] of missed) if (pick(g) === passes[i + 1](g)) cache[key] = null;
    pending = new Map([...missed].filter(([key]) => !(key in cache)));
  }
  await saveCache();
}

const playtimeOf = (g) => {
  const t = cache[normalize(g.title)];
  return t?.main && t.count >= MIN_REPORTS ? { main: t.main, extra: t.extra, complete: t.complete } : null;
};

let top = 0, topTimed = 0;
for (const [i, data] of datasets.entries()) {
  data.games = data.games.map((g) => ({ ...g, playtime: playtimeOf(g) }));
  await writeFile(new URL(`../data/${FILES[i]}`, import.meta.url), JSON.stringify(data, null, 2));
  const timed = data.games.filter((g) => g.playtime).length;
  console.log(`Wrote data/${FILES[i]} — ${timed}/${data.games.length} with a main-story time`);
  for (const g of data.games) {
    if (g.metacritic?.score >= 80) { top++; if (g.playtime) topTimed++; }
  }
}
// The number that decides whether a play-time filter is worth building (TODO.md).
console.log(`Critic 80+: ${topTimed}/${top} have a main-story time (${top ? Math.round((topTimed / top) * 100) : 0}%)`);
