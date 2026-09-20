"""Pull every game's corpus from one source, through one code path.

Mixing sources invalidates the comparison. A main-story fan transcript and a
complete extracted dialogue archive are different populations, and a game
measured on the second will look harder than one measured on the first for
reasons that have nothing to do with its English. So: one platform
(MediaWiki), one parser, one population definition, and a provenance record
per game saying exactly what was taken.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wikitext as W  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "corpus" / "raw"
CONFIG = ROOT / "corpus" / "games.json"

USER_AGENT = "game-english-corpus/1.0 (research; vocabulary difficulty measurement)"
COURTESY_DELAY = 0.4
TITLES_PER_REQUEST = 20

# What each population admits, as patterns matched against category names.
# This is the whole point of the module: the population is enforced in code,
# not left to whoever assembled the corpus.
POPULATIONS = {
    "story-dialogue": {
        "include": r"transcript|cutscene|mission.*script|main.*story",
        "exclude": r"item|weapon|armou?r|equipment|document|note|book|lore|"
                   r"description|ambient|barks?|idle",
    },
    "all-dialogue": {
        "include": r"transcript|dialogue|dialog|script|conversation|quotes?|"
                   r"cutscene|voice.*line|bark|banter|ambient|idle|chatter|"
                   r"companion|greeting",
        "exclude": r"item|weapon|armou?r|equipment|consumable|document|note|"
                   r"book|lore|description|soundtrack|music|achievement|trophy",
    },
    "all-text": {
        "include": r"transcript|dialogue|dialog|script|conversation|quotes?|"
                   r"cutscene|voice.*line|bark|banter|ambient|idle|chatter|"
                   r"companion|greeting|item|document|note|book|lore|description",
        "exclude": r"soundtrack|music|achievement|trophy|gallery|image",
    },
}


class Wiki:
    def __init__(self, host: str):
        self.host = host
        self.endpoint = f"https://{host}/api.php"

    def query(self, **params) -> dict:
        params.update(format="json", formatversion="2")
        url = f"{self.endpoint}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8", "replace"))

    def query_all(self, key: str, **params):
        """Follow MediaWiki continuations to the end of a list."""
        while True:
            data = self.query(**params)
            yield from data.get("query", {}).get(key, [])
            cont = data.get("continue")
            if not cont:
                return
            params.update(cont)
            time.sleep(COURTESY_DELAY)

    def categories(self) -> list[str]:
        return [c["category"] if isinstance(c, dict) and "category" in c else c["*"]
                for c in self.query_all("allcategories", action="query",
                                        list="allcategories", aclimit=500)]

    def category_members(self, category: str) -> list[str]:
        return [p["title"] for p in self.query_all(
            "categorymembers", action="query", list="categorymembers",
            cmtitle=f"Category:{category}", cmlimit=500, cmnamespace=0)]

    def search(self, term: str, limit: int = 200) -> list[str]:
        return [p["title"] for p in self.query_all(
            "search", action="query", list="search", srsearch=term,
            srlimit=min(limit, 500), srnamespace=0)][:limit]

    def wikitext(self, titles: list[str]) -> dict[str, tuple[str, int]]:
        out: dict[str, tuple[str, int]] = {}
        for i in range(0, len(titles), TITLES_PER_REQUEST):
            chunk = titles[i:i + TITLES_PER_REQUEST]
            data = self.query(action="query", prop="revisions", rvprop="content|ids",
                              rvslots="main", titles="|".join(chunk))
            for page in data.get("query", {}).get("pages", []):
                revs = page.get("revisions") or []
                if not revs:
                    continue
                content = revs[0].get("slots", {}).get("main", {}).get("content")
                if content:
                    out[page["title"]] = (content, revs[0].get("revid", 0))
            time.sleep(COURTESY_DELAY)
        return out


def select_categories(available: list[str], population: str,
                      extra: list[str] | None = None,
                      game_filter: str | None = None) -> list[str]:
    """Pick the wiki's categories that belong to this population.

    `game_filter` matters more than it looks. Most of these wikis cover a
    whole series on one host — reddead.fandom.com carries both Redemption
    games, residentevil.fandom.com the entire series, zelda.fandom.com every
    Zelda — so selecting on population alone collects the wrong game's
    dialogue alongside the right one. That is worse than mixing sources,
    because nothing downstream can detect it.
    """
    if population not in POPULATIONS:
        raise ValueError(f"unknown population {population!r}; "
                         f"expected one of {sorted(POPULATIONS)}")
    rules = POPULATIONS[population]
    include = re.compile(rules["include"], re.I)
    exclude = re.compile(rules["exclude"], re.I)
    picked = [c for c in available if include.search(c) and not exclude.search(c)]
    if game_filter:
        game = re.compile(game_filter, re.I)
        picked = [c for c in picked if game.search(c)]
    for name in extra or []:
        if name not in picked:
            picked.append(name)
    return sorted(picked)


def discover(host: str, population: str) -> dict:
    """Report what a wiki offers, without downloading any of it.

    Run this before trusting a game's row: the categories a wiki happens to
    maintain decide what can be collected from it, and they vary a lot.
    """
    wiki = Wiki(host)
    available = wiki.categories()
    return {
        "host": host,
        "population": population,
        "categories_total": len(available),
        "categories_selected": select_categories(available, population),
        # Shown so a shared wiki's game_filter can be written against what the
        # wiki actually calls things, rather than guessed.
        "categories_matching_population": [
            c for c in available
            if re.search(POPULATIONS[population]["include"], c, re.I)
        ][:200],
    }


def fetch_game(slug: str, spec: dict, population: str) -> dict:
    """Download one game's corpus and write it with its provenance."""
    host = spec["wiki"]
    wiki = Wiki(host)
    print(f"  {slug}: {host}", file=sys.stderr)

    available = wiki.categories()
    categories = select_categories(available, population, spec.get("categories"),
                                   spec.get("game_filter"))
    if spec.get("shared_wiki") and not spec.get("game_filter") \
            and not spec.get("categories"):
        print(f"    REFUSED: {host} covers more than one game and this entry has "
              f"no game_filter. Run `discover` and set one, or the corpus will "
              f"mix games.", file=sys.stderr)
        return {"slug": slug, "pages": 0, "lines": 0, "words": 0,
                "categories": [], "host": host, "refused": "shared wiki, no game_filter"}
    titles: list[str] = []
    for category in categories:
        members = wiki.category_members(category)
        titles += members
        print(f"    [{category}] {len(members)} pages", file=sys.stderr)

    for term in spec.get("search", []):
        hits = wiki.search(term)
        titles += hits
        print(f"    search {term!r}: {len(hits)} pages", file=sys.stderr)

    titles = sorted(set(titles))
    if not titles:
        print(f"    no pages matched — run `discover` against {host}", file=sys.stderr)
        return {"slug": slug, "pages": 0, "lines": 0, "words": 0,
                "categories": categories, "host": host}

    pages = wiki.wikitext(titles)
    out_dir = RAW / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    revisions: dict[str, int] = {}
    for title, (source, revid) in sorted(pages.items()):
        extracted = W.to_lines(source)
        if extracted:
            lines += extracted
            revisions[title] = revid

    (out_dir / "corpus.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    words = sum(len(x.split()) for x in lines)
    provenance = {
        "slug": slug,
        "source": "mediawiki",
        "host": host,
        "endpoint": wiki.endpoint,
        "population": population,
        "categories": categories,
        "pages": len(revisions),
        "lines": len(lines),
        "words": words,
        "revisions": revisions,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "licence": "Fandom content is CC BY-SA; raw text is never committed",
    }
    (out_dir / "provenance.json").write_text(json.dumps(provenance, indent=2),
                                             encoding="utf-8")
    print(f"    {len(revisions)} pages, {len(lines)} lines, ~{words} words",
          file=sys.stderr)
    return provenance


def load_config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def main(slugs: list[str] | None = None) -> None:
    config = load_config()
    population = config.get("population", "all-dialogue")
    games = config["games"]
    targets = slugs or sorted(games)

    print(f"population: {population}", file=sys.stderr)
    report = {}
    for slug in targets:
        spec = games.get(slug)
        if not spec:
            print(f"  {slug}: not in games.json, skipped", file=sys.stderr)
            continue
        if not spec.get("wiki"):
            print(f"  {slug}: no wiki configured, skipped", file=sys.stderr)
            continue
        try:
            report[slug] = fetch_game(slug, spec, population)
        except Exception as exc:                      # noqa: BLE001
            print(f"  {slug}: failed — {exc}", file=sys.stderr)
    return report


if __name__ == "__main__":
    main(sys.argv[1:] or None)
