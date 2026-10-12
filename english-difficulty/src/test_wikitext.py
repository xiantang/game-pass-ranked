"""Offline tests for the wikitext parser.

Every fixture is invented for the test. Real transcript pages are copyrighted
and this repository does not carry game text — the point is to exercise the
markup shapes Fandom transcript pages use, not their contents.

    python src/test_wikitext.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wikitext as W  # noqa: E402

FAILURES: list[str] = []


def check(name: str, got, want) -> None:
    if got != want:
        FAILURES.append(f"{name}\n    got:  {got!r}\n    want: {want!r}")


def check_in(name: str, needle: str, haystack) -> None:
    joined = haystack if isinstance(haystack, str) else "\n".join(haystack)
    if needle not in joined:
        FAILURES.append(f"{name}\n    missing: {needle!r}\n    in: {joined!r}")


def check_not_in(name: str, needle: str, haystack) -> None:
    joined = haystack if isinstance(haystack, str) else "\n".join(haystack)
    if needle in joined:
        FAILURES.append(f"{name}\n    should not contain: {needle!r}\n    in: {joined!r}")


# --- links -------------------------------------------------------------
check("piped link shows the label",
      W.resolve_links("Meet [[Harbour Town|the harbour]] tonight."),
      "Meet the harbour tonight.")
check("plain link shows the page",
      W.resolve_links("Head to [[Stonebridge]]."),
      "Head to Stonebridge.")
check("file links vanish entirely",
      W.resolve_links("[[File:Map.png|thumb|A map]]Follow me.").strip(),
      "Follow me.")
check("external link keeps its label",
      W.resolve_links("See [https://example.org the notes] later."),
      "See the notes later.")

# --- templates ---------------------------------------------------------
check("quote template yields its line",
      W.resolve_templates("{{Quote|We leave at dawn.|Captain}}").strip(),
      "We leave at dawn.")
check("unknown templates are dropped whole",
      W.resolve_templates("{{Infobox|name=Captain|role=guide}}Ready?").strip(),
      "Ready?")
check("nested template inside a quote resolves",
      W.resolve_templates("{{Quote|Ask {{Name|the smith}} about it.|Guard}}").strip(),
      "Ask  about it.")
check("named parameters do not shift the positional index",
      W.resolve_templates("{{Quote|author=Guard|Hold the line.}}").strip(),
      "Hold the line.")
check("unbalanced braces do not eat the page",
      "Still here." in W.resolve_templates("{{Broken|oops Still here."),
      True)

# --- whole pages -------------------------------------------------------
PAGE = """<!-- transcript begins -->
== Chapter one ==
{{Infobox mission|name=The Crossing|length=12 minutes}}
:'''Guard:''' You are [[Player Character|the one]] they spoke of.
:'''Traveller:''' ''(steps back)'' I am nobody.
{{Quote|Then nobody may pass.|Guard}}
{| class="wikitable"
! Speaker !! Line
|-
| Guard || Move along.
|}
<ref>Cited from the mission briefing.</ref>
* '''Traveller:''' Wait — I will pay.
[[Category:Transcripts]]
"""

lines = W.to_lines(PAGE)
check_in("dialogue survives", "You are the one they spoke of.", lines)
check_in("quote template survives", "Then nobody may pass.", lines)
check_in("list-item dialogue survives", "Wait — I will pay.", lines)
check_not_in("comments are gone", "transcript begins", lines)
check_not_in("headings are gone", "Chapter one", lines)
check_not_in("infobox values are gone", "12 minutes", lines)
check_not_in("refs are gone", "mission briefing", lines)
check_not_in("category links are gone", "Category:", lines)
check_not_in("table markup is gone", "wikitable", lines)
check_not_in("bold markup is gone", "'''", lines)

# Speaker labels must still be present here: clean.py removes them, so that
# transcripts which never went through a wiki get the same treatment.
check_in("speaker labels are left for clean.py", "Guard:", lines)

# --- the parser hands over to clean.py ---------------------------------
import clean as C  # noqa: E402

cleaned = C.clean_text("\n".join(lines))
check_not_in("clean.py strips the speaker label", "Guard:", cleaned)
check_in("and keeps the words", "You are the one they spoke of.", cleaned)
check_not_in("stage directions are gone", "steps back", cleaned)

if FAILURES:
    print(f"{len(FAILURES)} failure(s):\n", file=sys.stderr)
    for f in FAILURES:
        print(f"  {f}\n", file=sys.stderr)
    raise SystemExit(1)
print("wikitext: all checks passed")
