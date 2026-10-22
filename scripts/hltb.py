"""Searches HowLongToBeat for scripts/fetch-playtime.mjs, which does the matching.

Reads a JSON array of {"key", "q"} on stdin and prints one JSON line per query,
{"key", "items": [...]} or {"key", "error"}, as soon as it has it, so a run that
dies halfway still leaves the finished lookups for the caller to cache.

HLTB has no public API; howlongtobeatpy (pinned in requirements.txt) tracks the
site's own search call. One query a second keeps the load polite.
"""
import asyncio
import json
import sys

from howlongtobeatpy import HowLongToBeat

GAP_SECONDS = 1.0


def hours(seconds):
    return round(seconds / 3600, 1) if seconds else None


def item(g):
    j = g.json_content
    return {
        "id": g.game_id,
        "name": g.game_name,
        "alias": g.game_alias or None,
        "year": g.release_world or None,
        "type": j.get("game_type"),
        "main": hours(j.get("comp_main")),
        "extra": hours(j.get("comp_plus")),
        "complete": hours(j.get("comp_100")),
        "count": j.get("comp_main_count") or 0,
    }


async def main():
    # Matching happens on the Node side, so keep every result: the library's own
    # case-sensitive similarity filter drops "LIMBO" against HLTB's "Limbo".
    hltb = HowLongToBeat(0.0)
    for query in json.load(sys.stdin):
        try:
            results = await hltb.async_search(query["q"], similarity_case_sensitive=False)
            if results is None:
                raise RuntimeError("search failed (HLTB may have changed its API)")
            line = {"key": query["key"], "items": [item(g) for g in results[:10]]}
        except Exception as err:  # one bad query must not lose the rest
            line = {"key": query["key"], "error": str(err)}
        print(json.dumps(line, ensure_ascii=False), flush=True)
        await asyncio.sleep(GAP_SECONDS)


asyncio.run(main())
