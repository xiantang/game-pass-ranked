# XGP × Metacritic

A local page listing the whole Xbox Game Pass and PlayStation Plus catalogs, sortable by
Metacritic score. Switch between the two at the top right.

```bash
npm run build    # refresh the catalog + scores (a few minutes)
npm run serve    # http://localhost:5173
```

Live at **https://games.vim0.com**.

## Deploy

The page is fully static, so it is served for free straight from the `main` branch by
GitHub Pages, on a custom domain whose DNS lives in Cloudflare.

- **Data refresh:** `.github/workflows/refresh-data.yml` runs `npm run build` every Monday
  at 02:00 UTC and commits `data/` when anything changed; the commit republishes the site.
  Trigger it by hand with `gh workflow run refresh-data.yml`. A failed fetch fails the job
  before the commit, so the live site keeps the previous data.
- **Domain:** the `CNAME` file holds `games.vim0.com`. In Cloudflare, `games` is a CNAME
  to `xiantang.github.io`. It must stay **DNS only** (grey cloud) until GitHub has issued
  the certificate. If you later turn on the proxy (orange cloud), set SSL/TLS to
  **Full (strict)**, because Flexible causes a redirect loop.

## How it works

| Step | Script | Output |
| --- | --- | --- |
| Pull the Game Pass console + PC lists, then product details | `scripts/fetch-xgp.mjs` | `data/xgp.json` |
| Match each title on Metacritic, attach critic + user scores | `scripts/fetch-metacritic.mjs` | `data/games.json` (+ `data/mc-cache.json`, `data/mc-user-cache.json`) |
| Pull the PS Plus lists | `scripts/fetch-psplus.mjs` | `data/psplus.json` |
| Same Metacritic pass for PS Plus | `scripts/fetch-metacritic.mjs psplus` | `data/psplus-games.json` |
| Render, filter and sort in the browser | `index.html` | — |

Both APIs are the public JSON endpoints that xbox.com and metacritic.com call from their
own front ends. No key of your own is needed.

- `MARKET=US npm run build` fetches another store region (default `SG`).
- `data/mc-cache.json` is the lookup cache — keep it, and a re-run only queries
  Metacritic for titles it has not seen. Delete it to force a full refresh.

## Scores

Two scores per game, both from Metacritic:

- **Critic score** (0-100) comes from the search endpoint, alongside the match itself.
- **User score** (0-10) is not in search results — it needs the game page's own
  `user-score-summary` payload, one request per matched game. Those are cached
  separately in `data/mc-user-cache.json` and keyed by slug, so the console and PC
  SKUs of one game share a single lookup.

Both use Metacritic's own thresholds for colour: 75/50 for critics, 7.5/5.0 for users.
Sort by either, and filter on a minimum of either.

## Recommendations

`node scripts/recommend.mjs` ranks the catalog against a play history hard-coded at
the top of that script. Taste is modelled as clusters weighted by hours actually
played; each catalog game is scored on how strongly its title, description and
genres match a cluster, times a quality term built from both Metacritic scores.

Two details that matter more than the scoring itself:

- **Exclusion is exact.** Matching a played game is by title equality (or a long
  history name the store title starts with), so "Hades" cannot swallow "Hades II".
- **Named games match on the title only.** A pirate blurb mentioning "flintlock
  pistols" is not the game *Flintlock*.

Affinity saturates (`raw / (raw + 3)`) and quality is squared, so a 95-rated game
with one clear signal outranks a mediocre game that trips six keywords.

## Matching

Store titles carry noise Metacritic never has (`®`, `Cross-Gen Bundle`, `Standard Edition`,
`for Windows 10`). The matcher strips that, converts roman numerals, compares character
bigrams, and then applies two guards:

- **Sequel numbers must agree** — so `Gears of War: Ultimate Edition` cannot match `Gears of War 2`.
- **Release year breaks ties** — so `Modern Warfare III` lands on the 2023 game (56), not the 2011 one (88).

## Play on

The device filter mirrors xbox.com's own facets, using the rules from its catalog
script (`xgpcatPopulate-2025.js`):

| Facet | Rule |
| --- | --- |
| Xbox Series X\|S | `XboxConsoleGenCompatible` includes `ConsoleGen9` (or is `null`) |
| Xbox One | includes `ConsoleGen8`, or the field is `null`/absent |
| Windows PC | listed in the PC catalog |
| Handhelds | same as Windows PC — Xbox has no separate handheld flag, its site filters this facet against the PC list |
| Play Anywhere | any SKU has `XboxXPA === true` |

Checking several devices widens the results (union), as on the store.

## PS Plus

The PS Plus catalog comes from the endpoint playstation.com's own PS Plus game finder
calls, `https://www.playstation.com/bin/imagic/gameslist?locale=en-sg&categoryList=<list>`.
Refresh just this side with `npm run fetch:ps`.

| List | Contents | Lowest plan |
| --- | --- | --- |
| `plus-monthly-games-list` | Monthly games | Essential |
| `plus-games-list` | Game Catalog | Extra |
| `ubisoft-classics-list` | Ubisoft Classics | Extra |
| `plus-classics-list` | Classics Catalog | Premium |

Plans are cumulative, as in the game finder's own ribbons: picking **Extra** shows
everything Essential and Extra members can play. Each card is tagged with the lowest plan
that includes the game. A game in several lists (the Ubisoft Classics are all in the Game
Catalog too) keeps its lowest tier. Monthly games rotate, so Essential is only ever a
handful of titles.

The **PS5** device filter includes PS4 games, since the PS5 plays them (and the emulated
classics) through backward compatibility; **PS5 native** shows only games with a PS5 version.
Cards still carry the store's own `PS5` / `PS4` tags.

Store titles add PlayStation noise (`PS4 & PS5`, `PlayStation®Hits`, `[PS4 & PS5]`), which
the matcher strips as well. Both services share the Metacritic caches, so a game on both
is only looked up once.

Chinese titles come from the `zh-hans-hk` locale (`zh-hans-cn` has no PS Plus page); the
HK catalog is not identical to SG, so a few titles stay English. Override with `ZH_LOCALE`.

## 中文 / language

The page ships a 中文 / EN switch (top right). It picks up `navigator.language` on
first visit and remembers the choice in `localStorage`.

Chinese titles are always **Simplified**, and come from three places in order:

1. **The store.** A second pass over the same catalog API (`languages=zh-cn` for Xbox,
   `zh-hans-hk` for PS Plus). Only about 40% of titles have one, and some publishers
   ship it in Traditional.
2. **Wikidata.** The commonly used name, for example GTA V as 侠盗猎车手V. A candidate must
   be a video game whose English label or alias equals the Metacritic title exactly.
   `languagefallback` returns the Simplified form.
3. **Steam.** The publisher's localized name, for Wikidata's misses only. Steam's search
   rate-limits hard, so this pass runs with two workers and waits out any 429.
   Bilingual names such as `BALL x PIT — 球比伦战记` keep only the Chinese part.

**Overrides first.** `data/zh-overrides.json` maps an English title (Metacritic's or
the store's) to a hand-written name, and beats every source above. Use it when a lookup
misses a well-known game (战神：诸神黄昏) or picks a wrong one.

Store names are cleaned of platform and SKU noise (`《战地风云 2042》Xbox One`,
`（Windows版）`, `- 标准版`, `(游戏预览版)`) and of a repeated English title
(`SHADOW OF THE COLOSSUS 汪达与巨像`). A name that still mixes in English words
(`Ghost of Tsushima 导演剪辑版`) is also looked up, and a fully Chinese result wins. Some
official names are genuinely mixed (`EA Sports PGA 巡回赛`) and stay that way.

`scripts/zh-names.mjs` runs last in `npm run build`. It converts every title with
`opencc-js` (Taiwan phrasing to mainland Simplified) and records where each came from
in `titleZhSource`. Lookups are cached in `data/zh-name-cache.json`, so a weekly run only
queries new games. Small indie games have no Chinese name anywhere and stay in English.

In Chinese mode a card shows the Chinese title with the English one beneath it, search
matches either, and A–Z sorting uses `Intl.Collator('zh-Hans')` so titles order by pinyin.

## Release year

The year shown, sorted on, and filtered by is Metacritic's **original** release date,
not the store's. The store date is frequently the re-release or Game Pass listing date —
101 titles differ by more than four years (GoldenEye 007 is listed as 2023 but is a
1997 game), which would make an age filter useless. The store date is the fallback for
titles with no Metacritic match.

The page opens filtered to **2010 or newer**; pick *Any year* to see older games too.

Unmatched or unscored titles still appear in the page under **Include unrated**.
Roughly 85% of SKUs resolve to a score; the rest are mostly Game Preview titles and
brand-new releases Metacritic has not reviewed.
