"""Turn a raw transcript dump into the English a player actually hears or reads.

Transcripts carry a lot that is not game English: who is speaking, what the
camera does, wiki furniture, file headers. Left in, speaker names alone can be
a tenth of the tokens and would show up as vocabulary.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "corpus" / "raw"
CLEAN = ROOT / "corpus" / "clean"

# A leading "ARTHUR:" or "Jin Sakai —". Kept deliberately tight: a line that
# merely contains a colon ("Listen: it matters") must survive intact.
SPEAKER = re.compile(r"^\s*(?:\[[^\]]{0,40}\]\s*)?([A-Z][\w'’.-]*(?:\s+[A-Z][\w'’.-]*){0,3})\s*[:：]\s*")
SPEAKER_DASH = re.compile(r"^\s*([A-Z][\w'’.-]*(?:\s+[A-Z][\w'’.-]*){0,2})\s*[—–]\s+")

STAGE = [
    re.compile(r"\[[^\]]*\]"),          # [he draws his sword]
    re.compile(r"\([^)]*\)"),           # (laughs)
    re.compile(r"\*[^*]*\*"),           # *sighs*
    re.compile(r"<[^>]*>"),             # markup and game tags
    re.compile(r"\{[^}]*\}"),           # {colour codes}, {variable}
]

WIKI = [
    re.compile(r"^=+.*?=+$"),                     # == Section ==
    re.compile(r"^\|.*$"),                        # table rows
    re.compile(r"^[*#:;]+\s*$"),                  # bare list bullets
    re.compile(r"^\s*(?:Retrieved from|Categories?:|Edit|Jump to).*$", re.I),
]

TIMESTAMP = re.compile(r"^\s*\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d+)?\s*(?:-->.*)?$")
SUBTITLE_INDEX = re.compile(r"^\s*\d{1,5}\s*$")

# Lines that are interface, not speech.
UI_HINTS = re.compile(
    r"^\s*(?:press|hold|tap|loading|autosave|checkpoint|objective|tutorial|"
    r"continue|new game|options|settings|quit|resume|chapter\s+\d+|act\s+[ivx]+)\b",
    re.I,
)

NOISE_ONLY = re.compile(r"^[^A-Za-z]*$")


def _strip_markup(line: str) -> str:
    for pattern in STAGE:
        line = pattern.sub(" ", line)
    return line


def clean_line(line: str) -> str | None:
    """Return the speakable English in a line, or None to drop it."""
    line = unicodedata.normalize("NFKC", line).strip()
    if not line:
        return None
    if TIMESTAMP.match(line) or SUBTITLE_INDEX.match(line):
        return None
    if any(p.match(line) for p in WIKI):
        return None

    line = _strip_markup(line)

    stripped = SPEAKER.sub("", line, count=1)
    if stripped != line:
        line = stripped
    else:
        line = SPEAKER_DASH.sub("", line, count=1)

    line = re.sub(r"\s+", " ", line).strip(" -–—\t")
    if not line or NOISE_ONLY.match(line):
        return None
    if UI_HINTS.match(line):
        return None
    # A line with no lower-case letter at all is a heading or a shout in caps
    # lock; headings are far more common in transcript dumps.
    if not any(c.islower() for c in line):
        return None
    if len(line.split()) < 2:
        return None
    return line


def clean_text(raw: str, drop_repeats: bool = True) -> list[str]:
    """Clean a whole dump.

    Repeated lines are collapsed by default: barks ("Over here!", "Reloading!")
    repeat for hours and would otherwise dominate the frequency profile of any
    game with combat chatter.
    """
    out: list[str] = []
    seen: set[str] = set()
    for line in raw.splitlines():
        cleaned = clean_line(line)
        if cleaned is None:
            continue
        if drop_repeats:
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
        out.append(cleaned)
    return out


def clean_game(slug: str, drop_repeats: bool = True) -> list[str]:
    src = RAW / slug
    files = sorted(src.rglob("*.txt")) if src.is_dir() else []
    if not files and (RAW / f"{slug}.txt").exists():
        files = [RAW / f"{slug}.txt"]
    if not files:
        return []
    raw = "\n".join(f.read_text(encoding="utf-8", errors="replace") for f in files)
    return clean_text(raw, drop_repeats=drop_repeats)


def write_clean(slug: str, lines: list[str]) -> Path:
    CLEAN.mkdir(parents=True, exist_ok=True)
    path = CLEAN / f"{slug}.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
