// Ranks the Game Pass catalog against a play history.
//
// Taste is expressed as clusters weighted by hours actually played, and each
// catalog game is scored on how strongly its title/description/genres match a
// cluster, then multiplied by a quality term built from both Metacritic scores.
import { readFile } from 'node:fs/promises';

// --- the play history, hours merged across platforms -------------------------
const PLAYED = [
  ['Elden Ring Nightreign', '艾尔登法环：黑夜君临', 185.7], ['Elden Ring', '艾尔登法环', 171.7],
  ['Slay the Spire 2', '杀戮尖塔 2', 137.1], ['Sekiro', '只狼', 113.5],
  ['Hollow Knight Silksong', '空洞骑士：丝之歌', 81.5], ['Black Myth Wukong', '黑神话：悟空', 80.2],
  ['The First Berserker Khazan', '第一狂战士：卡赞', 78], ['Red Dead Redemption 2', '荒野大镖客2', 75],
  ['Dark Souls III', '黑暗之魂3', 71], ['Dark Souls Remastered', '黑暗之魂 重制版', 71],
  ['Lies of P', '匹诺曹的谎言', 56], ['The Witcher 3', '巫师3', 53],
  ['Slay the Spire', '杀戮尖塔', 49.5], ['Dark Souls II Scholar of the First Sin', '黑暗之魂2', 40.6],
  ['Dota Underlords', '刀塔霸业', 26.4], ['Dead Cells', '死亡细胞', 20],
  ['Ring Fit Adventure', '健身环大冒险', 20], ['Clair Obscur Expedition 33', '光与影：33号远征队', 19],
  ['It Takes Two', '双人成行', 18], ['Stardew Valley', '星露谷物语', 16.5],
  ['Hades', '哈迪斯', 16], ['Batman Arkham Knight', '蝙蝠侠：阿卡姆骑士', 15],
  ['Asphalt 9', '狂野飙车9', 15], ['Zelda Tears of the Kingdom', '王国之泪', 14],
  ['Vampire Survivors', '吸血鬼幸存者', 11], ['Monster Hunter Rise', '怪物猎人崛起', 9.8],
  ['Nintendo Switch Sports', '', 9.5], ['Nine Sols', '九日', 9.3],
  ['Mario Kart 8 Deluxe', '', 9.2], ['Another Crab\'s Treasure', '蟹蟹寻宝奇遇', 9.2],
  ['Hollow Knight', '空洞骑士', 9.1], ['Street Fighter 6', '街头霸王6', 8.9],
  ['Overcooked', '胡闹厨房', 7.5], ['Boomerang Fu', '随动回旋镖', 7.4],
  ['Super Mario Party', '', 7.3], ['Monster Hunter Wilds', '怪物猎人：荒野', 6.7],
  ['God of War', '战神', 6.6], ["Kingdom Come Deliverance II", '天国：拯救2', 6.5],
  ['Balatro', '小丑牌', 6.3], ['Dave the Diver', '潜水员戴夫', 6.3],
  ['Pico Park', '只只大冒险', 6.2], ['Deep Rock Galactic', '深岩银河', 6],
  ['Super Smash Bros Ultimate', '', 5.7], ['Fall Guys', '糖豆人', 3.2],
  ['Animal Crossing New Horizons', '集合啦动物森友会', 2.8],
];

// --- taste clusters, weighted by the hours behind each ------------------------
// The weights are the share of total playtime, so the ranking follows what was
// actually played rather than what sounds interesting.
const CLUSTERS = {
  soulslike: {
    hours: 877, label: '魂系 / 高难动作',
    strong: ['soulslike', 'souls-like', 'soulsborne', 'souls like'],
    // Genre tags never say "soulslike", so the well-known ones are named outright.
    titles: ['wo long', 'remnant ii', 'sifu', 'wuchang', 'ninja gaiden', 'nioh',
      'lords of the fallen', 'steelrising', 'thymesia', 'mortal shell', 'code vein',
      'the surge', 'ashen', 'blasphemous', 'salt and sanctuary', 'flintlock', 'death howl'],
    weak: ['punishing', 'unforgiving', 'brutal difficulty', 'relentless', 'die and retry',
      'demanding combat', 'precise combat', 'stamina', 'parry', 'formidable boss', 'merciless'],
    genres: ['Action RPG'],
  },
  roguelike: {
    hours: 266, label: 'Roguelike / 卡牌构筑',
    strong: ['roguelike', 'roguelite', 'rogue-like', 'deckbuilder', 'deck-building', 'deck building'],
    weak: ['run-based', 'each run', 'permadeath', 'procedurally generated', 'synergies', 'build your deck'],
    genres: ['Card Battle'],
  },
  openworld: {
    hours: 153, label: '大型开放世界 RPG',
    strong: ['open world', 'open-world'],
    weak: ['vast world', 'branching narrative', 'choices matter', 'role-playing', 'explore a living'],
    genres: ['Open-World Action', 'Western RPG', 'JRPG'],
  },
  metroidvania: {
    hours: 91, label: '银河恶魔城',
    strong: ['metroidvania'],
    weak: ['interconnected world', 'hand-drawn', 'unlock new abilities', 'explore a sprawling'],
    genres: ['Metroidvania'],
  },
  coop: {
    hours: 48, label: '本地 / 联机合作',
    strong: ['co-op', 'coop', 'cooperative'],
    weak: ['couch', 'party game', 'friends', 'up to four players', 'local multiplayer'],
    genres: ['Party'],
  },
};
const TOTAL_HOURS = Object.values(CLUSTERS).reduce((n, c) => n + c.hours, 0);

const norm = (s) => String(s || '').toLowerCase().replace(/[^a-z0-9一-鿿]+/g, ' ').trim();

// A played game must never be recommended back, but "Hades" must not swallow
// "Hades II". So: exact title equality, or a long history name that the store
// title starts with (which absorbs edition suffixes without matching sequels).
const EDITION = /\s*(standard|deluxe|ultimate|complete|definitive|enhanced|remastered|goty|game of the year|digital|bundle|edition|version|windows|pc)\b.*$/;
const titleForms = (game) => [game.title, game.metacritic?.title, game.titleZh]
  .filter(Boolean)
  .map((t) => norm(String(t).replace(/[《》]/g, '').replace(EDITION, '')));

function isPlayed(game) {
  const forms = titleForms(game);
  return PLAYED.some(([en, zh]) => {
    for (const name of [norm(en), zh ? norm(zh) : '']) {
      if (!name) continue;
      if (forms.includes(name)) return true;
      if (name.length >= 10 && forms.some((f) => f.startsWith(name + ' '))) return true;
    }
    return false;
  });
}

function affinity(game) {
  const titleText = [game.title, game.metacritic?.title].filter(Boolean).join(' ').toLowerCase();
  const text = [game.title, game.shortDescription, (game.metacritic?.genres || []).join(' ')]
    .join(' ').toLowerCase();
  const genres = game.metacritic?.genres || [];
  const hits = {}, why = {};
  for (const [key, c] of Object.entries(CLUSTERS)) {
    const strong = (c.strong || []).filter((k) => text.includes(k));
    // Named titles are checked against the title only — "flintlock pistols" in a
    // pirate game's blurb is not the game Flintlock.
    const named = (c.titles || []).filter((k) => titleText.includes(k));
    const weak = (c.weak || []).filter((k) => text.includes(k));
    const genre = (c.genres || []).filter((g) => genres.includes(g));

    // A genre tag alone is far too broad — "Action RPG" covers Mass Effect as
    // readily as Nioh. Require an explicit signal, or a genre backed by two
    // supporting phrases.
    const gated = strong.length || named.length || (genre.length && weak.length >= 2);
    if (!gated) continue;

    const raw = 3 * strong.length + 4 * named.length + weak.length + 1.5 * genre.length;
    // Saturating: a fourth keyword says little more than the third, so a
    // 95-rated game with one clear signal outranks a mediocre keyword pile-up.
    hits[key] = (raw / (raw + 3)) * (c.hours / TOTAL_HOURS);
    why[key] = [...strong, ...named, ...weak, ...genre].slice(0, 3).join(', ');
  }
  return { hits, why };
}

// Quality blends both scores, and only counts a user score backed by real volume.
function quality(mc) {
  const critic = mc.score / 100;
  const user = mc.userScore != null && (mc.userReviewCount ?? 0) >= 30 ? mc.userScore / 10 : critic;
  return 0.5 * critic + 0.5 * user;
}

const data = JSON.parse(await readFile(new URL('../data/games.json', import.meta.url), 'utf8'));

// Collapse the console/PC duplicates the store lists separately.
const byGame = new Map();
for (const g of data.games) {
  const key = g.metacritic?.url || g.title.toLowerCase();
  if (!byGame.has(key) || byGame.get(key).title.length > g.title.length) byGame.set(key, g);
}

const played = [], candidates = [];
for (const g of byGame.values()) {
  if (!g.metacritic?.score) continue;
  (isPlayed(g) ? played : candidates).push(g);
}

const ranked = candidates
  .map((g) => {
    const { hits, why } = affinity(g);
    const total = Object.values(hits).reduce((a, b) => a + b, 0);
    // Quality is squared so it carries real weight against affinity.
    return { g, hits, why, score: total * quality(g.metacritic) ** 2 };
  })
  .filter((r) => r.score > 0)
  .sort((a, b) => b.score - a.score);

const topCluster = (r) => Object.entries(r.hits).sort((a, b) => b[1] - a[1])[0][0];
const fmt = (r) => {
  const m = r.g.metacritic;
  const k = topCluster(r);
  const name = (r.g.titleZh || r.g.title).replace(/[《》]/g, '');
  return `  ${String(m.score).padStart(2)}/${String(m.userScore ?? '–').padEnd(3)} ${CLUSTERS[k].label.padEnd(18)} ${name.padEnd(28)} ${r.why[k]}`;
};

console.log(`目录中已玩过（不再推荐）：${played.length} 款`);
console.log(played.map((g) => g.titleZh || g.title).sort().join('、'));

console.log(`\n=== 综合推荐 Top 20 ===\n媒体/玩家 主要匹配           游戏                         匹配依据`);
ranked.slice(0, 20).forEach((r) => console.log(fmt(r)));

for (const [key, c] of Object.entries(CLUSTERS)) {
  const top = ranked.filter((r) => topCluster(r) === key).slice(0, 8);
  if (!top.length) continue;
  console.log(`\n=== ${c.label}（${c.hours}h） ===`);
  top.forEach((r) => console.log(`  ${r.g.metacritic.score}/${r.g.metacritic.userScore ?? '–'}  ${r.g.titleZh || r.g.title}`));
}
