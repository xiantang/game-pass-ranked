"""Collect a game's spoken English from the captions of a no-commentary playthrough.

Fandom cannot supply this game list. Six of the eight wikis have no dialogue
category at all, and the two that do yield 50k words for one game and 1.3k for
another. Captions cover every game on one source with one parser, which is the
constraint the comparison rests on.

What this buys, and what it costs, was measured rather than assumed. The same
game (`rdr2`) was collected both ways and the two measurements compared:

    coverage @2k/5k/10k   +0.9% / +0.5% / +0.4%   usable
    proper nouns          +5.1%                    usable
    CEFR B2+              -16.4%                   biased low
    archaic per 1k        -45.0%                   unusable
    mean sentence length  -25.9%                   unusable
    subordination         -33.4%                   unusable

The vocabulary axis survives because coverage counts a distribution, and a few
misheard words do not move it. The syntax axis does not survive, because the
automatic track carries no punctuation and the parser has nothing to split
sentences on: the text is not simpler, it is unpunctuated. The archaic axis
halves because speech recognition guesses an archaic word as its modern
neighbour, which matters most for exactly the games whose difficulty is
archaic.

So the corpora collected here declare which axes they support, and the report
prints nothing for the rest. An honest gap is worth more than a filled column
that is wrong by a third.
"""
from __future__ import annotations

import json
import re
import statistics
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "corpus" / "raw"
CONFIG = ROOT / "corpus" / "games.json"

SOURCE = "youtube-captions"

# Measured against the wiki corpus for the same game; see the module docstring.
RELIABLE_AXES = ["vocabulary_coverage", "proper_nouns", "load"]
UNRELIABLE_AXES = ["sentence", "archaic", "register", "cefr"]

# The original-language automatic track. The plain `en` track can be a machine
# translation of some other language, which would measure the translator.
TRACK = "en-orig"
FALLBACK_TRACK = "en"

# What the recogniser emits when it is not transcribing speech. `foreign` is
# its marker for audio it could not place as English at all, and it lands in
# the text as an ordinary word, so it has to go before anything counts words.
ASR_MARKERS = re.compile(r"\[(music|applause|laughter|sound effects?|"
                         r"inaudible|crosstalk)\]|\bforeign\b", re.I)


def _yt(*args: str, timeout: int = 900) -> str:
    out = subprocess.run(["yt-dlp", "--no-update", *args],
                         capture_output=True, text=True, timeout=timeout)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip().splitlines()[-1] if out.stderr else "yt-dlp failed")
    return out.stdout


def video_meta(video: str) -> dict:
    """Duration and title, taken from the video rather than from the captions.

    The caption timestamps run past the end of the video on some tracks, so
    words per hour is computed against the duration reported here.
    """
    line = _yt("--skip-download", "--print", "%(duration)s\t%(title)s\t%(channel)s",
               f"https://www.youtube.com/watch?v={video}", timeout=300).strip()
    duration, title, channel = (line.split("\t") + ["", ""])[:3]
    return {"duration_s": int(float(duration)), "title": title, "channel": channel}


def download_track(video: str, into: Path) -> tuple[Path, str]:
    """Prefer the original-language track, fall back to plain `en`.

    Which one was used is recorded, because `en` is sometimes a machine
    translation of another language rather than a transcript of this audio.
    """
    for track in (TRACK, FALLBACK_TRACK):
        _yt("--skip-download", "--write-auto-subs", "--sub-langs", track,
            "--sub-format", "json3", "-o", str(into / "%(id)s.%(ext)s"),
            f"https://www.youtube.com/watch?v={video}")
        found = sorted(into.glob(f"{video}*.json3"))
        if found:
            return found[0], track
    raise RuntimeError(f"no English automatic captions for {video}")


def parse_track(path: Path) -> tuple[list[str], float]:
    """Caption events in, lines out, plus a speech rate and a noise figure.

    Events carrying `aAppend` are the rolling preview of the line below them
    and hold no words of their own; including them would double the corpus.

    The rate is taken from the gap between one caption's start and the next,
    not from a caption's own duration: a caption stays on screen while the
    next one begins, so the durations sum to more than the video is long.
    """
    events = json.loads(path.read_text(encoding="utf-8")).get("events", [])
    spoken = [e for e in events if e.get("aAppend") != 1 and e.get("segs")]
    lines, rates = [], []
    markers = raw_tokens = 0
    for event, nxt in zip(spoken, spoken[1:] + [None]):
        text = "".join(s.get("utf8", "") for s in event["segs"])
        raw_tokens += len(text.split())
        text, dropped = ASR_MARKERS.subn(" ", text)
        markers += dropped
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        lines.append(text)
        if nxt:
            gap = nxt.get("tStartMs", 0) - event.get("tStartMs", 0)
            if 500 < gap < 15000:
                rates.append(len(text.split()) / (gap / 60000))
    rate = round(statistics.median(rates), 1) if rates else 0.0
    # How much of the track was not speech the recogniser could transcribe.
    # A high figure means the corpus is thin for reasons that have nothing to
    # do with the game's English.
    noise = round(100.0 * markers / raw_tokens, 2) if raw_tokens else 0.0
    return lines, rate, noise


def fetch_game(slug: str, spec: dict, population: str) -> dict:
    video = (spec.get("captions") or {}).get("video")
    if not video:
        print(f"  {slug}: no captions.video configured", file=sys.stderr)
        return {}
    print(f"  {slug}: youtube/{video}", file=sys.stderr)
    meta = video_meta(video)
    with tempfile.TemporaryDirectory() as tmp:
        track, track_name = download_track(video, Path(tmp))
        lines, wpm, noise = parse_track(track)

    words = sum(len(x.split()) for x in lines)
    hours = meta["duration_s"] / 3600
    out_dir = RAW / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "corpus.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    provenance = {
        "slug": slug,
        "source": SOURCE,
        "host": "youtube.com",
        "population": population,
        "video": video,
        "title": meta["title"],
        "channel": meta["channel"],
        "track": f"{track_name} (automatic speech recognition)",
        "pages": 1,
        "lines": len(lines),
        "words": words,
        "duration_hours": round(hours, 2),
        "words_per_hour": round(words / hours) if hours else None,
        "words_per_minute": wpm,
        "asr_marker_pct": noise,
        "reliable_axes": RELIABLE_AXES,
        "unreliable_axes": UNRELIABLE_AXES,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "licence": "ASR transcript of copyrighted game audio; raw text is never committed",
    }
    (out_dir / "provenance.json").write_text(json.dumps(provenance, indent=2),
                                             encoding="utf-8")
    print(f"    {len(lines)} lines, ~{words} words, {hours:.1f}h, "
          f"{provenance['words_per_hour']} words/h, {wpm} words/min", file=sys.stderr)
    return provenance


def main(slugs: list[str] | None = None) -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    population = config.get("population", "all-dialogue")
    games = config["games"]
    print(f"population: {population}", file=sys.stderr)
    for slug in slugs or sorted(games):
        try:
            fetch_game(slug, games[slug], population)
        except Exception as exc:                        # noqa: BLE001
            print(f"  {slug}: FAILED — {exc}", file=sys.stderr)
