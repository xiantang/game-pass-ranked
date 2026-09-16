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

// Each scored file, and the raw catalog it was built from. Store Chinese titles are
// always read from the raw catalog, so re-running this script never cleans an
// already-cleaned name a second time.
const FILES = [
  { file: 'games.json', raw: 'xgp.json' },
  { file: 'psplus-games.json', raw: 'psplus.json' },
];
const CACHE_PATH = new URL('../data/zh-name-cache.json', import.meta.url);
// Hand-written names, keyed by English title (Metacritic's or the store's). They win
// over every other source, for games the lookups miss or name badly.
const OVERRIDES_PATH = new URL('../data/zh-overrides.json', import.meta.url);
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

// Accents fold to plain letters first: Metacritic's "God of War: Ragnarok" has to
// equal Wikidata's "God of War Ragnarök", not lose the ö.
const norm = (s) => String(s).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
  .replace(/[®™©]/g, '').replace(/&/g, 'and').replace(/[^a-z0-9]/g, '');

// Store names carry platform and SKU noise the page already shows elsewhere:
// "《战地风云 2042》Xbox One", "山羊模拟器3（Windows版）", "Diablo IV - 标准版",
// "(游戏预览版)", "《我的世界：地下城》Windows 版 + Launcher". Edition names that
// identify a different game ("重制版", "导演剪辑版") stay.
const PLATFORM = String.raw`(?:xbox\s*(?:series\s*x\s*\|\s*s|series\s*x\/s|one|360)?|windows(?:\s*10)?|pc|ps[45](?:\s*[&＆]\s*ps[45])?)`;
const NOISE_PATTERNS = [
  new RegExp(String.raw`\s*[(（]\s*${PLATFORM}\s*版?\s*[)）]`, 'gi'),
  new RegExp(String.raw`\s*[-–—]?\s*${PLATFORM}\s*版?\s*$`, 'gi'),
  /\s*\+\s*launcher\s*$/i,
  /\s*[(（]\s*游戏预览版\s*[)）]/g,
  /\s*[-–—]?\s*(?:数字|數位)?标准版\s*$/,
  /\s*(?:跨越世代|跨世代)(?:礼包|包|版)\s*$/,
];

function tidy(name) {
  let s = toSimplified(name).replace(/[®™©]/g, '')
    // Full-width digits and letters ("女神异闻录５") read as a typo next to normal text.
    .replace(/[０-９Ａ-Ｚａ-ｚ]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0xfee0))
    .trim();
  for (let i = 0; i < 2; i++) for (const re of NOISE_PATTERNS) s = s.replace(re, '').trim();
  // 《》 around the name itself: "《战地风云3》" -> "战地风云3", "《Control》终极合辑" -> "Control 终极合辑".
  s = s.replace(/《([^《》]+)》\s*/, (_, inner) => inner + ' ');
  return s.replace(/\s+/g, ' ').replace(/\s+([：:）)])/g, '$1').trim();
}

// "Mixed" means an English word of three or more letters is left, which on a card
// reads as untranslated. Roman numerals and a few words Chinese titles really use
// ("Online", "VR") do not count.
const KEEP_LATIN = /^(?:[ivxlc]+|online|vr|hd|dlc|ex|dx)$/i;
const isMixed = (name) => (name.match(/[A-Za-z][A-Za-z'’.]{2,}/g) || [])
  .some((w) => !KEEP_LATIN.test(w.replace(/['’.]/g, '')));

// Bilingual names: "Wo Long: Fallen Dynasty （卧龙：苍天陨落）", "纵横秘湾 Corsair Cove",
// "Roboquest (机械守护者)". If a bracket or a run holds all the Chinese, keep that.
function chineseOnly(name) {
  const bracket = name.match(/[(（]([^()（）]*[一-鿿][^()（）]*)[)）]/);
  if (bracket && !HAS_CJK.test(name.replace(bracket[0], ''))) return bracket[1].trim();
  return name;
}

// Store and Steam names often repeat the English title next to the Chinese one:
// "SHADOW OF THE COLOSSUS 汪达与巨像", "九王 9 Kings". Drop it when Chinese remains.
const EDITION_WORDS = /^(?:终极|完整|标准|豪华|高级|年度游戏|游戏预览|导演剪辑|重制|高清|复刻|合辑|合集|典藏|收藏|数字|黄金|决定|周年|纪念|特别|版|包|礼包)+$/;

function withoutEnglish(zh, englishTitles) {
  let s = zh;
  for (const en of englishTitles) {
    const plain = String(en || '').replace(/[®™©]/g, '').trim();
    if (plain.length < 2) continue;
    const at = s.toLowerCase().indexOf(plain.toLowerCase());
    if (at < 0) continue;
    const rest = (s.slice(0, at) + ' ' + s.slice(at + plain.length))
      .replace(/^[\s\/|—–:：-]+|[\s\/|—–:：-]+$/g, '').replace(/\s+/g, ' ').trim();
    // "《Control》终极合辑" must not shrink to "终极合辑": what is left has to be a name,
    // not only edition words.
    const chinese = rest.replace(/[^一-鿿]/g, '');
    if (chinese && !EDITION_WORDS.test(chinese)) s = rest;
  }
  return s;
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
    `&props=labels|aliases|claims&languages=en|mul&ids=${ids.join('|')}`);
  const match = ids.map((id) => details.entities[id]).find((e) => {
    const types = (e?.claims?.P31 || []).map((c) => c.mainsnak?.datavalue?.value?.id);
    if (!types.some((t) => GAME_TYPES.has(t))) return false;
    // Wikidata now keeps many names under "mul" (all languages) instead of "en".
    const names = ['en', 'mul'].flatMap((l) =>
      [e.labels?.[l]?.value, ...(e.aliases?.[l] || []).map((a) => a.value)]).filter(Boolean);
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

const overrides = new Map(Object.entries(JSON.parse(await readFile(OVERRIDES_PATH, 'utf8')))
  .map(([en, zh]) => [norm(en), zh]));
const overrideFor = (g) => overrides.get(norm(queryOf(g))) ?? overrides.get(norm(g.title));

let cache = {};
try { cache = JSON.parse(await readFile(CACHE_PATH, 'utf8')); } catch {}

const readData = async (name) => JSON.parse(await readFile(new URL(`../data/${name}`, import.meta.url), 'utf8'));
const datasets = await Promise.all(FILES.map(async ({ file, raw }) => ({
  file,
  url: new URL(`../data/${file}`, import.meta.url),
  data: await readData(file),
  storeZh: new Map((await readData(raw)).games.map((g) => [g.productId, g.titleZh])),
})));
const storeZhOf = new Map(datasets.flatMap(({ data, storeZh }) =>
  data.games.map((g) => [g, storeZh.get(g.productId) || null])));

// Queries are the Metacritic title when matched (clean, canonical English) and the
// store title otherwise.
const queryOf = (g) => (g.metacritic?.title || g.title).replace(/[®™©]/g, '').trim();
// A usable store title: the store's own, and actually Chinese. Some "zh" store titles
// are just a different English name, and those need a lookup like any other.
const storeTitle = (g) => {
  const zh = storeZhOf.get(g);
  return zh && HAS_CJK.test(zh) ? zh : null;
};
const pending = [...new Set(datasets.flatMap(({ data }) => data.games)
  .filter((g) => !overrideFor(g) && !(storeTitle(g) && !isMixed(tidy(storeTitle(g)))))
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
    const english = [g.title, g.metacritic?.title];
    const clean = (name) => (name ? tidy(chineseOnly(withoutEnglish(tidy(name), english))) : null);
    const override = overrideFor(g);
    const store = storeTitle(g) ? clean(storeTitle(g)) : null;
    const hit = cache[norm(queryOf(g))];
    const lookup = hit ? clean(hit.name) : null;
    // Prefer whichever name is fully Chinese: the store's "Ghost of Tsushima 导演剪辑版"
    // loses to a lookup of 对马岛之魂 导演剪辑版. If none is, a mixed name still beats English.
    const candidates = [
      override && [clean(override), 'override'],
      store && [store, 'store'],
      lookup && [lookup, hit.source],
    ].filter((c) => c && HAS_CJK.test(c[0]));
    // An override with no Chinese in it means "keep the English title" (INSIDE, not 里面).
    const [name, source] = override && !HAS_CJK.test(override) ? [null, 'override']
      : override ? candidates[0]
      : candidates.find(([n]) => !isMixed(n)) || candidates[0] || [null, null];
    g.titleZh = name;
    g.titleZhSource = source;
  }
  await writeFile(url, JSON.stringify(data, null, 2));
  const by = (s) => data.games.filter((g) => g.titleZhSource === s).length;
  const withZh = data.games.filter((g) => g.titleZh).length;
  // Any character that changes under conversion is Traditional left behind.
  const mixed = data.games.filter((g) => g.titleZh && isMixed(g.titleZh)).length;
  const traditional = data.games.filter((g) => g.titleZh && toSimplified(g.titleZh) !== g.titleZh).length;
  console.log(`${file}: ${withZh}/${data.games.length} Chinese titles ` +
    `(override ${by('override')}, store ${by('store')}, steam ${by('steam')}, wikidata ${by('wikidata')}) · ${traditional} still Traditional · ${mixed} mixed with English`);
}
