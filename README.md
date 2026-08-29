# XGP × Metacritic

A local page listing the whole Xbox Game Pass catalog, sortable by Metacritic critic score.

```bash
npm run build    # refresh the catalog + scores (a few minutes)
npm run serve    # http://localhost:5173
```

## How it works

| Step | Script | Output |
| --- | --- | --- |
| Pull the Game Pass console + PC lists, then product details | `scripts/fetch-xgp.mjs` | `data/xgp.json` |
| Match each title on Metacritic and attach the critic score | `scripts/fetch-metacritic.mjs` | `data/games.json` (+ `data/mc-cache.json`) |
| Render, filter and sort in the browser | `index.html` | — |

Both APIs are the public JSON endpoints that xbox.com and metacritic.com call from their
own front ends. No key of your own is needed.

- `MARKET=US npm run build` fetches another store region (default `SG`).
- `data/mc-cache.json` is the lookup cache — keep it, and a re-run only queries
  Metacritic for titles it has not seen. Delete it to force a full refresh.

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

## Release year

The year shown, sorted on, and filtered by is Metacritic's **original** release date,
not the store's. The store date is frequently the re-release or Game Pass listing date —
101 titles differ by more than four years (GoldenEye 007 is listed as 2023 but is a
1997 game), which would make an age filter useless. The store date is the fallback for
titles with no Metacritic match.

Unmatched or unscored titles still appear in the page under **Include unrated**.
Roughly 85% of SKUs resolve to a score; the rest are mostly Game Preview titles and
brand-new releases Metacritic has not reviewed.
