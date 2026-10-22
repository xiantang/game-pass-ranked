// Title matching shared by the Metacritic and HowLongToBeat lookups: both compare messy
// store titles against another catalog's clean ones.

// Store titles carry a lot of noise Metacritic never has: platform tags, edition
// suffixes, trademark symbols. Strip it before comparing.
const NOISE = /\b(xbox (series x\|s|series x\/s|one|360)?|windows \d*|pc|for windows|game preview|cross[- ]?gen|standalone|digital version|console version|pc version|version|standard|deluxe|ultimate|complete|definitive|enhanced|remastered|anniversary|goty|game of the year|digital|bundle|edition|editions|ps4|ps5|playstation ?hits|playstation ?[45]|for nintendo switch( 2)?|full game)\b/g;

const ROMAN = { ii: 2, iii: 3, iv: 4, v: 5, vi: 6, vii: 7, viii: 8, ix: 9, x: 10, xi: 11, xii: 12, xiii: 13 };

export function normalize(title) {
  return title
    .toLowerCase()
    .replace(/[®™©]/g, ' ')
    .replace(/\((?:[^)]*)\)/g, ' ')
    .replace(/\[[^\]]*\]/g, ' ')
    // PlayStation cross-gen suffix: "PS4 & PS5", "PS4&PS5", "PS4＆PS5".
    .replace(/\bps4\s*[&＆]\s*ps5\b/g, ' ')
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
export function sameEntry(a, b) {
  const A = sequelNumbers(a), B = sequelNumbers(b);
  if (A.size !== B.size) return false;
  for (const n of A) if (!B.has(n)) return false;
  return true;
}

// Bigram similarity alone lets "Ape Academy" match "Escape Academy" and "Ryse:
// Legendary" match "Rysen". Require the store title's first word to be a word of
// the candidate ("Hellblade 2" / "Senua's Saga: Hellblade II"), or both titles to
// start the same once spaces, accents and punctuation are gone ("farcry 6" /
// "Far Cry 6", "Disney•Pixar" / "Disney/Pixar").
export const flat = (s) => s.normalize('NFD').replace(/[^a-z0-9 ]/g, '');
export function sameStart(a, b) {
  const A = flat(a), B = flat(b);
  const head = (s) => s.split(' ')[0];
  const joined = (s) => s.replace(/ /g, '');
  return B.split(' ').includes(head(A)) ||
    (joined(B).startsWith(head(A)) && joined(A).startsWith(head(B)));
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
export function similarity(a, b) {
  if (!a || !b) return 0;
  if (a === b) return 1;
  const A = bigrams(a), B = bigrams(b);
  let hits = 0, total = 0;
  for (const [g, n] of A) { total += n; hits += Math.min(n, B.get(g) || 0); }
  for (const n of B.values()) total += n;
  return total ? (2 * hits) / total : 0;
}
