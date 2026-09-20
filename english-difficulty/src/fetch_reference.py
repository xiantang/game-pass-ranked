"""Build the reference data the difficulty metrics are scored against.

Everything here is downloaded from public sources and derived locally, so
`reference/` is regenerable and stays out of git. Sources and licences are
recorded in reference/meta.json.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sys
import urllib.request
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "reference"
CACHE = REF / "_cache"

SOURCES = {
    "en_50k": {
        "url": "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master"
               "/content/2018/en/en_50k.txt",
        "what": "OpenSubtitles 2018 English word frequencies, rank-ordered",
        "licence": "CC BY-SA 4.0 — hermitdave/FrequencyWords",
    },
    "cefrj": {
        "url": "https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/master"
               "/cefrj-vocabulary-profile-1.5.csv",
        "what": "CEFR-J Vocabulary Profile, A1-B2",
        "licence": "CC BY-SA 4.0 — Open Language Profiles",
    },
    "octanove": {
        "url": "https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/master"
               "/octanove-vocabulary-profile-c1c2-1.0.csv",
        "what": "Octanove Vocabulary Profile, C1-C2",
        "licence": "CC BY-SA 4.0 — Open Language Profiles",
    },
    "dictionary": {
        "url": "https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt",
        "what": "370k English word forms, used only to tell a real word from noise",
        "licence": "Unlicense — dwyl/english-words",
    },
    "gutenberg": {
        "url": "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages"
               "/corpora/gutenberg.zip",
        "what": "NLTK Gutenberg sample — public-domain literature, mostly pre-1900",
        "licence": "Public domain",
    },
    "brown": {
        "url": "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages"
               "/corpora/brown.zip",
        "what": "Brown Corpus — genre-balanced 1961 American English",
        "licence": "Free for research use",
    },
    "nps_chat": {
        "url": "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages"
               "/corpora/nps_chat.zip",
        "what": "NPS Chat Corpus — instant-messaging English",
        "licence": "Free for research use",
    },
}

# Frequency bands, as counts of the most frequent lemmas.
BANDS = [2000, 3000, 5000, 10000, 20000]

WORD_RE = re.compile(r"[a-z][a-z'-]*")


def fetch(key: str) -> bytes:
    """Download a source once and cache it on disk."""
    spec = SOURCES[key]
    suffix = ".zip" if spec["url"].endswith(".zip") else Path(spec["url"]).suffix
    path = CACHE / f"{key}{suffix}"
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        print(f"  downloading {key} ...", file=sys.stderr)
        req = urllib.request.Request(spec["url"], headers={"User-Agent": "game-english-corpus/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            path.write_bytes(resp.read())
    return path.read_bytes()


def build_frequency() -> dict:
    """Rank -> band lookup from the OpenSubtitles list.

    Subtitles are the right reference for games: both are spoken-register English
    delivered as on-screen text. An academic list (BNC/COCA) would rank literary
    vocabulary as more common than a player ever hears it.
    """
    ranks: dict[str, int] = {}
    text = fetch("en_50k").decode("utf-8", "replace")
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        word = parts[0].lower()
        if not WORD_RE.fullmatch(word):
            continue
        ranks.setdefault(word, len(ranks) + 1)
    return ranks


def build_cefr() -> dict:
    """Headword -> CEFR level, keeping the *easiest* level a headword has.

    A word a learner already meets at A1 in one sense is not a hard word just
    because it also carries a C1 sense.
    """
    order = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}
    levels: dict[str, str] = {}

    def absorb(blob: bytes) -> None:
        reader = csv.DictReader(io.StringIO(blob.decode("utf-8-sig", "replace")))
        for row in reader:
            level = (row.get("CEFR") or "").strip().upper()
            if level not in order:
                continue
            for variant in (row.get("headword") or "").split("/"):
                word = variant.strip().lower()
                if not WORD_RE.fullmatch(word):
                    continue
                if word not in levels or order[level] < order[levels[word]]:
                    levels[word] = level

    absorb(fetch("cefrj"))
    absorb(fetch("octanove"))
    return levels


def _zip_words(key: str, member_filter, detag: bool = False) -> Counter:
    counts: Counter = Counter()
    with zipfile.ZipFile(io.BytesIO(fetch(key))) as zf:
        for name in zf.namelist():
            if not member_filter(name):
                continue
            raw = zf.read(name).decode("utf-8", "replace")
            if detag:
                raw = re.sub(r"/\S+", " ", raw)
            counts.update(WORD_RE.findall(raw.lower()))
    return counts


# Archaisms an 18-book sample is too small to catch on frequency alone. Merged
# in at a floor score so coverage does not depend on which books NLTK ships.
ARCHAIC_SEED = """
thou thee thy thine ye hath hast doth dost shalt canst couldst wouldst
shouldst didst hadst wast wert saith sayeth speaketh maketh taketh cometh
mayest seest goest doest tis twas twere ere erst whilst amongst betwixt
amidst unto whence whither hither thither yonder henceforth heretofore
wherefore naught nought forsooth prithee methinks mayhap verily alack alas
behold hark lo nay sire milord milady liege thence therein thereof whereon
begat spake smote dwelt hearken raiment
""".split()

ARCHAIC_SEED_SCORE = 4.0

# log2 of the literary:spoken ratio a word must clear to count as archaic.
# A ratio of 2 only says literature leans on a word more than speech does,
# which is true of `the` and `and`; 16x is a genuine register break.
ARCHAIC_MIN_SCORE = 4.0

# A word contemporary speech still reaches for is not archaic, whatever the
# ratio says. Without this the index fills up with two artefacts of an 18-book
# sample: modern formal connectives the KJV leans on (`upon`, `nor`, `thus`,
# `therefore`) and the subject matter of the two longest texts in it
# (`sons`, `kings`, `servants`, `whale`). Only words modern subtitles have all
# but abandoned survive on frequency evidence; everything a game actually needs
# from the elevated-but-current register is measured by the CEFR and band axes
# instead. ARCHAIC_SEED is merged in afterwards, so `thou` and `thy` still
# count even though fantasy film subtitles keep them alive.
ARCHAIC_MODERN_CORE_RANK = 15000


def _is_obsolete_spelling(word: str, modern: Counter) -> bool:
    """True for Early Modern orthography rather than archaic vocabulary.

    The Gutenberg sample carries the KJV Bible and Shakespeare in original
    spelling, so ``haue``, ``vpon``, ``loue`` and ``selfe`` score as the most
    literary words in English. They are ``have``, ``upon``, ``love`` and
    ``self`` — no modern game writes them, so they only pad the index. A word
    modern English never uses, which lands on a common modern word once 17th
    century spelling conventions are undone, is one of these.
    """
    if word in modern:
        return False
    candidates = {
        word.replace("u", "v"), word.replace("v", "u"),
        word.replace("ee", "e"), word.replace("oo", "o"),
        word.replace("ie", "y"), word.rstrip("e"),
        word.replace("-", ""),
    }
    candidates |= {c.rstrip("e") for c in candidates}
    return any(c != word and modern.get(c, 0) > 1_000 for c in candidates)


def build_archaic(freq_ranks: dict) -> dict:
    """Data-driven archaic/literary index, not a hand-written word list.

    A word scores high when 19th-century literature uses it far more often than
    contemporary speech does. The score is log2 of the ratio between a word's
    share of the Gutenberg sample and its share of modern subtitle English, so
    +3 means roughly eight times more literary than spoken.

    Three filters keep the index honest, because the raw ratio is dominated by
    artefacts rather than by archaism:

    - Tokens holding an apostrophe are dropped. The subtitle list mangles them
      (``don't`` is split across ``don``, ``dont``, ``don`t`` and ``don.t``), so
      every contraction looks absent from modern English and scores at the top.
    - A word must appear in at least three of the texts, which removes character
      names and one-book jargon.
    - A word capitalised in most of its occurrences is a proper noun, not
      vocabulary.
    """
    import math

    lit: Counter = Counter()
    caps: Counter = Counter()
    docs: Counter = Counter()

    token_re = re.compile(r"[A-Za-z][A-Za-z'`-]*")
    with zipfile.ZipFile(io.BytesIO(fetch("gutenberg"))) as zf:
        for name in zf.namelist():
            if not name.endswith(".txt"):
                continue
            raw = zf.read(name).decode("utf-8", "replace")
            seen = set()
            for tok in token_re.findall(raw):
                if "'" in tok or "`" in tok:
                    continue
                low = tok.lower()
                lit[low] += 1
                if tok[0].isupper():
                    caps[low] += 1
                seen.add(low)
            for word in seen:
                docs[word] += 1
    lit_total = sum(lit.values())

    # Modern side: fold the subtitle list's apostrophe variants together.
    modern: Counter = Counter()
    for line in fetch("en_50k").decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        word = re.sub(r"[`'.\u00b4]", "", parts[0].lower())
        if WORD_RE.fullmatch(word):
            modern[word] += int(parts[1])
    modern_total = sum(modern.values())

    scores: dict[str, float] = {}
    for word, n in lit.items():
        if n < 12 or docs[word] < 3:
            continue
        rank = freq_ranks.get(word)
        if rank is not None and rank <= ARCHAIC_MODERN_CORE_RANK:
            continue
        if caps[word] / n > 0.5:
            continue
        lit_share = n / lit_total
        modern_share = (modern.get(word, 0) + 0.5) / modern_total
        ratio = lit_share / modern_share
        score = math.log2(ratio)
        if score >= ARCHAIC_MIN_SCORE:
            scores[word] = round(score, 3)

    scores = {w: s for w, s in scores.items() if not _is_obsolete_spelling(w, modern)}

    for word in ARCHAIC_SEED:
        scores[word] = max(scores.get(word, 0.0), ARCHAIC_SEED_SCORE)
    return scores


def build_ladder() -> dict:
    """Plain-text reference registers, used to calibrate the difficulty scale."""
    out = {}
    with zipfile.ZipFile(io.BytesIO(fetch("gutenberg"))) as zf:
        for name in zf.namelist():
            if name.endswith(".txt"):
                key = Path(name).stem
                out[f"gutenberg/{key}"] = zf.read(name).decode("utf-8", "replace")

    with zipfile.ZipFile(io.BytesIO(fetch("brown"))) as zf:
        cats: dict[str, list[str]] = {}
        try:
            for line in zf.read("brown/cats.txt").decode("utf-8", "replace").splitlines():
                bits = line.split()
                if len(bits) >= 2:
                    cats.setdefault(bits[1], []).append(bits[0])
        except KeyError:
            pass
        for cat, files in cats.items():
            chunks = []
            for fname in files:
                raw = zf.read(f"brown/{fname}").decode("utf-8", "replace")
                chunks.append(re.sub(r"/\S+", "", raw))
            out[f"brown/{cat}"] = "\n".join(chunks)

    # The post's own words sit between the Post tag and its <terminals> block,
    # which holds the part-of-speech annotation rather than anything a human
    # typed. System notices (joins, parts) are not conversation.
    post_re = re.compile(r"<Post([^>]*)>(.*?)<terminals>", re.S)
    with zipfile.ZipFile(io.BytesIO(fetch("nps_chat"))) as zf:
        lines = []
        for name in zf.namelist():
            if not name.endswith(".xml"):
                continue
            blob = zf.read(name).decode("utf-8", "replace")
            for attrs, body in post_re.findall(blob):
                if 'class="System"' in attrs:
                    continue
                text = re.sub(r"<[^>]+>", " ", body).strip()
                if text:
                    lines.append(text)
        if lines:
            out["chat/nps"] = "\n".join(lines)
    return out


def main() -> None:
    REF.mkdir(parents=True, exist_ok=True)
    print("building reference data", file=sys.stderr)

    ranks = build_frequency()
    (REF / "frequency.json").write_text(
        json.dumps({"bands": BANDS, "ranks": ranks}), encoding="utf-8")
    print(f"  frequency: {len(ranks)} lemmas", file=sys.stderr)

    cefr = build_cefr()
    (REF / "cefr.json").write_text(json.dumps(cefr), encoding="utf-8")
    print(f"  cefr: {len(cefr)} headwords", file=sys.stderr)

    words = {
        w for w in fetch("dictionary").decode("utf-8", "replace").split()
        if WORD_RE.fullmatch(w.lower())
    }
    (REF / "dictionary.json").write_text(json.dumps(sorted(words)), encoding="utf-8")
    print(f"  dictionary: {len(words)} word forms", file=sys.stderr)

    archaic = build_archaic(ranks)
    (REF / "archaic.json").write_text(json.dumps(archaic), encoding="utf-8")
    print(f"  archaic: {len(archaic)} scored words", file=sys.stderr)

    ladder = build_ladder()
    ladder_dir = REF / "ladder"
    ladder_dir.mkdir(exist_ok=True)
    for key, text in ladder.items():
        path = ladder_dir / (key.replace("/", "__") + ".txt")
        path.write_text(text, encoding="utf-8")
    print(f"  ladder: {len(ladder)} reference registers", file=sys.stderr)

    meta = {
        "builtAt": date.today().isoformat(),
        "bands": BANDS,
        "sources": {
            k: {**v, "sha256": hashlib.sha256(fetch(k)).hexdigest()[:16]}
            for k, v in SOURCES.items()
        },
    }
    (REF / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print("done", file=sys.stderr)


if __name__ == "__main__":
    main()
